"""SafeRoute AI — Phase 42 offline ground-truth route replay.

This module deliberately *reuses* the production ``HazardAggregator`` and
``DeterministicRiskEngine`` unchanged. It answers a research question only:

    How much do detector errors change route scores, rankings, and research
    eligibility compared with manually verified ground truth?

It never writes to the risk engine, never changes the scoring formula, and its
eligibility rule is explicitly research-only. The production recommendation path
is untouched.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from src.detection.schemas import (
    DetectionRecord,
    DetectionStatus,
    ImageDetectionResult,
)
from src.risk.aggregate import HazardAggregator
from src.risk.engine import DeterministicRiskEngine

from .dataset_validation import DatasetImage, DatasetInventory
from .matching import GroundTruthBox, PredictionBox

RESEARCH_ELIGIBILITY_RULE = (
    "research_only: route status == 'assessed' AND route_score >= threshold; "
    "this does not alter production recommendation behaviour"
)


class RouteReplayError(ValueError):
    """Raised when route replay inputs are insufficient or ambiguous."""


@dataclass(frozen=True)
class RouteComparison:
    route_id: str
    segment_count: int
    predicted_score: Optional[float]
    ground_truth_score: Optional[float]
    score_delta: Optional[float]
    predicted_rank: Optional[int]
    ground_truth_rank: Optional[int]
    rank_change: Optional[int]
    predicted_status: str
    ground_truth_status: str
    predicted_eligible: bool
    ground_truth_eligible: bool
    prediction_changed_eligibility: bool
    predicted_hazard_count: int
    ground_truth_hazard_count: int
    predicted_coverage_fraction: float
    ground_truth_coverage_fraction: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "route_id": self.route_id,
            "segment_count": self.segment_count,
            "predicted_score": self.predicted_score,
            "ground_truth_score": self.ground_truth_score,
            "score_delta": self.score_delta,
            "predicted_rank": self.predicted_rank,
            "ground_truth_rank": self.ground_truth_rank,
            "rank_change": self.rank_change,
            "predicted_status": self.predicted_status,
            "ground_truth_status": self.ground_truth_status,
            "predicted_eligible": self.predicted_eligible,
            "ground_truth_eligible": self.ground_truth_eligible,
            "prediction_changed_eligibility": self.prediction_changed_eligibility,
            "predicted_hazard_count": self.predicted_hazard_count,
            "ground_truth_hazard_count": self.ground_truth_hazard_count,
            "predicted_coverage_fraction": self.predicted_coverage_fraction,
            "ground_truth_coverage_fraction": self.ground_truth_coverage_fraction,
        }


@dataclass(frozen=True)
class RouteReplayReport:
    routes: Mapping[str, RouteComparison]
    ranking_reversals: Tuple[Tuple[str, str], ...]
    rank_correlation: Optional[float]
    images_replayed: int
    images_total: int
    eligibility_threshold: float
    eligibility_rule: str
    caveats: Tuple[str, ...]

    @property
    def coverage_fraction(self) -> float:
        return float(self.images_replayed / max(1, self.images_total))

    @property
    def ranking_changed(self) -> bool:
        return bool(self.ranking_reversals) or any(
            route.rank_change not in (None, 0) for route in self.routes.values()
        )

    @property
    def eligibility_changed_routes(self) -> Tuple[str, ...]:
        return tuple(
            sorted(
                route_id
                for route_id, route in self.routes.items()
                if route.prediction_changed_eligibility
            )
        )

    @property
    def enough_evidence(self) -> bool:
        return self.images_total > 0 and self.images_replayed == self.images_total and bool(self.routes)

    def to_dict(self) -> Dict[str, object]:
        return {
            "routes": {route_id: route.to_dict() for route_id, route in self.routes.items()},
            "ranking_reversals": [list(pair) for pair in self.ranking_reversals],
            "rank_correlation": self.rank_correlation,
            "images_replayed": self.images_replayed,
            "images_total": self.images_total,
            "coverage_fraction": self.coverage_fraction,
            "eligibility_threshold": self.eligibility_threshold,
            "eligibility_rule": self.eligibility_rule,
            "eligibility_changed_routes": list(self.eligibility_changed_routes),
            "ranking_changed": self.ranking_changed,
            "enough_evidence": self.enough_evidence,
            "caveats": list(self.caveats),
        }


def _to_detection(
    *,
    model_version: str,
    image_id: str,
    route_id: str,
    segment_id: str,
    hazard_class: str,
    confidence: float,
    bbox_norm: Sequence[float],
) -> DetectionRecord:
    # IoU de-duplication inside the aggregator is scale-invariant; the pixel
    # fields are populated from the normalized box without altering geometry.
    return DetectionRecord(
        model_version=model_version,
        image_id=image_id,
        route_id=route_id,
        segment_id=segment_id,
        hazard_class=hazard_class,
        confidence=float(confidence),
        bbox_xyxy=[float(value) * 1000.0 for value in bbox_norm],
        bbox_norm=[float(value) for value in bbox_norm],
        status="detected",
    )


def _image_result(
    image: DatasetImage,
    detections: List[DetectionRecord],
    model_version: str,
) -> ImageDetectionResult:
    return ImageDetectionResult(
        model_version=model_version,
        pipeline_version="phase42-route-replay",
        status=DetectionStatus.SUCCESS if detections else DetectionStatus.NO_DETECTIONS,
        image_id=image.image_id,
        route_id=image.route_id,
        segment_id=image.segment_id,
        detections=detections,
    )


def _competition_ranks(
    scores: Mapping[str, Optional[float]],
) -> Dict[str, Optional[int]]:
    scored = [(route_id, score) for route_id, score in scores.items() if score is not None]
    scored.sort(key=lambda item: (-float(item[1]), item[0]))
    ranks: Dict[str, Optional[int]] = {route_id: None for route_id in scores}
    previous_score: Optional[float] = None
    previous_rank = 0
    for index, (route_id, score) in enumerate(scored, start=1):
        value = float(score)
        if previous_score is not None and math.isclose(value, previous_score, abs_tol=1e-9):
            ranks[route_id] = previous_rank
        else:
            ranks[route_id] = index
            previous_rank = index
            previous_score = value
    return ranks


def _average_ranks(values: Mapping[str, float]) -> Dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1])
    ranks: Dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and math.isclose(
            ordered[end + 1][1], ordered[index][1], abs_tol=1e-9
        ):
            end += 1
        average = (index + end) / 2.0 + 1.0
        for position in range(index, end + 1):
            ranks[ordered[position][0]] = average
        index = end + 1
    return ranks


def spearman_rank_correlation(
    left: Mapping[str, float],
    right: Mapping[str, float],
) -> Optional[float]:
    """Spearman correlation over the routes present in both mappings."""
    common = sorted(set(left) & set(right))
    if len(common) < 2:
        return None
    left_ranks = _average_ranks({key: float(left[key]) for key in common})
    right_ranks = _average_ranks({key: float(right[key]) for key in common})
    n = len(common)
    mean = (n + 1) / 2.0
    numerator = sum(
        (left_ranks[key] - mean) * (right_ranks[key] - mean) for key in common
    )
    denominator = math.sqrt(
        sum((left_ranks[key] - mean) ** 2 for key in common)
        * sum((right_ranks[key] - mean) ** 2 for key in common)
    )
    if denominator == 0.0:
        return None
    return float(numerator / denominator)


def _paired_reversals(
    predicted: Mapping[str, Optional[float]],
    ground_truth: Mapping[str, Optional[float]],
) -> Tuple[Tuple[str, str], ...]:
    routes = sorted(
        route_id
        for route_id in predicted
        if predicted.get(route_id) is not None and ground_truth.get(route_id) is not None
    )
    reversals: List[Tuple[str, str]] = []
    for index, left in enumerate(routes):
        for right in routes[index + 1 :]:
            pred_order = float(predicted[left]) - float(predicted[right])
            gt_order = float(ground_truth[left]) - float(ground_truth[right])
            if pred_order == 0.0 or gt_order == 0.0:
                continue
            if (pred_order > 0.0) != (gt_order > 0.0):
                reversals.append((left, right))
    return tuple(reversals)


def replay_routes(
    inventory: DatasetInventory,
    predictions_by_image: Mapping[str, Sequence[PredictionBox]],
    *,
    engine: Optional[DeterministicRiskEngine] = None,
    aggregator: Optional[HazardAggregator] = None,
    eligibility_min_score: float = 60.0,
) -> RouteReplayReport:
    """Compare predicted route outcomes against ground-truth route outcomes."""
    images_by_route: Dict[str, List[DatasetImage]] = {}
    for image in inventory.images:
        if not image.route_id or not image.segment_id:
            raise RouteReplayError(
                f"Image {image.image_id} has no route_id/segment_id metadata; "
                "route replay cannot group evidence into segments."
            )
        images_by_route.setdefault(image.route_id, []).append(image)
    if not images_by_route:
        raise RouteReplayError("No routes available for replay")

    engine = engine or DeterministicRiskEngine()
    aggregator = aggregator or HazardAggregator()
    gt_by_image = inventory.ground_truth_by_image()

    predicted_scores: Dict[str, Optional[float]] = {}
    gt_scores: Dict[str, Optional[float]] = {}
    predicted_status: Dict[str, str] = {}
    gt_status: Dict[str, str] = {}
    predicted_coverage: Dict[str, float] = {}
    gt_coverage: Dict[str, float] = {}
    predicted_hazards: Dict[str, int] = {}
    gt_hazards: Dict[str, int] = {}
    segment_counts: Dict[str, int] = {}

    for route_id, route_images in sorted(images_by_route.items()):
        segment_ids = sorted({image.segment_id for image in route_images})
        segment_counts[route_id] = len(segment_ids)

        predicted_assessments = []
        gt_assessments = []
        lengths: List[float] = []

        for segment_id in segment_ids:
            segment_images = [
                image for image in route_images if image.segment_id == segment_id
            ]
            length_m = segment_images[0].segment_length_m or engine.default_length_m
            lengths.append(float(length_m))

            pred_results: List[ImageDetectionResult] = []
            gt_results: List[ImageDetectionResult] = []
            for image in segment_images:
                assert image.route_id is not None and image.segment_id is not None
                pred_detections = [
                    _to_detection(
                        model_version="serving_detector",
                        image_id=image.image_id,
                        route_id=image.route_id,
                        segment_id=image.segment_id,
                        hazard_class=prediction.class_name,
                        confidence=prediction.confidence,
                        bbox_norm=prediction.bbox_norm,
                    )
                    for prediction in predictions_by_image.get(image.image_id, ())
                ]
                gt_detections = [
                    _to_detection(
                        model_version="verified_ground_truth",
                        image_id=image.image_id,
                        route_id=image.route_id,
                        segment_id=image.segment_id,
                        hazard_class=box.class_name,
                        confidence=1.0,
                        bbox_norm=box.bbox_norm,
                    )
                    for box in gt_by_image.get(image.image_id, ())
                ]
                pred_results.append(
                    _image_result(image, pred_detections, "serving_detector")
                )
                gt_results.append(
                    _image_result(image, gt_detections, "verified_ground_truth")
                )

            predicted_assessments.append(
                aggregator.assess_segment(
                    segment_id=segment_id,
                    image_results=pred_results,
                    expected_image_count=len(segment_images),
                    route_id=route_id,
                )
            )
            gt_assessments.append(
                aggregator.assess_segment(
                    segment_id=segment_id,
                    image_results=gt_results,
                    expected_image_count=len(segment_images),
                    route_id=route_id,
                )
            )

        pred_route = engine.score_route(route_id, predicted_assessments, lengths)
        gt_route = engine.score_route(route_id, gt_assessments, lengths)

        predicted_scores[route_id] = pred_route.route_score
        gt_scores[route_id] = gt_route.route_score
        predicted_status[route_id] = pred_route.status.value
        gt_status[route_id] = gt_route.status.value
        predicted_coverage[route_id] = pred_route.coverage.fraction
        gt_coverage[route_id] = gt_route.coverage.fraction
        predicted_hazards[route_id] = pred_route.hazards_total
        gt_hazards[route_id] = gt_route.hazards_total

    predicted_ranks = _competition_ranks(predicted_scores)
    gt_ranks = _competition_ranks(gt_scores)

    def eligible(score: Optional[float], status: str) -> bool:
        return (
            score is not None
            and status == "assessed"
            and float(score) >= float(eligibility_min_score)
        )

    routes: Dict[str, RouteComparison] = {}
    for route_id in sorted(images_by_route):
        pred_score = predicted_scores[route_id]
        gt_score = gt_scores[route_id]
        delta = (
            float(pred_score) - float(gt_score)
            if pred_score is not None and gt_score is not None
            else None
        )
        pred_rank = predicted_ranks.get(route_id)
        gt_rank = gt_ranks.get(route_id)
        pred_eligible = eligible(pred_score, predicted_status[route_id])
        gt_eligible = eligible(gt_score, gt_status[route_id])
        routes[route_id] = RouteComparison(
            route_id=route_id,
            segment_count=segment_counts[route_id],
            predicted_score=pred_score,
            ground_truth_score=gt_score,
            score_delta=delta,
            predicted_rank=pred_rank,
            ground_truth_rank=gt_rank,
            rank_change=(
                int(gt_rank) - int(pred_rank)
                if pred_rank is not None and gt_rank is not None
                else None
            ),
            predicted_status=predicted_status[route_id],
            ground_truth_status=gt_status[route_id],
            predicted_eligible=pred_eligible,
            ground_truth_eligible=gt_eligible,
            prediction_changed_eligibility=pred_eligible != gt_eligible,
            predicted_hazard_count=predicted_hazards[route_id],
            ground_truth_hazard_count=gt_hazards[route_id],
            predicted_coverage_fraction=predicted_coverage[route_id],
            ground_truth_coverage_fraction=gt_coverage[route_id],
        )

    comparable_predicted = {
        route_id: score
        for route_id, score in predicted_scores.items()
        if score is not None
    }
    comparable_gt = {
        route_id: score for route_id, score in gt_scores.items() if score is not None
    }

    return RouteReplayReport(
        routes=routes,
        ranking_reversals=_paired_reversals(predicted_scores, gt_scores),
        rank_correlation=spearman_rank_correlation(comparable_predicted, comparable_gt),
        images_replayed=len(inventory.images),
        images_total=len(inventory.images),
        eligibility_threshold=float(eligibility_min_score),
        eligibility_rule=RESEARCH_ELIGIBILITY_RULE,
        caveats=(
            "Offline research comparison only; src/risk/engine.py is unchanged.",
            "Research eligibility is not the production recommendation policy.",
            "Ground truth uses confidence 1.0 for severity assignment; predicted "
            "hazards use serving confidence, so score deltas include confidence "
            "calibration as well as missed/false hazards.",
            "Segment geometry is taken from dataset metadata; no route geometry "
            "is fabricated when metadata is absent.",
        ),
    )


__all__ = [
    "RESEARCH_ELIGIBILITY_RULE",
    "RouteComparison",
    "RouteReplayError",
    "RouteReplayReport",
    "replay_routes",
    "spearman_rank_correlation",
]
