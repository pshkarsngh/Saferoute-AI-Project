"""SafeRoute AI — Pure Deterministic Risk Engine.

Engine Version: risk-v1
Phase ID: PHASE_12
Follows: TRD §9, ARCHITECTURE §7, master_rules.md Rules 7, 9, 11, 12, 17.
"""

import math
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from src.risk.aggregate import deduplicate_adjacent_segment_hazards
from src.risk.schemas import (
    AssessmentStatus,
    CoverageInfo,
    HazardRecord,
    SegmentAssessment,
    SegmentScoreResult,
    RouteSafetyResult,
)

DEFAULT_ENGINE_CONFIG = Path("config/risk_engine.yaml")


def compute_config_hash(config_path: Path) -> str:
    """Compute SHA-256 hash of configuration file for traceability (Rule 17)."""
    h = hashlib.sha256()
    with open(config_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


class DeterministicRiskEngine:
    """Pure, unit-testable deterministic risk and safety scoring engine.
    
    Hard constraints:
    - Sole owner of safety score computation (Rule 7).
    - Pure function: identical inputs -> identical outputs.
    - Zero LLM involvement (Rule 12).
    - Facility data must not enter the score (Rule 11).
    - Missing imagery is never zero risk; unassessed segments never yield safe scores (Rule 9).
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None, config_dict: Optional[Dict[str, Any]] = None):
        if config_dict is not None:
            self.config = config_dict
            self.config_hash = "IN_MEMORY_CONFIG"
        else:
            if config_path is None:
                workspace_root = Path(__file__).resolve().parent.parent.parent
                config_path = (workspace_root / DEFAULT_ENGINE_CONFIG).resolve()
            else:
                config_path = Path(config_path).resolve()

            if not config_path.is_file():
                raise FileNotFoundError(f"Risk engine configuration not found at {config_path}")

            self.config_hash = compute_config_hash(config_path)
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)

        # Mathematical parameters (TRD §9.1)
        s_cfg = self.config.get("scoring", {})
        self.lambda_decay = float(s_cfg.get("lambda_decay", 0.10))
        self.min_score = float(s_cfg.get("min_score", 0.0))
        self.max_score = float(s_cfg.get("max_score", 100.0))
        self.min_length_km = float(s_cfg.get("min_segment_length_km", 0.10))
        self.default_length_m = float(s_cfg.get("default_segment_length_m", 100.0))

        # Coverage policies (Rule 9)
        c_cfg = self.config.get("coverage_policy", {})
        self.min_coverage_threshold = float(c_cfg.get("min_coverage_threshold", 0.50))
        self.full_coverage_threshold = float(c_cfg.get("full_coverage_threshold", 0.90))
        self.suppress_insufficient = bool(c_cfg.get("suppress_insufficient_coverage", True))

        self.engine_version = self.config.get("metadata", {}).get("engine_version", "risk-v1")
        self.model_version = self.config.get("metadata", {}).get("model_version", "saferoute-yolo11-v1")

        # PHASE_23B: cross-segment de-duplication policy (TRD §9.4 / ARCHITECTURE §7).
        hm_cfg = self.config.get("hazard_metric", {}) or {}
        self.dedup_adjacent_segments = bool(hm_cfg.get("dedup_adjacent_segments", True))
        self.adjacent_boundary_iou = float(hm_cfg.get("adjacent_boundary_iou", 0.50))

    def compute_hazard_density(self, aggregate_hazard: float, length_m: float) -> float:
        """Calculate normalized hazard density H_i per kilometer.
        
        Formula:
            H_i = sum(severities) / max(length_meters / 1000.0, min_segment_length_km)
        """
        length_km = max(float(length_m) / 1000.0, self.min_length_km)
        h_density = max(0.0, float(aggregate_hazard)) / length_km
        return round(float(h_density), 4)

    def compute_safety_score_formula(self, h_density: float) -> float:
        """Evaluate candidate score formula S_i = 100 * exp(-lambda * H_i).
        
        Properties:
            - H_i = 0   -> S_i = 100.0
            - As H_i -> inf, S_i -> 0.0
            - Strictly bounded in [min_score, max_score]
        """
        decay_val = math.exp(-self.lambda_decay * max(0.0, float(h_density)))
        raw_score = 100.0 * decay_val
        bounded_score = max(self.min_score, min(self.max_score, raw_score))
        return round(float(bounded_score), 2)

    def score_segment(
        self,
        assessment: SegmentAssessment,
        length_m: Optional[float] = None,
    ) -> SegmentScoreResult:
        """Compute deterministic safety score for a single route segment.
        
        Strict Rule 9 enforcement:
        - Unassessed or failed segments produce NO score (None), with suppression flag set.
        - Insufficient coverage (< 50%) suppresses safe verdicts.
        """
        seg_length = float(length_m if length_m is not None else self.default_length_m)
        seg_length = max(1.0, seg_length)
        limitations = list(assessment.limitations)
        is_suppressed = False

        # Status inspection (Rule 9)
        if assessment.status == AssessmentStatus.UNASSESSED:
            limitations.append("Missing road imagery; segment safety cannot be assessed.")
            return SegmentScoreResult(
                segment_id=assessment.segment_id,
                model_version=self.model_version,
                length_m=seg_length,
                coverage=assessment.coverage,
                hazard_density_H=None,
                segment_score=None,
                status=AssessmentStatus.UNASSESSED,
                is_suppressed=True,
                limitations=limitations,
            )

        if assessment.status == AssessmentStatus.FAILED:
            limitations.append("Imagery acquisition or detection failed; score unavailable.")
            return SegmentScoreResult(
                segment_id=assessment.segment_id,
                model_version=self.model_version,
                length_m=seg_length,
                coverage=assessment.coverage,
                hazard_density_H=None,
                segment_score=None,
                status=AssessmentStatus.FAILED,
                is_suppressed=True,
                limitations=limitations,
            )

        # Calculate hazard density H_i and raw score S_i
        h_density = self.compute_hazard_density(assessment.aggregate_hazard, seg_length)
        score_val = self.compute_safety_score_formula(h_density)

        # Check coverage sufficiency
        if self.suppress_insufficient and assessment.coverage.fraction < self.min_coverage_threshold:
            is_suppressed = True
            limitations.append(
                f"Insufficient imagery coverage ({assessment.coverage.fraction:.1%} < {self.min_coverage_threshold:.0%}); "
                f"safe verdict is suppressed."
            )

        return SegmentScoreResult(
            segment_id=assessment.segment_id,
            model_version=self.model_version,
            length_m=seg_length,
            coverage=assessment.coverage,
            hazard_density_H=h_density,
            segment_score=score_val,
            status=assessment.status,
            is_suppressed=is_suppressed,
            limitations=limitations,
        )

    def score_route(
        self,
        route_id: str,
        segment_assessments: List[SegmentAssessment],
        segment_lengths_m: Optional[List[float]] = None,
    ) -> RouteSafetyResult:
        """Compute length-weighted route safety score across all segments.
        
        Pure function: Identical assessments + lengths -> identical output.
        """
        if not segment_assessments:
            empty_cov = CoverageInfo(images_total=0, images_used=0, fraction=0.0)
            return RouteSafetyResult(
                route_id=route_id,
                model_version=self.model_version,
                route_score=None,
                coverage=empty_cov,
                config_hash=self.config_hash,
                status=AssessmentStatus.UNASSESSED,
                segment_scores=[],
                limitations=["Route contains no segments to evaluate."],
                hazards_total=0,
                detection_outcome="unassessed",
                safety_note="Route has no segments to evaluate; safety is unassessed.",
            )

        # PHASE_23B: apply the declared cross-segment de-duplication policy so the
        # same image's hazard is not double-counted across adjacent segments.
        assessments = list(segment_assessments)
        dedup_count = 0
        if self.dedup_adjacent_segments:
            assessments, dedup_count = deduplicate_adjacent_segment_hazards(
                assessments, self.adjacent_boundary_iou)

        # Match lengths
        lengths = (
            list(segment_lengths_m)
            if segment_lengths_m and len(segment_lengths_m) == len(assessments)
            else [self.default_length_m] * len(assessments)
        )

        segment_scores: List[SegmentScoreResult] = []
        assessed_weighted_score_sum = 0.0
        assessed_length_sum = 0.0
        total_length_sum = 0.0
        total_images_all = 0
        used_images_all = 0
        route_limitations: List[str] = []
        if dedup_count:
            route_limitations.append(
                f"Deduplicated {dedup_count} cross-segment duplicate hazard(s) "
                f"sharing image identity across adjacent segments."
            )

        has_partial = False
        has_unassessed = False
        has_failed = False

        for asm, length in zip(assessments, lengths):
            seg_res = self.score_segment(asm, length)
            segment_scores.append(seg_res)

            total_length_sum += seg_res.length_m
            total_images_all += asm.coverage.images_total
            used_images_all += asm.coverage.images_used

            if seg_res.status == AssessmentStatus.UNASSESSED:
                has_unassessed = True
            elif seg_res.status == AssessmentStatus.FAILED:
                has_failed = True
            elif seg_res.status == AssessmentStatus.PARTIALLY_ASSESSED:
                has_partial = True

            # Include valid, scored segments in length-weighted tally
            if seg_res.segment_score is not None:
                assessed_weighted_score_sum += seg_res.length_m * seg_res.segment_score
                assessed_length_sum += seg_res.length_m

        # Compute route coverage fraction
        route_fraction = float(used_images_all / max(1, total_images_all)) if total_images_all > 0 else 0.0
        route_coverage = CoverageInfo(
            images_total=total_images_all,
            images_used=used_images_all,
            fraction=route_fraction,
        )

        # Calculate length-weighted route score
        if assessed_length_sum > 0.0:
            final_route_score = round(assessed_weighted_score_sum / assessed_length_sum, 2)
        else:
            final_route_score = None

        # Route status classification
        if assessed_length_sum == 0.0:
            if has_failed and not has_unassessed:
                route_status = AssessmentStatus.FAILED
                route_limitations.append("All segments on this route failed imagery acquisition or decode.")
            else:
                route_status = AssessmentStatus.UNASSESSED
                route_limitations.append("Route has zero imagery coverage; safety score is unassessed (Rule 9).")
        elif has_unassessed or has_partial or has_failed or route_fraction < self.full_coverage_threshold:
            route_status = AssessmentStatus.PARTIALLY_ASSESSED
            route_limitations.append(
                f"Partial route coverage ({route_fraction:.1%} covered); unassessed segments omitted from hazard score."
            )
        else:
            route_status = AssessmentStatus.ASSESSED

        # PHASE_22: explicit detection outcome so a zero-hazard result (score 100)
        # is never presented as proof of a safe road (Rule 9).
        hazards_total = sum(
            len(asm.hazards)
            for asm, sr in zip(assessments, segment_scores)
            if sr.segment_score is not None
        )
        if route_status == AssessmentStatus.FAILED:
            outcome = "detector_failed"
            note = ("Detection failed on this route; no safety conclusion is possible.")
        elif route_status == AssessmentStatus.UNASSESSED:
            outcome = "unassessed"
            note = ("No assessable imagery for this route; road safety is unassessed "
                    "(missing evidence is not proof of safety).")
        elif hazards_total > 0:
            outcome = "hazards_detected"
            note = ("Supported hazards were detected on assessed segments; the score "
                    "reflects verified detections.")
        elif route_status == AssessmentStatus.PARTIALLY_ASSESSED or route_fraction < 1.0:
            outcome = "insufficient_coverage"
            note = ("Only part of the route had assessable imagery; the unassessed "
                    "remainder must NOT be treated as safe.")
        else:
            outcome = "no_hazards_detected"
            note = ("Imagery was assessed and no supported hazards were detected. "
                    "This is NOT proof that the road is safe (Rule 9) — only that the "
                    "detector found none in the available imagery.")

        return RouteSafetyResult(
            route_id=route_id,
            model_version=self.model_version,
            route_score=final_route_score,
            coverage=route_coverage,
            config_hash=self.config_hash,
            status=route_status,
            segment_scores=segment_scores,
            limitations=route_limitations,
            hazards_total=hazards_total,
            detection_outcome=outcome,
            safety_note=note,
        )
