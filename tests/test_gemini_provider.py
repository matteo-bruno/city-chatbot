"""The Gemini provider, driven through a stub that speaks the real wire format."""

from __future__ import annotations

import pytest
from gemini_stub import DEFAULT_USAGE, GeminiStub, call_chunk, text_chunk

from citychat.providers.base import (
    STOP_END_TURN,
    STOP_MAX_TOKENS,
    STOP_REFUSAL,
    STOP_TOOL_USE,
    ToolCall,
    ToolResult,
)
from citychat.providers.gemini import GeminiProvider, sanitise_schema
from citychat.tools import tool_specs


def provider(context, stub: GeminiStub, **kwargs) -> GeminiProvider:
    return GeminiProvider(
        model="gemini-3.8-flash",
        system_prompt="SYSTEM",
        tools=tool_specs(context),
        api_key="test-key",
        transport=stub,
        **kwargs,
    )


def drive(prov: GeminiProvider, messages: list[dict]):
    """Collect the text deltas and the final turn."""
    deltas: list[str] = []
    turn = None
    for event in prov.stream(messages):
        if event["type"] == "text":
            deltas.append(event["text"])
        else:
            turn = event["turn"]
    return deltas, turn


# --------------------------------------------------------------- schema shape


def test_sanitise_schema_upper_cases_types_and_drops_unsupported_keys():
    cleaned = sanitise_schema(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "place": {"type": "string", "description": "a name"},
                "limit": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["place"],
        }
    )
    assert cleaned["type"] == "OBJECT"
    assert "additionalProperties" not in cleaned
    assert cleaned["properties"]["place"]["type"] == "STRING"
    assert cleaned["properties"]["place"]["description"] == "a name"
    assert cleaned["properties"]["tags"]["items"]["type"] == "STRING"
    assert cleaned["required"] == ["place"]


def test_sanitise_schema_preserves_enums():
    cleaned = sanitise_schema({"type": "string", "enum": ["best", "worst"]})
    assert cleaned == {"type": "STRING", "enum": ["best", "worst"]}


def test_function_declarations_carry_no_unsupported_keys(context):
    prov = provider(context, GeminiStub())
    assert len(prov._function_declarations) == len(tool_specs(context))
    for declaration in prov._function_declarations:
        assert declaration["name"] and declaration["description"]
        rendered = repr(declaration)
        assert "additionalProperties" not in rendered
        # Every type must be the upper-case enum form proto3 JSON expects.
        assert '"input_schema"' not in rendered
        assert "'type': 'object'" not in rendered


# ----------------------------------------------------------------- request body


