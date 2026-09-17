"""The tool surface the model sees, and what each tool returns."""

from __future__ import annotations

import json

import pytest

from citychat.tools import run_tool, tool_definitions


def call(context, name: str, args: dict) -> tuple[dict, bool]:
    payload, is_error = run_tool(context, name, args)
    return json.loads(payload), is_error


def test_tool_definitions_are_well_formed_and_stable(context):
    definitions = tool_definitions(context)
    names = [d["name"] for d in definitions]
    assert names == [
        "city_overview",
        "area_accessibility",
        "compare_areas",
        "rank_areas",
        "list_known_places",
        "search_methodology",
    ]
    for definition in definitions:
        assert definition["description"]
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
    # Definitions sit in front of the cache breakpoint, so they must be stable.
    assert tool_definitions(context) == definitions


def test_web_search_is_only_offered_when_enabled(context, settings):
    assert all(d.get("type") != "web_search_20260209" for d in tool_definitions(context))

    from dataclasses import replace

    from citychat.context import CityContext

    enabled = CityContext(replace(settings, web_search=True))
    web = [d for d in tool_definitions(enabled) if d.get("name") == "web_search"]
    assert len(web) == 1
    assert web[0]["type"] == "web_search_20260209"
    assert web[0]["max_uses"] == enabled.settings.web_search_max_uses


def test_city_overview_returns_both_modes_by_default(context):
    result, is_error = call(context, "city_overview", {})
    assert not is_error
    assert set(result["modes"]) == {"walking", "cycling"}
    assert result["city"] == "Milan"
    assert result["data_vintage"]


def test_city_overview_can_be_restricted_to_one_mode(context):
    result, _ = call(context, "city_overview", {"travel_mode": "walking"})
    assert set(result["modes"]) == {"walking"}


def test_area_accessibility_by_name(context):
    result, is_error = call(context, "area_accessibility", {"place": "Rogoredo"})
    assert not is_error
    assert result["area"]["name"] == "Rogoredo"
    assert result["travel_mode"] == "walking"
    assert result["proximity_time_min"] > 0
    assert "meets_15_minute_standard" in result["assessment"]
    assert result["city_comparison"]["city_proximity_time_min"] > 0
    # A circle-derived area must carry the caveat the prompt tells us to surface.
    assert "caveat" in result


def test_area_accessibility_by_coordinates(context):
    result, is_error = call(
        context, "area_accessibility", {"lat": 45.4642, "lon": 9.19, "radius_m": 500}
    )
    assert not is_error
    assert result["cells"] > 0
    assert result["area"]["centre_precision"] == "exact coordinates"


def test_area_accessibility_reports_a_missing_place_as_a_tool_error(context):
    result, is_error = call(context, "area_accessibility", {"place": "Porta Verde"})
    assert is_error
    assert result["error"] == "place_not_found"
    assert "Porta Venezia" in result["did_you_mean"]


def test_area_accessibility_reports_out_of_coverage(context):
    result, is_error = call(context, "area_accessibility", {"lat": 41.9028, "lon": 12.4964})
    assert is_error
    assert result["error"] == "outside_coverage"
    assert "Milan" in result["message"]


def test_area_accessibility_rejects_an_unknown_mode(context):
    result, is_error = call(
        context, "area_accessibility", {"place": "Duomo", "travel_mode": "jetpack"}
    )
    assert is_error
    assert result["error"] == "bad_request"


def test_compare_areas_sorts_best_first_and_reports_misses(context):
    result, _ = call(context, "compare_areas", {"places": ["Muggiano", "Duomo", "Nowhereville"]})
    rows = result["areas_best_first"]
    assert [r["area"] for r in rows] == ["Duomo", "Muggiano"]
    assert rows[0]["meets_15_minute_standard"] is True
    assert result["unresolved"][0]["error"] == "place_not_found"


def test_compare_areas_needs_two_places(context):
    result, is_error = call(context, "compare_areas", {"places": ["Duomo"]})
    assert is_error and result["error"] == "bad_request"


def test_rank_areas_best_and_worst_are_opposites(context):
    best, _ = call(context, "rank_areas", {"order": "best", "limit": 3})
    worst, _ = call(context, "rank_areas", {"order": "worst", "limit": 3})
    assert best["ranked"][0]["minutes"] < worst["ranked"][0]["minutes"]
    assert "named areas in the gazetteer" in best["scope"]


def test_rank_areas_by_category_and_kind(context):
    result, _ = call(
        context,
        "rank_areas",
        {"order": "worst", "indicator": "healthcare", "kind": "municipality", "limit": 5},
    )
    assert result["indicator"] == "healthcare"
    assert result["ranked"]
    assert "municipality" in result["scope"]


def test_rank_areas_rejects_an_unknown_indicator(context):
    result, is_error = call(context, "rank_areas", {"indicator": "happiness"})
    assert is_error and result["error"] == "bad_request"


def test_list_known_places_filters(context):
    everything, _ = call(context, "list_known_places", {})
    assert everything["total_known"] == len(context.gazetteer)
    filtered, _ = call(context, "list_known_places", {"query": "porta"})
    assert filtered["matched"] >= 4
    # Aliases count too: Navigli matches through "Porta Ticinese".
    by_name = {p.name: p for p in context.gazetteer.places}
    for name in filtered["places"]:
        place = by_name[name]
        haystack = " ".join([place.name, *place.aliases]).lower()
        assert "porta" in haystack


def test_search_methodology_returns_cited_passages(context):
    result, is_error = call(
        context, "search_methodology", {"query": "relocation algorithm capacity"}
    )
    assert not is_error
    assert result["passages"]
    assert result["passages"][0]["source"]


def test_unknown_tool_is_an_error_not_an_exception(context):
    result, is_error = call(context, "teleport", {})
    assert is_error and result["error"] == "unknown_tool"


def test_non_object_input_is_an_error(context):
    payload, is_error = run_tool(context, "city_overview", ["nope"])
    assert is_error
    assert json.loads(payload)["error"] == "bad_request"


@pytest.mark.parametrize("name", ["city_overview", "list_known_places", "rank_areas"])
def test_tools_tolerate_empty_input(context, name):
    _, is_error = call(context, name, {})
    assert not is_error
