"""SafeRoute AI — Facility Geometry Helpers (PHASE_29).

Small, dependency-free helpers used to measure how far a facility is from a
route corridor.

Everything here is a STRAIGHT-LINE (planar / great-circle) measurement. A
road-network distance is only ever obtained from a real routing provider
response — never estimated here (Rule 20).
"""

import math
from typing import Iterable, List, Optional, Sequence, Tuple

from src.routing.segmentation import haversine_distance_m

#: Metres per degree of latitude (mean value), used for the local planar
#: projection of a point onto a segment.
_METERS_PER_DEG_LAT = 110540.0
_METERS_PER_DEG_LON_AT_EQUATOR = 111320.0

Point = Tuple[float, float]  # (lon, lat)


def _project_to_segment_m(
    p: Point,
    a: Point,
    b: Point,
) -> Tuple[float, Point]:
    """Distance in meters from ``p`` to segment ``a``–``b`` and the closest point.

    A local equirectangular projection is used around the segment's midpoint —
    accurate for city-scale distances and identical in spirit to the frontend's
    own measurement.
    """
    lat_ref = math.radians((a[1] + b[1]) / 2.0)
    per_deg_lon = _METERS_PER_DEG_LON_AT_EQUATOR * math.cos(lat_ref)
    per_deg_lat = _METERS_PER_DEG_LAT

    ax, ay = a[0] * per_deg_lon, a[1] * per_deg_lat
    bx, by = b[0] * per_deg_lon, b[1] * per_deg_lat
    px, py = p[0] * per_deg_lon, p[1] * per_deg_lat

    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    t = 0.0 if len_sq == 0 else ((px - ax) * dx + (py - ay) * dy) / len_sq
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    distance = math.hypot(px - cx, py - cy)

    lon = cx / per_deg_lon if per_deg_lon else a[0]
    lat = cy / per_deg_lat
    return distance, (lon, lat)


def nearest_point_on_polyline(
    point: Point,
    polyline: Sequence[Point],
) -> Tuple[float, Optional[Point]]:
    """Straight-line distance (m) from ``point`` to ``polyline`` and the closest point.

    Returns ``(distance_m, closest_point)``. ``closest_point`` is ``None`` only
    when the polyline is empty. The distance is measured to the polyline
    (not to its vertices) so a long straight segment is handled correctly.
    """
    if not polyline:
        return float("inf"), None
    if len(polyline) == 1:
        return haversine_distance_m(point, polyline[0]), polyline[0]

    best_distance = float("inf")
    best_point: Optional[Point] = None
    for i in range(1, len(polyline)):
        distance, closest = _project_to_segment_m(point, polyline[i - 1], polyline[i])
        if distance < best_distance:
            best_distance = distance
            best_point = closest
    return best_distance, best_point


def distance_to_polylines_m(
    point: Point,
    polylines: Iterable[Sequence[Point]],
) -> Tuple[float, Optional[Point]]:
    """Straight-line distance (m) from ``point`` to the nearest of ``polylines``."""
    best_distance = float("inf")
    best_point: Optional[Point] = None
    for polyline in polylines:
        distance, closest = nearest_point_on_polyline(point, polyline)
        if distance < best_distance:
            best_distance = distance
            best_point = closest
    return best_distance, best_point


def polylines_bbox(
    polylines: Iterable[Sequence[Point]],
    pad_m: float = 0.0,
) -> Optional[Tuple[float, float, float, float]]:
    """Bounding box ``(south, west, north, east)`` around all polylines.

    The box is padded by ``pad_m`` meters so a corridor search covers the
    requested radius around the route. ``None`` is returned when there is no
    usable geometry.
    """
    lats: List[float] = []
    lons: List[float] = []
    for polyline in polylines:
        for lon, lat in polyline:
            lons.append(float(lon))
            lats.append(float(lat))
    if not lats:
        return None

    mean_abs_lat = (min(lats) + max(lats)) / 2.0
    pad_lat = pad_m / _METERS_PER_DEG_LAT
    per_deg_lon = _METERS_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(mean_abs_lat))
    pad_lon = pad_m / per_deg_lon if per_deg_lon else pad_m / _METERS_PER_DEG_LON_AT_EQUATOR

    return (
        min(lats) - pad_lat,
        min(lons) - pad_lon,
        max(lats) + pad_lat,
        max(lons) + pad_lon,
    )


def normalise_polylines(raw: object) -> List[List[Point]]:
    """Normalise a client-supplied polyline payload into ``[[(lon, lat), …], …]``.

    Invalid entries are dropped rather than repaired, so a malformed request
    can never produce a fabricated geometry.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[List[Point]] = []
    for line in raw:
        if not isinstance(line, (list, tuple)) or not line:
            continue
        points: List[Point] = []
        for coord in line:
            if not isinstance(coord, (list, tuple)) or len(coord) < 2:
                continue
            try:
                lon = float(coord[0])
                lat = float(coord[1])
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(lon) and math.isfinite(lat)):
                continue
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                continue
            points.append((lon, lat))
        if points:
            out.append(points)
    return out