def test_request_body_matches_the_documented_shape(context):
    stub = GeminiStub([[text_chunk("hi", finish="STOP", usage=DEFAULT_USAGE)]])
    prov = provider(context, stub, max_tokens=2048)
    drive(prov, [prov.user_message("hello")])

    body = stub.requests[0]
    assert body["systemInstruction"] == {"parts": [{"text": "SYSTEM"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert body["generationConfig"]["maxOutputTokens"] == 2048
    assert "functionDeclarations" in body["tools"][0]
    assert "googleSearch" not in repr(body["tools"])
    # Streaming endpoint, SSE framing, key in the header not the query string.
    assert "streamGenerateContent" in stub.urls[0]
    assert "alt=sse" in stub.urls[0]
    assert "key=" not in stub.urls[0]


def test_thinking_budget_and_temperature_are_passed_when_set(context):
    stub = GeminiStub([[text_chunk("hi", finish="STOP")]])
    prov = provider(context, stub, temperature=0.2, thinking_budget=0)
    drive(prov, [prov.user_message("hello")])

    generation = stub.requests[0]["generationConfig"]
    assert generation["temperature"] == 0.2
    assert generation["thinkingConfig"] == {"thinkingBudget": 0}


def test_search_grounding_is_added_only_when_enabled(context):
    stub = GeminiStub([[text_chunk("hi", finish="STOP")]])
    prov = provider(context, stub, web_search=True)
    drive(prov, [prov.user_message("hello")])
    assert {"googleSearch": {}} in stub.requests[0]["tools"]


# -------------------------------------------------------------------- streaming


def test_text_is_streamed_chunk_by_chunk(context):
    stub = GeminiStub(
        [
            [
                text_chunk("Milan "),
                text_chunk("averages "),
                text_chunk("9.8 min", finish="STOP", usage=DEFAULT_USAGE),
            ]
        ]
    )
    prov = provider(context, stub)
    deltas, turn = drive(prov, [prov.user_message("hi")])

    assert deltas == ["Milan ", "averages ", "9.8 min"]
    assert turn.text == "Milan averages 9.8 min"
    assert turn.stop_reason == STOP_END_TURN
    assert turn.usage["totalTokenCount"] == 120
    # The assistant message must be replayable as history.
    assert turn.assistant_message["role"] == "model"
    assert turn.assistant_message["parts"] == [
        {"text": "Milan "},
        {"text": "averages "},
        {"text": "9.8 min"},
    ]


def test_a_function_call_is_normalised(context):
    stub = GeminiStub(
        [[call_chunk("area_accessibility", {"place": "Rogoredo"}, usage=DEFAULT_USAGE)]]
    )
    prov = provider(context, stub)
    _, turn = drive(prov, [prov.user_message("is rogoredo walkable?")])

    assert turn.stop_reason == STOP_TOOL_USE
    assert len(turn.tool_calls) == 1
    call = turn.tool_calls[0]
    assert call.name == "area_accessibility"
    assert call.arguments == {"place": "Rogoredo"}
    assert call.id  # synthesised, since Gemini sends none


def test_parallel_function_calls_keep_their_order(context):
    stub = GeminiStub(
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
            ]
        ]
    )
    prov = provider(context, stub)
    _, turn = drive(prov, [prov.user_message("compare")])

    assert [c.name for c in turn.tool_calls] == ["city_overview", "area_accessibility"]
    assert len({c.id for c in turn.tool_calls}) == 2


def test_tool_results_go_back_as_function_responses_in_call_order(context):
    prov = provider(context, GeminiStub())
    calls = [
        ToolCall(id="call_0", name="city_overview", arguments={}),
        ToolCall(id="call_1", name="area_accessibility", arguments={"place": "Duomo"}),
    ]
    from citychat.providers.base import ModelTurn

    turn = ModelTurn(tool_calls=calls)
    results = [
        ToolResult(call=calls[0], payload='{"city": "Milan"}', is_error=False),
        ToolResult(call=calls[1], payload='{"proximity_time_min": 4.1}', is_error=False),
    ]
    messages = prov.tool_result_messages(turn, results)

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    parts = messages[0]["parts"]
    assert [p["functionResponse"]["name"] for p in parts] == [
        "city_overview",
        "area_accessibility",
    ]
    # `response` must be an object, so a JSON payload is passed through as one.
    assert parts[0]["functionResponse"]["response"] == {"city": "Milan"}


def test_a_non_object_tool_payload_is_wrapped():
    call = ToolCall(id="c", name="x", arguments={})
    assert ToolResult(call=call, payload="[1, 2]", is_error=False).parsed() == {"result": [1, 2]}
    assert ToolResult(call=call, payload="not json", is_error=False).parsed() == {
        "result": "not json"
    }


def test_thought_parts_are_replayed_but_not_shown(context):
    stub = GeminiStub(
        [
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {"text": "reasoning", "thought": True},
                                    {"text": "the answer"},
                                ],
                            },
                            "finishReason": "STOP",
                        }
                    ]
                }
            ]
        ]
    )
    prov = provider(context, stub)
    deltas, turn = drive(prov, [prov.user_message("hi")])

    assert deltas == ["the answer"]
    assert turn.text == "the answer"
    assert {"text": "reasoning", "thought": True} in turn.assistant_message["parts"]


# ---------------------------------------------------------------- stop reasons


@pytest.mark.parametrize(
    "finish,expected",
    [
        ("STOP", STOP_END_TURN),
        ("MAX_TOKENS", STOP_MAX_TOKENS),
        ("SAFETY", STOP_REFUSAL),
        ("PROHIBITED_CONTENT", STOP_REFUSAL),
        ("RECITATION", STOP_REFUSAL),
    ],
)
def test_finish_reasons_map_onto_neutral_stop_reasons(context, finish, expected):
    stub = GeminiStub([[text_chunk("partial", finish=finish)]])
    _, turn = drive(provider(context, stub), [{"role": "user", "parts": [{"text": "hi"}]}])
    assert turn.stop_reason == expected


