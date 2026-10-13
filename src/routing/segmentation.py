"""SafeRoute AI — Deterministic Route Segmentation Engine.

Phase ID: PHASE_13
Follows PRD FR-R4, TRD §10.1, ARCHITECTURE §8.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from src.routing.schemas import (
    Coordinate,
    RouteGeometry,
    RouteSegment,
)

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_m(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate geodesic distance in meters between two (lon, lat) points."""
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def compute_linestring_length_m(coords: List[Tuple[float, float]]) -> float:
    """Compute total length in meters along a sequence of (lon, lat) coordinates."""
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine_distance_m(coords[i], coords[i + 1])
    return total


class RouteSegmenter:
    """Subdivides route geometries into assessable segments with stable identifiers (FR-R4).
    
    Invariants:
    - Pure function: Identical route coordinates -> identical segment IDs and metrics.
    - Stable identifiers: 'seg-{route_id}-{sequence:04d}'.
    """

    def __init__(
        self,
        target_segment_length_m: float = 200.0,
        min_segment_length_m: float = 50.0,
        max_segment_length_m: float = 500.0,
    ):
        self.target_length_m = target_segment_length_m
        self.min_length_m = min_segment_length_m
        self.max_length_m = max_segment_length_m

    def segment_from_steps(
        self,
        route_id: str,
        steps: List[Dict[str, Any]],
        fallback_coordinates: Optional[List[Tuple[float, float]]] = None,
    ) -> List[RouteSegment]:
        """Decompose route steps (from OSRM / provider steps) into discrete segments."""
        if not steps and fallback_coordinates:
            return self.segment_from_coordinates(route_id, fallback_coordinates)

        segments: List[RouteSegment] = []
        seq = 0

        for step in steps:
            step_geom = step.get("geometry", {})
            coords = step_geom.get("coordinates", [])
            if not coords or len(coords) < 2:
                continue

            length_m = float(step.get("distance", compute_linestring_length_m(coords)))
            duration_s = float(step.get("duration", 0.0))
            name = step.get("name") or step.get("ref") or "Unnamed Road"
            maneuver = step.get("maneuver", {})
            instruction = maneuver.get("instruction") or f"Continue on {name}"

            # If step is excessively long (> max_segment_length_m), chunk it into smaller sub-segments
            if length_m > self.max_length_m and len(coords) > 2:
                sub_segments = self._subdivide_step(
                    route_id=route_id,
                    start_seq=seq,
                    coords=coords,
                    total_length_m=length_m,
                    total_duration_s=duration_s,
                    name=name,
                    instruction=instruction,
                )
                segments.extend(sub_segments)
                seq += len(sub_segments)
            else:
                start_c = Coordinate(latitude=coords[0][1], longitude=coords[0][0])
                end_c = Coordinate(latitude=coords[-1][1], longitude=coords[-1][0])
                seg_id = f"seg-{route_id}-{seq:04d}"

                segments.append(
                    RouteSegment(
                        segment_id=seg_id,
                        route_id=route_id,
                        sequence=seq,
                        length_m=max(1.0, length_m),
                        duration_s=max(0.1, duration_s),
                        start_coord=start_c,
                        end_coord=end_c,
                        geometry=RouteGeometry(coordinates=coords),
                        road_name=name,
                        instruction=instruction,
                    )
                )
                seq += 1

        if not segments and fallback_coordinates:
            return self.segment_from_coordinates(route_id, fallback_coordinates)

        return segments

    def segment_from_coordinates(
        self,
        route_id: str,
        coordinates: List[Tuple[float, float]],
        total_duration_s: float = 0.0,
    ) -> List[RouteSegment]:
        """Subdivide a raw coordinate sequence into target-length segments."""
        if len(coordinates) < 2:
            return []

        segments: List[RouteSegment] = []
        seq = 0
        current_chunk: List[Tuple[float, float]] = [coordinates[0]]
        accumulated_dist = 0.0
        total_route_length = compute_linestring_length_m(coordinates)

        for i in range(1, len(coordinates)):
            pt = coordinates[i]
            d = haversine_distance_m(current_chunk[-1], pt)
            accumulated_dist += d
            current_chunk.append(pt)

            if accumulated_dist >= self.target_length_m or i == len(coordinates) - 1:
                # If last segment is too tiny, append to previous if possible
                if i == len(coordinates) - 1 and accumulated_dist < self.min_length_m and segments:
                    prev = segments[-1]
                    merged_coords = prev.geometry.coordinates + current_chunk[1:]
                    merged_len = compute_linestring_length_m(merged_coords)
                    segments[-1] = RouteSegment(
                        segment_id=prev.segment_id,
                        route_id=route_id,
                        sequence=prev.sequence,
                        length_m=merged_len,
                        duration_s=prev.duration_s + (accumulated_dist / max(1.0, total_route_length)) * total_duration_s,
                        start_coord=prev.start_coord,
                        end_coord=Coordinate(latitude=pt[1], longitude=pt[0]),
                        geometry=RouteGeometry(coordinates=merged_coords),
                        road_name=prev.road_name,
                        instruction=prev.instruction,
                    )
                    break

                seg_id = f"seg-{route_id}-{seq:04d}"
                start_c = Coordinate(latitude=current_chunk[0][1], longitude=current_chunk[0][0])
                end_c = Coordinate(latitude=current_chunk[-1][1], longitude=current_chunk[-1][0])
                seg_duration = (
                    (accumulated_dist / max(1.0, total_route_length)) * total_duration_s
                    if total_route_length > 0
                    else 0.0
                )

                segments.append(
                    RouteSegment(
                        segment_id=seg_id,
                        route_id=route_id,
                        sequence=seq,
                        length_m=accumulated_dist,
                        duration_s=seg_duration,
                        start_coord=start_c,
                        end_coord=end_c,
                        geometry=RouteGeometry(coordinates=list(current_chunk)),
                        road_name=f"Segment {seq}",
                        instruction=f"Proceed along segment {seq}",
                    )
                )
                seq += 1
                current_chunk = [pt]
                accumulated_dist = 0.0

        return segments

    def _subdivide_step(
        self,
        route_id: str,
        start_seq: int,
        coords: List[Tuple[float, float]],
        total_length_m: float,
        total_duration_s: float,
        name: str,
        instruction: str,
    ) -> List[RouteSegment]:
        """Divide long step coordinates into target-sized chunks."""
        sub_segs = self.segment_from_coordinates(
            route_id=route_id,
            coordinates=coords,
            total_duration_s=total_duration_s,
        )
        # Update sequence and road names
        for idx, s in enumerate(sub_segs):
            s.sequence = start_seq + idx
            s.segment_id = f"seg-{route_id}-{s.sequence:04d}"
            s.road_name = name
            s.instruction = instruction
        return sub_segs
