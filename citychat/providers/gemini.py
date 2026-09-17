"""Gemini provider, over the Generative Language REST API.

Raw HTTP rather than the `google-genai` SDK, deliberately: `httpx2` already
ships with the Anthropic SDK, so this adds no dependency, and the wire format
is small and documented. Everything Gemini-specific is in this file.

    POST {base}/v1beta/models/{model}:streamGenerateContent?alt=sse
    x-goog-api-key: <key>

Notable differences from Claude that this file absorbs:

* History is `contents` with roles `user` / `model`, and parts rather than
  content blocks. Tool calls are `functionCall` parts; results go back as
  `functionResponse` parts in a `user` turn.
* `functionCall` parts carry no id, so ids are synthesised locally and results
  are returned in call order, which is how Gemini matches them.
* Function parameters use a subset of OpenAPI Schema: `additionalProperties`
  and friends are rejected, and the `type` enum is upper case, so schemas are
  sanitised on the way out.
* Grounding with Google Search is a tool entry rather than a separate API, and
  some model versions refuse to combine it with function declarations, so it
  is dropped and retried once if the API objects.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from .base import (
    STOP_END_TURN,
    STOP_MAX_TOKENS,
    STOP_REFUSAL,
    STOP_TOOL_USE,
    ModelTurn,
    Provider,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolSpec,
)

logger = logging.getLogger("citychat.providers.gemini")

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
API_VERSION = "v1beta"

# JSON Schema keywords the Gemini schema subset does not accept.
UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {"additionalProperties", "$schema", "$id", "default", "examples", "const", "pattern"}
)
SCHEMA_TYPES = frozenset({"string", "number", "integer", "boolean", "array", "object", "null"})

# finishReason values that mean the model declined rather than finished.
REFUSAL_FINISH_REASONS = frozenset(
    {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"}
)


def sanitise_schema(schema: Any) -> Any:
    """Rewrite JSON Schema into the subset Gemini's function declarations take."""
    if isinstance(schema, list):
        return [sanitise_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in UNSUPPORTED_SCHEMA_KEYS:
            continue
        if key == "type" and isinstance(value, str) and value.lower() in SCHEMA_TYPES:
            # The Type enum is upper case; proto3 JSON is case-sensitive.
            out[key] = value.upper()
        elif key in ("properties", "items", "anyOf", "oneOf"):
            out[key] = sanitise_schema(value)
        elif key == "properties" or isinstance(value, (dict, list)):
            out[key] = sanitise_schema(value)
        else:
            out[key] = value
    return out


class GeminiProvider(Provider):
    name = "gemini"
    api_label = "the Gemini API"

    def __init__(
        self,
        model: str,
        system_prompt: str,
        tools: list[ToolSpec],
        *,
        api_key: str = "",
        max_tokens: int = 4096,
        temperature: float | None = None,
        thinking_budget: int | None = None,
        base_url: str = DEFAULT_BASE_URL,
        web_search: bool = False,
        timeout: float = 120.0,
        transport: Any | None = None,
    ) -> None:
        super().__init__(model or DEFAULT_MODEL, system_prompt, tools)
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.thinking_budget = thinking_budget
        self.base_url = base_url.rstrip("/")
        self.web_search = web_search
        self.timeout = timeout
        # A custom transport is how the tests drive this without a network.
        self._transport = transport
        self._send_search = bool(web_search)
        self._function_declarations = [
            {
                "name": spec.name,
                "description": spec.description,
                **(
                    {"parameters": sanitise_schema(spec.json_schema())}
                    if spec.parameters.get("properties")
                    else {}
                ),
            }
            for spec in self.tools
        ]

    # ---------------------------------------------------------------- plumbing

    def _client(self):
        import httpx2 as httpx

        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def _url(self, method: str = "streamGenerateContent") -> str:
        return f"{self.base_url}/{API_VERSION}/models/{self.model}:{method}"

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _body(self, messages: list[dict]) -> dict:
        generation: dict[str, Any] = {"maxOutputTokens": self.max_tokens}
        if self.temperature is not None:
            generation["temperature"] = self.temperature
        if self.thinking_budget is not None:
            generation["thinkingConfig"] = {"thinkingBudget": self.thinking_budget}

        tools: list[dict] = []
        if self._function_declarations:
            tools.append({"functionDeclarations": self._function_declarations})
        if self._send_search:
            tools.append({"googleSearch": {}})

        body: dict[str, Any] = {
            # Stable prefix first: Gemini's implicit caching, where the model
            # supports it, keys on a matching request prefix just as Claude's
            # explicit breakpoint does.
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "contents": messages,
            "generationConfig": generation,
        }
        if tools:
            body["tools"] = tools
        return body

    # ----------------------------------------------------------- conversation

    def user_message(self, text: str) -> dict:
        return {"role": "user", "parts": [{"text": text}]}

    def is_conversation_start(self, message: dict) -> bool:
        if message.get("role") != "user":
            return False
        parts = message.get("parts") or []
        return not any(isinstance(part, dict) and "functionResponse" in part for part in parts)

    def tool_result_messages(self, turn: ModelTurn, results: list[ToolResult]) -> list[dict]:
        # Gemini matches responses to calls by order within the parts list, so
        # the order here must mirror the order of the functionCall parts.
        return [
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": result.call.name,
                            "response": result.parsed(),
                        }
                    }
                    for result in results
                ],
            }
        ]

    # --------------------------------------------------------------- streaming

    def stream(self, messages: list[dict]) -> Iterator[dict]:
        import httpx2 as httpx

        if not self.api_key:
            raise ProviderError(
                "No Gemini API key configured. Set GEMINI_API_KEY and restart.", kind="auth"
            )

        while True:
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            model_parts: list[dict] = []
            usage: dict = {}
            finish_reason = ""
            block_reason = ""
            retry = False

            try:
                with self._client() as client:
                    with client.stream(
                        "POST",
                        self._url(),
                        params={"alt": "sse"},
                        headers=self._headers(),
                        json=self._body(messages),
                    ) as response:
                        if response.status_code >= 400:
                            response.read()
                            detail = _error_detail(response)
                            dropped = self._drop_unsupported_feature(detail)
                            if dropped:
                                logger.warning(
                                    "%s rejected %s; retrying without it", self.model, dropped
                                )
                                retry = True
                            else:
                                raise ProviderError(self._describe_status(response, detail))
                        else:
                            for line in response.iter_lines():
                                if not line.startswith("data:"):
                                    continue
                                chunk = line[5:].strip()
                                if not chunk:
                                    continue
                                try:
                                    payload = json.loads(chunk)
                                except ValueError:
                                    logger.warning("skipping unparseable SSE chunk")
                                    continue
                                yield from self._consume_chunk(
                                    payload, text_parts, calls, model_parts
                                )
                                usage = _merge_usage(usage, payload.get("usageMetadata"))
                                finish_reason = _finish_reason(payload) or finish_reason
                                block_reason = _block_reason(payload) or block_reason
            except ProviderError:
                raise
            except httpx.HTTPError as exc:
                raise ProviderError(
                    f"Could not reach the Gemini API ({type(exc).__name__}). "
                    "Check network connectivity and CITYCHAT_GEMINI_BASE_URL."
                ) from exc

            if retry:
                continue
            break

        stop = STOP_END_TURN
        detail = finish_reason or ""
        if block_reason:
            stop, detail = STOP_REFUSAL, f"prompt blocked: {block_reason}"
        elif finish_reason in REFUSAL_FINISH_REASONS:
            stop = STOP_REFUSAL
        elif finish_reason == "MAX_TOKENS":
            stop = STOP_MAX_TOKENS
        if calls and stop == STOP_END_TURN:
            stop = STOP_TOOL_USE

        yield {
            "type": "turn",
            "turn": ModelTurn(
                text="".join(text_parts),
                tool_calls=calls,
                stop_reason=stop,
                usage=usage,
                assistant_message={"role": "model", "parts": model_parts},
                detail=detail,
            ),
        }

    def _consume_chunk(
        self,
        payload: dict,
        text_parts: list[str],
        calls: list[ToolCall],
        model_parts: list[dict],
    ) -> Iterator[dict]:
        for candidate in payload.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                if part.get("thought"):
                    # Thought summaries are not shown to the user, but must be
                    # echoed back, signature and all, to keep the turn valid.
                    model_parts.append(part)
                    continue
                if "text" in part and part["text"]:
                    text_parts.append(part["text"])
                    model_parts.append({"text": part["text"]})
                    yield {"type": "text", "text": part["text"]}
                elif "functionCall" in part:
                    call = part["functionCall"] or {}
                    arguments = call.get("args") or {}
                    if not isinstance(arguments, dict):
                        arguments = {}
                    calls.append(
                        ToolCall(
                            id=call.get("id") or f"call_{len(calls)}",
                            name=call.get("name") or "",
                            arguments=arguments,
                        )
                    )
                    model_parts.append(part)
                else:
                    model_parts.append(part)

    # ------------------------------------------------------------------ errors

    def _drop_unsupported_feature(self, detail: str) -> str | None:
        """Search grounding and function calling cannot always be combined."""
        lowered = detail.lower()
        if self._send_search and (
            "googlesearch" in lowered
            or "google_search" in lowered
            or ("tool" in lowered and "support" in lowered)
        ):
            self._send_search = False
            return "googleSearch grounding (set CITYCHAT_WEB_SEARCH=0 to silence this)"
        return None

    def _describe_status(self, response: Any, detail: str) -> str:
        code = response.status_code
        lowered = detail.lower()
        # Observed live: a malformed key comes back as 400, not 401/403, so the
        # message matters more than the status for telling auth from the rest.
        if "api key not valid" in lowered or "api_key_invalid" in lowered:
            return (
                "The Gemini API rejected the key as invalid. Check GEMINI_API_KEY "
                f"(get one at https://aistudio.google.com/apikey). ({detail})"
            )
        if "api key" in lowered and ("expired" in lowered or "permission" in lowered):
            return f"The Gemini API rejected the key. Check GEMINI_API_KEY. ({detail})"
        if code in (401, 403):
            return (
                "The Gemini API rejected the key. Check GEMINI_API_KEY, and that the "
                f"Generative Language API is enabled for it. ({detail})"
            )
        if code == 404:
            available = self._list_models_hint()
            return (
                f"Model {self.model!r} was not found. Set CITYCHAT_MODEL to one the key can "
                f"use.{available} ({detail})"
            )
        if code == 429:
            return "Rate limited or out of quota on the Gemini API. Please retry in a moment."
        if code >= 500:
            return "The Gemini API returned a server error. Please retry."
        return f"The Gemini API rejected the request: {detail}"

    def _list_models_hint(self) -> str:
        """On a 404, name the models the key can actually use."""
        try:
            import httpx2 as httpx

            with self._client() as client:
                response = client.get(
                    f"{self.base_url}/{API_VERSION}/models",
                    headers=self._headers(),
                    params={"pageSize": 100},
                )
                response.raise_for_status()
                names = [
                    str(entry.get("name", "")).removeprefix("models/")
                    for entry in response.json().get("models") or []
                    if "generateContent" in (entry.get("supportedGenerationMethods") or [])
                ]
        except (httpx.HTTPError, ValueError, KeyError):
            return " Run `python scripts/check_provider.py --list-models` to see the options."
        if not names:
            return ""
        return " Available: " + ", ".join(sorted(names)[:25]) + "."

    def list_models(self) -> list[dict]:
        """Models this key can use, for `scripts/check_provider.py`."""
        with self._client() as client:
            response = client.get(
                f"{self.base_url}/{API_VERSION}/models",
                headers=self._headers(),
                params={"pageSize": 100},
            )
            response.raise_for_status()
            return response.json().get("models") or []

    def describe(self) -> dict:
        return {
            **super().describe(),
            "max_output_tokens": self.max_tokens,
            "thinking_budget": self.thinking_budget,
            "search_grounding": self._send_search,
        }


def _error_detail(response: Any) -> str:
    try:
        body = response.json()
    except ValueError:
        return (response.text or "")[:400]
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:400]
    return json.dumps(body)[:400]


def _finish_reason(payload: dict) -> str:
    for candidate in payload.get("candidates") or []:
        if candidate.get("finishReason"):
            return str(candidate["finishReason"])
    return ""


def _block_reason(payload: dict) -> str:
    feedback = payload.get("promptFeedback") or {}
    return str(feedback.get("blockReason") or "")


def _merge_usage(total: dict, usage: dict | None) -> dict:
    """Gemini reports cumulative usage per chunk, so the last value wins."""
    if not usage:
        return total
    merged = dict(total)
    for key, value in usage.items():
        if isinstance(value, (int, float)):
            merged[key] = value
    return merged
