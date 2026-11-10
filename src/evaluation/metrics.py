"""SafeRoute AI — Phase 42 detector metrics.

Metric conventions
------------------
* AP uses 101-point interpolated precision (COCO/VOC style), reported per class.
* ``mAP50`` / ``mAP50-95`` are macro averages over evaluated classes.
* A class with zero ground-truth instances gets ``None`` (not ``0.0``) for AP;
  it is reported as ``insufficient_sample`` rather than as a perfect/zero score.
* Precision/recall use micro counts across classes at the operational working
  point (the production confidence threshold).
* ``FP/km`` is ``None`` when no verified distance is supplied. It is never
  invented from a frame count.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .matching import (
    DatasetMatch,
    GroundTruthBox,
    PredictionBox,
    ScoredPrediction,
    match_dataset,
)


def safe_divide(numerator: float, denominator: float) -> Optional[float]:
    """Divide, returning ``None`` when the denominator is zero/undefined."""
    if denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


@dataclass(frozen=True)
class CountMetrics:
    """Micro precision/recall for one class or an aggregation."""

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    ground_truth_count: int
    predicted_count: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "ground_truth_count": self.ground_truth_count,
            "predicted_count": self.predicted_count,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


def compute_counts(tp: int, fp: int, fn: int) -> CountMetrics:
    """Build count-based precision/recall metrics without hiding zero counts."""
    if tp < 0 or fp < 0 or fn < 0:
        raise ValueError("TP/FP/FN counts must be non-negative")
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return CountMetrics(
        true_positives=int(tp),
        false_positives=int(fp),
        false_negatives=int(fn),
        precision=precision,
        recall=recall,
        f1=f1,
        ground_truth_count=int(tp + fn),
        predicted_count=int(tp + fp),
    )


def average_precision(
    scored_predictions: Sequence[ScoredPrediction],
    ground_truth_count: int,
) -> Optional[float]:
    """101-point interpolated AP for one class at one IoU threshold.

    Returns ``None`` when there are no ground-truth instances: an undefined AP
    is not the same as an AP of zero.
    """
    if ground_truth_count <= 0:
        return None

    # Stable descending-confidence order.
    ordered = sorted(
        enumerate(scored_predictions),
        key=lambda item: (-item[1].confidence, item[0]),
    )
    tp_cum = 0
    fp_cum = 0
    recalls: List[float] = []
    precisions: List[float] = []
    for _, prediction in ordered:
        if prediction.is_true_positive:
            tp_cum += 1
        else:
            fp_cum += 1
        recalls.append(tp_cum / float(ground_truth_count))
        precisions.append(tp_cum / float(tp_cum + fp_cum))

    # Sentinel points make the interpolation well defined at recall 0 and 1.
    mrec = [0.0] + recalls + [1.0]
    mpre = [0.0] + precisions + [0.0]
    for index in range(len(mpre) - 2, -1, -1):
        mpre[index] = max(mpre[index], mpre[index + 1])

    total = 0.0
    for step in range(101):
        target = step / 100.0
        # Highest precision at any recall >= target.
        best = 0.0
        for recall, precision in zip(mrec, mpre):
            if recall >= target:
                best = max(best, precision)
        total += best
    return float(total / 101.0)


@dataclass(frozen=True)
class ClassAP:
    class_name: str
    ground_truth_count: int
    prediction_count: int
    ap50: Optional[float]
    ap50_95: Optional[float]
    ap_by_iou: Mapping[str, Optional[float]]
    status: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "class_name": self.class_name,
            "ground_truth_count": self.ground_truth_count,
            "prediction_count": self.prediction_count,
            "ap50": self.ap50,
            "ap50_95": self.ap50_95,
            "ap_by_iou": dict(self.ap_by_iou),
            "status": self.status,
        }


@dataclass(frozen=True)
class APMetrics:
    per_class: Mapping[str, ClassAP]
    map50: Optional[float]
    map50_95: Optional[float]
    classes_evaluated: Tuple[str, ...]
    classes_insufficient: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "per_class": {name: ap.to_dict() for name, ap in self.per_class.items()},
            "map50": self.map50,
            "map50_95": self.map50_95,
            "classes_evaluated": list(self.classes_evaluated),
            "classes_insufficient": list(self.classes_insufficient),
        }


def compute_ap_metrics(
    matches_by_threshold: Mapping[float, DatasetMatch],
    class_names: Sequence[str],
) -> APMetrics:
    """Compute per-class AP50/AP50-95 from matches at every IoU threshold."""
    if not matches_by_threshold:
        return APMetrics(
            per_class={},
            map50=None,
            map50_95=None,
            classes_evaluated=(),
            classes_insufficient=tuple(class_names),
        )

    thresholds = sorted(matches_by_threshold)
    names = list(dict.fromkeys(list(class_names) + [
        name
        for match in matches_by_threshold.values()
        for name in match.per_class
    ]))

    per_class: Dict[str, ClassAP] = {}
    for class_name in names:
        ap_by_iou: Dict[str, Optional[float]] = {}
        gt_count = 0
        prediction_count = 0
        for threshold in thresholds:
            match = matches_by_threshold[threshold]
            summary = match.per_class.get(class_name)
            if summary is not None:
                gt_count = max(gt_count, summary.ground_truth_count)
                prediction_count = max(prediction_count, summary.true_positives + summary.false_positives)
            class_predictions = [
                p for p in match.scored_predictions if p.class_name == class_name
            ]
            ap_by_iou[f"{threshold:.2f}"] = average_precision(class_predictions, gt_count)

        ap50 = ap_by_iou.get("0.50")
        valid_ap = [value for value in ap_by_iou.values() if value is not None]
        ap50_95 = float(sum(valid_ap) / len(valid_ap)) if valid_ap else None
        if gt_count == 0:
            status = "insufficient_sample"
        elif ap50 is None:
            status = "undefined"
        else:
            status = "ok"
        per_class[class_name] = ClassAP(
            class_name=class_name,
            ground_truth_count=gt_count,
            prediction_count=prediction_count,
            ap50=ap50,
            ap50_95=ap50_95,
            ap_by_iou=ap_by_iou,
            status=status,
        )

    evaluated = tuple(name for name, ap in per_class.items() if ap.status == "ok")
    insufficient = tuple(name for name, ap in per_class.items() if ap.status != "ok")
    map50_values = [per_class[name].ap50 for name in evaluated if per_class[name].ap50 is not None]
    map5095_values = [
        per_class[name].ap50_95 for name in evaluated if per_class[name].ap50_95 is not None
    ]
    return APMetrics(
        per_class=per_class,
        map50=float(sum(map50_values) / len(map50_values)) if map50_values else None,
        map50_95=(
            float(sum(map5095_values) / len(map5095_values)) if map5095_values else None
        ),
        classes_evaluated=evaluated,
        classes_insufficient=insufficient,
    )


def false_positives_per_km(
    false_positive_count: int,
    distance_km: Optional[float],
) -> Optional[float]:
    """Operational false positives per verified kilometre (``None`` if unknown)."""
    if distance_km is None or distance_km <= 0:
        return None
    return float(false_positive_count) / float(distance_km)


def miss_rate(false_negatives: int, ground_truth_count: int) -> Optional[float]:
    """Fraction of annotated hazards that were not matched (``None`` if none)."""
    return safe_divide(false_negatives, ground_truth_count)


def operational_summary(
    match: DatasetMatch,
    distance_km: Optional[float],
    class_names: Sequence[str],
) -> Dict[str, object]:
    """Report operational precision/recall, FP/km and miss rate by class."""
    per_class: Dict[str, object] = {}
    overall = compute_counts(
        sum(summary.true_positives for summary in match.per_class.values()),
        sum(summary.false_positives for summary in match.per_class.values()),
        sum(summary.false_negatives for summary in match.per_class.values()),
    )
    for class_name in class_names:
        summary = match.per_class.get(class_name)
        if summary is None:
            counts = compute_counts(0, 0, 0)
            fp_km = None
            miss = None
        else:
            counts = compute_counts(
                summary.true_positives,
                summary.false_positives,
                summary.false_negatives,
            )
            fp_km = false_positives_per_km(summary.false_positives, distance_km)
            miss = miss_rate(summary.false_negatives, summary.ground_truth_count)
        per_class[class_name] = {
            **counts.to_dict(),
            "false_positives_per_km": fp_km,
            "miss_rate": miss,
            "status": "ok" if counts.ground_truth_count > 0 else "insufficient_sample",
        }

    return {
        "overall": {
            **overall.to_dict(),
            "false_positives_per_km": false_positives_per_km(
                overall.false_positives, distance_km
            ),
            "miss_rate": miss_rate(overall.false_negatives, overall.ground_truth_count),
        },
        "per_class": per_class,
        "distance_km": distance_km,
        "iou_threshold": match.iou_threshold,
    }


def _box_center(box: Sequence[float]) -> Tuple[float, float]:
    return ((float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0)


def deduplicate_frame_false_positives(
    observations: Iterable[object],
    max_center_distance: float = 0.15,
) -> int:
    """Heuristically collapse repeated false positives across adjacent frames.

    Each observation must expose ``session_id``, ``class_name`` and
    ``bbox_norm``. Observations without a session id are never merged (we do not
    assume unrelated images are the same road). The result is an explicitly
    heuristic cluster count, not a substitute for verified distance.

    This is reported alongside the raw frame-level FP count; neither is treated
    as an independent observation count.
    """
    clusters: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}
    for index, observation in enumerate(observations):
        session_id = getattr(observation, "session_id", None)
        class_name = str(getattr(observation, "class_name", ""))
        bbox = getattr(observation, "bbox_norm", None)
        if not session_id or not class_name or bbox is None or len(bbox) != 4:
            # Unknown provenance: cannot safely merge; count separately.
            clusters[(f"__unclustered__{index}", class_name)] = [
                _box_center(bbox) if bbox is not None and len(bbox) == 4 else (0.0, 0.0)
            ]
            continue
        key = (str(session_id), class_name)
        center = _box_center(bbox)
        bucket = clusters.setdefault(key, [])
        if not any(
            math.dist(center, existing) <= max_center_distance for existing in bucket
        ):
            bucket.append(center)
    return sum(len(centers) for centers in clusters.values())


def group_metrics(
    predictions_by_image: Mapping[str, Sequence[PredictionBox]],
    ground_truths_by_image: Mapping[str, Sequence[GroundTruthBox]],
    group_by_image: Mapping[str, str],
    image_ids: Iterable[str],
    class_names: Sequence[str],
    iou_threshold: float = 0.50,
) -> Dict[str, object]:
    """Compute per-condition metrics without pooling away weak groups."""
    buckets: Dict[str, List[str]] = {}
    for image_id in image_ids:
        group = group_by_image.get(image_id, "unlabelled")
        buckets.setdefault(group, []).append(image_id)

    results: Dict[str, object] = {}
    for group, ids in sorted(buckets.items()):
        subset_ids = set(ids)
        preds = {i: predictions_by_image.get(i, ()) for i in subset_ids}
        gts = {i: ground_truths_by_image.get(i, ()) for i in subset_ids}
        match = match_dataset(preds, gts, subset_ids, iou_threshold, class_names)
        per_class: Dict[str, object] = {}
        for class_name in class_names:
            summary = match.per_class.get(class_name)
            if summary is None:
                counts = compute_counts(0, 0, 0)
                ap = None
            else:
                counts = compute_counts(
                    summary.true_positives,
                    summary.false_positives,
                    summary.false_negatives,
                )
                class_predictions = [
                    p for p in match.scored_predictions if p.class_name == class_name
                ]
                ap = average_precision(class_predictions, summary.ground_truth_count)
            per_class[class_name] = {
                **counts.to_dict(),
                "ap50": ap,
                "status": "ok" if counts.ground_truth_count > 0 else "insufficient_sample",
            }
        overall = compute_counts(
            sum(s.true_positives for s in match.per_class.values()),
            sum(s.false_positives for s in match.per_class.values()),
            sum(s.false_negatives for s in match.per_class.values()),
        )
        results[group] = {
            "image_count": len(ids),
            "overall": overall.to_dict(),
            "per_class": per_class,
        }
    return results


__all__ = [
    "APMetrics",
    "ClassAP",
    "CountMetrics",
    "average_precision",
    "compute_ap_metrics",
    "compute_counts",
    "deduplicate_frame_false_positives",
    "false_positives_per_km",
    "group_metrics",
    "miss_rate",
    "operational_summary",
    "safe_divide",
]
