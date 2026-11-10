"""SafeRoute AI — Phase 42 ground-truth matching.

Pure geometry and one-to-one assignment. This module contains no risk logic and
no model loading, so it is fully unit-testable without a checkpoint or dataset.

Matching policy
---------------
* Predictions are considered in descending confidence order (deterministic
  tie-break on input order).
* A prediction may only match a ground-truth box of the **same class**.
* A ground-truth box may be matched at most once.
* The best (highest IoU) still-unmatched ground truth above the threshold wins.
* Predictions without a match are false positives; unmatched ground truth is
  false negatives.

All boxes are ``[x1, y1, x2, y2]`` normalized to the **original** image. The
production detector rescales letterbox padding away before populating
``DetectionRecord.bbox_norm``, so no further coordinate conversion is applied
here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# COCO-style IoU sweep used for AP50-95.
IOU_THRESHOLDS: Tuple[float, ...] = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))

Box = Tuple[float, float, float, float]


class BoxValidationError(ValueError):
    """Raised when a bounding box is malformed or non-normalized."""


class MatchingError(ValueError):
    """Raised when the prediction/ground-truth image sets are inconsistent."""


def _as_float(value: object, field: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise BoxValidationError(f"{field} is not numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise BoxValidationError(f"{field} is not finite: {value!r}")
    return number


def validate_bbox_norm(
    box: Sequence[float],
    *,
    label: str = "bbox_norm",
    boundary_tolerance: float = 0.0,
) -> Box:
    """Validate and freeze a normalized ``[x1, y1, x2, y2]`` box.

    Rejects wrong lengths, non-finite values, out-of-range coordinates, zero
    area, and inverted corners.

    ``boundary_tolerance`` exists only for human labels whose center/size
    encoding rounds a boundary-touching box a fraction outside ``[0, 1]``.
    Coordinates within the tolerance are clamped to the image boundary; anything
    beyond it is still rejected. Production predictions use the strict default
    (``0.0``) because the serving detector already clips to ``[0, 1]``.
    """
    if boundary_tolerance < 0.0 or boundary_tolerance > 0.05:
        raise BoxValidationError(
            f"boundary_tolerance must be in [0, 0.05], got {boundary_tolerance}"
        )
    if box is None or len(box) != 4:
        raise BoxValidationError(f"{label} must have exactly 4 values, got {box!r}")
    x1 = _as_float(box[0], f"{label}[0]")
    y1 = _as_float(box[1], f"{label}[1]")
    x2 = _as_float(box[2], f"{label}[2]")
    y2 = _as_float(box[3], f"{label}[3]")

    lower = -boundary_tolerance
    upper = 1.0 + boundary_tolerance
    for name, value in (("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2)):
        if value < lower or value > upper:
            raise BoxValidationError(
                f"{label}.{name}={value} is outside normalized range [0, 1] "
                f"(tolerance {boundary_tolerance})"
            )
    # Clamp only the allowed rounding overshoot; never a larger excursion.
    x1 = min(1.0, max(0.0, x1))
    y1 = min(1.0, max(0.0, y1))
    x2 = min(1.0, max(0.0, x2))
    y2 = min(1.0, max(0.0, y2))
    if x2 <= x1 or y2 <= y1:
        raise BoxValidationError(
            f"{label} must satisfy x2>x1 and y2>y1, got {box!r}"
        )
    return (x1, y1, x2, y2)


def compute_iou(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    """Return intersection-over-union for two valid normalized boxes."""

    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return float(inter / union)


@dataclass(frozen=True)
class GroundTruthBox:
    """One annotated hazard box in a specific image."""

    image_id: str
    class_name: str
    bbox_norm: Box
    session_id: Optional[str] = None
    condition: Optional[str] = None
    route_id: Optional[str] = None
    segment_id: Optional[str] = None
    image_path: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox_norm", validate_bbox_norm(self.bbox_norm))
        if not self.class_name:
            raise BoxValidationError("GroundTruthBox.class_name must not be empty")


@dataclass(frozen=True)
class PredictionBox:
    """One serving-pipeline prediction in a specific image."""

    image_id: str
    class_name: str
    confidence: float
    bbox_norm: Box
    status: str = "detected"

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox_norm", validate_bbox_norm(self.bbox_norm))
        conf = _as_float(self.confidence, "confidence")
        if conf < 0.0 or conf > 1.0:
            raise BoxValidationError(
                f"confidence={conf} is outside [0, 1] for image {self.image_id!r}"
            )
        object.__setattr__(self, "confidence", conf)
        if not self.class_name:
            raise BoxValidationError("PredictionBox.class_name must not be empty")


@dataclass(frozen=True)
class ScoredPrediction:
    """A prediction annotated as TP/FP after matching at one IoU threshold."""

    image_id: str
    class_name: str
    confidence: float
    is_true_positive: bool
    matched_gt: Optional[GroundTruthBox] = None
    bbox_norm: Optional[Box] = None


@dataclass(frozen=True)
class ImageMatch:
    image_id: str
    scored_predictions: Tuple[ScoredPrediction, ...]
    false_negatives: Tuple[GroundTruthBox, ...]


@dataclass(frozen=True)
class ClassMatchSummary:
    class_name: str
    true_positives: int
    false_positives: int
    false_negatives: int
    ground_truth_count: int


@dataclass(frozen=True)
class DatasetMatch:
    """Result of matching every prediction against every annotation."""

    iou_threshold: float
    image_matches: Tuple[ImageMatch, ...]
    per_class: Mapping[str, ClassMatchSummary]
    scored_predictions: Tuple[ScoredPrediction, ...]
    false_negatives: Tuple[GroundTruthBox, ...]

    @property
    def true_positives(self) -> int:
        return sum(1 for p in self.scored_predictions if p.is_true_positive)

    @property
    def false_positives(self) -> int:
        return sum(1 for p in self.scored_predictions if not p.is_true_positive)

    @property
    def false_negative_count(self) -> int:
        return len(self.false_negatives)

    @property
    def ground_truth_count(self) -> int:
        return sum(summary.ground_truth_count for summary in self.per_class.values())


def match_image(
    predictions: Sequence[PredictionBox],
    ground_truths: Sequence[GroundTruthBox],
    iou_threshold: float = 0.50,
) -> ImageMatch:
    """Match predictions to ground truth for a single image."""

    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError(f"iou_threshold must be in [0, 1], got {iou_threshold}")

    image_ids = {p.image_id for p in predictions} | {g.image_id for g in ground_truths}
    if len(image_ids) > 1:
        raise MatchingError(
            f"match_image received multiple image_ids: {sorted(image_ids)}"
        )

    # Stable descending-confidence ordering.
    ordered = sorted(enumerate(predictions), key=lambda item: (-item[1].confidence, item[0]))
    unmatched_gt: List[int] = list(range(len(ground_truths)))
    scored: List[ScoredPrediction] = []

    for _, pred in ordered:
        if pred.status == "unsupported_class" or pred.class_name.startswith("unsupported_class"):
            raise MatchingError(
                "Unsupported-class predictions must be filtered before matching "
                f"(image {pred.image_id!r})"
            )

        best_idx: Optional[int] = None
        best_iou = -1.0
        for gt_idx in unmatched_gt:
            gt = ground_truths[gt_idx]
            if gt.class_name != pred.class_name:
                continue
            iou = compute_iou(pred.bbox_norm, gt.bbox_norm)
            if iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_idx = gt_idx

        if best_idx is None:
            scored.append(
                ScoredPrediction(
                    image_id=pred.image_id,
                    class_name=pred.class_name,
                    confidence=pred.confidence,
                    is_true_positive=False,
                    bbox_norm=pred.bbox_norm,
                )
            )
        else:
            matched_gt = ground_truths[best_idx]
            unmatched_gt.remove(best_idx)
            scored.append(
                ScoredPrediction(
                    image_id=pred.image_id,
                    class_name=pred.class_name,
                    confidence=pred.confidence,
                    is_true_positive=True,
                    matched_gt=matched_gt,
                    bbox_norm=pred.bbox_norm,
                )
            )

    image_id = next(iter(image_ids), "")
    false_negatives = tuple(ground_truths[i] for i in unmatched_gt)
    return ImageMatch(
        image_id=image_id,
        scored_predictions=tuple(scored),
        false_negatives=false_negatives,
    )


def match_dataset(
    predictions_by_image: Mapping[str, Sequence[PredictionBox]],
    ground_truths_by_image: Mapping[str, Sequence[GroundTruthBox]],
    image_ids: Iterable[str],
    iou_threshold: float = 0.50,
    class_names: Optional[Sequence[str]] = None,
) -> DatasetMatch:
    """Match a whole dataset, enforcing annotation completeness.

    ``image_ids`` must exactly equal the annotated image set. A prediction for
    an image with no annotation entry raises: missing annotations are NEVER
    silently converted into negative images.
    """

    ids = set(image_ids)
    if not ids:
        raise MatchingError("Cannot match an empty image set")

    gt_ids = set(ground_truths_by_image)
    pred_ids = set(predictions_by_image)

    if pred_ids - ids:
        raise MatchingError(
            "Predictions exist for images outside the evaluated set: "
            f"{sorted(pred_ids - ids)[:5]}"
        )
    if gt_ids - ids:
        raise MatchingError(
            "Annotations exist for images outside the evaluated set: "
            f"{sorted(gt_ids - ids)[:5]}"
        )
    missing_annotations = ids - gt_ids
    if missing_annotations:
        raise MatchingError(
            "Missing annotation entries for evaluated images; missing labels are "
            f"not negatives: {sorted(missing_annotations)[:5]}"
        )

    classes = set(class_names or [])
    for gt_list in ground_truths_by_image.values():
        for gt in gt_list:
            if gt.image_id not in ids:
                raise MatchingError(f"GroundTruthBox.image_id {gt.image_id!r} is not in image_ids")
            classes.add(gt.class_name)
    for pred_list in predictions_by_image.values():
        for pred in pred_list:
            if pred.image_id not in ids:
                raise MatchingError(f"PredictionBox.image_id {pred.image_id!r} is not in image_ids")
            classes.add(pred.class_name)

    image_matches: List[ImageMatch] = []
    all_scored: List[ScoredPrediction] = []
    all_fn: List[GroundTruthBox] = []
    for image_id in sorted(ids):
        result = match_image(
            list(predictions_by_image.get(image_id, ())),
            list(ground_truths_by_image.get(image_id, ())),
            iou_threshold=iou_threshold,
        )
        image_matches.append(result)
        all_scored.extend(result.scored_predictions)
        all_fn.extend(result.false_negatives)

    per_class: Dict[str, ClassMatchSummary] = {}
    for class_name in sorted(classes):
        class_scored = [p for p in all_scored if p.class_name == class_name]
        tp = sum(1 for p in class_scored if p.is_true_positive)
        fp = len(class_scored) - tp
        fn = sum(1 for g in all_fn if g.class_name == class_name)
        per_class[class_name] = ClassMatchSummary(
            class_name=class_name,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            ground_truth_count=tp + fn,
        )

    return DatasetMatch(
        iou_threshold=float(iou_threshold),
        image_matches=tuple(image_matches),
        per_class=per_class,
        scored_predictions=tuple(all_scored),
        false_negatives=tuple(all_fn),
    )


__all__ = [
    "IOU_THRESHOLDS",
    "BoxValidationError",
    "ClassMatchSummary",
    "DatasetMatch",
    "GroundTruthBox",
    "ImageMatch",
    "MatchingError",
    "PredictionBox",
    "ScoredPrediction",
    "compute_iou",
    "match_dataset",
    "match_image",
    "validate_bbox_norm",
]
