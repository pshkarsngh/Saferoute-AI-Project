"""SafeRoute AI — Safety Analysis Pipeline orchestration (PHASE_16).

Orchestrates: routing -> imagery -> preprocessing -> detection -> aggregation ->
deterministic risk -> comparison -> grounded explanation.

All structured calculations happen here/backend-side. The risk engine owns scores
(Rule 7); facilities never enter the score (Rule 11); the LLM only explains (Rule 12).
"""

import dataclasses
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config.thresholds import assert_threshold_consistency
from src.facilities.service import FacilitiesService
from src.imagery.adapter import PermittedImageryAdapter
from src.llm.explainer import GroundedExplanationService
from src.risk.aggregate import HazardAggregator, deduplicate_adjacent_segment_hazards
from src.risk.comparison import RouteComparer, assessed_length_fraction
from src.risk.engine import DeterministicRiskEngine
from src.risk.schemas import AssessmentStatus
from src.routing.adapter import create_routing_adapter
from src.routing.schemas import Coordinate, RouteRequest, RoutingStatus

MODEL_VERSION = "saferoute-yolo11-v2"


def _restamp_detection_result(result, route_id: str, segment_id: str):
    """Return a copy of a cached detection result tagged for another segment.

    PHASE_27: the same downloaded frame can legitimately match several segments
    (adjacent segments — and even two alternative routes sharing a road — often
    reference the same Mapillary image). Inference on identical pixels with
    identical weights is deterministic, so the heavy YOLO pass is computed once
    per image per analysis request and only the route/segment identifiers are
    re-stamped for the new caller. Evidence, scores and thresholds are
    unchanged (Rules 7, 9, 10).
    """
    if result.route_id == route_id and result.segment_id == segment_id:
        return result
    detections = [
        dataclasses.replace(d, route_id=route_id, segment_id=segment_id)
        for d in result.detections
    ]
    return dataclasses.replace(
        result, route_id=route_id, segment_id=segment_id, detections=detections)


