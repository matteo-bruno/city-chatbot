"""Queries over the prepared Milan store."""

from __future__ import annotations

import pytest

from citychat.citydata import THRESHOLD_MIN, CityStore, band_for


@pytest.fixture(scope="module")
def store(context) -> CityStore:
    return context.store


def test_store_metadata_matches_the_source_file(store: CityStore):
    assert store.name == "Milan"
    assert store.meta["cell_count"] == 7637
    assert store.modes == ["bicycle", "foot"]
    assert store.aggregate == "proximity_time"
    assert len(store.categories) == 9
    assert store.meta["population_total"] > 3_000_000


def test_aggregate_really_is_the_mean_of_the_categories(store: CityStore):
    # The prep script verifies this per cell; the share must be near-total or
    # the stored proximity time means something other than the paper's PT.
    for mode in store.modes:
        check = store.meta["aggregate_definition"][mode]
        assert check["share_matching_category_mean"] > 0.98


def test_mode_synonyms_resolve(store: CityStore):
    assert store.resolve_mode(None) == "foot"
    for name in ("walking", "on foot", "FOOT", "pedestrian"):
        assert store.resolve_mode(name) == "foot"
    for name in ("bike", "cycling", "bicycle"):
        assert store.resolve_mode(name) == "bicycle"
    with pytest.raises(ValueError):
        store.resolve_mode("helicopter")


def test_unknown_indicator_is_rejected(store: CityStore):
    with pytest.raises(ValueError):
        store.column("teleportation", "foot")


def test_city_overview_headline_numbers(store: CityStore):
    walking = store.overview("walking")["modes"]["walking"]
    assert 9.0 < walking["proximity_time_city_min"] < 10.5
    assert 80 < walking["F15_residents_within_15min_pct"] < 90
    # Milan is close to but short of the 90% criterion on foot.
    assert walking["is_15_minute_city"] is False
    assert 0.2 < walking["gini_of_accessibility"] < 0.35
    # Health care and culture are the slow categories, outdoor space the fast one.
    slowest = walking["categories_slowest_first"]
    assert slowest[0]["category"] in ("healthcare", "culture")
    assert slowest[-1]["category"] == "outdoor"


def test_cycling_is_faster_than_walking_everywhere(store: CityStore):
    modes = store.overview()["modes"]
    assert modes["cycling"]["proximity_time_city_min"] < modes["walking"]["proximity_time_city_min"]
    assert modes["cycling"]["F15_residents_within_15min_pct"] > 99


def test_population_weighting_beats_the_plain_cell_average(store: CityStore):
    walking = store.overview("walking")["modes"]["walking"]
    # Empty peripheral cells drag the unweighted mean far above what residents see.
    assert walking["unweighted_cell_mean_min"] > walking["proximity_time_city_min"] + 3


def test_area_stats_for_the_centre_beat_the_city(context, store: CityStore):
    resolved = context.resolve_area(place="Duomo")
    stats = store.area_stats(resolved.selection.indices, "foot")
    assert stats["cells"] > 5
    assert stats["proximity_time_min"] < 6
    assert stats["assessment"]["meets_15_minute_standard"] is True
    assert stats["city_comparison"]["difference_vs_city_min"] < 0
    assert len(stats["categories_slowest_first"]) == 9
    # Sorted slowest first.
    minutes = [c["minutes"] for c in stats["categories_slowest_first"]]
    assert minutes == sorted(minutes, reverse=True)


def test_area_stats_for_the_rural_fringe_fail_the_standard(context, store: CityStore):
    resolved = context.resolve_area(place="Figino")
    stats = store.area_stats(resolved.selection.indices, "foot")
    assert stats["proximity_time_min"] > THRESHOLD_MIN
    assert stats["assessment"]["meets_15_minute_standard"] is False


def test_area_stats_on_an_empty_selection_reports_an_error(store: CityStore):
    assert "error" in store.area_stats([], "foot")


def test_percentile_is_monotonic(store: CityStore):
    assert store.population_percentile_of(5, "foot") < store.population_percentile_of(15, "foot")


def test_ranking_orders_best_and_worst_consistently(context, store: CityStore):
    selections = list(context.named_selections())
    best = store.rank_selections(selections, "foot", limit=5, order="best")
    worst = store.rank_selections(selections, "foot", limit=5, order="worst")
    assert [r["minutes"] for r in best] == sorted(r["minutes"] for r in best)
    assert worst[0]["minutes"] > best[0]["minutes"]
    assert best[0]["meets_15_minute_standard"] is True


def test_ranking_by_a_single_category_differs_from_the_overall_score(context, store: CityStore):
    selections = list(context.named_selections())
    overall = store.rank_selections(selections, "foot", limit=3, order="worst")
    healthcare = store.rank_selections(
        selections, "foot", indicator="healthcare", limit=3, order="worst"
    )
    assert healthcare[0]["minutes"] != overall[0]["minutes"]


def test_band_labels():
    assert band_for(8) == "excellent"
    assert band_for(15) == "within the 15-minute standard"
    assert band_for(15.1) == "just outside the 15-minute standard"
    assert band_for(45) == "very poor"
