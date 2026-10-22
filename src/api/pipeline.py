"""SafeRoute AI — Safety Analysis Pipeline orchestration (PHASE_16).

Orchestrates: routing -> imagery -> preprocessing -> detection -> aggregation ->
deterministic risk -> comparison -> grounded explanation.

All structured calculations happen here/backend-side. The risk engine owns scores
(Rule 7); facilities never enter the score (Rule 11); the LLM only explains (Rule 12).
"""

import dataclasses
import os
import threading
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

        # PHASE_31: the per-request detection memo (PHASE_27) is complemented by
        # a process-wide memo keyed on the IMAGE FILE IDENTITY (path, size,
        # mtime), the detector version and its inference parameters. Repeating an
        # analysis of the same corridor therefore does not re-run YOLO on frames
        # it has already inferred: identical bytes + identical weights/params
        # produce identical detections by construction. A key that cannot be
        # verified (missing file, changed file, changed config) always falls
        # through to a real inference, so this can never invent evidence
        # (Rules 7, 9, 10).
        self.DETECTION_MEMO_MAX_ENTRIES = 4096
        self._detection_memo: Dict[tuple, Any] = {}
        self._detection_memo_lock = threading.Lock()

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
            # PHASE_30: every routing provider that actually contributed a
            # route to this analysis (e.g. "osrm" and "valhalla").
            "providers": list(resp.providers),
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
            record["route_explanations"] = {}
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
        # PHASE_31: the analysis-level explanation and the per-route explanations
        # are independent jobs over the same verified record, so they are issued
        # together instead of one after the other. Each job still runs the same
        # grounded call and the same validation; only the schedule changed, so a
        # route's text can never depend on another job's outcome (Rules 7, 9, 12).
        (record["explanation"], record["route_explanations"],
         explanation_ms, route_explanations_ms) = self._build_explanations(record)

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
            "route_explanations_ms": round(route_explanations_ms, 1),
            "total_ms": round((time.perf_counter() - t_total) * 1000.0, 1),
        }
        return record

    def _build_explanations(self, record: Dict[str, Any]):
        """Produce the analysis-level and per-route explanations concurrently.

        Returns ``(explanation, route_explanations, explanation_ms,
        route_explanations_ms)`` where each duration is the wall time of that
        job itself. The two jobs share no mutable state: ``explain`` owns the
        analysis-level diagnostics and ``explain_route`` never touches them, so
        running them together cannot change either result (Rules 7, 12).
        """

        def _analysis_job():
            start = time.perf_counter()
            result = self.explainer.explain(record).to_dict()
            return result, (time.perf_counter() - start) * 1000.0

        def _routes_job():
            start = time.perf_counter()
            result = self._build_route_explanations(record)
            return result, (time.perf_counter() - start) * 1000.0

        with ThreadPoolExecutor(max_workers=2) as pool:
            analysis_future = pool.submit(_analysis_job)
            routes_future = pool.submit(_routes_job)
            explanation, explanation_ms = analysis_future.result()
            route_explanations, route_explanations_ms = routes_future.result()
        return explanation, route_explanations, explanation_ms, route_explanations_ms

    def _build_route_explanations(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Return one grounded explanation per analysed route (PHASE_30).

        The explanations are produced from the SAME verified route records the
        risk engine scored, so they can never claim a score, hazard or evidence
        the backend did not produce (Rules 7, 12). Each route is explained
        independently and concurrently — one route's explanation never depends
        on another route's — so a slow local model cannot reorder or alter the
        assessed routes (Rule 10).
        """
        routes = list(record.get("routes") or [])
        if not routes:
            return {}

        context: Dict[str, Any] = {
            "analysis_id": record.get("analysis_id"),
            "model_version": record.get("model_version"),
            "config_hash": record.get("config_hash"),
            "status": record.get("status"),
            "created_at": record.get("created_at"),
            "limitations": list(record.get("limitations") or []),
            "comparison": record.get("comparison") or {},
        }

        def _explain_one(route: Dict[str, Any]):
            try:
                return self.explainer.explain_route(route, context=context)
            except Exception:  # noqa: BLE001 - a route never breaks the analysis
                return None

        if len(routes) > 1:
            with ThreadPoolExecutor(max_workers=min(4, len(routes))) as pool:
                results = list(pool.map(_explain_one, routes))
        else:
            results = [_explain_one(routes[0])]

        explanations: Dict[str, Any] = {}
        for route, result in zip(routes, results):
            route_id = route.get("route_id")
            if not route_id:
                continue
            if result is not None:
                explanations[route_id] = result.to_dict()
            else:
                explanations[route_id] = {
                    "analysis_id": str(record.get("analysis_id", "")),
                    "explanation": (
                        "The backend could not produce an explanation for this route."
                    ),
                    "referenced_routes": [route_id],
                    "referenced_hazards": [],
                    "disclosures": ["explanation_unavailable"],
                    "source": "unavailable",
                }
        return explanations

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

    def _detection_memo_key(self, detector, file_path: str, image_id) -> Optional[tuple]:
        """Identity a cached inference may be reused for, or None to skip the memo.

        The file's size and nanosecond mtime identify the exact bytes that were
        inferred (a rewritten/replaced JPEG always produces a new key), and the
        detector version + inference parameters identify the exact model
        configuration. Nothing that could change a detection is omitted, so a
        hit is evidence-equivalent to re-running inference (Rules 7, 9).
        """
        try:
            stat = os.stat(file_path)
        except (OSError, TypeError, ValueError):
            return None
        return (
            str(file_path),
            int(stat.st_size),
            int(stat.st_mtime_ns),
            str(image_id),
            type(detector).__name__,
            str(getattr(detector, "model_version", "")),
            getattr(detector, "imgsz", None),
            getattr(detector, "conf_threshold", None),
            getattr(detector, "iou_threshold", getattr(detector, "iou", None)),
            getattr(detector, "max_det", None),
            getattr(detector, "augment", None),
            getattr(detector, "batch", None),
            str(getattr(detector, "checkpoint_path", "")),
            str(getattr(detector, "device", None)),
        )

    def _detect_with_memo(self, detector, img, route_id: str, segment_id: str):
        """Infer one image, reusing an identical prior inference when possible.

        Results are copied out of the memo so a caller can never mutate the
        cached record (the pipeline re-stamps route/segment identifiers on the
        copy). A miss always runs the real detector.
        """
        key = self._detection_memo_key(detector, str(img.file_path), img.image_id)
        if key is not None:
            with self._detection_memo_lock:
                cached = self._detection_memo.get(key)
            if cached is not None:
                return dataclasses.replace(cached, detections=list(cached.detections))

        result = detector.detect(
            img.file_path, image_id=img.image_id,
            route_id=route_id, segment_id=segment_id)

        if key is not None:
            with self._detection_memo_lock:
                if len(self._detection_memo) >= self.DETECTION_MEMO_MAX_ENTRIES:
                    # FIFO eviction: the oldest key is the least likely to be
                    # reused for the corridor currently being analysed.
                    self._detection_memo.pop(next(iter(self._detection_memo)), None)
                self._detection_memo[key] = dataclasses.replace(
                    result, detections=list(result.detections))
        return result

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
                        cached = self._detect_with_memo(detector, img, route.route_id, seg.segment_id)
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
        # PHASE_30: per-class hazard counts, derived from the SAME detection
        # records the risk engine scored. Purely additive bookkeeping — it
        # never changes a score (Rule 7) and never invents a detection.
        hazard_counts: Dict[str, int] = {}
        for hazard in hazard_records:
            hazard_class = hazard.get("hazard_class")
            if not isinstance(hazard_class, str) or not hazard_class:
                continue
            hazard_counts[hazard_class] = hazard_counts.get(hazard_class, 0) + 1
        result["hazard_counts"] = hazard_counts
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