def test_a_blocked_prompt_is_a_refusal(context):
    stub = GeminiStub([[{"promptFeedback": {"blockReason": "SAFETY"}}]])
    _, turn = drive(provider(context, stub), [{"role": "user", "parts": [{"text": "hi"}]}])
    assert turn.stop_reason == STOP_REFUSAL
    assert "SAFETY" in turn.detail


# --------------------------------------------------------------------- errors


def test_a_missing_key_fails_before_any_request(context):
    from citychat.providers.base import ProviderError

    stub = GeminiStub()
    prov = GeminiProvider(
        model="gemini-3.8-flash",
        system_prompt="SYSTEM",
        tools=tool_specs(context),
        api_key="",
        transport=stub,
    )
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        list(prov.stream([prov.user_message("hi")]))
    assert stub.requests == []


def test_a_bad_key_is_explained(context):
    from citychat.providers.base import ProviderError

    stub = GeminiStub(error=(403, {"error": {"message": "API key not valid"}}))
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        drive(provider(context, stub), [{"role": "user", "parts": [{"text": "hi"}]}])


def test_an_unknown_model_lists_the_available_ones(context):
    from citychat.providers.base import ProviderError

    stub = GeminiStub(
        error=(404, {"error": {"message": "models/nope is not found"}}),
        models=["gemini-3.8-flash", "gemini-2.5-flash"],
    )
    with pytest.raises(ProviderError) as excinfo:
        drive(provider(context, stub), [{"role": "user", "parts": [{"text": "hi"}]}])
    message = str(excinfo.value)
    assert "CITYCHAT_MODEL" in message
    assert "gemini-2.5-flash" in message


def test_rate_limiting_and_server_errors_are_explained(context):
    from citychat.providers.base import ProviderError

    for status, phrase in ((429, "Rate limited"), (503, "server error")):
        stub = GeminiStub(error=(status, {"error": {"message": "boom"}}))
        with pytest.raises(ProviderError, match=phrase):
            drive(provider(context, stub), [{"role": "user", "parts": [{"text": "hi"}]}])


def test_search_grounding_is_dropped_and_retried_when_rejected(context):
    """Some model versions refuse to combine grounding with function calling."""
    stub = GeminiStub(
        script=[[text_chunk("answered anyway", finish="STOP")]],
        error=(400, {"error": {"message": "Tool use with googleSearch is unsupported"}}),
        error_times=1,
    )
    prov = provider(context, stub, web_search=True)
    _, turn = drive(prov, [prov.user_message("hi")])

    assert turn.text == "answered anyway"
    assert len(stub.requests) == 2
    assert "googleSearch" in repr(stub.requests[0]["tools"])
    assert "googleSearch" not in repr(stub.requests[1]["tools"])


def test_unparseable_sse_chunks_are_skipped(context):
    import httpx2 as httpx

    def handler(request):
        return httpx.Response(
            200,
            content=b'data: {"bad json\r\n\r\ndata: '
            + b'{"candidates":[{"content":{"role":"model","parts":[{"text":"ok"}]},"finishReason":"STOP"}]}'
            + b"\r\n\r\n",
            headers={"Content-Type": "text/event-stream"},
        )

    prov = GeminiProvider(
        model="m",
        system_prompt="S",
        tools=tool_specs(context),
        api_key="k",
        transport=httpx.MockTransport(handler),
    )
    deltas, turn = drive(prov, [prov.user_message("hi")])
    assert deltas == ["ok"]
    assert turn.stop_reason == STOP_END_TURN


# ------------------------------------------------------------ history trimming


def test_is_conversation_start_rejects_a_function_response_turn(context):
    prov = provider(context, GeminiStub())
    assert prov.is_conversation_start({"role": "user", "parts": [{"text": "hi"}]})
    assert not prov.is_conversation_start(
        {"role": "user", "parts": [{"functionResponse": {"name": "x", "response": {}}}]}
    )
    assert not prov.is_conversation_start({"role": "model", "parts": [{"text": "hi"}]})


def test_an_invalid_key_is_recognised_even_at_status_400(context):
    """Observed live: Google returns 400, not 401, for a malformed key."""
    from citychat.providers.base import ProviderError

    stub = GeminiStub(
        error=(400, {"error": {"message": "API key not valid. Please pass a valid API key."}})
    )
    with pytest.raises(ProviderError) as excinfo:
        drive(provider(context, stub), [{"role": "user", "parts": [{"text": "hi"}]}])
    message = str(excinfo.value)
    assert "GEMINI_API_KEY" in message
    assert "aistudio.google.com/apikey" in message
