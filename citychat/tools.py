"""The tools the model can call, and their implementations.

Design notes:

* The city data is *not* in the prompt. It is 7,637 cells; putting it there
  would be expensive and would still leave the model doing arithmetic. Instead
  the tools return already-aggregated, population-weighted answers, so the
  model's job is interpretation and wording.
* Tool results are JSON with units in the key names (`proximity_time_min`),
  which stops the model from inventing units or mixing modes up.
* Tool order is fixed and the definitions carry no volatile text, so they sit
  in front of the prompt-cache breakpoint.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .citydata import THRESHOLD_MIN
from .context import CityContext, OutsideCoverage, PlaceNotFound

MAX_COMPARE_AREAS = 6


def tool_definitions(context: CityContext) -> list[dict]:
    """Client tool schemas, specialised with this city's vocabulary."""
    store = context.store
    modes = [store.mode_label(m) for m in store.modes]
    indicators = ([store.aggregate] if store.aggregate else []) + list(store.categories)
    mode_property = {
        "type": "string",
        "description": f"Travel mode. One of: {', '.join(modes)}. Defaults to {store.mode_label(store.default_mode)}.",
    }

    definitions: list[dict] = [
        {
            "name": "city_overview",
            "description": (
                f"City-wide accessibility indicators for {store.name}: the population-weighted "
                "proximity time, the share of residents within 10/15/20/30 minutes (F15), the "
                "Gini index of accessibility, per-category city scores, decile distribution and "
                "the most and least accessible cells. Use this for any question about the city "
                "as a whole, including whether it qualifies as a 15-minute city."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "travel_mode": {
                        **mode_property,
                        "description": mode_property["description"] + " Omit to get every mode.",
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "area_accessibility",
            "description": (
                "Accessibility of one neighbourhood, district or point inside "
                f"{store.name}. Give either `place` (a name, resolved against the gazetteer) or "
                "`lat` and `lon`. Returns the area's population-weighted proximity time, whether "
                f"it meets the {THRESHOLD_MIN:.0f}-minute standard, the share of its residents "
                "within each threshold, a comparison against the city, and a per-category "
                "breakdown sorted slowest first. Use this for 'is X a 15-minute neighbourhood', "
                "'how long to reach shops in X', and anything about one specific area."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "place": {
                        "type": "string",
                        "description": "Neighbourhood, district or landmark name, e.g. 'Rogoredo'.",
                    },
                    "lat": {"type": "number", "description": "Latitude, WGS84."},
                    "lon": {"type": "number", "description": "Longitude, WGS84."},
                    "radius_m": {
                        "type": "number",
                        "description": (
                            "Radius in metres around the centre. Only needed to widen or narrow "
                            "the default area; ignored when an official boundary is available."
                        ),
                    },
                    "travel_mode": mode_property,
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "compare_areas",
            "description": (
                f"Compare up to {MAX_COMPARE_AREAS} named areas of {store.name} side by side: "
                "proximity time, whether each meets the 15-minute standard, population, and the "
                "slowest service category for each. Use this instead of several "
                "`area_accessibility` calls when the question is comparative."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "places": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"2 to {MAX_COMPARE_AREAS} place names.",
                    },
                    "travel_mode": mode_property,
                },
                "required": ["places"],
                "additionalProperties": False,
            },
        },
        {
            "name": "rank_areas",
            "description": (
                "Rank the gazetteer's named areas by an accessibility indicator. Use for "
                "'which neighbourhoods are the best/worst served', 'where is healthcare "
                "furthest away', and similar questions. Only covers named areas, not every cell."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "order": {
                        "type": "string",
                        "enum": ["best", "worst"],
                        "description": "'best' = shortest times first, 'worst' = longest first.",
                    },
                    "indicator": {
                        "type": "string",
                        "description": (
                            "Which indicator to rank by. One of: " + ", ".join(indicators) + ". "
                            f"Defaults to {store.aggregate} (the overall score)."
                        ),
                    },
                    "limit": {"type": "integer", "description": "How many areas to return (1-25)."},
                    "kind": {
                        "type": "string",
                        "description": "Restrict to one place kind, e.g. 'neighbourhood' or 'municipality'.",
                    },
                    "travel_mode": mode_property,
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "list_known_places",
            "description": (
                "List the place names this deployment can resolve, optionally filtered by a "
                "search string or kind. Use it when a name could not be resolved, or when the "
                "user asks what they can ask about."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional substring filter."},
                    "kind": {"type": "string", "description": "Optional kind filter."},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum names to return (default 60).",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "search_methodology",
            "description": (
                "Full-text search over the reference library (the source paper and any other "
                "ingested documents). Use it when a question needs the literature's own wording "
                "or a detail beyond the methodology summary already in your instructions: "
                "algorithm specifics, published per-city figures, limitations, related work."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords to search for."},
                    "limit": {
                        "type": "integer",
                        "description": "Passages to return (default 4, max 8).",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    ]

    if context.settings.web_search:
        web_tool: dict[str, Any] = {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": context.settings.web_search_max_uses,
        }
        if context.settings.web_search_allowed_domains:
            web_tool["allowed_domains"] = context.settings.web_search_allowed_domains
        definitions.append(web_tool)

    return definitions


# --------------------------------------------------------------------- helpers


def _clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _place_miss(exc: PlaceNotFound, context: CityContext) -> dict:
    payload: dict = {
        "error": "place_not_found",
        "query": exc.query,
        "message": (
            f"{exc.query!r} is not in the gazetteer for {context.store.name}. Tell the user the "
            "name could not be located and offer the suggestions, or ask for coordinates. Do not "
            "guess a location."
        ),
    }
    if exc.suggestions:
        payload["did_you_mean"] = exc.suggestions
    if context.geocoder is None:
        payload["note"] = "live geocoding is disabled in this deployment"
    return payload


def _outside_coverage(exc: OutsideCoverage) -> dict:
    return {
        "error": "outside_coverage",
        "place": exc.place.describe(),
        "message": (
            f"{exc.place.name} resolved successfully but lies outside the {exc.city} dataset"
            + (
                f" (nearest scored cell is {exc.distance_m / 1000:.1f} km away)."
                if exc.distance_m != float("inf")
                else "."
            )
            + " Say so; this deployment only holds data for "
            + exc.city
            + "."
        ),
    }


# ----------------------------------------------------------------- dispatchers


def _tool_city_overview(context: CityContext, args: dict) -> dict:
    return context.store.overview(args.get("travel_mode"))


def _tool_area_accessibility(context: CityContext, args: dict) -> dict:
    mode = context.store.resolve_mode(args.get("travel_mode"))
    try:
        resolved = context.resolve_area(
            place=args.get("place"),
            lat=args.get("lat"),
            lon=args.get("lon"),
            radius_m=args.get("radius_m"),
        )
    except PlaceNotFound as exc:
        return _place_miss(exc, context)
    except OutsideCoverage as exc:
        return _outside_coverage(exc)

    payload = {
        "area": resolved.place.describe(),
        "resolved_by": resolved.resolved_by,
        "selection": {"method": resolved.selection.method, **resolved.selection.detail},
        "city": context.store.name,
        **context.store.area_stats(resolved.selection.indices, mode),
    }
    if not resolved.place.has_boundary and resolved.place.precision == "approximate":
        payload["caveat"] = (
            "This area is a circle around an approximate centre, not an administrative "
            "boundary, so the figures describe the immediate surroundings of that point."
        )
    return payload


def _tool_compare_areas(context: CityContext, args: dict) -> dict:
    mode = context.store.resolve_mode(args.get("travel_mode"))
    names = [n for n in (args.get("places") or []) if str(n).strip()][:MAX_COMPARE_AREAS]
    if len(names) < 2:
        return {"error": "bad_request", "message": "give at least two place names"}

    rows: list[dict] = []
    misses: list[dict] = []
    for name in names:
        try:
            resolved = context.resolve_area(place=name)
        except PlaceNotFound as exc:
            misses.append(_place_miss(exc, context))
            continue
        except OutsideCoverage as exc:
            misses.append(_outside_coverage(exc))
            continue
        stats = context.store.area_stats(resolved.selection.indices, mode)
        slowest = (stats.get("categories_slowest_first") or [{}])[0]
        rows.append(
            {
                "area": resolved.place.name,
                "proximity_time_min": stats.get("proximity_time_min"),
                "meets_15_minute_standard": (stats.get("assessment") or {}).get(
                    "meets_15_minute_standard"
                ),
                "population": stats.get("population"),
                "slowest_category": slowest.get("label"),
                "slowest_category_min": slowest.get("minutes"),
                "geometry": resolved.place.describe()["geometry"],
            }
        )
    rows.sort(key=lambda r: (r["proximity_time_min"] is None, r["proximity_time_min"]))

    city_pt = (
        context.store.profile["modes"][mode]
        .get("proximity_time", {})
        .get("population_weighted_mean_min")
    )
    out: dict = {
        "city": context.store.name,
        "travel_mode": context.store.mode_label(mode),
        "city_proximity_time_min": city_pt,
        "areas_best_first": rows,
    }
    if misses:
        out["unresolved"] = misses
    return out


def _tool_rank_areas(context: CityContext, args: dict) -> dict:
    store = context.store
    mode = store.resolve_mode(args.get("travel_mode"))
    order = "worst" if str(args.get("order", "best")).lower() == "worst" else "best"
    limit = _clamp(args.get("limit"), 1, 25, 10)
    kind = args.get("kind") or None
    indicator = args.get("indicator") or store.aggregate
    try:
        store.column(indicator, mode)
    except ValueError as exc:
        return {"error": "bad_request", "message": str(exc)}

    selections = list(context.named_selections(kind))
    rows = store.rank_selections(
        selections, mode=mode, indicator=indicator, limit=limit, order=order
    )
    return {
        "city": store.name,
        "travel_mode": store.mode_label(mode),
        "indicator": indicator,
        "indicator_label": store.category_labels.get(indicator, indicator),
        "order": order,
        "ranked": rows,
        "scope": (
            f"Ranking covers the {len(selections)} named areas in the gazetteer"
            + (f" of kind {kind!r}" if kind else "")
            + ", not every cell in the city."
        ),
    }


def _tool_list_known_places(context: CityContext, args: dict) -> dict:
    query = (args.get("query") or "").strip().lower()
    kind = args.get("kind") or None
    limit = _clamp(args.get("limit"), 1, 200, 60)
    names = [
        place.name
        for place in context.gazetteer.places
        if (kind is None or place.kind == kind)
        and (
            not query
            or query in place.name.lower()
            or any(query in a.lower() for a in place.aliases)
        )
    ]
    names.sort()
    return {
        "city": context.store.name,
        "total_known": len(context.gazetteer),
        "matched": len(names),
        "places": names[:limit],
        "sources": context.gazetteer.sources,
        "note": (
            "Any coordinate inside the city can also be queried directly with lat/lon."
            if context.geocoder is None
            else "Live geocoding is enabled, so other addresses and landmarks can be resolved too."
        ),
    }


def _tool_search_methodology(context: CityContext, args: dict) -> dict:
    limit = _clamp(args.get("limit"), 1, 8, 4)
    hits = context.knowledge.search(args.get("query", ""), limit)
    return {
        "query": args.get("query", ""),
        "passages": hits,
        "documents_available": context.knowledge.documents(),
        "note": (
            "No passage matched; answer from the methodology already in your instructions and "
            "say if something is genuinely not covered."
            if not hits
            else "Verbatim extracts from the reference library. Quote or paraphrase, and cite the source field."
        ),
    }


DISPATCH: dict[str, Callable[[CityContext, dict], dict]] = {
    "city_overview": _tool_city_overview,
    "area_accessibility": _tool_area_accessibility,
    "compare_areas": _tool_compare_areas,
    "rank_areas": _tool_rank_areas,
    "list_known_places": _tool_list_known_places,
    "search_methodology": _tool_search_methodology,
}


def run_tool(context: CityContext, name: str, args: dict) -> tuple[str, bool]:
    """Execute a client tool. Returns (json_text, is_error).

    Errors are returned to the model as tool results rather than raised: the
    model can then apologise, retry with different arguments, or ask the user,
    which is what the guardrails in the system prompt tell it to do.
    """
    handler = DISPATCH.get(name)
    if handler is None:
        return json.dumps({"error": "unknown_tool", "tool": name}), True
    if not isinstance(args, dict):
        return json.dumps({"error": "bad_request", "message": "tool input must be an object"}), True
    try:
        result = handler(context, args)
    except ValueError as exc:  # unknown mode/indicator, missing arguments
        return json.dumps({"error": "bad_request", "message": str(exc)}), True
    except Exception as exc:  # defensive: never kill the conversation
        return json.dumps({"error": "tool_failed", "message": f"{type(exc).__name__}: {exc}"}), True
    return json.dumps(result, ensure_ascii=False, default=str), "error" in result
