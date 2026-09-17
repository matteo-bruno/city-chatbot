"""The provider seam: everything that differs between model APIs lives here.

The conversation loop in `citychat/agent.py` is provider-neutral. It knows
about text, tool calls and tool results, and nothing about content blocks,
`functionCall` parts, cache breakpoints or SSE framing. Each provider:

* declares the tools in its own dialect (`ToolSpec` -> whatever the API wants);
* streams one model turn, yielding text as it arrives and returning a
  `ModelTurn`;
* owns the wire format of the conversation history, because a history is not
  portable between APIs anyway.

Adding a provider means implementing this class and registering it in
`citychat/providers/__init__.py`. Nothing else changes.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field

# Neutral stop reasons. Providers map their own vocabulary onto these.
STOP_END_TURN = "end_turn"
STOP_TOOL_USE = "tool_use"
STOP_REFUSAL = "refusal"
STOP_PAUSED = "paused"
STOP_MAX_TOKENS = "max_tokens"


@dataclass(frozen=True)
class ToolSpec:
    """A tool in provider-neutral form: a name, a description, JSON Schema."""

    name: str
    description: str
    parameters: dict
    required: tuple[str, ...] = ()

    def json_schema(self) -> dict:
        schema = dict(self.parameters)
        if self.required:
            schema["required"] = list(self.required)
        return schema


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    call: ToolCall
    payload: str  # JSON text, as `run_tool` produces
    is_error: bool

    def parsed(self) -> dict:
        try:
            value = json.loads(self.payload)
        except (TypeError, ValueError):
            return {"result": self.payload}
        return value if isinstance(value, dict) else {"result": value}


@dataclass
class ModelTurn:
    """One assistant turn, normalised."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = STOP_END_TURN
    usage: dict = field(default_factory=dict)
    # The provider-native message to append to the history for this turn.
    assistant_message: dict = field(default_factory=dict)
    detail: str = ""


class ProviderError(Exception):
    """A model call failed in a way the user should be told about."""

    def __init__(self, message: str, *, kind: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind


class Provider(ABC):
    """One model API."""

    #: short registry key, e.g. "gemini"
    name: str = "provider"
    #: human-readable API name for messages, e.g. "the Gemini API"
    api_label: str = "the model API"

    def __init__(self, model: str, system_prompt: str, tools: list[ToolSpec]) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools

    # ----------------------------------------------------------- conversation

    @abstractmethod
    def user_message(self, text: str) -> dict:
        """A plain user turn in this provider's history format."""

    @abstractmethod
    def is_conversation_start(self, message: dict) -> bool:
        """True if a trimmed history may begin with this message.

        A message carrying only tool results is meaningless without the
        assistant turn that requested them, so history trimming uses this to
        push the window forward to a real user turn.
        """

    @abstractmethod
    def tool_result_messages(self, turn: ModelTurn, results: list[ToolResult]) -> list[dict]:
        """The message(s) that carry tool results back for one assistant turn."""

    @abstractmethod
    def stream(self, messages: list[dict]) -> Iterator[dict]:
        """Run one turn.

        Yields `{"type": "text", "text": ...}` as output arrives, then exactly
        one `{"type": "turn", "turn": ModelTurn}` as the last event. Raises
        `ProviderError` for anything the caller should surface to the user.
        """

    # ------------------------------------------------------------ description

    def describe(self) -> dict:
        return {"provider": self.name, "model": self.model, "api": self.api_label}

    def supports_pause_resume(self) -> bool:
        """Whether a `paused` stop reason can be continued by resending."""
        return False
