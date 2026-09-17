"""Geometry helpers: distances, centroids, point-in-polygon, the cell index."""

from __future__ import annotations

import math

from citychat.geo import (
    CellIndex,
    bbox_of,
    haversine_m,
    point_in_polygon,
    ring_centroid,
)

# A ~1 km square around Milan's Duomo.
SQUARE = [[(9.19, 45.46), (9.203, 45.46), (9.203, 45.47), (9.19, 45.47), (9.19, 45.46)]]


def test_haversine_against_a_known_distance():
    # Duomo to Milano Centrale is about 2 km.
    metres = haversine_m(9.1900, 45.4642, 9.2049, 45.4863)
    assert 2_400 < metres < 2_800


def test_haversine_is_zero_for_identical_points():
    assert haversine_m(9.19, 45.46, 9.19, 45.46) == 0.0


def test_ring_centroid_of_a_square_is_its_middle():
    lon, lat = ring_centroid(SQUARE[0])
    assert math.isclose(lon, 9.1965, abs_tol=1e-4)
    assert math.isclose(lat, 45.465, abs_tol=1e-4)


def test_point_in_polygon_inside_and_outside():
    assert point_in_polygon(9.1965, 45.465, SQUARE)
    assert not point_in_polygon(9.30, 45.465, SQUARE)


def test_point_in_polygon_honours_holes():
    outer = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
    hole = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6), (0.4, 0.4)]
    assert point_in_polygon(0.1, 0.1, [outer, hole])
    assert not point_in_polygon(0.5, 0.5, [outer, hole])


def test_bbox_of_points():
    assert bbox_of([(1.0, 2.0), (-1.0, 5.0)]) == (-1.0, 2.0, 1.0, 5.0)


def _grid_index(step: float = 0.002, n: int = 12) -> CellIndex:
    lons = [9.19 + step * (i % n) for i in range(n * n)]
    lats = [45.46 + step * (i // n) for i in range(n * n)]
    return CellIndex(lons, lats)


def test_cell_index_radius_query_matches_brute_force():
    index = _grid_index()
    lon, lat, radius = 9.20, 45.47, 700.0
    found = set(index.within_radius(lon, lat, radius))
    expected = {
        i
        for i in range(len(index.lons))
        if haversine_m(lon, lat, index.lons[i], index.lats[i]) <= radius
    }
    assert found == expected and found


def test_cell_index_radius_query_can_be_empty():
    assert _grid_index().within_radius(12.5, 41.9, 500.0) == []  # Rome


def test_cell_index_nearest_grows_the_search_radius():
    index = _grid_index()
    hit = index.nearest(9.1895, 45.4595)
    assert hit is not None
    _, distance = hit
    assert distance < 200


def test_cell_index_nearest_gives_up_outside_the_city():
    assert _grid_index().nearest(12.5, 41.9, max_radius_m=5_000) is None


def test_cell_index_polygon_query():
    index = _grid_index()
    inside = index.within_polygons([SQUARE])
    assert inside
    for i in inside:
        assert point_in_polygon(index.lons[i], index.lats[i], SQUARE)
