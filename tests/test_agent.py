"""The conversation loop, driven by a scripted fake API client."""

from __future__ import annotations

import json

import pytest
from fake_client import FakeClient, ScriptedTurn, text, thinking, tool_use

from citychat.agent import CityAgent, HistoryProviderMismatch, trim_history
from citychat.tools import tool_specs


def agent_with(context, script, **kwargs) -> CityAgent:
    return CityAgent(context, client=FakeClient(script, **kwargs))


def test_a_plain_answer_needs_no_tools(context):
    agent = agent_with(context, [ScriptedTurn([text("Proximity time is an average travel time.")])])
    turn = agent.ask(agent.prepare_messages([], "What is the proximity time?"))
    assert turn.text == "Proximity time is an average travel time."
    assert turn.tool_calls == []
    assert turn.stop_reason == "end_turn"
    assert turn.error is None
    # History is mirrored back: user turn plus assistant turn.
    assert [m["role"] for m in turn.messages] == ["user", "assistant"]


def test_text_is_streamed_as_deltas(context):
    agent = agent_with(context, [ScriptedTurn([text("one two three")])])
    events = list(agent.run(agent.prepare_messages([], "hi")))
    deltas = [e["text"] for e in events if e["type"] == "text"]
    assert len(deltas) == 3
    assert "".join(deltas) == "one two three"
    assert events[-1]["type"] == "done"


def test_a_tool_call_is_executed_and_fed_back(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn(
                [tool_use("area_accessibility", {"place": "Rogoredo"})], stop_reason="tool_use"
            ),
            ScriptedTurn([text("Rogoredo is a 15-minute neighbourhood on foot.")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "Is Rogoredo a 15-minute neighbourhood?"))

    assert turn.tool_calls == [
        {"name": "area_accessibility", "input": {"place": "Rogoredo"}, "is_error": False}
    ]
    assert [m["role"] for m in turn.messages] == ["user", "assistant", "user", "assistant"]

    # The tool result carries real figures, keyed to the tool_use id.
    result_block = turn.messages[2]["content"][0]
    assert result_block["type"] == "tool_result"
    assert result_block["tool_use_id"] == "tu_1"
    payload = json.loads(result_block["content"])
    assert payload["area"]["name"] == "Rogoredo"
    assert payload["proximity_time_min"] > 0


def test_tool_progress_is_reported_as_events(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn([tool_use("city_overview", {})], stop_reason="tool_use"),
            ScriptedTurn([text("done")]),
        ],
    )
    kinds = [e["type"] for e in agent.run(agent.prepare_messages([], "overview?"))]
    assert "tool_call" in kinds and "tool_result" in kinds


