"""Population-weighted statistics: the numbers every answer rests on."""

from __future__ import annotations

import math

from citychat.stats import (
    weighted_gini,
    weighted_mean,
    weighted_quantile,
    weighted_share_below,
)


def test_weighted_mean_uses_population_not_cell_count():
    # One crowded fast cell and one empty slow cell: residents see 5 minutes.
    assert weighted_mean([5.0, 30.0], [1000.0, 1.0]) < 5.1


def test_weighted_mean_falls_back_to_plain_mean_when_unpopulated():
    assert weighted_mean([4.0, 6.0], [0.0, 0.0]) == 5.0


def test_weighted_mean_skips_missing_values():
    assert weighted_mean([None, 10.0], [5.0, 5.0]) == 10.0


def test_weighted_mean_of_nothing_is_none():
    assert weighted_mean([], []) is None
    assert weighted_mean([None], [1.0]) is None


def test_share_below_is_a_percentage_of_population():
    # 3 of 4 residents are within 15 minutes.
    assert weighted_share_below([10.0, 20.0], [3.0, 1.0], 15.0) == 75.0


def test_share_below_is_inclusive_of_the_threshold():
    assert weighted_share_below([15.0], [1.0], 15.0) == 100.0


def test_gini_is_zero_under_perfect_equality():
    assert weighted_gini([12.0] * 5, [10.0] * 5) == 0.0


def test_gini_approaches_its_maximum_under_total_concentration():
    # With n equal groups the maximum attainable Gini is 1 - 1/n.
    assert math.isclose(weighted_gini([0, 0, 0, 0, 100], [1] * 5), 0.8, abs_tol=1e-9)


def test_gini_grows_with_spread():
    weights = [1.0] * 4
    tight = weighted_gini([9.0, 10.0, 11.0, 12.0], weights)
    wide = weighted_gini([2.0, 10.0, 18.0, 30.0], weights)
    assert wide > tight > 0


def test_weighted_quantile_respects_weights():
    # 99% of the population sits at 30 minutes, so the median is 30.
    assert weighted_quantile([5.0, 30.0], [1.0, 99.0], 0.5) == 30.0
