"""The full conversation loop over the Gemini provider.

Same loop as the Claude tests, different dialect: this is what proves the
provider seam actually holds - tool rounds, parallel calls, tool errors, the
tool budget, refusals and history replay all work with Gemini's `contents`
format and nothing in `agent.py` knows which provider it is talking to.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from gemini_stub import DEFAULT_USAGE, GeminiStub, call_chunk, text_chunk

from citychat.agent import CityAgent
from citychat.context import CityContext
from citychat.providers.gemini import GeminiProvider
from citychat.tools import tool_specs


@pytest.fixture
def gemini_context(settings):
    return CityContext(replace(settings, provider="gemini", model="gemini-3.8-flash"))


def agent_with(gemini_context, script, **kwargs) -> tuple[CityAgent, GeminiStub]:
    stub = GeminiStub(script, **kwargs)
    provider = GeminiProvider(
        model="gemini-3.8-flash",
        system_prompt="SYSTEM",
        tools=tool_specs(gemini_context),
        api_key="test-key",
        transport=stub,
    )
    return CityAgent(gemini_context, provider=provider), stub


def test_a_plain_answer_over_gemini(gemini_context):
    agent, _ = agent_with(
        gemini_context, [[text_chunk("Proximity time is an average.", finish="STOP")]]
    )
    turn = agent.ask(agent.prepare_messages([], "What is the proximity time?"))

    assert turn.text == "Proximity time is an average."
    assert turn.error is None
    assert [m["role"] for m in turn.messages] == ["user", "model"]
    assert turn.messages[0]["parts"] == [{"text": "What is the proximity time?"}]


def test_a_tool_round_trip_over_gemini(gemini_context):
    agent, stub = agent_with(
        gemini_context,
        [
            [call_chunk("area_accessibility", {"place": "Rogoredo"}, usage=DEFAULT_USAGE)],
            [text_chunk("Yes, about 8 minutes on foot.", finish="STOP", usage=DEFAULT_USAGE)],
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "Is Rogoredo a 15-minute neighbourhood?"))

    assert turn.text == "Yes, about 8 minutes on foot."
    assert turn.tool_calls == [
        {"name": "area_accessibility", "input": {"place": "Rogoredo"}, "is_error": False}
    ]
    assert [m["role"] for m in turn.messages] == ["user", "model", "user", "model"]

    # The tool result went back as a functionResponse carrying the real figures.
    response = turn.messages[2]["parts"][0]["functionResponse"]
    assert response["name"] == "area_accessibility"
    assert response["response"]["area"]["name"] == "Rogoredo"
    assert response["response"]["proximity_time_min"] > 0

    # And the second request replayed the whole conversation.
    assert len(stub.requests[1]["contents"]) == 3


def test_parallel_tool_calls_over_gemini(gemini_context):
    agent, _ = agent_with(
        gemini_context,
        [
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {"functionCall": {"name": "city_overview", "args": {}}},
                                    {
                                        "functionCall": {
                                            "name": "area_accessibility",
                                            "args": {"place": "Duomo"},
                                        }
                                    },
                                ],
                            },
                            "finishReason": "STOP",
                        }
                    ]
                }
            ],
            [text_chunk("Both done.", finish="STOP")],
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "compare"))

    assert len(turn.tool_calls) == 2
    parts = turn.messages[2]["parts"]
    assert [p["functionResponse"]["name"] for p in parts] == [
        "city_overview",
        "area_accessibility",
    ]


def test_a_failing_tool_is_reported_to_gemini(gemini_context):
    agent, _ = agent_with(
        gemini_context,
        [
            [call_chunk("area_accessibility", {"place": "Porta Verde"})],
            [text_chunk("I could not locate that area.", finish="STOP")],
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "Is Porta Verde walkable?"))

    response = turn.messages[2]["parts"][0]["functionResponse"]["response"]
    assert response["error"] == "place_not_found"
    assert turn.tool_calls[0]["is_error"] is True
    assert turn.text == "I could not locate that area."


def test_the_tool_budget_is_enforced_over_gemini(gemini_context):
    limited = CityContext(replace(gemini_context.settings, max_tool_rounds=1))
    agent, _ = agent_with(
        limited,
        [
            [call_chunk("city_overview", {})],
            [call_chunk("city_overview", {})],
            [text_chunk("Answering with what I have.", finish="STOP")],
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "loop please"))

    budget = turn.messages[-2]["parts"][0]["functionResponse"]["response"]
    assert budget["error"] == "tool_budget_exhausted"
    assert turn.text == "Answering with what I have."


def test_a_refusal_over_gemini_is_surfaced(gemini_context):
    agent, _ = agent_with(gemini_context, [[text_chunk("", finish="SAFETY")]])
    events = list(agent.run(agent.prepare_messages([], "something blocked")))

    assert any(e["type"] == "error" for e in events)
    done = events[-1]
    assert done["stop_reason"] == "refusal"
    assert done["error"] == "refusal"
    assert done["text"]


def test_an_api_failure_over_gemini_is_readable(gemini_context):
    agent, _ = agent_with(
        gemini_context,
        [[text_chunk("never reached", finish="STOP")]],
        error=(403, {"error": {"message": "API key not valid"}}),
    )
    events = list(agent.run(agent.prepare_messages([], "hello")))

    assert events[0]["type"] == "error"
    assert "GEMINI_API_KEY" in events[0]["message"]
    assert events[-1]["stop_reason"] == "error"
    assert events[-1]["provider"] == "gemini"


def test_usage_accumulates_across_gemini_rounds(gemini_context):
    agent, _ = agent_with(
        gemini_context,
        [
            [call_chunk("city_overview", {}, usage=DEFAULT_USAGE)],
            [text_chunk("ok", finish="STOP", usage=DEFAULT_USAGE)],
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "hi"))
    # Two billed requests, so the prompt tokens of both are counted.
    assert turn.usage["promptTokenCount"] == 200
    assert turn.usage["candidatesTokenCount"] == 40


def test_multi_turn_history_replays_over_gemini(gemini_context):
    agent, stub = agent_with(
        gemini_context,
        [[text_chunk("first", finish="STOP")], [text_chunk("second", finish="STOP")]],
    )
    first = agent.ask(agent.prepare_messages([], "one"))
    second = agent.ask(agent.prepare_messages(first.messages, "two", "gemini"))

    assert [m["role"] for m in second.messages] == ["user", "model", "user", "model"]
    assert stub.requests[1]["contents"][0] == {"role": "user", "parts": [{"text": "one"}]}


def test_history_trimming_uses_the_gemini_dialect(gemini_context):
    from citychat.agent import trim_history

    agent, _ = agent_with(gemini_context, [])
    history = [
        {"role": "user", "parts": [{"text": "q"}]},
        {"role": "model", "parts": [{"functionCall": {"name": "t", "args": {}}}]},
        {"role": "user", "parts": [{"functionResponse": {"name": "t", "response": {}}}]},
        {"role": "model", "parts": [{"text": "answer"}]},
    ]
    # A window starting on the functionResponse would be invalid, so it is dropped.
    assert trim_history(history, 2, agent.provider) == []
    assert trim_history(history, 10, agent.provider) == history


def test_the_system_prompt_is_identical_between_gemini_turns(gemini_context):
    agent, stub = agent_with(
        gemini_context,
        [[text_chunk("a", finish="STOP")], [text_chunk("b", finish="STOP")]],
    )
    first = agent.ask(agent.prepare_messages([], "one"))
    agent.ask(agent.prepare_messages(first.messages, "two", "gemini"))

    assert stub.requests[0]["systemInstruction"] == stub.requests[1]["systemInstruction"]
    assert stub.requests[0]["tools"] == stub.requests[1]["tools"]


def test_the_real_system_prompt_is_sent_when_built_from_settings(gemini_context):
    """The registry path, rather than an injected provider."""
    agent = CityAgent(gemini_context)
    assert agent.provider_name == "gemini"
    assert agent.provider.model == "gemini-3.8-flash"
    assert "City briefing" in agent.provider.system_prompt
    assert json.dumps(agent.describe())