def test_parallel_tool_calls_return_in_one_user_message(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn(
                [
                    tool_use("city_overview", {}, id="a"),
                    tool_use("area_accessibility", {"place": "Duomo"}, id="b"),
                ],
                stop_reason="tool_use",
            ),
            ScriptedTurn([text("both done")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "compare"))
    results = turn.messages[2]["content"]
    assert len(results) == 2
    assert {r["tool_use_id"] for r in results} == {"a", "b"}
    assert len(turn.tool_calls) == 2


def test_a_failing_tool_is_reported_to_the_model_not_raised(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn(
                [tool_use("area_accessibility", {"place": "Porta Verde"})], stop_reason="tool_use"
            ),
            ScriptedTurn([text("I could not locate that area.")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "Is Porta Verde walkable?"))
    result_block = turn.messages[2]["content"][0]
    assert result_block["is_error"] is True
    assert json.loads(result_block["content"])["error"] == "place_not_found"
    assert turn.tool_calls[0]["is_error"] is True
    assert turn.text == "I could not locate that area."


def test_thinking_blocks_are_replayed_verbatim(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn(
                [thinking("reasoning", "sig-1"), tool_use("city_overview", {})],
                stop_reason="tool_use",
            ),
            ScriptedTurn([text("ok")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "hi"))
    replayed = turn.messages[1]["content"][0]
    assert replayed == {"type": "thinking", "thinking": "reasoning", "signature": "sig-1"}


def test_the_tool_budget_is_enforced_and_the_model_told_to_conclude(context):
    from dataclasses import replace

    from citychat.context import CityContext

    limited = CityContext(replace(context.settings, max_tool_rounds=1))
    agent = agent_with(
        limited,
        [
            ScriptedTurn([tool_use("city_overview", {}, id="a")], stop_reason="tool_use"),
            ScriptedTurn([tool_use("city_overview", {}, id="b")], stop_reason="tool_use"),
            ScriptedTurn([text("Answering with what I have.")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "loop please"))
    budget_message = turn.messages[-2]["content"][0]
    assert budget_message["is_error"] is True
    assert json.loads(budget_message["content"])["error"] == "tool_budget_exhausted"
    assert turn.text == "Answering with what I have."


def test_pause_turn_is_resumed(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn([text("searching")], stop_reason="pause_turn"),
            ScriptedTurn([text(" and done")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "look it up"))
    assert turn.text == "searching and done"
    assert turn.stop_reason == "end_turn"


def test_a_refusal_is_surfaced_without_crashing(context):
    agent = agent_with(context, [ScriptedTurn([], stop_reason="refusal")])
    events = list(agent.run(agent.prepare_messages([], "something declined")))
    assert any(e["type"] == "error" for e in events)
    done = events[-1]
    assert done["stop_reason"] == "refusal"
    assert done["error"] == "refusal"
    assert done["text"]


def test_an_api_error_becomes_a_readable_message(context):
    import anthropic

    error = anthropic.APIConnectionError(request=None)
    agent = agent_with(context, [ScriptedTurn([text("never reached")])], raise_on_call=error)
    events = list(agent.run(agent.prepare_messages([], "hello")))
    assert events[0]["type"] == "error"
    assert "Could not reach" in events[0]["message"]
    assert events[-1]["stop_reason"] == "error"


def test_usage_is_accumulated_across_rounds(context):
    agent = agent_with(
        context,
        [
            ScriptedTurn([tool_use("city_overview", {})], stop_reason="tool_use"),
            ScriptedTurn([text("ok")]),
        ],
    )
    turn = agent.ask(agent.prepare_messages([], "hi"))
    assert turn.usage["input_tokens"] == 20
    assert turn.usage["output_tokens"] == 10


def test_the_request_is_shaped_for_prompt_caching(context):
    client = FakeClient([ScriptedTurn([text("ok")])])
    agent = CityAgent(context, client=client)
    agent.ask(agent.prepare_messages([], "hi"))

    request = client.requests[0]
    assert request["model"] == agent.provider.model
    assert request["output_config"] == {"effort": context.settings.effort}
    system = request["system"]
    assert len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "City briefing" in system[0]["text"]
    assert [t["name"] for t in request["tools"]] == [s.name for s in tool_specs(context)]
    # Anthropic wants the JSON Schema verbatim, `additionalProperties` included.
    assert request["tools"][0]["input_schema"]["additionalProperties"] is False


def test_the_system_prompt_is_identical_between_turns(context):
    client = FakeClient([ScriptedTurn([text("a")]), ScriptedTurn([text("b")])])
    agent = CityAgent(context, client=client)
    first = agent.ask(agent.prepare_messages([], "one"))
    agent.ask(agent.prepare_messages(first.messages, "two"))
    # Any difference here would break the cache prefix on every second turn.
    assert client.requests[0]["system"] == client.requests[1]["system"]
    assert client.requests[0]["tools"] == client.requests[1]["tools"]


def test_refusal_fallback_can_be_switched_off(context):
    from dataclasses import replace

    from citychat.context import CityContext

    plain = CityContext(replace(context.settings, refusal_fallback=False))
    client = FakeClient([ScriptedTurn([text("ok")])])
    agent = CityAgent(plain, client=client)
    agent.ask(agent.prepare_messages([], "hi"))
    assert "fallbacks" not in client.requests[0]

    client2 = FakeClient([ScriptedTurn([text("ok")])])
    agent2 = CityAgent(context, client=client2)
    agent2.ask(agent2.prepare_messages([], "hi"))
    assert client2.requests[0]["fallbacks"] == "default"
    assert client2.requests[0]["betas"] == ["server-side-fallback-2026-07-01"]


def test_multi_turn_history_is_carried_forward(context):
    client = FakeClient([ScriptedTurn([text("first")]), ScriptedTurn([text("second")])])
    agent = CityAgent(context, client=client)
    first = agent.ask(agent.prepare_messages([], "one"))
    second = agent.ask(agent.prepare_messages(first.messages, "two"))
    assert [m["role"] for m in second.messages] == ["user", "assistant", "user", "assistant"]
    assert client.requests[1]["messages"][0]["content"] == "one"


# --------------------------------------------------------------- history trim


@pytest.fixture(scope="module")
def anthropic_provider(context):
    return CityAgent(context, client=FakeClient([])).provider


def test_trim_history_keeps_everything_when_short(anthropic_provider):
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    assert trim_history(history, 10, anthropic_provider) == history


def test_trim_history_never_starts_on_an_orphaned_tool_result(anthropic_provider):
    history = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "x", "name": "t", "input": {}}],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "{}"}]},
        {"role": "assistant", "content": "answer"},
    ]
    trimmed = trim_history(history, 2, anthropic_provider)
    # The window would have started on the tool result, which the API rejects.
    assert trimmed == []


def test_trim_history_keeps_a_valid_window(anthropic_provider):
    history = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "new"},
        {"role": "assistant", "content": "new answer"},
    ]
    assert trim_history(history, 2, anthropic_provider) == [history[2], history[3]]


@pytest.mark.parametrize("limit", [0, -1])
def test_trim_history_with_no_limit_keeps_all(limit, anthropic_provider):
    history = [{"role": "user", "content": "a"}] * 5
    assert len(trim_history(history, limit, anthropic_provider)) == 5


# ------------------------------------------------- model-gated request params


def bad_request(message: str):
    """A real BadRequestError, as the SDK would raise it for a rejected field."""
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(400, request=request, json={"error": {"message": message}})
    return anthropic.BadRequestError(message, response=response, body=None)


