"""Everything the assistant knows, assembled once at start-up.

One `CityContext` binds together the prepared city store, the place gazetteer,
the optional geocoder and the knowledge base. The agent and the tools talk
only to this object, so swapping the city or the geocoder does not touch them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: F401  (re-exported for callers building Settings)

from .citydata import AreaSelection, CityStore, discover_cities
from .config import Settings
from .knowledge import KnowledgeBase
from .places import DEFAULT_RADIUS_M, Gazetteer, NominatimGeocoder, Place

# Beyond this distance from the nearest scored cell, a resolved place is
# outside the dataset rather than merely in a thinly covered corner of it.
OUT_OF_COVERAGE_M = 5_000.0


class PlaceNotFound(Exception):
    def __init__(self, query: str, suggestions: list[str]) -> None:
        super().__init__(f"could not resolve {query!r}")
        self.query = query
        self.suggestions = suggestions


class OutsideCoverage(Exception):
    def __init__(self, place: Place, distance_m: float, city: str) -> None:
        super().__init__(f"{place.name} is outside the {city} dataset")
        self.place = place
        self.distance_m = distance_m
        self.city = city


@dataclass
class ResolvedArea:
    place: Place
    selection: AreaSelection
    resolved_by: str


class CityContext:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = self._load_store(settings)
        self.knowledge = KnowledgeBase(settings.knowledge_dir)
        self.gazetteer = self._load_gazetteer(settings, self.store)
        self.geocoder = self._load_geocoder(settings, self.store)

    # ---------------------------------------------------------------- loading

    @staticmethod
    def _load_store(settings: Settings) -> CityStore:
        available = discover_cities(settings.cities_dir)
        if not available:
            raise RuntimeError(
                f"no prepared city found in {settings.cities_dir}. Run: "
                "python scripts/prepare_city.py <file.geojson.gz> --slug <slug>"
            )
        slug = settings.city or next(iter(available))
        if slug not in available:
            raise RuntimeError(
                f"city {slug!r} not prepared; available: {', '.join(sorted(available))}"
            )
        return CityStore(available[slug])

    @staticmethod
    def _load_gazetteer(settings: Settings, store: CityStore) -> Gazetteer:
        gazetteer = Gazetteer(city=store.name)
        # Official boundaries first: `Gazetteer.add` keeps the first source for
        # a given name, so seed points only fill the gaps they leave.
        for path in sorted(settings.places_dir.glob(f"{store.slug}*.geojson")):
            gazetteer.load_geojson(path)
        for path in sorted(settings.places_dir.glob(f"{store.slug}*.json")):
            if path.suffix == ".json" and not path.name.endswith(".geojson"):
                gazetteer.load_json(path)
        return gazetteer

    @staticmethod
    def _load_geocoder(settings: Settings, store: CityStore) -> NominatimGeocoder | None:
        if settings.geocoder != "nominatim":
            return None
        return NominatimGeocoder(
            base_url=settings.nominatim_url,
            user_agent=settings.geocoder_user_agent,
            email=settings.geocoder_email or None,
            cache_path=settings.cache_dir / f"geocode-{store.slug}.json",
            viewbox=store.meta.get("bbox"),
        )

    # ------------------------------------------------------------- resolution

    def resolve_area(
        self,
        place: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        radius_m: float | None = None,
    ) -> ResolvedArea:
        """Name (or coordinate pair) to a set of city cells."""
        if lat is not None and lon is not None:
            target = Place(
                name=place or f"{lat:.5f}, {lon:.5f}",
                lat=float(lat),
                lon=float(lon),
                radius_m=radius_m or DEFAULT_RADIUS_M,
                kind="coordinates",
                source="caller",
                precision="exact coordinates",
            )
            resolved_by = "coordinates"
        elif place:
            target = self.gazetteer.resolve(place)
            resolved_by = "gazetteer"
            if target is None and self.geocoder is not None:
                target = self.geocoder.geocode(place, city_hint=self.store.name)
                resolved_by = "geocoder"
            if target is None:
                raise PlaceNotFound(place, self.gazetteer.suggest(place))
            if radius_m:  # caller override, e.g. "the wider Rogoredo area"
                target = Place(**{**target.__dict__, "radius_m": float(radius_m), "polygons": None})
        else:
            raise ValueError("give either `place` or both `lat` and `lon`")

        selection = self.store.select_place(target)
        if not selection.indices:
            distance = selection.detail.get("nearest_cell_distance_m")
            if distance is None or distance > OUT_OF_COVERAGE_M:
                raise OutsideCoverage(target, distance or float("inf"), self.store.name)
        return ResolvedArea(target, selection, resolved_by)

    def named_selections(self, kind: str | None = None):
        for entry in self.gazetteer.places:
            if kind and entry.kind != kind:
                continue
            yield entry.name, self.store.select_place(entry)

    # ------------------------------------------------------------ description

    def data_summary(self) -> dict:
        """Short machine-readable description of what this deployment serves."""
        meta = self.store.meta
        return {
            "city": self.store.name,
            "country": meta.get("country"),
            "population_total": meta.get("population_total"),
            "cells": meta.get("cell_count"),
            "travel_modes": [self.store.mode_label(m) for m in self.store.modes],
            "categories": list(self.store.categories),
            "named_places": len(self.gazetteer),
            "place_sources": self.gazetteer.sources,
            "provider": self.settings.provider,
            "geocoder": self.settings.geocoder,
            "web_search": self.settings.web_search,
            "knowledge_documents": self.knowledge.documents(),
            "data_vintage": meta.get("data_vintage"),
            "prepared_on": meta.get("prepared_on"),
        }
