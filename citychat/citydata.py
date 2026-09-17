"""In-memory store over one prepared city, and the aggregations the bot needs.

`scripts/prepare_city.py` writes three files per city; this loads them once at
start-up (280 KB for Milan, so a fraction of a second) and answers area
queries from memory. No database, no geospatial dependency.

Everything is population-weighted, matching the paper: an area's proximity
time is what its *residents* experience, not the average of its map cells.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import geo, stats
from .places import DEFAULT_RADIUS_M, Place

# Verdict bands for a single area's proximity time, in minutes.
BANDS = (
    (10.0, "excellent"),
    (15.0, "within the 15-minute standard"),
    (20.0, "just outside the 15-minute standard"),
    (30.0, "poor"),
    (float("inf"), "very poor"),
)

# A city is conventionally called a 15-minute city when at least this share of
# its residents live within the threshold (the paper's criterion).
CITY_F15_TARGET_PCT = 90.0
THRESHOLD_MIN = 15.0


def band_for(minutes: float) -> str:
    return next(label for limit, label in BANDS if minutes <= limit)


@dataclass
class AreaSelection:
    """A set of cells standing in for a named area."""

    indices: list[int]
    method: str
    detail: dict


class CityStore:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        self.meta: dict = json.loads((self.dir / "meta.json").read_text(encoding="utf-8"))
        self.profile: dict = json.loads((self.dir / "profile.json").read_text(encoding="utf-8"))
        with gzip.open(self.dir / "cells.json.gz", "rt", encoding="utf-8") as fh:
            cells = json.load(fh)
        self.ids: list[str] = cells["ids"]
        self.lon: list[float] = cells["lon"]
        self.lat: list[float] = cells["lat"]
        self.population: list[float] = cells["population"]
        self.values: dict[str, list[float | None]] = cells["values"]
        self.index = geo.CellIndex(self.lon, self.lat)

        schema = self.meta["schema"]
        self.modes: list[str] = schema["modes"]
        self.categories: list[str] = schema["categories"]
        self.aggregate: str | None = schema["aggregate"]
        self.columns: dict[str, dict[str, str]] = schema["columns"]
        self.category_labels: dict[str, str] = self.meta.get("category_labels", {})
        self.mode_labels: dict[str, str] = self.meta.get("mode_labels", {})

    # ------------------------------------------------------------- properties

    @property
    def slug(self) -> str:
        return self.meta["slug"]

    @property
    def name(self) -> str:
        return self.meta["name"]

    @property
    def default_mode(self) -> str:
        return "foot" if "foot" in self.modes else self.modes[0]

    def mode_label(self, mode: str) -> str:
        return self.mode_labels.get(mode, mode)

    def resolve_mode(self, mode: str | None) -> str:
        """Accept 'walking'/'on foot'/'bike' as well as the raw column suffix."""
        if not mode:
            return self.default_mode
        key = mode.strip().lower()
        if key in self.modes:
            return key
        synonyms = {
            "walk": "foot",
            "walking": "foot",
            "on foot": "foot",
            "pedestrian": "foot",
            "bike": "bicycle",
            "biking": "bicycle",
            "cycling": "bicycle",
            "cycle": "bicycle",
        }
        mapped = synonyms.get(key)
        if mapped in self.modes:
            return mapped
        for candidate, label in self.mode_labels.items():
            if key == label.lower():
                return candidate
        raise ValueError(f"unknown travel mode {mode!r}; available: {', '.join(self.modes)}")

    def column(self, indicator: str, mode: str) -> str:
        by_mode = self.columns.get(indicator)
        if not by_mode or mode not in by_mode:
            available = ", ".join([self.aggregate or ""] + self.categories).strip(", ")
            raise ValueError(f"unknown indicator {indicator!r}; available: {available}")
        return by_mode[mode]

    # ------------------------------------------------------------- selections

    def select_radius(self, lat: float, lon: float, radius_m: float) -> AreaSelection:
        idx = self.index.within_radius(lon, lat, radius_m)
        detail = {"centre": [round(lat, 5), round(lon, 5)], "radius_m": round(radius_m)}
        if not idx:
            nearest = self.index.nearest(lon, lat)
            if nearest:
                i, distance = nearest
                detail["nearest_cell_distance_m"] = round(distance)
                if distance <= max(radius_m, 1500.0):
                    # Just outside the circle but clearly the right place.
                    return AreaSelection([i], "nearest cell", detail)
        return AreaSelection(idx, "cells within radius", detail)

    def select_place(self, place: Place) -> AreaSelection:
        if place.has_boundary:
            idx = self.index.within_polygons(place.polygons)
            if idx:
                return AreaSelection(idx, "cells inside the boundary", {"boundary": place.name})
            # A district smaller than one cell: fall back to its centroid.
        return self.select_radius(place.lat, place.lon, place.radius_m or DEFAULT_RADIUS_M)

    # ------------------------------------------------------------ aggregation

    def _series(self, indices: Sequence[int], column: str) -> tuple[list[float], list[float]]:
        values: list[float] = []
        weights: list[float] = []
        for i in indices:
            v = self.values[column][i]
            if v is None:
                continue
            values.append(v)
            weights.append(self.population[i])
        return values, weights

    def population_percentile_of(self, minutes: float, mode: str) -> float | None:
        """Share of the city's residents with a proximity time below `minutes`."""
        if not self.aggregate:
            return None
        column = self.column(self.aggregate, mode)
        share = stats.weighted_share_below(self.values[column], self.population, minutes)
        return round(share, 1) if share is not None else None

    def area_stats(self, indices: Sequence[int], mode: str) -> dict:
        """Population-weighted indicators for a set of cells."""
        indices = list(indices)
        population = sum(self.population[i] for i in indices)
        out: dict = {
            "travel_mode": self.mode_label(mode),
            "cells": len(indices),
            "population": round(population),
        }
        city_pop = self.meta.get("population_total") or 0
        if city_pop:
            out["share_of_city_population_pct"] = round(100 * population / city_pop, 2)
        if not indices:
            out["error"] = "no data cells fall in this area"
            return out

        if self.aggregate:
            column = self.column(self.aggregate, mode)
            values, weights = self._series(indices, column)
            out["cells_with_scores"] = len(values)
            if not values:
                out["error"] = (
                    "cells here carry no accessibility score: the source data drops cells "
                    "with no point of interest anywhere near them"
                )
                return out
            pt = stats.weighted_mean(values, weights)
            out["proximity_time_min"] = round(pt, 1)
            out["proximity_time_spread_min"] = [round(min(values), 1), round(max(values), 1)]
            out["assessment"] = {
                "threshold_min": THRESHOLD_MIN,
                "meets_15_minute_standard": pt <= THRESHOLD_MIN,
                "band": band_for(pt),
            }
            shares = {
                str(int(t)): round(stats.weighted_share_below(values, weights, t), 1)
                for t in (10, 15, 20, 30)
                if stats.weighted_share_below(values, weights, t) is not None
            }
            if shares:
                out["residents_within_minutes_pct"] = shares

            city_pt = (
                self.profile["modes"][mode]
                .get("proximity_time", {})
                .get("population_weighted_mean_min")
            )
            if city_pt is not None:
                out["city_comparison"] = {
                    "city_proximity_time_min": city_pt,
                    "difference_vs_city_min": round(pt - city_pt, 1),
                    "city_residents_with_shorter_proximity_time_pct": self.population_percentile_of(
                        pt, mode
                    ),
                }

        categories = []
        city_categories = self.profile["modes"][mode].get("categories", {})
        for cat in self.categories:
            values, weights = self._series(indices, self.column(cat, mode))
            if not values:
                continue
            value = stats.weighted_mean(values, weights)
            entry = {
                "category": cat,
                "label": self.category_labels.get(cat, cat),
                "minutes": round(value, 1),
            }
            city_value = city_categories.get(cat, {}).get("population_weighted_mean_min")
            if city_value is not None:
                entry["city_minutes"] = city_value
                entry["difference_vs_city_min"] = round(value - city_value, 1)
            categories.append(entry)
        categories.sort(key=lambda e: -e["minutes"])
        out["categories_slowest_first"] = categories
        return out

    # -------------------------------------------------------------- overviews

    def overview(self, mode: str | None = None) -> dict:
        modes = [self.resolve_mode(mode)] if mode else self.modes
        out: dict = {
            "city": self.name,
            "country": self.meta.get("country"),
            "population_total": self.meta.get("population_total"),
            "cells": self.meta.get("cell_count"),
            "cells_with_scores": self.meta.get("cells_with_scores"),
            "covered_area_km2": self.meta.get("covered_area_km2"),
            "mean_cell_area_km2": self.meta.get("mean_cell_area_km2"),
            "data_source": self.meta.get("data_source"),
            "data_vintage": self.meta.get("data_vintage"),
            "prepared_on": self.meta.get("prepared_on"),
            "category_labels": self.category_labels,
            "city_15_minute_criterion": (
                f"at least {CITY_F15_TARGET_PCT:.0f}% of residents within {THRESHOLD_MIN:.0f} minutes"
            ),
            "modes": {},
        }
        for m in modes:
            entry = self.profile["modes"][m]
            pt = entry.get("proximity_time", {})
            f15 = (pt.get("population_share_within") or {}).get("15")
            out["modes"][self.mode_label(m)] = {
                "proximity_time_city_min": pt.get("population_weighted_mean_min"),
                "unweighted_cell_mean_min": pt.get("unweighted_mean_min"),
                "range_min": [pt.get("min_min"), pt.get("max_min")],
                "F15_residents_within_15min_pct": f15,
                "residents_within_minutes_pct": pt.get("population_share_within"),
                "gini_of_accessibility": pt.get("gini"),
                "percentiles_min": pt.get("population_weighted_percentiles_min"),
                "is_15_minute_city": (None if f15 is None else f15 >= CITY_F15_TARGET_PCT),
                "categories_slowest_first": sorted(
                    (
                        {
                            "category": cat,
                            "label": self.category_labels.get(cat, cat),
                            "minutes": data.get("population_weighted_mean_min"),
                            "residents_within_15min_pct": (
                                data.get("population_share_within") or {}
                            ).get("15"),
                        }
                        for cat, data in entry.get("categories", {}).items()
                    ),
                    key=lambda e: -(e["minutes"] or 0),
                ),
                "least_accessible_cells": entry.get("least_accessible_cells"),
                "most_accessible_cells": entry.get("most_accessible_cells"),
            }
        return out

    def rank_selections(
        self,
        selections: Iterable[tuple[str, AreaSelection]],
        mode: str,
        indicator: str | None = None,
        limit: int = 10,
        order: str = "best",
    ) -> list[dict]:
        """Rank named areas by an indicator, skipping areas with no data."""
        indicator = indicator or self.aggregate
        column = self.column(indicator, mode)
        rows: list[dict] = []
        for name, selection in selections:
            values, weights = self._series(selection.indices, column)
            if not values:
                continue
            value = stats.weighted_mean(values, weights)
            rows.append(
                {
                    "area": name,
                    "minutes": round(value, 1),
                    "population": round(sum(self.population[i] for i in selection.indices)),
                    "cells": len(selection.indices),
                    "meets_15_minute_standard": value <= THRESHOLD_MIN,
                }
            )
        rows.sort(key=lambda r: r["minutes"], reverse=(order == "worst"))
        return rows[:limit]


def discover_cities(root: Path) -> dict[str, Path]:
    root = Path(root)
    if not root.exists():
        return {}
    return {
        path.name: path
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "meta.json").exists()
    }
