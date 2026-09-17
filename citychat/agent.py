"""The conversation loop.

A hand-written loop rather than the SDK's beta tool runner, for three reasons:
it streams tool-call progress and text deltas out as events so a web client can
render them; it mirrors the message history back to the caller so the service
can stay stateless; and it resumes `pause_turn`, which a long server-side web
search can trigger. Everything else is a plain Messages API call.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .context import CityContext
from .prompt import build_system_prompt
from .tools import run_tool, tool_definitions

logger = logging.getLogger("citychat.agent")

# Server-side refusal fallback: if a safety classifier declines a turn, the API
# reroutes it to a capable fallback model instead of returning nothing.
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

MAX_PAUSE_RESUMES = 3

REFUSAL_MESSAGE = (
    "I could not produce an answer to that. Try rephrasing, or ask me about this city's "
    "accessibility data or the 15-minute-city methodology."
)


@dataclass
class Turn:
    """Result of one user message."""

    text: str = ""
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    error: str | None = None


def _blocks_to_params(message: Any) -> list[dict]:
    """Assistant content blocks as plain JSON, so history can be stored or shipped.

    Thinking blocks are kept verbatim: the API requires them to be echoed back
    unchanged while a tool-use turn is in flight, and re-sending them on later
    turns of the same model is harmless.
    """
    return json.loads(message.to_json())["content"]


def _merge_usage(total: dict, usage: Any) -> dict:
    if usage is None:
        return total
    data = usage if isinstance(usage, dict) else json.loads(usage.to_json())
    for key, value in data.items():
        if isinstance(value, (int, float)):
            total[key] = total.get(key, 0) + value
        elif value is not None and key not in total:
            total[key] = value
    return total


class CityAgent:
    def __init__(self, context: CityContext, client: Any | None = None) -> None:
        self.context = context
        self.settings: Settings = context.settings
        self.system_prompt = build_system_prompt(context)
        self.tools = tool_definitions(context)
        self._client = client

    # ---------------------------------------------------------------- plumbing

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            kwargs: dict[str, Any] = {}
            if self.settings.api_key:
                kwargs["api_key"] = self.settings.api_key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _request_kwargs(self, messages: list[dict]) -> dict:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            # One breakpoint at the end of a system prompt that never changes.
            "system": [
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": self.tools,
            "messages": messages,
            "output_config": {"effort": self.settings.effort},
        }
        if self.settings.refusal_fallback:
            kwargs["betas"] = [REFUSAL_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def _stream(self, messages: list[dict]):
        kwargs = self._request_kwargs(messages)
        if self.settings.refusal_fallback:
            return self.client.beta.messages.stream(**kwargs)
        return self.client.messages.stream(**kwargs)

    # ------------------------------------------------------------------ public

    def prepare_messages(self, history: list[dict], user_message: str) -> list[dict]:
        trimmed = trim_history(history, self.settings.max_history_messages)
        return [*trimmed, {"role": "user", "content": user_message}]

    def run(self, messages: list[dict]) -> Iterator[dict]:
        """Drive one turn, yielding events.

        Event types: `text` (a streamed delta), `tool_call`, `tool_result`,
        `error`, and finally `done` carrying the full text, the updated message
        list and token usage.
        """
        messages = list(messages)
        usage: dict = {}
        tool_calls: list[dict] = []
        answer_parts: list[str] = []
        pause_resumes = 0

        # +2: one extra round to tell the model its tool budget is spent, and
        # one more for it to answer with what it has.
        for round_index in range(self.settings.max_tool_rounds + 2):
            try:
                with self._stream(messages) as stream:
                    for event in stream:
                        if (
                            event.type == "content_block_delta"
                            and getattr(event.delta, "type", None) == "text_delta"
                        ):
                            answer_parts.append(event.delta.text)
                            yield {"type": "text", "text": event.delta.text}
                    message = stream.get_final_message()
            except Exception as exc:  # network, auth, rate limit, bad request
                logger.exception("model request failed")
                detail = _describe_api_error(exc)
                yield {"type": "error", "message": detail}
                yield {
                    "type": "done",
                    "text": "".join(answer_parts),
                    "messages": messages,
                    "tool_calls": tool_calls,
                    "stop_reason": "error",
                    "usage": usage,
                    "error": detail,
                }
                return

            usage = _merge_usage(usage, getattr(message, "usage", None))
            messages.append({"role": "assistant", "content": _blocks_to_params(message)})

            if message.stop_reason == "refusal":
                details = getattr(message, "stop_details", None)
                logger.warning("turn refused: %s", details)
                yield {"type": "error", "message": REFUSAL_MESSAGE}
                yield {
                    "type": "done",
                    "text": "".join(answer_parts) or REFUSAL_MESSAGE,
                    "messages": messages,
                    "tool_calls": tool_calls,
                    "stop_reason": "refusal",
                    "usage": usage,
                    "error": "refusal",
                }
                return

            if message.stop_reason == "pause_turn":
                # A server-side tool ran long; resend to let it continue.
                pause_resumes += 1
                if pause_resumes > MAX_PAUSE_RESUMES:
                    break
                continue

            tool_uses = [b for b in message.content if b.type == "tool_use"]
            if not tool_uses:
                break

            if round_index >= self.settings.max_tool_rounds:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(
                                    {
                                        "error": "tool_budget_exhausted",
                                        "message": "Answer now with what you already have, and say what is missing.",
                                    }
                                ),
                                "is_error": True,
                            }
                            for block in tool_uses
                        ],
                    }
                )
                continue

            results = []
            for block in tool_uses:
                yield {"type": "tool_call", "name": block.name, "input": block.input}
                payload, is_error = run_tool(self.context, block.name, block.input)
                tool_calls.append({"name": block.name, "input": block.input, "is_error": is_error})
                yield {"type": "tool_result", "name": block.name, "is_error": is_error}
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": payload,
                        **({"is_error": True} if is_error else {}),
                    }
                )
            # All results for one assistant turn go back in a single user message.
            messages.append({"role": "user", "content": results})

        yield {
            "type": "done",
            "text": "".join(answer_parts),
            "messages": messages,
            "tool_calls": tool_calls,
            "stop_reason": getattr(message, "stop_reason", None),
            "usage": usage,
        }

    def ask(self, messages: list[dict]) -> Turn:
        """Non-streaming convenience wrapper around `run`."""
        turn = Turn()
        for event in self.run(messages):
            if event["type"] == "done":
                turn = Turn(
                    text=event["text"],
                    messages=event["messages"],
                    tool_calls=event["tool_calls"],
                    stop_reason=event["stop_reason"],
                    usage=event["usage"],
                    error=event.get("error"),
                )
        return turn


def trim_history(history: list[dict], max_messages: int) -> list[dict]:
    """Keep the most recent messages, never starting on an orphaned tool result.

    A `user` message whose content is only `tool_result` blocks is meaningless
    without the assistant `tool_use` it answers, so the window is pushed
    forward until it starts on a real user turn.
    """
    if max_messages <= 0 or len(history) <= max_messages:
        window = list(history)
    else:
        window = list(history[-max_messages:])
    while window and not _is_plain_user_message(window[0]):
        window.pop(0)
    return window


def _is_plain_user_message(message: dict) -> bool:
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


def _describe_api_error(exc: Exception) -> str:
    """User-facing text for an SDK exception, without leaking internals."""
    try:
        import anthropic
    except ImportError:
        return f"The model request failed ({type(exc).__name__})."

    if isinstance(exc, anthropic.AuthenticationError):
        return "The Claude API key is missing or invalid. Set ANTHROPIC_API_KEY and restart."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "The Claude API key does not have access to this model."
    if isinstance(exc, anthropic.NotFoundError):
        return "The configured model was not found. Check CITYCHAT_MODEL."
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
