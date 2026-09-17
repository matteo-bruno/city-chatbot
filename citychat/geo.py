"""Small, dependency-free geometry helpers.

The city data is a grid of small hexagonal cells (H3 resolution 9, ~174 m edge).
Everything we need for the chatbot is: distance between two WGS84 points,
polygon centroids, point-in-polygon tests and a coarse spatial index so that
"give me every cell around this point" does not scan the whole city.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

EARTH_RADIUS_M = 6_371_008.8

Point = tuple[float, float]  # (lon, lat)
Ring = Sequence[Point]


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two (lon, lat) points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def ring_centroid(ring: Ring) -> Point:
    """Area-weighted centroid of a closed planar ring, in (lon, lat).

    Uses the shoelace formula on raw degrees. Over a 200 m hexagon the
    distortion is far below the precision we report, so projecting first
    would only add a dependency.
    """
    pts = list(ring)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if not pts:
        raise ValueError("empty ring")
    if len(pts) < 3:
        return (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )

    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area2) < 1e-15:  # degenerate ring: fall back to the vertex mean
        return (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )
    return (cx / (3 * area2), cy / (3 * area2))


def polygon_centroid(coordinates: Sequence[Ring]) -> Point:
    """Centroid of a GeoJSON Polygon (outer ring only)."""
    return ring_centroid(coordinates[0])


def point_in_ring(lon: float, lat: float, ring: Ring) -> bool:
    """Ray-casting point-in-polygon test for a single ring."""
    inside = False
    pts = list(ring)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > lat) != (y1 > lat):
            # x coordinate of the edge at this latitude
            x_cross = x0 + (lat - y0) * (x1 - x0) / (y1 - y0)
            if lon < x_cross:
                inside = not inside
    return inside


def point_in_polygon(lon: float, lat: float, coordinates: Sequence[Ring]) -> bool:
    """Point in a GeoJSON Polygon, honouring holes."""
    if not coordinates or not point_in_ring(lon, lat, coordinates[0]):
        return False
    return not any(point_in_ring(lon, lat, hole) for hole in coordinates[1:])


def point_in_multipolygon(lon: float, lat: float, polygons: Sequence[Sequence[Ring]]) -> bool:
    return any(point_in_polygon(lon, lat, poly) for poly in polygons)


def bbox_of(points: Iterable[Point]) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat)."""
    xs: list[float] = []
    ys: list[float] = []
    for lon, lat in points:
        xs.append(lon)
        ys.append(lat)
    if not xs:
        raise ValueError("no points")
    return min(xs), min(ys), max(xs), max(ys)


def geometry_points(geometry: dict) -> list[Point]:
    """Flatten any GeoJSON geometry into its coordinate list."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Point":
        return [(coords[0], coords[1])]
    if gtype in ("MultiPoint", "LineString"):
        return [(c[0], c[1]) for c in coords]
    if gtype in ("MultiLineString", "Polygon"):
        return [(c[0], c[1]) for part in coords for c in part]
    if gtype == "MultiPolygon":
        return [(c[0], c[1]) for poly in coords for part in poly for c in part]
    if gtype == "GeometryCollection":
        return [p for g in geometry.get("geometries", []) for p in geometry_points(g)]
    raise ValueError(f"unsupported geometry type: {gtype!r}")


def as_multipolygon(geometry: dict) -> list[list[Ring]]:
    """Normalise Polygon/MultiPolygon into a list of polygons."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return [[[(c[0], c[1]) for c in ring] for ring in coords]]
    if gtype == "MultiPolygon":
        return [[[(c[0], c[1]) for c in ring] for ring in poly] for poly in coords]
    raise ValueError(f"expected Polygon or MultiPolygon, got {gtype!r}")


class CellIndex:
    """Coarse uniform-grid index over cell centroids.

    Buckets centroids into ~0.01 degree tiles (roughly 1.1 km x 0.8 km in
    Milan) and answers radius queries by visiting only the tiles a circle can
    touch. Good enough for a few hundred thousand cells and needs no C
    extension.
    """

    def __init__(
        self, lons: Sequence[float], lats: Sequence[float], tile_deg: float = 0.01
    ) -> None:
        if len(lons) != len(lats):
            raise ValueError("lons/lats length mismatch")
        self.lons = lons
        self.lats = lats
        self.tile_deg = tile_deg
        self._tiles: dict[tuple[int, int], list[int]] = {}
        for i, (lon, lat) in enumerate(zip(lons, lats)):
            self._tiles.setdefault(self._key(lon, lat), []).append(i)

    def _key(self, lon: float, lat: float) -> tuple[int, int]:
        return (math.floor(lon / self.tile_deg), math.floor(lat / self.tile_deg))

    def within_radius(self, lon: float, lat: float, radius_m: float) -> list[int]:
        """Indices of cells whose centroid is within radius_m of the point."""
        dlat = radius_m / 111_320.0
        cos_lat = max(0.01, math.cos(math.radians(lat)))
        dlon = radius_m / (111_320.0 * cos_lat)
        x0, y0 = self._key(lon - dlon, lat - dlat)
        x1, y1 = self._key(lon + dlon, lat + dlat)
        hits: list[int] = []
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                for i in self._tiles.get((tx, ty), ()):
                    if haversine_m(lon, lat, self.lons[i], self.lats[i]) <= radius_m:
                        hits.append(i)
        return hits

    def nearest(
        self, lon: float, lat: float, max_radius_m: float = 20_000.0
    ) -> tuple[int, float] | None:
        """Closest cell centroid, growing the search radius until something is found."""
        radius = 400.0
        while radius <= max_radius_m:
            candidates = self.within_radius(lon, lat, radius)
            if candidates:
                best = min(
                    candidates, key=lambda i: haversine_m(lon, lat, self.lons[i], self.lats[i])
                )
                return best, haversine_m(lon, lat, self.lons[best], self.lats[best])
            radius *= 2
        return None

    def within_polygons(self, polygons: Sequence[Sequence[Ring]]) -> list[int]:
        """Indices of cells whose centroid falls inside any of the polygons."""
        pts = [p for poly in polygons for ring in poly for p in ring]
        min_lon, min_lat, max_lon, max_lat = bbox_of(pts)
        x0, y0 = self._key(min_lon, min_lat)
        x1, y1 = self._key(max_lon, max_lat)
        hits: list[int] = []
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                for i in self._tiles.get((tx, ty), ()):
                    lon, lat = self.lons[i], self.lats[i]
                    if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                        if point_in_multipolygon(lon, lat, polygons):
                            hits.append(i)
        return hits
