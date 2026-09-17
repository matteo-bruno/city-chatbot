#!/usr/bin/env python3
"""Turn a city indicator GeoJSON into the compact store the chatbot serves.

    python scripts/prepare_city.py data/raw/milan.geojson.gz --slug milan --name "Milan"

Reads a FeatureCollection whose features are small polygons (H3 cells) with
`population` and `<indicator>_<mode>` properties, and writes:

    data/cities/<slug>/meta.json      schema, coverage, provenance
    data/cities/<slug>/profile.json   precomputed city-level indicators
    data/cities/<slug>/cells.json.gz  columnar per-cell values

Only centroids are kept, not the polygon rings: every question the chatbot
answers is an aggregate over an area, and dropping the geometry makes the
store ~10x smaller and instant to load.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from citychat import geo, stats  # noqa: E402
from citychat.schema import detect_schema, label_maps  # noqa: E402

THRESHOLDS = (5, 10, 15, 20, 30, 45)
DECILES = tuple(round(0.1 * i, 1) for i in range(1, 10))


def open_maybe_gzip(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def ring_area_m2(ring: list[tuple[float, float]]) -> float:
    """Shoelace area of a small ring, in square metres (equirectangular)."""
    if len(ring) < 3:
        return 0.0
    lat0 = sum(p[1] for p in ring) / len(ring)
    k = math.cos(math.radians(lat0))
    pts = [(lon * k * 111_320.0, lat * 110_574.0) for lon, lat in ring]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    area2 = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        area2 += x0 * y1 - x1 * y0
    return abs(area2) / 2.0


def build_columns(features: list[dict], schema: dict) -> dict:
    """Columnar per-cell arrays: ids, centroids, population, one list per indicator."""
    id_field = schema["id_field"]
    pop_field = schema["population_field"]
    columns = schema["columns"]

    ids: list[str] = []
    lons: list[float] = []
    lats: list[float] = []
    population: list[float] = []
    areas: list[float] = []
    values: dict[str, list[float | None]] = {
        col: [] for modes in columns.values() for col in modes.values()
    }

    for i, feat in enumerate(features):
        props = feat.get("properties") or {}
        geometry = feat.get("geometry")
        if not geometry:
            continue
        polygons = geo.as_multipolygon(geometry)
        lon, lat = geo.ring_centroid(polygons[0][0])
        ids.append(str(props.get(id_field) if id_field else feat.get("id", i)))
        lons.append(round(lon, 6))
        lats.append(round(lat, 6))
        pop = props.get(pop_field) if pop_field else None
        population.append(float(pop) if isinstance(pop, (int, float)) else 0.0)
        areas.append(sum(ring_area_m2(poly[0]) for poly in polygons))
        for col in values:
            raw = props.get(col)
            values[col].append(float(raw) if isinstance(raw, (int, float)) else None)

    return {
        "ids": ids,
        "lon": lons,
        "lat": lats,
        "population": population,
        "values": values,
        "_areas": areas,
    }


def aggregate_consistency(
    cells: dict, schema: dict, mode: str, tolerance: float = 0.06
) -> dict | None:
    """Check that the aggregate column really is the mean of the category columns.

    Reported in meta.json so the chatbot can state how the score is built for
    *this* dataset rather than quoting the paper and hoping.
    """
    if not schema["aggregate"]:
        return None
    agg_col = schema["columns"][schema["aggregate"]][mode]
    cat_cols = [schema["columns"][c][mode] for c in schema["categories"]]
    if not cat_cols:
        return None
    checked = 0
    matching = 0
    worst = 0.0
    for i in range(len(cells["ids"])):
        cat_values = [cells["values"][c][i] for c in cat_cols]
        agg = cells["values"][agg_col][i]
        if agg is None or any(v is None for v in cat_values):
            continue
        checked += 1
        diff = abs(sum(cat_values) / len(cat_values) - agg)
        worst = max(worst, diff)
        if diff <= tolerance:
            matching += 1
    if not checked:
        return None
    return {
        "cells_checked": checked,
        "share_matching_category_mean": round(matching / checked, 4),
        "max_abs_difference_min": round(worst, 3),
        "tolerance_min": tolerance,
    }


def indicator_summary(values: list[float | None], population: list[float]) -> dict:
    covered = [(v, p) for v, p in zip(values, population) if v is not None]
    vals = [v for v, _ in covered]
    pops = [p for _, p in covered]
    if not vals:
        return {"covered_cells": 0}
    summary = {
        "covered_cells": len(vals),
        "population_weighted_mean_min": round(stats.weighted_mean(vals, pops), 2),
        "unweighted_mean_min": round(sum(vals) / len(vals), 2),
        "min_min": round(min(vals), 2),
        "max_min": round(max(vals), 2),
        "population_share_within": {
            str(t): round(stats.weighted_share_below(vals, pops, t), 2) for t in THRESHOLDS
        },
    }
    gini = stats.weighted_gini(vals, pops)
    if gini is not None:
        summary["gini"] = round(gini, 4)
    summary["population_weighted_percentiles_min"] = {
        str(int(q * 100)): round(stats.weighted_quantile(vals, pops, q), 2) for q in DECILES
    }
    return summary


def extreme_cells(cells: dict, column: str, n: int, worst: bool) -> list[dict]:
    rows = [
        (cells["values"][column][i], i)
        for i in range(len(cells["ids"]))
        if cells["values"][column][i] is not None and cells["population"][i] > 0
    ]
    rows.sort(reverse=worst)
    out = []
    for value, i in rows[:n]:
        out.append(
            {
                "cell_id": cells["ids"][i],
                "lat": cells["lat"][i],
                "lon": cells["lon"][i],
                "population": round(cells["population"][i], 1),
                "value_min": round(value, 2),
            }
        )
    return out


def build_profile(cells: dict, schema: dict) -> dict:
    population = cells["population"]
    profile: dict = {"modes": {}}
    for mode in schema["modes"]:
        agg_col = schema["columns"][schema["aggregate"]][mode] if schema["aggregate"] else None
        entry: dict = {"categories": {}}
        if agg_col:
            entry["proximity_time"] = indicator_summary(cells["values"][agg_col], population)
            entry["least_accessible_cells"] = extreme_cells(cells, agg_col, 5, worst=True)
            entry["most_accessible_cells"] = extreme_cells(cells, agg_col, 5, worst=False)
        for cat in schema["categories"]:
            col = schema["columns"][cat][mode]
            entry["categories"][cat] = indicator_summary(cells["values"][col], population)
        profile["modes"][mode] = entry
    return profile


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("source", type=Path, help="input .geojson or .geojson.gz")
    ap.add_argument("--slug", help="city slug (default: derived from the filename)")
    ap.add_argument("--name", help="display name (default: slug, title-cased)")
    ap.add_argument("--country", default=None)
    ap.add_argument("--out", type=Path, default=Path("data/cities"))
    ap.add_argument("--aggregate-field", default="proximity_time")
    ap.add_argument(
        "--data-source",
        default="Accessibility scores computed with the framework of Bruno et al., "
        "Nature Cities (2024); OpenStreetMap POIs, WorldPop population, OSRM routing.",
    )
    ap.add_argument("--data-vintage", default=None, help="e.g. 'OSM May 2023, WorldPop 2020'")
    args = ap.parse_args()

    slug = args.slug or slugify(args.source.name.split(".")[0])
    name = args.name or slug.replace("-", " ").title()

    print(f"reading {args.source} ...", flush=True)
    with open_maybe_gzip(args.source) as fh:
        payload = json.load(fh)
    features = payload.get("features") if isinstance(payload, dict) else None
    if not features:
        print("error: no features found (expected a GeoJSON FeatureCollection)", file=sys.stderr)
        return 1

    schema = detect_schema(list(features[0].get("properties") or {}), args.aggregate_field)
    if not schema["modes"]:
        print("error: no `<indicator>_<mode>` columns detected", file=sys.stderr)
        return 1
    print(
        f"  {len(features)} cells; modes={schema['modes']}; "
        f"aggregate={schema['aggregate']}; {len(schema['categories'])} categories",
        flush=True,
    )

    cells = build_columns(features, schema)
    areas = cells.pop("_areas")
    n = len(cells["ids"])
    total_pop = sum(cells["population"])
    bbox = geo.bbox_of(zip(cells["lon"], cells["lat"]))
    mean_area_km2 = (sum(areas) / len(areas)) / 1e6 if areas else None

    category_labels, mode_labels = label_maps(schema["categories"], schema["modes"])
    consistency = {m: aggregate_consistency(cells, schema, m) for m in schema["modes"]}

    agg_cols = (
        {m: schema["columns"][schema["aggregate"]][m] for m in schema["modes"]}
        if schema["aggregate"]
        else {}
    )
    covered = {m: sum(1 for v in cells["values"][c] if v is not None) for m, c in agg_cols.items()}

    meta = {
        "slug": slug,
        "name": name,
        "country": args.country,
        "prepared_on": date.today().isoformat(),
        "source_file": args.source.name,
        "data_source": args.data_source,
        "data_vintage": args.data_vintage,
        "cell_count": n,
        "cells_with_scores": covered,
        "population_total": round(total_pop, 1),
        "mean_cell_area_km2": round(mean_area_km2, 5) if mean_area_km2 else None,
        "covered_area_km2": round(sum(areas) / 1e6, 2),
        "bbox": [round(v, 6) for v in bbox],
        "schema": schema,
        "category_labels": category_labels,
        "mode_labels": mode_labels,
        "aggregate_definition": consistency,
        "thresholds_min": list(THRESHOLDS),
    }

    profile = build_profile(cells, schema)

    out_dir = args.out / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    (out_dir / "profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")
    with gzip.open(out_dir / "cells.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(cells, fh, separators=(",", ":"), sort_keys=True)

    print(f"wrote {out_dir}/meta.json, profile.json, cells.json.gz")
    for mode in schema["modes"]:
        pt = profile["modes"][mode].get("proximity_time", {})
        if pt:
            print(
                f"  {mode:8s} PT_city={pt['population_weighted_mean_min']:5.2f} min  "
                f"F15={pt['population_share_within']['15']:5.1f}%  gini={pt.get('gini')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