class SafetyAnalysisPipeline:
    """Provider-independent orchestration of the SafeRoute AI assessment pipeline."""

    def __init__(
        self,
        routing_provider=None,
        imagery_adapter=None,
        detector=None,
        aggregator=None,
        engine=None,
        facilities_service=None,
        explainer=None,
        comparer=None,
        imagery_workers: Optional[int] = None,
    ):
        self.routing = routing_provider or create_routing_adapter("mock")
        self.imagery = imagery_adapter or PermittedImageryAdapter()
        self._detector = detector
        self.aggregator = aggregator or HazardAggregator()
        self.engine = engine or DeterministicRiskEngine()
        self.facilities = facilities_service or FacilitiesService()
        self.explainer = explainer or GroundedExplanationService()
        self.comparer = comparer or RouteComparer()
        self.model_version = MODEL_VERSION
        self.config_hash = self.engine.config_hash

        # PHASE_26: imagery retrieval is network-bound and independent per segment,
        # so it is prefetched concurrently (bounded thread pool) instead of one
        # avatar request at a time. This changes ONLY the I/O schedule: segment
        # ordering, detection, aggregation, scoring, thresholds and the provider
        # contract are untouched (Rules 7, 9, 10). Set SAFEROUTE_IMAGERY_WORKERS=1
        # to force strictly sequential retrieval.
        # PHASE_27: measured on the live Mapillary provider, wall-clock imagery
        # retrieval for a 20 km / ~100-segment trip dropped from ~18 s (8 workers)
        # to ~4 s (16 workers) with identical evidence, so the default is 16.
        if imagery_workers is None:
            try:
                imagery_workers = int(os.environ.get("SAFEROUTE_IMAGERY_WORKERS", "16"))
            except (TypeError, ValueError):
                imagery_workers = 16
        self.imagery_workers = max(1, int(imagery_workers))

        # PHASE_22 guard: fail loudly if detector/aggregator confidence thresholds
        # diverge (would silently discard detections). Only checked when using the
        # real configs (not when a custom aggregator/engine is injected).
        if aggregator is None and engine is None:
            assert_threshold_consistency()

    def _get_detector(self):
        if self._detector is None:
            from src.detection.detector import HazardDetector
            self._detector = HazardDetector()
        return self._detector

    def resolve_routes(self, origin: Coordinate, destination: Coordinate) -> Dict[str, Any]:
        resp = self.routing.get_routes(RouteRequest(origin=origin, destination=destination))
        return resp.to_dict()

    def analyze(self, origin: Coordinate, destination: Coordinate) -> Dict[str, Any]:
        t_total = time.perf_counter()
        analysis_id = "an-" + uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        resp = self.routing.get_routes(RouteRequest(origin=origin, destination=destination))
        routing_ms = (time.perf_counter() - t0) * 1000.0

        record: Dict[str, Any] = {
            "analysis_id": analysis_id,
            "search_id": analysis_id,
            "created_at": now,
            "origin": origin.to_dict(),
            "destination": destination.to_dict(),
            "provider": resp.provider,
            "model_version": self.model_version,
            "config_hash": self.config_hash,
            "routes": [],
            "recommendation": None,
            "limitations": list(resp.limitations),
            "status": "unassessed",
        }

        if resp.status != RoutingStatus.OK or not resp.routes:
            record["status"] = "failed"
            record["routing_status"] = resp.status.value
            if resp.error_message:
                record["limitations"].append(resp.error_message)
            t0 = time.perf_counter()
            record["explanation"] = self.explainer.explain(record).to_dict()
            timings = {
                "routing_ms": round(routing_ms, 1),
                "explanation_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            }
            timings["total_ms"] = round((time.perf_counter() - t_total) * 1000.0, 1)
            record["timings_ms"] = timings
            return record

        # PHASE_26: imagery retrieval for EVERY route is network-bound and
        # independent, so it is prefetched in one bounded thread pool across all
        # routes at once (better overlap than per-route). Results are re-split by
        # route and the per-route analysis below still runs in route order, so the
        # comparison/ranking sees exactly the same route sequence as before
        # (Rules 7, 9, 10).
        routes = list(resp.routes)
        per_route_segments = [list(route.segments) for route in routes]
        flat_segments = [seg for segs in per_route_segments for seg in segs]
        t0 = time.perf_counter()
        flat_imagery = self._prefetch_segment_imagery(flat_segments)
        imagery_ms = (time.perf_counter() - t0) * 1000.0

        cursor = 0
        # PHASE_27: one detection memo per analysis request. Segments that match
        # the same downloaded frame share one YOLO inference (results re-stamped
        # per segment), removing duplicate work without changing evidence.
        detection_cache: Dict[Any, Any] = {}
        for route, segments in zip(routes, per_route_segments):
            route_imagery = flat_imagery[cursor:cursor + len(segments)]
            cursor += len(segments)
            record["routes"].append(
                self._analyze_route(route, route_imagery, detection_cache=detection_cache))

        t0 = time.perf_counter()
        record["comparison"] = self._build_comparison(record["routes"], assessed_at=record["created_at"])
        comparison_ms = (time.perf_counter() - t0) * 1000.0
        record["recommendation"] = record["comparison"]["recommended_route_id"]
        record["status"] = self._overall_status(record["routes"])
        t0 = time.perf_counter()
        record["explanation"] = self.explainer.explain(record).to_dict()
        explanation_ms = (time.perf_counter() - t0) * 1000.0

        # PHASE_27 observability: additive per-stage wall-clock breakdown so the
        # dominant cost is measurable from a real response. Scores, evidence and
        # the recommendation above are untouched (Rule 7).
        detection_ms = sum(r.get("timings_ms", {}).get("detection_ms", 0.0) for r in record["routes"])
        scoring_ms = sum(r.get("timings_ms", {}).get("risk_scoring_ms", 0.0) for r in record["routes"])
        record["timings_ms"] = {
            "routing_ms": round(routing_ms, 1),
            "imagery_ms": round(imagery_ms, 1),
            "detection_ms": round(detection_ms, 1),
            "risk_scoring_ms": round(scoring_ms, 1),
            "comparison_ms": round(comparison_ms, 1),
            "explanation_ms": round(explanation_ms, 1),
            "total_ms": round((time.perf_counter() - t_total) * 1000.0, 1),
        }
        return record

    def _prefetch_segment_imagery(self, segments) -> List[Any]:
        """Retrieve imagery for every segment, preserving segment order.

        Retrieval is pure network I/O with no ordering dependency, so it runs in a
        bounded thread pool. Results are placed back at their original index, so
        the downstream detection/aggregation/scoring loop sees exactly the same
        sequence it would have seen sequentially (Rules 7, 9, 10).

        Any per-segment failure is re-raised in segment order, so a provider error
        surfaces exactly as it would have in the sequential path.
        """
        segments = list(segments)
        if not segments:
            return []
        if self.imagery_workers <= 1 or len(segments) == 1:
            return [self.imagery.get_imagery_for_segment(seg) for seg in segments]

        results: List[Any] = [None] * len(segments)
        errors: Dict[int, BaseException] = {}

        def fetch(index: int, segment) -> None:
            try:
                results[index] = self.imagery.get_imagery_for_segment(segment)
            except BaseException as exc:  # noqa: BLE001 - surfaced in original order
                errors[index] = exc

        with ThreadPoolExecutor(max_workers=min(self.imagery_workers, len(segments))) as pool:
            futures = [pool.submit(fetch, i, seg) for i, seg in enumerate(segments)]
            for future in futures:
                future.result()

        if errors:
            raise errors[min(errors)]
        return results

    def _analyze_route(self, route, imagery_by_index=None, detection_cache=None) -> Dict[str, Any]:
        segment_assessments = []
        lengths: List[float] = []
        imagery_meta: List[Dict[str, Any]] = []
        hazard_records: List[Dict[str, Any]] = []
        detection_ms = 0.0

        if detection_cache is None:
            detection_cache = {}

        segment_list = list(route.segments)
        if imagery_by_index is None:
            # Standalone call (e.g. tests): fetch this route's imagery now.
            imagery_by_index = self._prefetch_segment_imagery(segment_list)

        for seg, imagery in zip(segment_list, imagery_by_index):
            image_results = []
            expected = 0
            if imagery.is_available:
                detector = self._get_detector()
                for img in imagery.images:
                    t0 = time.perf_counter()
                    cache_key = (str(img.file_path), img.image_id)
                    cached = detection_cache.get(cache_key)
                    if cached is None:
                        cached = detector.detect(
                            img.file_path, image_id=img.image_id,
                            route_id=route.route_id, segment_id=seg.segment_id)
                        detection_cache[cache_key] = cached
                    image_results.append(
                        _restamp_detection_result(cached, route.route_id, seg.segment_id))
                    detection_ms += (time.perf_counter() - t0) * 1000.0
                expected = len(imagery.images)
            assessment = self.aggregator.assess_segment(
                seg.segment_id, image_results, expected_image_count=expected, route_id=route.route_id)
            segment_assessments.append(assessment)
            lengths.append(seg.length_m)
            imagery_meta.append(imagery.to_dict())

        # PHASE_23B: cross-segment de-duplication by shared image identity so the
        # same physical hazard is not counted repeatedly across adjacent segments.
        # This honours the declared risk-engine policy (dedup_adjacent_segments).
        if getattr(self.engine, "dedup_adjacent_segments", False):
            segment_assessments, _ = deduplicate_adjacent_segment_hazards(
                segment_assessments,
                getattr(self.engine, "adjacent_boundary_iou", 0.50),
            )

        for assessment in segment_assessments:
            for h in assessment.hazards:
                hazard_records.append(h.to_dict() if hasattr(h, "to_dict") else dict(h))

        t0 = time.perf_counter()
        result = self.engine.score_route(route.route_id, segment_assessments, lengths).to_dict()
        risk_scoring_ms = (time.perf_counter() - t0) * 1000.0
        result["provider"] = route.provider
        result["summary"] = route.summary
        result["distance_m"] = route.distance_m
        result["duration_s"] = route.duration_s
        result["geometry"] = route.geometry.to_dict()
        result["segments"] = [s.to_dict() for s in route.segments]
        result["hazards"] = hazard_records
        result["imagery"] = imagery_meta
        result["timings_ms"] = {
            "detection_ms": round(detection_ms, 1),
            "risk_scoring_ms": round(risk_scoring_ms, 1),
        }

        # PHASE_25: classify the evidence actually used for this route. Demo imagery
        # is not geographically matched to the requested roads, so a route scored
        # from it is labelled and excluded from the real-world recommendation
        # (Rule 9, Rule 20).
        demo_used = any(
            img.get("is_demo")
            for meta in imagery_meta
            for img in (meta.get("images") or [])
        )
        stale_used = any(
            img.get("is_stale") or (img.get("status") == "stale")
            for meta in imagery_meta
            for img in (meta.get("images") or [])
        )
        result["evidence_class"] = "demo" if demo_used else ("stale" if stale_used else "real")
        result["assessed_length_fraction"] = assessed_length_fraction(result)
        if demo_used:
            result["limitations"] = list(result.get("limitations", [])) + [
                "Demo imagery (not geographically matched to this route) contributed to "
                "this score; it is pipeline-demonstration evidence only and is excluded "
                "from the real-world recommendation (Rule 9, Rule 20)."
            ]
        if stale_used and not demo_used:
            result["limitations"] = list(result.get("limitations", [])) + [
                "Stale imagery (captured beyond policy age or unverifiable) contributed "
                "to evidence; stale evidence is not used to justify a recommendation (Rule 9)."
            ]
        return result

    def _build_comparison(self, routes: List[Dict[str, Any]],
                          assessed_at: Optional[str] = None) -> Dict[str, Any]:
        """Delegate ranking/recommendation to the deterministic RouteComparer (PHASE_25).

        The comparer only compares already-computed deterministic scores; it never
        calculates or alters a score (Rule 7) and never recommends using demo
        imagery, insufficient coverage, or a tie (Rules 9, 12, 14, 20).
        """
        return self.comparer.build(routes, assessed_at=assessed_at)

    def _overall_status(self, routes: List[Dict[str, Any]]) -> str:
        if not routes or all(r.get("route_score") is None for r in routes):
            return "unassessed"
        if any(r.get("route_score") is None or r.get("status") == "partially_assessed" for r in routes):
            return "partially_assessed"
        return "assessed"
