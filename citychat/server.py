"""HTTP surface: a JSON endpoint, an SSE endpoint and a static demo page.

    uvicorn citychat.server:app --reload

Deliberately thin. All the behaviour lives in `CityAgent`, so this file can be
replaced by whatever the host site already uses (Flask, Django, a serverless
function) without touching the assistant.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .agent import CityAgent, HistoryProviderMismatch
from .config import Settings
from .context import CityContext
from .sessions import SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("citychat.server")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

settings = Settings.from_env()
context = CityContext(settings)
agent = CityAgent(context)
sessions = SessionStore(max_sessions=settings.max_sessions)

app = FastAPI(
    title="City accessibility chatbot",
    version=__version__,
    description="Chat over one city's 15-minute-accessibility indicators.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[dict] | None = Field(
        default=None,
        description=(
            "Prior messages in the active provider's own format. Send back what the last "
            "response returned."
        ),
    )
    provider: str | None = Field(
        default=None,
        description=(
            "Which provider produced `history`. Echo back the `provider` field from the last "
            "response; a mismatch is rejected rather than sent as a malformed request."
        ),
    )
    session_id: str | None = Field(
        default=None,
        description="Server-side history instead of `history`. Pass 'new' to start one.",
    )


class ChatResponse(BaseModel):
    reply: str
    city: str
    provider: str
    model: str
    session_id: str | None = None
    history: list[dict] | None = None
    tool_calls: list[dict] = []
    usage: dict = {}
    stop_reason: str | None = None
    error: str | None = None


def _resolve_history(request: ChatRequest) -> tuple[list[dict], str | None, str | None]:
    """(history, history_provider, session_id)."""
    if request.session_id:
        session_id = sessions.new_id() if request.session_id == "new" else request.session_id
        state = sessions.get(session_id)
        return list(state.messages), state.provider or None, session_id
    return list(request.history or []), request.provider, None


def _prepare(request: ChatRequest) -> tuple[list[dict], str | None]:
    history, history_provider, session_id = _resolve_history(request)
    try:
        messages = agent.prepare_messages(history, request.message, history_provider)
    except HistoryProviderMismatch as exc:
        # A stale transcript from another provider: say so with a 409 so the
        # client knows to start over rather than silently losing context.
        if session_id:
            sessions.clear(session_id)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return messages, session_id


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "city": context.store.name,
        **agent.describe(),
        # For Claude the SDK also resolves an `ant auth login` profile, so an
        # empty key here does not necessarily mean no credentials.
        "api_key_from_environment": bool(settings.api_key_for_provider),
        "active_sessions": len(sessions),
    }


@app.get("/api/city")
def city() -> dict:
    """What this deployment holds, plus the city-level indicators."""
    return {
        "dataset": {**context.data_summary(), "model": agent.provider.model},
        "indicators": context.store.overview(),
    }


@app.get("/api/places")
def places(query: str | None = None, kind: str | None = None) -> dict:
    q = (query or "").lower()
    items = [
        p.describe()
        for p in context.gazetteer.places
        if (kind is None or p.kind == kind)
        and (not q or q in p.name.lower() or any(q in a.lower() for a in p.aliases))
    ]
    items.sort(key=lambda p: p["name"])
    return {"city": context.store.name, "count": len(items), "places": items}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    messages, session_id = _prepare(request)
    turn = agent.ask(messages)
    if session_id:
        sessions.set(session_id, agent.provider_name, turn.messages)
    return ChatResponse(
        reply=turn.text,
        city=context.store.name,
        provider=agent.provider_name,
        model=agent.provider.model,
        session_id=session_id,
        history=None if session_id else turn.messages,
        tool_calls=turn.tool_calls,
        usage=turn.usage,
        stop_reason=turn.stop_reason,
        error=turn.error,
    )


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Server-sent events: `text` deltas, tool progress, then `done`."""
    messages, session_id = _prepare(request)

    def emit():
        yield _sse(
            {
                "type": "start",
                "city": context.store.name,
                "provider": agent.provider_name,
                "model": agent.provider.model,
                "session_id": session_id,
            }
        )
        for event in agent.run(messages):
            if event["type"] == "done":
                if session_id:
                    sessions.set(session_id, agent.provider_name, event["messages"])
                payload = {
                    "type": "done",
                    "text": event["text"],
                    "tool_calls": event["tool_calls"],
                    "usage": event["usage"],
                    "stop_reason": event["stop_reason"],
                    "provider": agent.provider_name,
                    "session_id": session_id,
                    "error": event.get("error"),
                }
                if not session_id:
                    payload["history"] = event["messages"]
                yield _sse(payload)
            else:
                yield _sse(event)

    return StreamingResponse(
        emit(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/api/session/{session_id}")
def clear_session(session_id: str) -> dict:
    return {"cleared": sessions.clear(session_id)}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@app.get("/")
def index():
    page = WEB_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"detail": "no demo page bundled; use /api/chat"}, status_code=404)
    return FileResponse(page)


@app.exception_handler(ValueError)
def value_error_handler(_request, exc: ValueError) -> JSONResponse:
    """Turn a bad argument (unknown travel mode, missing place) into a 400."""
    return JSONResponse({"detail": str(exc)}, status_code=400)
