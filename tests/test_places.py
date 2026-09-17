"""Name resolution: the gazetteer, boundaries and the coverage guards."""

from __future__ import annotations

import json

import pytest

from citychat.context import OutsideCoverage, PlaceNotFound
from citychat.places import Gazetteer, Place, normalise


def test_normalise_strips_accents_case_and_punctuation():
    assert normalise("Città Studi - Milano!") == "citta studi milano"
    assert normalise("  QT8  ") == "qt8"


def test_resolution_handles_aliases_typos_and_a_city_prefix():
    gazetteer = Gazetteer(city="Milan")
    gazetteer.add(Place(name="Rogoredo", lat=45.4295, lon=9.2410, aliases=["Milano Rogoredo"]))
    gazetteer.add(Place(name="Porta Romana", lat=45.4498, lon=9.2010))

    assert gazetteer.resolve("rogoredo").name == "Rogoredo"
    assert gazetteer.resolve("ROGOREDO").name == "Rogoredo"
    assert gazetteer.resolve("Milano Rogoredo").name == "Rogoredo"
    assert gazetteer.resolve("Milan Rogoredo").name == "Rogoredo"
    assert gazetteer.resolve("Porta Romna").name == "Porta Romana"  # typo
    assert gazetteer.resolve("Barcelona") is None


def test_suggestions_are_empty_when_nothing_is_close():
    gazetteer = Gazetteer(city="Milan")
    gazetteer.add(Place(name="Rogoredo", lat=45.4295, lon=9.2410))
    assert gazetteer.suggest("rogored") == ["Rogoredo"]
    assert gazetteer.suggest("zzzzzzzzzz") == []


def test_boundaries_take_precedence_over_seed_points(tmp_path):
    """A named polygon must win over an approximate centre of the same name."""
    boundary = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NIL": "Rogoredo"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[9.23, 45.42], [9.25, 45.42], [9.25, 45.44], [9.23, 45.44], [9.23, 45.42]]
                    ],
                },
            }
        ],
    }
    path = tmp_path / "milan.boundaries.geojson"
    path.write_text(json.dumps(boundary))

    gazetteer = Gazetteer(city="Milan")
    gazetteer.load_geojson(path)
    gazetteer.add(Place(name="Rogoredo", lat=45.4295, lon=9.2410, source="seed"))

    resolved = gazetteer.resolve("Rogoredo")
    assert resolved.has_boundary
    assert resolved.precision == "official boundary"
    assert resolved.describe()["geometry"] == "administrative boundary"


def test_seed_gazetteer_loads_and_covers_the_city(context):
    assert len(context.gazetteer) > 50
    # Every seed place must land on real data, or its coordinate is wrong.
    for place in context.gazetteer.places:
        selection = context.store.select_place(place)
        assert selection.indices, f"{place.name} matched no cells"


def test_seed_coordinates_rank_the_centre_above_the_fringe(context):
    """A coarse sanity check that the hand-compiled centres are in the right place."""

    def walking_minutes(name: str) -> float:
        resolved = context.resolve_area(place=name)
        return context.store.area_stats(resolved.selection.indices, "foot")["proximity_time_min"]

    assert walking_minutes("Duomo") < walking_minutes("Bicocca") < walking_minutes("Muggiano")


def test_a_close_typo_still_resolves(context):
    assert context.resolve_area(place="Rogorredoo").place.name == "Rogoredo"


def test_unresolvable_name_raises_with_suggestions(context):
    with pytest.raises(PlaceNotFound) as excinfo:
        context.resolve_area(place="Porta Verde")
    assert "Porta Venezia" in excinfo.value.suggestions


def test_unrelated_name_raises_without_misleading_suggestions(context):
    with pytest.raises(PlaceNotFound) as excinfo:
        context.resolve_area(place="Quartiere Zeta")
    assert excinfo.value.suggestions == []


def test_coordinates_outside_the_dataset_are_refused(context):
    with pytest.raises(OutsideCoverage):
        context.resolve_area(lat=41.9028, lon=12.4964)  # Rome


def test_coordinates_inside_the_dataset_resolve(context):
    resolved = context.resolve_area(lat=45.4642, lon=9.1900, radius_m=600)
    assert resolved.resolved_by == "coordinates"
    assert resolved.selection.indices


def test_radius_override_widens_the_selection(context):
    narrow = context.resolve_area(place="Rogoredo", radius_m=300)
    wide = context.resolve_area(place="Rogoredo", radius_m=1500)
    assert len(wide.selection.indices) > len(narrow.selection.indices)


def test_missing_arguments_are_rejected(context):
    with pytest.raises(ValueError):
        context.resolve_area()
