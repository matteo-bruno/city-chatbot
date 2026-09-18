"""An httpx transport that speaks the documented Gemini SSE wire format.

Lets the Gemini provider be driven through a full tool round trip - request
shape, SSE parsing, function-call accumulation, usage, error paths - with no
API key and no network. It also records every request body, so the tests can
assert on what we actually put on the wire.
"""

from __future__ import annotations

import json

from citychat.http import httpx


def sse(chunks: list[dict]) -> bytes:
    return b"".join(b"data: " + json.dumps(chunk).encode() + b"\r\n\r\n" for chunk in chunks)


def text_chunk(text: str, finish: str | None = None, usage: dict | None = None) -> dict:
    chunk: dict = {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}
    if finish:
        chunk["candidates"][0]["finishReason"] = finish
    if usage:
        chunk["usageMetadata"] = usage
    return chunk


def call_chunk(name: str, args: dict, finish: str = "STOP", usage: dict | None = None) -> dict:
    chunk: dict = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"functionCall": {"name": name, "args": args}}],
                },
                "finishReason": finish,
            }
        ]
    }
    if usage:
        chunk["usageMetadata"] = usage
    return chunk


DEFAULT_USAGE = {"promptTokenCount": 100, "candidatesTokenCount": 20, "totalTokenCount": 120}


class GeminiStub(httpx.MockTransport):
    """Replays a script of turns; each turn is a list of SSE chunks."""

    def __init__(
        self,
        script: list[list[dict]] | None = None,
        models: list[str] | None = None,
        error: tuple[int, dict] | None = None,
        error_times: int = 1,
    ) -> None:
        self.script = list(script or [])
        self.models = models or ["gemini-3.8-flash", "gemini-2.5-flash"]
        self.error = error
        self.error_times = error_times
        self.requests: list[dict] = []
        self.urls: list[str] = []
        super().__init__(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))

        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": f"models/{name}",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                        for name in self.models
                    ]
                },
            )

        self.requests.append(json.loads(request.content))

        if self.error is not None and self.error_times > 0:
            self.error_times -= 1
            status, body = self.error
            return httpx.Response(status, json=body)

        if not self.script:
            raise AssertionError("Gemini stub ran out of scripted turns")
        return httpx.Response(
            200,
            content=sse(self.script.pop(0)),
            headers={"Content-Type": "text/event-stream"},
        )
