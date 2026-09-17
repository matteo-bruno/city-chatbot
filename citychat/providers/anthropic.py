"""Claude provider.

This is the original implementation, moved behind the provider seam. Nothing
about it changed: prompt caching on a frozen system block, `output_config`
effort, the server-side refusal fallback, `pause_turn` resumption and the
model-gated-parameter retry all still apply, and only to Claude.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from .base import (
    STOP_END_TURN,
    STOP_MAX_TOKENS,
    STOP_PAUSED,
    STOP_REFUSAL,
    STOP_TOOL_USE,
    ModelTurn,
    Provider,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolSpec,
)

logger = logging.getLogger("citychat.providers.anthropic")

DEFAULT_MODEL = "claude-opus-5"

# Server-side refusal fallback: if a safety classifier declines a turn, the API
# reroutes it to a capable fallback model instead of returning nothing.
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

WEB_SEARCH_TOOL_TYPE = "web_search_20260209"

STOP_REASONS = {
    "end_turn": STOP_END_TURN,
    "tool_use": STOP_TOOL_USE,
    "refusal": STOP_REFUSAL,
    "pause_turn": STOP_PAUSED,
    "max_tokens": STOP_MAX_TOKENS,
}


class AnthropicProvider(Provider):
    name = "anthropic"
    api_label = "the Claude API"

    def __init__(
        self,
        model: str,
        system_prompt: str,
        tools: list[ToolSpec],
        *,
        api_key: str = "",
        max_tokens: int = 4096,
        effort: str = "medium",
        refusal_fallback: bool = True,
        web_search: bool = False,
        web_search_max_uses: int = 4,
        web_search_allowed_domains: list[str] | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(model or DEFAULT_MODEL, system_prompt, tools)
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.effort = effort
        self.web_search = web_search
        self.web_search_max_uses = web_search_max_uses
        self.web_search_allowed_domains = web_search_allowed_domains or []
        self._client = client
        # Two request parameters are model-gated: `output_config.effort` is not
        # accepted by every model (Haiku 4.5, Sonnet 4.5), and the refusal
        # `fallbacks` beta only applies to models that can refuse. Rather than
        # keep a capability table that goes stale, each is switched off for the
        # process the first time the API rejects it, so changing the model is
        # enough on its own.
        self._send_effort = bool(effort)
        self._send_fallbacks = bool(refusal_fallback)
        self._wire_tools = self._build_tools()

    # ---------------------------------------------------------------- plumbing

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            kwargs: dict[str, Any] = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _build_tools(self) -> list[dict]:
        wire: list[dict] = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.json_schema(),
            }
            for spec in self.tools
        ]
        if self.web_search:
            web: dict[str, Any] = {
                "type": WEB_SEARCH_TOOL_TYPE,
                "name": "web_search",
                "max_uses": self.web_search_max_uses,
            }
            if self.web_search_allowed_domains:
                web["allowed_domains"] = self.web_search_allowed_domains
            wire.append(web)
        return wire

    def _request_kwargs(self, messages: list[dict]) -> dict:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # One breakpoint at the end of a system prompt that never changes.
            "system": [
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": self._wire_tools,
            "messages": messages,
        }
        if self._send_effort:
            kwargs["output_config"] = {"effort": self.effort}
        if self._send_fallbacks:
            kwargs["betas"] = [REFUSAL_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def _open_stream(self, messages: list[dict]):
        kwargs = self._request_kwargs(messages)
        if self._send_fallbacks:
            return self.client.beta.messages.stream(**kwargs)
        return self.client.messages.stream(**kwargs)

    def _drop_unsupported_parameter(self, exc: Exception) -> str | None:
        """On a 400 naming a model-gated parameter, stop sending it."""
        import anthropic

        if not isinstance(exc, anthropic.BadRequestError):
            return None
        detail = str(getattr(exc, "message", "") or exc).lower()
        if self._send_effort and ("effort" in detail or "output_config" in detail):
            self._send_effort = False
            return "output_config.effort (set CITYCHAT_EFFORT= to silence this)"
        if self._send_fallbacks and ("fallback" in detail or REFUSAL_FALLBACK_BETA in detail):
            self._send_fallbacks = False
            return "fallbacks (set CITYCHAT_REFUSAL_FALLBACK=0 to silence this)"
        return None

    # ----------------------------------------------------------- conversation

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def is_conversation_start(self, message: dict) -> bool:
        if message.get("role") != "user":
            return False
        content = message.get("content")
        if isinstance(content, str):
            return True
        if isinstance(content, list):
            return not any(
                isinstance(block, dict) and block.get("type") == "tool_result" for block in content
            )
        return False

    def tool_result_messages(self, turn: ModelTurn, results: list[ToolResult]) -> list[dict]:
        # All results for one assistant turn go back in a single user message.
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": result.call.id,
                        "content": result.payload,
                        **({"is_error": True} if result.is_error else {}),
                    }
                    for result in results
                ],
            }
        ]

    def supports_pause_resume(self) -> bool:
        return True

    # --------------------------------------------------------------- streaming

    def stream(self, messages: list[dict]) -> Iterator[dict]:
        while True:
            try:
                with self._open_stream(messages) as stream:
                    for event in stream:
                        if (
                            event.type == "content_block_delta"
                            and getattr(event.delta, "type", None) == "text_delta"
                        ):
                            yield {"type": "text", "text": event.delta.text}
                    message = stream.get_final_message()
            except Exception as exc:
                # A model that does not accept one of the optional parameters
                # rejects the request before streaming anything, so retrying
                # without it is safe and loses no output.
                dropped = self._drop_unsupported_parameter(exc)
                if dropped:
                    logger.warning("%s rejected %s; retrying without it", self.model, dropped)
                    continue
                raise ProviderError(self._describe_error(exc)) from exc
            break

        content = json.loads(message.to_json())["content"]
        text = "".join(b["text"] for b in content if b.get("type") == "text")
        calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") or {})
            for b in content
            if b.get("type") == "tool_use"
        ]
        stop = STOP_REASONS.get(message.stop_reason or "", message.stop_reason or STOP_END_TURN)
        if calls and stop == STOP_END_TURN:
            stop = STOP_TOOL_USE

        yield {
            "type": "turn",
            "turn": ModelTurn(
                text=text,
                tool_calls=calls,
                stop_reason=stop,
                usage=_usage_dict(getattr(message, "usage", None)),
                assistant_message={"role": "assistant", "content": content},
                detail=str(getattr(message, "stop_details", "") or ""),
            ),
        }

    # ------------------------------------------------------------------ errors

    def _describe_error(self, exc: Exception) -> str:
        try:
            import anthropic
        except ImportError:  # pragma: no cover - the SDK is a hard dependency
            return f"The model request failed ({type(exc).__name__})."

        if isinstance(exc, anthropic.AuthenticationError):
            return "The Claude API key is missing or invalid. Set ANTHROPIC_API_KEY and restart."
        if isinstance(exc, anthropic.PermissionDeniedError):
            return "The Claude API key does not have access to this model."
        if isinstance(exc, anthropic.NotFoundError):
            return f"Model {self.model!r} was not found. Check CITYCHAT_MODEL."
        if isinstance(exc, anthropic.RateLimitError):
            return "Rate limited by the Claude API. Please retry in a moment."
        if isinstance(exc, anthropic.BadRequestError):
            return f"The Claude API rejected the request: {exc.message}"
        if isinstance(exc, anthropic.APIConnectionError):
            return "Could not reach the Claude API. Check network connectivity."
        if isinstance(exc, anthropic.APIStatusError):
            if exc.status_code >= 500:
                return "The Claude API returned a server error. Please retry."
            return f"The Claude API returned an error: {exc.message}"
        return f"The model request failed ({type(exc).__name__})."

    def describe(self) -> dict:
        return {
            **super().describe(),
            "effort": self.effort if self._send_effort else None,
            "refusal_fallback": self._send_fallbacks,
            "web_search": self.web_search,
        }


def _usage_dict(usage: Any) -> dict:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    return json.loads(usage.to_json())
