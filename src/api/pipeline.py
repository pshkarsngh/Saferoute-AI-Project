"""SafeRoute AI — Safety Analysis Pipeline orchestration (PHASE_16).

Orchestrates: routing -> imagery -> preprocessing -> detection -> aggregation ->
deterministic risk -> comparison -> grounded explanation.

All structured calculations happen here/backend-side. The risk engine owns scores
(Rule 7); facilities never enter the score (Rule 11); the LLM only explains (Rule 12).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config.thresholds import assert_threshold_consistency
from src.facilities.service import FacilitiesService
from src.imagery.adapter import PermittedImageryAdapter
from src.llm.explainer import GroundedExplanationService
from src.risk.aggregate import HazardAggregator, deduplicate_adjacent_segment_hazards
from src.risk.engine import DeterministicRiskEngine
from src.risk.schemas import AssessmentStatus
from src.routing.adapter import create_routing_adapter
from src.routing.schemas import Coordinate, RouteRequest, RoutingStatus

MODEL_VERSION = "saferoute-yolo11-v1"


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
    ):
        self.routing = routing_provider or create_routing_adapter("mock")
        self.imagery = imagery_adapter or PermittedImageryAdapter()
        self._detector = detector
        self.aggregator = aggregator or HazardAggregator()
        self.engine = engine or DeterministicRiskEngine()
        self.facilities = facilities_service or FacilitiesService()
        self.explainer = explainer or GroundedExplanationService()
        self.model_version = MODEL_VERSION
        self.config_hash = self.engine.config_hash

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
        analysis_id = "an-" + uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        resp = self.routing.get_routes(RouteRequest(origin=origin, destination=destination))

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
            record["explanation"] = self.explainer.explain(record).to_dict()
            return record

        for route in resp.routes:
            record["routes"].append(self._analyze_route(route))

        record["comparison"] = self._build_comparison(record["routes"])
        record["recommendation"] = record["comparison"]["recommended_route_id"]
        record["status"] = self._overall_status(record["routes"])
        record["explanation"] = self.explainer.explain(record).to_dict()
        return record

    def _analyze_route(self, route) -> Dict[str, Any]:
        segment_assessments = []
        lengths: List[float] = []
        imagery_meta: List[Dict[str, Any]] = []
        hazard_records: List[Dict[str, Any]] = []

        for seg in route.segments:
            imagery = self.imagery.get_imagery_for_segment(seg)
            image_results = []
            expected = 0
            if imagery.is_available:
                detector = self._get_detector()
                for img in imagery.images:
                    image_results.append(detector.detect(
                        img.file_path, image_id=img.image_id,
                        route_id=route.route_id, segment_id=seg.segment_id))
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

        result = self.engine.score_route(route.route_id, segment_assessments, lengths).to_dict()
        result["provider"] = route.provider
        result["summary"] = route.summary
        result["distance_m"] = route.distance_m
        result["duration_s"] = route.duration_s
        result["geometry"] = route.geometry.to_dict()
        result["segments"] = [s.to_dict() for s in route.segments]
        result["hazards"] = hazard_records
        result["imagery"] = imagery_meta
        return result

    def _build_comparison(self, routes: List[Dict[str, Any]]) -> Dict[str, Any]:
        assessed = [r for r in routes if r.get("route_score") is not None]
        unassessed = [r for r in routes if r.get("route_score") is None]
        ranked = sorted(assessed, key=lambda r: r["route_score"], reverse=True)
        return {
            "ranking": [
                {"route_id": r["route_id"], "route_score": r["route_score"],
                 "status": r["status"], "coverage": r.get("coverage"), "distance_m": r.get("distance_m"),
                 "hazards_total": r.get("hazards_total", 0),
                 "detection_outcome": r.get("detection_outcome", "unassessed"),
                 "safety_note": r.get("safety_note", "")}
                for r in ranked
            ],
            "recommended_route_id": ranked[0]["route_id"] if ranked else None,
            "unassessed_route_ids": [r["route_id"] for r in unassessed],
            "note": ("Unassessed routes are never ranked or presented as safe (Rule 9). "
                     "A score of 100 means no supported hazard was detected in the "
                     "available imagery — it is NOT proof the road is safe."),
        }

    def _overall_status(self, routes: List[Dict[str, Any]]) -> str:
        if not routes or all(r.get("route_score") is None for r in routes):
            return "unassessed"
        if any(r.get("route_score") is None or r.get("status") == "partially_assessed" for r in routes):
            return "partially_assessed"
        return "assessed"
