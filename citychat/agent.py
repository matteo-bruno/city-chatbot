"""The conversation loop, provider-neutral.

The loop knows about text, tool calls and tool results. Everything that
differs between model APIs - request shape, streaming format, history
dialect, caching, error vocabulary - lives behind `citychat.providers`.

A hand-written loop rather than any SDK's tool runner, for three reasons: it
streams tool progress and text deltas out as events so a web client can render
them; it mirrors the history back to the caller so the service can stay
stateless; and it resumes a paused turn, which a long server-side search can
trigger.
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
from .providers import Provider, ProviderError, build_provider
from .providers.base import (
    STOP_PAUSED,
    STOP_REFUSAL,
    ModelTurn,
    ToolResult,
)
from .tools import run_tool, tool_specs

logger = logging.getLogger("citychat.agent")

MAX_PAUSE_RESUMES = 3

REFUSAL_MESSAGE = (
    "I could not produce an answer to that. Try rephrasing, or ask me about this city's "
    "accessibility data or the 15-minute-city methodology."
)

BUDGET_EXHAUSTED = json.dumps(
    {
        "error": "tool_budget_exhausted",
        "message": "Answer now with what you already have, and say what is missing.",
    }
)


class HistoryProviderMismatch(ValueError):
    """A history from one provider was replayed against another.

    Histories are provider-native (content blocks versus parts), so they are
    not interchangeable. Better to say so than to send a malformed request.
    """

    def __init__(self, expected: str, found: str) -> None:
        super().__init__(
            f"this conversation was started on the {found!r} provider but the service now runs "
            f"{expected!r}; start a new conversation"
        )
        self.expected = expected
        self.found = found


@dataclass
class Turn:
    """Result of one user message."""

    text: str = ""
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    error: str | None = None


class CityAgent:
    def __init__(
        self,
        context: CityContext,
        provider: Provider | None = None,
        client: Any | None = None,
    ) -> None:
        self.context = context
        self.settings: Settings = context.settings
        self.system_prompt = build_system_prompt(context)
        self.tool_specs = tool_specs(context)
        if provider is None:
            kwargs = {"client": client} if client is not None else {}
            provider = build_provider(self.settings, self.system_prompt, self.tool_specs, **kwargs)
        self.provider = provider

    # ------------------------------------------------------------------ public

    @property
    def provider_name(self) -> str:
        return self.provider.name

    def describe(self) -> dict:
        return {**self.provider.describe(), "tools": [spec.name for spec in self.tool_specs]}

    def prepare_messages(
        self, history: list[dict], user_message: str, history_provider: str | None = None
    ) -> list[dict]:
        if history and history_provider and history_provider != self.provider.name:
            raise HistoryProviderMismatch(self.provider.name, history_provider)
        trimmed = trim_history(history, self.settings.max_history_messages, self.provider)
        return [*trimmed, self.provider.user_message(user_message)]

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
        turn: ModelTurn | None = None

        # +2: one extra round to tell the model its tool budget is spent, and
        # one more for it to answer with what it has.
        for round_index in range(self.settings.max_tool_rounds + 2):
            try:
                for event in self.provider.stream(messages):
                    if event["type"] == "text":
                        answer_parts.append(event["text"])
                        yield {"type": "text", "text": event["text"]}
                    elif event["type"] == "turn":
                        turn = event["turn"]
            except ProviderError as exc:
                logger.warning("%s request failed: %s", self.provider.name, exc.message)
                yield {"type": "error", "message": exc.message}
                yield self._done(answer_parts, messages, tool_calls, usage, "error", exc.message)
                return
            except Exception as exc:  # defensive: never leak a traceback to a user
                logger.exception("unexpected failure calling %s", self.provider.name)
                detail = f"The model request failed ({type(exc).__name__})."
                yield {"type": "error", "message": detail}
                yield self._done(answer_parts, messages, tool_calls, usage, "error", detail)
                return

            if turn is None:  # a provider that yielded no turn event
                detail = f"The {self.provider.api_label} returned no response."
                yield {"type": "error", "message": detail}
                yield self._done(answer_parts, messages, tool_calls, usage, "error", detail)
                return

            usage = _merge_usage(usage, turn.usage)
            if turn.assistant_message:
                messages.append(turn.assistant_message)

            if turn.stop_reason == STOP_REFUSAL:
                logger.warning("turn refused by %s: %s", self.provider.name, turn.detail)
                yield {"type": "error", "message": REFUSAL_MESSAGE}
                yield self._done(
                    answer_parts or [REFUSAL_MESSAGE],
                    messages,
                    tool_calls,
                    usage,
                    STOP_REFUSAL,
                    "refusal",
                )
                return

            if turn.stop_reason == STOP_PAUSED and self.provider.supports_pause_resume():
                pause_resumes += 1
                if pause_resumes > MAX_PAUSE_RESUMES:
                    break
                continue

            if not turn.tool_calls:
                break

            if round_index >= self.settings.max_tool_rounds:
                spent = [
                    ToolResult(call=call, payload=BUDGET_EXHAUSTED, is_error=True)
                    for call in turn.tool_calls
                ]
                messages.extend(self.provider.tool_result_messages(turn, spent))
                continue

            results: list[ToolResult] = []
            for call in turn.tool_calls:
                yield {"type": "tool_call", "name": call.name, "input": call.arguments}
                payload, is_error = run_tool(self.context, call.name, call.arguments)
                tool_calls.append(
                    {"name": call.name, "input": call.arguments, "is_error": is_error}
                )
                yield {"type": "tool_result", "name": call.name, "is_error": is_error}
                results.append(ToolResult(call=call, payload=payload, is_error=is_error))
            messages.extend(self.provider.tool_result_messages(turn, results))

        yield self._done(
            answer_parts,
            messages,
            tool_calls,
            usage,
            turn.stop_reason if turn else None,
            None,
        )

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

    # ----------------------------------------------------------------- helpers

    def _done(
        self,
        answer_parts: list[str],
        messages: list[dict],
        tool_calls: list[dict],
        usage: dict,
        stop_reason: str | None,
        error: str | None,
    ) -> dict:
        return {
            "type": "done",
            "text": "".join(answer_parts),
            "messages": messages,
            "tool_calls": tool_calls,
            "stop_reason": stop_reason,
            "usage": usage,
            "provider": self.provider.name,
            "error": error,
        }


def trim_history(history: list[dict], max_messages: int, provider: Provider) -> list[dict]:
    """Keep the most recent messages, never starting on an orphaned tool result.

    A message carrying only tool results is meaningless without the assistant
    turn that requested them, so the window is pushed forward until it starts
    on a real user turn. What counts as one is provider-specific.
    """
    if max_messages <= 0 or len(history) <= max_messages:
        window = list(history)
    else:
        window = list(history[-max_messages:])
    while window and not provider.is_conversation_start(window[0]):
        window.pop(0)
    return window


def _merge_usage(total: dict, usage: dict | None) -> dict:
    """Accumulate token counts across tool rounds.

    Each round is a separate billed request, so counts add up. Non-numeric
    fields (a model name, a speed) are kept from the first round that has them.
    """
    if not usage:
        return total
    merged = dict(total)
    for key, value in usage.items():
        if isinstance(value, (int, float)):
            merged[key] = merged.get(key, 0) + value
        elif value is not None and key not in merged:
            merged[key] = value
    return merged
