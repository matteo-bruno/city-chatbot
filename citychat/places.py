"""Turning a place name into an area of the city.

The indicator data has no names in it, only hexagon ids, so "is Rogoredo a
15-minute neighbourhood?" needs a gazetteer. Three sources, in order of
preference, all optional and all pluggable:

1. **Official boundaries** - a GeoJSON of named districts (for Milan, the 88
   *Nuclei di Identita Locale*). Best answer: cells are selected by
   point-in-polygon, so the area is exactly the administrative one.
   See `scripts/fetch_milan_nil.py`.
2. **A seed list of points** - `data/places/<slug>.places.json`, each entry a
   name, an approximate centre and a radius. Ships with the repo so the bot
   works out of the box; coordinates are approximate by construction.
3. **A geocoder** - optional, off by default. Any place the user names gets
   resolved live (Nominatim/OpenStreetMap by default), then treated as a point
   with a radius.

Resolution is name-first and never guesses silently: an unresolved name comes
back as a miss with suggestions, which the chatbot is instructed to surface.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from . import geo
from .http import httpx

DEFAULT_RADIUS_M = 800.0


def normalise(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    aliases: list[str] = field(default_factory=list)
    radius_m: float | None = None
    polygons: list | None = None
    kind: str = "place"
    source: str = "gazetteer"
    precision: str = "approximate"

    @property
    def has_boundary(self) -> bool:
        return bool(self.polygons)

    def keys(self) -> list[str]:
        return [normalise(n) for n in [self.name, *self.aliases] if n]

    def describe(self) -> dict:
        out = {
            "name": self.name,
            "kind": self.kind,
            "lat": round(self.lat, 5),
            "lon": round(self.lon, 5),
            "source": self.source,
            "geometry": "administrative boundary" if self.has_boundary else "circle",
        }
        if not self.has_boundary:
            out["radius_m"] = round(self.radius_m or DEFAULT_RADIUS_M)
            out["centre_precision"] = self.precision
        if self.aliases:
            out["aliases"] = self.aliases
        return out


class Gazetteer:
    """Named areas for one city, loaded from JSON and/or GeoJSON files."""

    def __init__(self, city: str = "", default_radius_m: float = DEFAULT_RADIUS_M) -> None:
        self.city = city
        self.default_radius_m = default_radius_m
        self.places: list[Place] = []
        self.sources: list[str] = []
        self._by_key: dict[str, Place] = {}

    # ---------------------------------------------------------------- loading

    def add(self, place: Place) -> None:
        if place.radius_m is None and not place.has_boundary:
            place.radius_m = self.default_radius_m
        self.places.append(place)
        for key in place.keys():
            # First source wins, so official boundaries loaded first are not
            # overwritten by an approximate seed point of the same name.
            self._by_key.setdefault(key, place)

    def load_json(self, path: Path) -> None:
        """Load the seed format: {city, default_radius_m, places: [...]}."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.city = self.city or payload.get("city", "")
        self.default_radius_m = payload.get("default_radius_m", self.default_radius_m)
        for entry in payload.get("places", []):
            self.add(
                Place(
                    name=entry["name"],
                    lat=float(entry["lat"]),
                    lon=float(entry["lon"]),
                    aliases=list(entry.get("aliases", [])),
                    radius_m=entry.get("radius_m"),
                    kind=entry.get("kind", "neighbourhood"),
                    source=entry.get("source", Path(path).name),
                    precision=entry.get("precision", "approximate"),
                )
            )
        self.sources.append(f"{Path(path).name} (points)")

    def load_geojson(
        self, path: Path, name_field: str | None = None, kind: str = "district"
    ) -> None:
        """Load named polygons: the authoritative option when available."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        features = payload.get("features", [])
        candidates = ("name", "NIL", "nil", "ID_NIL", "nome", "label", "district")
        for feat in features:
            props = feat.get("properties") or {}
            field_name = name_field or next((f for f in candidates if f in props), None)
            if not field_name or not feat.get("geometry"):
                continue
            name = str(props.get(field_name) or "").strip()
            if not name:
                continue
            polygons = geo.as_multipolygon(feat["geometry"])
            lon, lat = geo.ring_centroid(max(polygons, key=lambda p: len(p[0]))[0])
            self.add(
                Place(
                    name=name,
                    lat=lat,
                    lon=lon,
                    polygons=polygons,
                    kind=kind,
                    source=Path(path).name,
                    precision="official boundary",
                )
            )
        self.sources.append(f"{Path(path).name} (boundaries)")

    # ------------------------------------------------------------- resolution

    def resolve(self, query: str) -> Place | None:
        """Exact name/alias match, then containment, then fuzzy match."""
        key = normalise(query)
        if not key:
            return None
        if key in self._by_key:
            return self._by_key[key]

        # Drop a leading city name ("Milan Rogoredo" -> "Rogoredo").
        city_key = normalise(self.city)
        if city_key and key.startswith(city_key + " "):
            trimmed = key[len(city_key) + 1 :]
            if trimmed in self._by_key:
                return self._by_key[trimmed]

        contained = [k for k in self._by_key if key in k or k in key]
        if contained:
            return self._by_key[min(contained, key=lambda k: (abs(len(k) - len(key)), k))]

        best, best_score = None, 0.0
        for k, place in self._by_key.items():
            score = SequenceMatcher(None, key, k).ratio()
            if score > best_score:
                best, best_score = place, score
        return best if best_score >= 0.82 else None

    def suggest(self, query: str, limit: int = 6, min_score: float = 0.55) -> list[str]:
        """Plausible "did you mean" candidates, empty when nothing is close."""
        key = normalise(query)
        scored = [
            (max(SequenceMatcher(None, key, k).ratio() for k in place.keys()), place.name)
            for place in self.places
        ]
        scored.sort(key=lambda p: (-p[0], p[1]))
        return [name for score, name in scored[:limit] if score >= min_score]

    def names(self, kind: str | None = None) -> list[str]:
        return sorted({p.name for p in self.places if kind is None or p.kind == kind})

    def __len__(self) -> int:
        return len(self.places)


class NominatimGeocoder:
    """Optional live geocoding through a Nominatim instance.

    Disabled by default. Enabling it means the bot can answer about any street
    or landmark, not only the gazetteer. Results are cached on disk, and the
    one-request-per-second rule of the public OSM endpoint is enforced here, so
    please still set a descriptive user agent and consider self-hosting for any
    real traffic.
    """

    def __init__(
        self,
        base_url: str = "https://nominatim.openstreetmap.org",
        user_agent: str = "city-chatbot/0.1",
        email: str | None = None,
        cache_path: Path | None = None,
        viewbox: Sequence[float] | None = None,
        timeout: float = 10.0,
        min_interval_s: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.email = email
        self.cache_path = Path(cache_path) if cache_path else None
        self.viewbox = list(viewbox) if viewbox else None
        self.timeout = timeout
        self.min_interval_s = min_interval_s
        self._last_call = 0.0
        self._cache: dict[str, dict | None] = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._cache = {}

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1), encoding="utf-8")
        except OSError:
            pass

    def geocode(self, query: str, city_hint: str = "") -> Place | None:
        full_query = (
            f"{query}, {city_hint}"
            if city_hint and normalise(city_hint) not in normalise(query)
            else query
        )
        cache_key = normalise(full_query)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return self._to_place(cached) if cached else None

        params = {
            "q": full_query,
            "format": "jsonv2",
            "limit": "1",
            "polygon_geojson": "1",
            "addressdetails": "0",
        }
        if self.viewbox:
            params["viewbox"] = ",".join(str(v) for v in self.viewbox)
            params["bounded"] = "1"
        if self.email:
            params["email"] = self.email

        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            response = httpx.get(
                f"{self.base_url}/search",
                params=params,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=self.timeout,
            )
            self._last_call = time.monotonic()
            response.raise_for_status()
            results = response.json()
        except Exception:  # network, timeout, rate limit, malformed body
            return None

        record = results[0] if results else None
        self._cache[cache_key] = record
        self._save_cache()
        return self._to_place(record) if record else None

    def _to_place(self, record: dict) -> Place | None:
        try:
            lat = float(record["lat"])
            lon = float(record["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        polygons = None
        geometry = record.get("geojson")
        if geometry and geometry.get("type") in ("Polygon", "MultiPolygon"):
            try:
                polygons = geo.as_multipolygon(geometry)
            except ValueError:
                polygons = None
        return Place(
            name=record.get("name") or str(record.get("display_name", "")).split(",")[0],
            lat=lat,
            lon=lon,
            polygons=polygons,
            kind=record.get("type", "place"),
            source="nominatim",
            precision="official boundary" if polygons else "geocoded point",
        )
