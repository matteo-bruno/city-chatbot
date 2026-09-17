"""The HTTP surface: JSON chat, SSE chat, sessions and the info endpoints."""

from __future__ import annotations

import importlib
import json
import os

import pytest
from fake_client import FakeClient, ScriptedTurn, text, tool_use

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Import the app with this repo's data, then swap in the fake API client."""
    os.environ.update(
        {
            "ANTHROPIC_API_KEY": "test-key",
            "CITYCHAT_CITY": "milan",
            "CITYCHAT_DATA_DIR": "data",
            "CITYCHAT_KNOWLEDGE_DIR": "knowledge",
            "CITYCHAT_ALLOW_ORIGINS": "https://example.org",
        }
    )
    module = importlib.import_module("citychat.server")
    return importlib.reload(module)


@pytest.fixture
def client(server):
    return fastapi_testclient.TestClient(server.app)


def script(server, turns):
    server.agent._client = FakeClient(turns)
    return server.agent._client


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["city"] == "Milan"
    assert "area_accessibility" in body["tools"]


def test_city_endpoint_exposes_dataset_and_indicators(client):
    body = client.get("/api/city").json()
    assert body["dataset"]["city"] == "Milan"
    assert body["indicators"]["modes"]["walking"]["proximity_time_city_min"] > 0


def test_places_endpoint_filters(client):
    body = client.get("/api/places", params={"query": "rogoredo"}).json()
    assert body["count"] == 1
    assert body["places"][0]["name"] == "Rogoredo"
    assert body["places"][0]["geometry"] == "circle"


def test_places_endpoint_filters_by_kind(client):
    body = client.get("/api/places", params={"kind": "municipality"}).json()
    assert body["count"] >= 5


def test_chat_returns_reply_and_history(client, server):
    script(server, [ScriptedTurn([text("Proximity time is an average travel time.")])])
    body = client.post("/api/chat", json={"message": "What is the proximity time?"}).json()
    assert body["reply"].startswith("Proximity time")
    assert body["city"] == "Milan"
    assert [m["role"] for m in body["history"]] == ["user", "assistant"]
    assert body["session_id"] is None
    assert body["error"] is None


def test_chat_runs_tools_and_reports_them(client, server):
    script(
        server,
        [
            ScriptedTurn(
                [tool_use("area_accessibility", {"place": "Rogoredo"})], stop_reason="tool_use"
            ),
            ScriptedTurn([text("Yes, about 8 minutes on foot.")]),
        ],
    )
    body = client.post(
        "/api/chat", json={"message": "Is Rogoredo a 15-minute neighbourhood?"}
    ).json()
    assert body["tool_calls"][0]["name"] == "area_accessibility"
    assert body["usage"]["input_tokens"] > 0


def test_client_side_history_round_trips(client, server):
    script(server, [ScriptedTurn([text("first")]), ScriptedTurn([text("second")])])
    first = client.post("/api/chat", json={"message": "one"}).json()
    second = client.post("/api/chat", json={"message": "two", "history": first["history"]}).json()
    assert second["reply"] == "second"
    assert len(second["history"]) == 4


def test_server_side_sessions(client, server):
    script(server, [ScriptedTurn([text("first")]), ScriptedTurn([text("second")])])
    first = client.post("/api/chat", json={"message": "one", "session_id": "new"}).json()
    session_id = first["session_id"]
    assert session_id and first["history"] is None

    second = client.post("/api/chat", json={"message": "two", "session_id": session_id}).json()
    assert second["reply"] == "second"
    assert client.delete(f"/api/session/{session_id}").json()["cleared"] is True
    assert client.delete(f"/api/session/{session_id}").json()["cleared"] is False


def test_streaming_endpoint_emits_sse_events(client, server):
    script(
        server,
        [
            ScriptedTurn([tool_use("city_overview", {})], stop_reason="tool_use"),
            ScriptedTurn([text("Milan averages 9.8 minutes on foot.")]),
        ],
    )
    with client.stream(
        "POST", "/api/chat/stream", json={"message": "Is Milan a 15-minute city?"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")
        ]

    kinds = [e["type"] for e in events]
    assert kinds[0] == "start"
    assert "tool_call" in kinds and "text" in kinds
    done = events[-1]
    assert done["type"] == "done"
    assert done["text"] == "Milan averages 9.8 minutes on foot."
    assert [m["role"] for m in done["history"]] == ["user", "assistant", "user", "assistant"]


def test_empty_message_is_rejected(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_cors_headers_follow_configuration(client):
    response = client.get("/health", headers={"Origin": "https://example.org"})
    assert response.headers["access-control-allow-origin"] == "https://example.org"


def test_demo_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "accessibility assistant" in response.text
