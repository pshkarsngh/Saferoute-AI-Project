"""SafeRoute AI — Segment-to-Imagery Spatial Matcher.

Phase ID: PHASE_14
Follows TRD §10.1, ARCHITECTURE §8.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.routing.schemas import RouteSegment
from src.routing.segmentation import haversine_distance_m


def point_to_segment_distance_m(
    pt: Tuple[float, float],
    line_coords: List[Tuple[float, float]],
) -> float:
    """Calculate minimum Haversine distance in meters from a point (lon, lat) to a line."""
    if not line_coords:
        return float("inf")
    if len(line_coords) == 1:
        return haversine_distance_m(pt, line_coords[0])

    min_dist = float("inf")
    for vertex in line_coords:
        d = haversine_distance_m(pt, vertex)
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
