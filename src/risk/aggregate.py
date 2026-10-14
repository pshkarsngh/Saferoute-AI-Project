"""SafeRoute AI — Hazard Aggregation & De-duplication Engine.

Phase ID: PHASE_11
Policy Version: severity-v1
Follows: TRD §8, ARCHITECTURE §7, master_rules.md Rules 5, 7, 9, 12, 14.
"""

from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict

from src.detection.schemas import DetectionRecord, ImageDetectionResult
from src.risk.schemas import (
    AssessmentStatus,
    CoverageInfo,
    HazardRecord,
    SegmentAssessment,
)
from src.risk.severity import SeverityPolicy


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """Compute Intersection-over-Union (IoU) of two bounding boxes [x1, y1, x2, y2]."""
    x_a = max(box1[0], box2[0])
    y_a = max(box1[1], box2[1])
    x_b = min(box1[2], box2[2])
    y_b = min(box1[3], box2[3])

    inter_w = max(0.0, x_b - x_a)
    inter_h = max(0.0, y_b - y_a)
    inter_area = inter_w * inter_h

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 1e-9:
        return 0.0
    return float(inter_area / union_area)


def _boxes_equivalent(box1: List[float], box2: List[float], tol: float = 1e-6) -> bool:
    """True when two bounding boxes are identical (handles degenerate/zero boxes)."""
    if len(box1) != 4 or len(box2) != 4:
        return False
    return all(abs(float(a) - float(b)) <= tol for a, b in zip(box1, box2))


def deduplicate_adjacent_segment_hazards(
    assessments: List["SegmentAssessment"],
    iou_threshold: float = 0.50,
) -> Tuple[List["SegmentAssessment"], int]:
    """Remove cross-segment duplicate hazards that share image identity.

    Implements the declared ``hazard_metric.dedup_adjacent_segments`` /
    ``adjacent_boundary_iou`` policy (TRD §9.4, ARCHITECTURE §7): the *same
    physical hazard* — identified by the same source ``image_id`` and hazard
    class, with an equivalent or IoU-overlapping bounding box — must not be
    counted again when it also falls within the buffer of an adjacent segment.

    Behaviour:
    - Segments are processed in route order; the first occurrence of an image
      hazard is retained and later identical occurrences are dropped.
    - Hazards with no ``image_id`` cannot be identified and are always retained
      (distinct unknown hazards are never silently discarded).
    - Distinct hazards on the same image (different class or non-overlapping
      boxes) are preserved.
    - Removed severity is subtracted from the owning segment's
      ``aggregate_hazard`` so scoring semantics are unchanged apart from the
      duplicate removal.

    This is a pure function: inputs are not mutated; changed segments are copied.

    Returns:
        (assessments, deduplicated_count)
    """
    seen: List[Tuple[str, str, List[float]]] = []
    result: List["SegmentAssessment"] = []
    dedup_count = 0

    for asm in assessments:
        kept: List[HazardRecord] = []
        removed_severity = 0.0
        removed_here = 0

        for hazard in asm.hazards:
            image_id = (hazard.image_id or "").strip()
            is_duplicate = False
            if image_id:
                for seen_id, seen_class, seen_box in seen:
                    if seen_id != image_id or seen_class != hazard.hazard_class:
                        continue
                    if _boxes_equivalent(seen_box, hazard.bbox_xyxy) or \
                            compute_iou(seen_box, hazard.bbox_xyxy) >= iou_threshold:
                        is_duplicate = True
                        break

            if is_duplicate:
                removed_severity += float(hazard.severity)
                removed_here += 1
                dedup_count += 1
                continue

            if image_id:
                seen.append((image_id, hazard.hazard_class, list(hazard.bbox_xyxy)))
            kept.append(hazard)

        if removed_here:
            new_limitations = list(asm.limitations) + [
                f"cross_segment_duplicate_hazards_deduplicated_{removed_here}"
            ]
            result.append(replace(
                asm,
                hazards=kept,
                aggregate_hazard=max(0.0, float(asm.aggregate_hazard) - removed_severity),
                limitations=new_limitations,
            ))
        else:
            result.append(asm)

    return result, dedup_count