def test_effort_is_omitted_when_unset(context):
    """`CITYCHAT_EFFORT=` means "use the model's own default"."""
    from dataclasses import replace

    from citychat.context import CityContext

    no_effort = CityContext(replace(context.settings, effort=""))
    client = FakeClient([ScriptedTurn([text("ok")])])
    agent = CityAgent(no_effort, client=client)
    agent.ask(agent.prepare_messages([], "hi"))
    assert "output_config" not in client.requests[0]


def test_a_model_rejecting_effort_is_retried_without_it(context):
    """Haiku 4.5 does not accept output_config.effort; the turn must still answer."""
    client = FakeClient(
        [ScriptedTurn([text("answered anyway")])],
        raise_on_call=bad_request("output_config.effort: unsupported parameter for this model"),
    )
    agent = CityAgent(context, client=client)
    turn = agent.ask(agent.prepare_messages([], "hi"))

    assert turn.text == "answered anyway"
    assert turn.error is None
    assert len(client.requests) == 2
    assert "output_config" in client.requests[0]
    assert "output_config" not in client.requests[1]
    # And it stays off for the rest of the process, so the cache prefix settles.
    assert agent.provider._send_effort is False


def test_a_model_rejecting_the_fallback_beta_is_retried_without_it(context):
    client = FakeClient(
        [ScriptedTurn([text("answered anyway")])],
        raise_on_call=bad_request("fallbacks: not available for model claude-sonnet-5"),
    )
    agent = CityAgent(context, client=client)
    turn = agent.ask(agent.prepare_messages([], "hi"))

    assert turn.text == "answered anyway"
    assert "fallbacks" in client.requests[0]
    assert "fallbacks" not in client.requests[1]
    assert "betas" not in client.requests[1]
    assert agent.provider._send_fallbacks is False


def test_an_unrelated_bad_request_is_surfaced_and_not_retried(context):
    client = FakeClient(
        [ScriptedTurn([text("never reached")])],
        raise_on_call=bad_request("messages.0: content must not be empty"),
    )
    agent = CityAgent(context, client=client)
    events = list(agent.run(agent.prepare_messages([], "hi")))

    assert events[0]["type"] == "error"
    assert "content must not be empty" in events[0]["message"]
    assert events[-1]["stop_reason"] == "error"
    assert len(client.requests) == 1  # no retry loop


def test_each_parameter_is_only_dropped_once(context):
    """A second rejection of an already-dropped field must not loop forever."""
    provider = CityAgent(context, client=FakeClient([])).provider
    assert provider._drop_unsupported_parameter(bad_request("bad effort")) is not None
    assert provider._drop_unsupported_parameter(bad_request("bad effort")) is None


# ------------------------------------------------------------- provider seam


def test_an_empty_model_setting_uses_the_provider_default(context):
    from citychat.providers import ANTHROPIC_DEFAULT_MODEL

    assert context.settings.model == ""
    agent = CityAgent(context, client=FakeClient([]))
    assert agent.provider.model == ANTHROPIC_DEFAULT_MODEL
    assert agent.provider_name == "anthropic"


def test_an_explicit_model_wins(context):
    from dataclasses import replace

    from citychat.context import CityContext

    pinned = CityContext(replace(context.settings, model="claude-sonnet-5"))
    agent = CityAgent(pinned, client=FakeClient([]))
    assert agent.provider.model == "claude-sonnet-5"


def test_an_unknown_provider_is_rejected_with_the_options(context):
    from dataclasses import replace

    from citychat.context import CityContext

    broken = CityContext(replace(context.settings, provider="llamafile"))
    with pytest.raises(RuntimeError, match="unknown CITYCHAT_PROVIDER"):
        CityAgent(broken)


def test_describe_reports_the_active_provider(context):
    described = CityAgent(context, client=FakeClient([])).describe()
    assert described["provider"] == "anthropic"
    assert described["api"] == "the Claude API"
    assert "area_accessibility" in described["tools"]


def test_a_history_from_another_provider_is_refused(context):
    """Content blocks and Gemini parts are not interchangeable."""
    agent = CityAgent(context, client=FakeClient([]))
    history = [{"role": "user", "parts": [{"text": "hi"}]}]
    with pytest.raises(HistoryProviderMismatch) as excinfo:
        agent.prepare_messages(history, "next", history_provider="gemini")
    assert excinfo.value.expected == "anthropic"
    assert excinfo.value.found == "gemini"


def test_a_matching_history_provider_is_accepted(context):
    agent = CityAgent(context, client=FakeClient([]))
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "there"}]
    messages = agent.prepare_messages(history, "next", history_provider="anthropic")
    assert len(messages) == 3


def test_an_empty_history_needs_no_provider_tag(context):
    agent = CityAgent(context, client=FakeClient([]))
    assert agent.prepare_messages([], "hi", history_provider="gemini")


def test_the_done_event_names_the_provider(context):
    agent = CityAgent(context, client=FakeClient([ScriptedTurn([text("ok")])]))
    events = list(agent.run(agent.prepare_messages([], "hi")))
    assert events[-1]["provider"] == "anthropic"
