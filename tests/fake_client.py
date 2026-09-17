"""A scripted stand-in for `anthropic.Anthropic`.

Lets the whole conversation loop - streaming, tool execution, history mirroring,
pause/refusal/error handling - be tested without an API key or a network call.
Each scripted turn is a list of content blocks plus a stop reason; the fake
records the requests it received so assertions can check caching headers, tool
definitions and the shape of the messages sent back.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Block:
    type: str
    text: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)
    id: str = ""
    thinking: str = ""
    signature: str = ""

    def to_dict(self) -> dict:
        if self.type == "text":
            return {"type": "text", "text": self.text}
        if self.type == "thinking":
            return {"type": "thinking", "thinking": self.thinking, "signature": self.signature}
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}


def text(value: str) -> Block:
    return Block(type="text", text=value)


def tool_use(name: str, tool_input: dict, id: str = "tu_1") -> Block:
    return Block(type="tool_use", name=name, input=tool_input, id=id)


def thinking(value: str = "", signature: str = "sig") -> Block:
    return Block(type="thinking", thinking=value, signature=signature)


@dataclass
class ScriptedTurn:
    blocks: list[Block]
    stop_reason: str = "end_turn"
    usage: dict = field(default_factory=lambda: {"input_tokens": 10, "output_tokens": 5})
    stop_details: Any = None


class FakeMessage:
    def __init__(self, turn: ScriptedTurn) -> None:
        self.content = turn.blocks
        self.stop_reason = turn.stop_reason
        self.usage = turn.usage
        self.stop_details = turn.stop_details

    def to_json(self) -> str:
        return json.dumps({"content": [b.to_dict() for b in self.content]})


class FakeStream:
    def __init__(self, turn: ScriptedTurn) -> None:
        self.turn = turn

    def __enter__(self) -> FakeStream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def __iter__(self) -> Iterator[Any]:
        for block in self.turn.blocks:
            if block.type != "text":
                continue
            # One delta per word, so partial streaming is exercised.
            for i, word in enumerate(block.text.split(" ")):
                piece = word if i == 0 else " " + word
                yield _Event("content_block_delta", _Delta("text_delta", piece))

    def get_final_message(self) -> FakeMessage:
        return FakeMessage(self.turn)


@dataclass
class _Delta:
    type: str
    text: str


@dataclass
class _Event:
    type: str
    delta: _Delta


class _Messages:
    def __init__(self, client: FakeClient) -> None:
        self._client = client

    def stream(self, **kwargs: Any) -> Any:
        self._client.requests.append(kwargs)
        if self._client.raise_on_call is not None:
            error = self._client.raise_on_call
            self._client.raise_on_call = None
            raise error
        if not self._client.script:
            raise AssertionError("fake client ran out of scripted turns")
        return FakeStream(self._client.script.pop(0))


class FakeClient:
    """Mimics both `client.messages` and `client.beta.messages`."""

    def __init__(self, script: list[ScriptedTurn], raise_on_call: Exception | None = None) -> None:
        self.script = list(script)
        self.requests: list[dict] = []
        self.raise_on_call = raise_on_call
        self.messages = _Messages(self)
        self.beta = type("Beta", (), {"messages": self.messages})()
