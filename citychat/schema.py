"""Schema discovery for city indicator files.

The chatbot must not hardcode "Milan" or "these nine categories". Instead the
prep script reads whatever `<indicator>_<mode>` columns a GeoJSON happens to
carry, and writes the resulting schema into the city's meta.json. The runtime
then only ever reads meta.json, so a new city (or a new category, or a new
travel mode) needs no code change.
"""

from __future__ import annotations

from collections import Counter

# Human-readable labels for the categories and modes used by the
# 15-minute-city framework (Bruno et al., Nature Cities, 2024). Anything not
# listed here falls back to a prettified version of the column name.
DEFAULT_CATEGORY_LABELS: dict[str, str] = {
    "outdoor": "outdoor activities (parks, squares, playgrounds)",
    "education": "learning (schools, kindergartens, universities, libraries)",
    "supplies": "supplies (groceries, markets, everyday shops)",
    "restaurant": "eating (restaurants, bars, cafes)",
    "transport": "moving (public transport stops and stations)",
    "culture": "cultural activities (museums, cinemas, theatres, venues)",
    "physical": "physical exercise (gyms, sport facilities, pools)",
    "services": "services (post, bank, pharmacy, public offices)",
    "healthcare": "health care (doctors, clinics, hospitals, pharmacies)",
}

DEFAULT_MODE_LABELS: dict[str, str] = {
    "foot": "walking",
    "bicycle": "cycling",
    "walk": "walking",
    "bike": "cycling",
}

# Columns that describe the cell itself rather than an indicator.
DEFAULT_ID_FIELDS = ("h3", "h3_index", "cell", "cell_id", "id")
DEFAULT_POPULATION_FIELDS = ("population", "pop", "residents")


def pretty_label(name: str) -> str:
    return name.replace("_", " ").strip()


def detect_schema(
    property_names: list[str],
    aggregate_base: str = "proximity_time",
    min_mode_occurrences: int = 3,
) -> dict:
    """Split property names into id / population / `<base>_<mode>` indicators.

    A token is treated as a travel mode when it appears as the suffix of at
    least `min_mode_occurrences` different columns; that is what separates
    `foot` in `supplies_foot` from `time` in `proximity_time`.
    """
    suffix_counts: Counter[str] = Counter()
    for name in property_names:
        if "_" in name:
            suffix_counts[name.rsplit("_", 1)[1]] += 1

    modes = sorted(m for m, n in suffix_counts.items() if n >= min_mode_occurrences)

    id_field = next((f for f in DEFAULT_ID_FIELDS if f in property_names), None)
    population_field = next((f for f in DEFAULT_POPULATION_FIELDS if f in property_names), None)

    bases: list[str] = []
    indicator_columns: dict[str, dict[str, str]] = {}  # base -> mode -> column
    for name in property_names:
        if name in (id_field, population_field) or "_" not in name:
            continue
        base, mode = name.rsplit("_", 1)
        if mode not in modes or not base:
            continue
        if base not in indicator_columns:
            indicator_columns[base] = {}
            bases.append(base)
        indicator_columns[base][mode] = name

    # Keep only bases measured in every mode, so cross-mode comparisons are fair.
    complete = [b for b in bases if set(indicator_columns[b]) == set(modes)]
    aggregate = aggregate_base if aggregate_base in complete else None
    categories = [b for b in complete if b != aggregate]

    ignored = [
        n
        for n in property_names
        if n not in (id_field, population_field)
        and n not in {c for b in complete for c in indicator_columns[b].values()}
    ]

    return {
        "id_field": id_field,
        "population_field": population_field,
        "modes": modes,
        "aggregate": aggregate,
        "categories": categories,
        "columns": {b: indicator_columns[b] for b in complete},
        "ignored_properties": sorted(ignored),
    }


def label_maps(categories: list[str], modes: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    cats = {c: DEFAULT_CATEGORY_LABELS.get(c, pretty_label(c)) for c in categories}
    mds = {m: DEFAULT_MODE_LABELS.get(m, pretty_label(m)) for m in modes}
    return cats, mds