class HazardAggregator:
    """Aggregates raw detections, applies confidence filtering & de-duplication,
    assigns deterministic severity, and constructs segment hazard assessments.
    
    Hard constraints:
    - Never computes route safety scores (Rule 7, Rule 12).
    - Missing imagery is never zero risk; unassessed segments are marked explicitly (Rule 9).
    - De-duplication rule is strictly configurable and transparent (TRD §8.3).
    """

    def __init__(self, policy: Optional[SeverityPolicy] = None):
        self.policy = policy if policy is not None else SeverityPolicy()

    def deduplicate_detections(
        self,
        detections: List[DetectionRecord],
        iou_threshold: Optional[float] = None,
    ) -> List[DetectionRecord]:
        """Apply spatial IoU de-duplication to detections within an image of the same class.
        
        Tie-break rule: When two detections of the same hazard class have IoU > threshold,
        retain the detection with the higher confidence score.
        """
        threshold = iou_threshold if iou_threshold is not None else self.policy.dedup_iou_threshold

        if not detections:
            return []

        # Group detections by hazard class
        by_class: Dict[str, List[DetectionRecord]] = defaultdict(list)
        for det in detections:
            by_class[det.hazard_class].append(det)

        deduplicated: List[DetectionRecord] = []

        for hazard_cls, class_dets in by_class.items():
            # Sort descending by confidence
            sorted_dets = sorted(class_dets, key=lambda d: d.confidence, reverse=True)
            keep: List[DetectionRecord] = []

            for candidate in sorted_dets:
                overlap = False
                for retained in keep:
                    # Compare pixel bounding boxes (or normalized)
                    iou = compute_iou(candidate.bbox_xyxy, retained.bbox_xyxy)
                    if iou >= threshold:
                        overlap = True
                        break
                if not overlap:
                    keep.append(candidate)

            deduplicated.extend(keep)

        return deduplicated

    def process_detection(self, detection: DetectionRecord) -> Optional[HazardRecord]:
        """Filter a single detection by confidence and convert to a HazardRecord."""
        if detection.confidence < self.policy.confidence_threshold:
            return None

        # Calculate bounded severity
        severity = self.policy.calculate_severity(
            hazard_class=detection.hazard_class,
            confidence=detection.confidence,
            bbox_norm=detection.bbox_norm,
        )

        return HazardRecord(
            model_version=detection.model_version,
            image_id=detection.image_id,
            route_id=detection.route_id,
            segment_id=detection.segment_id,
            hazard_class=detection.hazard_class,
            confidence=detection.confidence,
            bbox_xyxy=detection.bbox_xyxy,
            bbox_norm=detection.bbox_norm,
            severity=severity,
            status="assessed",
            error=detection.error,
        )

    def process_image_detections(
        self,
        image_result: ImageDetectionResult,
        apply_dedup: bool = True,
    ) -> List[HazardRecord]:
        """Process all detections from an image result into deduplicated HazardRecords."""
        if not image_result.detections:
            return []

        # 1. Filter by confidence
        filtered = [d for d in image_result.detections if d.confidence >= self.policy.confidence_threshold]

        # 2. De-duplicate overlapping boxes
        if apply_dedup and len(filtered) > 1:
            filtered = self.deduplicate_detections(filtered)

        # 3. Transform to HazardRecords with assigned severity
        hazard_records: List[HazardRecord] = []
        for det in filtered:
            record = self.process_detection(det)
            if record is not None:
                hazard_records.append(record)

        return hazard_records

    def assess_segment(
        self,
        segment_id: str,
        image_results: List[ImageDetectionResult],
        expected_image_count: int,
        route_id: Optional[str] = None,
    ) -> SegmentAssessment:
        """Aggregate all image hazards across a route segment into a SegmentAssessment.
        
        Args:
            segment_id: Unique identifier of the segment.
            image_results: List of ImageDetectionResult objects processed for this segment.
            expected_image_count: Total road imagery expected/requested for the segment.
            route_id: Optional route identifier.
            
        Returns:
            SegmentAssessment conforming strictly to ARCHITECTURE §7.
        """
        model_version = self.policy.model_version
        limitations: List[str] = []

        # 1. Determine coverage counts
        total_images = max(0, int(expected_image_count))
        valid_results = [res for res in image_results if res.status in (
            res.status.SUCCESS,
            res.status.NO_DETECTIONS
        )]
        images_used = len(valid_results)
        images_failed = len([res for res in image_results if res.status in (
            res.status.INVALID_IMAGE,
            res.status.FAILED,
            res.status.MISSING_CHECKPOINT
        )])

        fraction = float(images_used / max(1, total_images)) if total_images > 0 else 0.0

        # 2. Status determination & Rule 9 missing imagery enforcement
        if total_images == 0 or (images_used == 0 and images_failed == 0):
            # No imagery available at all: strictly UNASSESSED (Rule 9: missing != safe)
            status = AssessmentStatus.UNASSESSED
            limitations.append("No road imagery available for this segment; road safety is unassessed.")
        elif images_used == 0 and images_failed > 0:
            # All imagery failed validation/decode
            status = AssessmentStatus.FAILED
            limitations.append(f"All {images_failed} segment image(s) failed decoding or inference.")
        elif fraction < 1.0 or images_failed > 0:
            # Partial coverage
            status = AssessmentStatus.PARTIALLY_ASSESSED
            limitations.append(
                f"Partial imagery coverage ({images_used}/{total_images} images, {images_failed} failed); "
                f"uncovered sections remain unassessed."
            )
        else:
            # Complete assessment
            status = AssessmentStatus.ASSESSED

        # 3. Aggregate hazards across all valid images
        all_hazards: List[HazardRecord] = []
        for res in valid_results:
            img_hazards = self.process_image_detections(res, apply_dedup=True)
            all_hazards.extend(img_hazards)

        # 4. Compute aggregate hazard load (Sum of severities — NOT a safety score!)
        aggregate_hazard = float(sum(h.severity for h in all_hazards))

        coverage_info = CoverageInfo(
            images_total=total_images,
            images_used=images_used,
            fraction=fraction,
        )

        return SegmentAssessment(
            segment_id=segment_id,
            route_id=route_id,
            model_version=model_version,
            coverage=coverage_info,
            hazards=all_hazards,
            aggregate_hazard=aggregate_hazard,
            status=status,
            limitations=limitations,
        )
