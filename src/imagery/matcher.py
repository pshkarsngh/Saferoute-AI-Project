"""SafeRoute AI — Segment-to-Imagery Spatial Matcher.

Phase ID: PHASE_14
Follows TRD §10.1, ARCHITECTURE §8.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from src.routing.schemas import RouteSegment
from src.routing.segmentation import EARTH_RADIUS_METERS, haversine_distance_m


def _point_to_single_segment_distance_m(
    pt: Tuple[float, float],
    a: Tuple[float, float],
    b: Tuple[float, float],
) -> float:
    """Perpendicular point-to-line-segment distance in meters.

    Uses a local equirectangular projection centred on vertex ``a`` (valid at the
    scale of a single route segment). The magnitude of the projection is clamped
    to the segment extent, so a point beyond an endpoint correctly falls back to
    the nearest endpoint distance.
    """
    # Local planar coordinates (meters) around vertex ``a``.
    lat_ref = math.radians(a[1])
    cos_lat = math.cos(lat_ref)

    def _xy(coord: Tuple[float, float]) -> Tuple[float, float]:
        lon, lat = coord
        return (
            math.radians(lon) * EARTH_RADIUS_METERS * cos_lat,
            math.radians(lat) * EARTH_RADIUS_METERS,
        )

    ax, ay = _xy(a)
    bx, by = _xy(b)
    px, py = _xy(pt)

    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        # Degenerate segment (coincident vertices) -> point distance.
        return haversine_distance_m(pt, a)

    t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
    cx, cy = ax + t * abx, ay + t * aby
    return math.hypot(px - cx, py - cy)


def point_to_segment_distance_m(
    pt: Tuple[float, float],
    line_coords: List[Tuple[float, float]],
) -> float:
    """Minimum distance in meters from a point (lon, lat) to a polyline.

    The distance is the true perpendicular distance to the nearest *edge* of the
    polyline (not merely the nearest vertex), so a camera point in the middle of
    a long straight edge is matched even when it is far from either vertex.
    """
    if not line_coords:
        return float("inf")
    if len(line_coords) == 1:
        return haversine_distance_m(pt, line_coords[0])

    min_dist = float("inf")
    for i in range(len(line_coords) - 1):
        d = _point_to_single_segment_distance_m(pt, line_coords[i], line_coords[i + 1])
        if d < min_dist:
            min_dist = d
    return min_dist


class SegmentImageryMatcher:
    """Matches candidate street-level imagery frames to route segments.
    
    Documented Limitations (ARCHITECTURE §8):
    1. GPS Drift: Mobile dashcams exhibit $\pm 5-15$ meters positioning drift.
    2. Orientation: Matching checks spatial proximity, not camera azimuth angle.
    3. Accuracy Limits: Candidates beyond max_radius_meters are strictly rejected as 'unmatched'.
    """

    def __init__(self, search_radius_meters: float = 25.0, max_images_per_segment: int = 3):
        self.radius_m = search_radius_meters
        self.max_images = max_images_per_segment

    def match_candidates(
        self,
        segment: RouteSegment,
        candidates: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Match candidate images to segment geometry within search buffer.
        
        Args:
            segment: Target RouteSegment to match against.
            candidates: List of candidate image metadata dictionaries with 'coordinates' (lon, lat).
            
        Returns:
            List of (candidate_dict, distance_meters) tuples sorted by closest proximity.
        """
        line_coords = segment.geometry.coordinates
        matched: List[Tuple[Dict[str, Any], float]] = []

        for cand in candidates:
            c_coord = cand.get("coordinates")
            if not c_coord or len(c_coord) < 2:
                continue

            dist_m = point_to_segment_distance_m(tuple(c_coord), line_coords)
            if dist_m <= self.radius_m:
                matched.append((cand, dist_m))

        # Sort by proximity
        matched.sort(key=lambda x: x[1])
        return matched[: self.max_images]
