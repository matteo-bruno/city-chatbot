"""The system prompt: what the model always knows, and what must stay constant."""

from __future__ import annotations

from dataclasses import replace

from citychat.context import CityContext
from citychat.prompt import build_system_prompt, city_briefing


def test_prompt_contains_identity_rules_knowledge_and_briefing(context):
    prompt = build_system_prompt(context)
    for phrase in (
        "Milan",
        "# How to work",
        "# Scope",
        "# Reference knowledge",
        "# City briefing",
        "Numbers come from tools",
    ):
        assert phrase in prompt


def test_prompt_is_large_enough_to_cache_and_small_enough_to_send(context):
    # The cacheable prefix must clear the model's minimum (~1k tokens) while
    # staying a modest fixed cost per turn.
    approx_tokens = len(build_system_prompt(context)) / 4
    assert 1_500 < approx_tokens < 12_000


def test_prompt_is_deterministic(context):
    # Any per-call variation (a clock, a uuid) would break the cache prefix.
    assert build_system_prompt(context) == build_system_prompt(context)


def test_briefing_carries_the_headline_numbers_for_every_mode(context):
    briefing = city_briefing(context)
    assert "Walking" in briefing and "Cycling" in briefing
    walking = context.store.overview("walking")["modes"]["walking"]
    assert str(walking["proximity_time_city_min"]) in briefing
    assert str(walking["F15_residents_within_15min_pct"]) in briefing
    assert "does not meet the 90% criterion" in briefing  # Milan on foot
    assert "OpenStreetMap May 2023" in briefing


def test_briefing_declares_the_gazetteer_is_approximate(context):
    briefing = city_briefing(context)
    assert "No administrative boundaries are loaded" in briefing
    assert "Live geocoding is disabled" in briefing


def test_briefing_declares_capabilities_that_are_switched_on(context, settings):
    enabled = CityContext(replace(settings, web_search=True, geocoder="nominatim"))
    briefing = city_briefing(enabled)
    assert "Web search is available" in briefing
    assert "Live geocoding is enabled" in briefing
