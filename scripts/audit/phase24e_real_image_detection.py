#!/usr/bin/env python3
"""SafeRoute AI — PHASE 24E: Real-image detection-pipeline verification.

Runs the **application** detection pipeline (``src.detection.detector.HazardDetector``
from the shipped ``detect-v2`` module) — which loads the checkpoint named in
``config/detection.yaml`` and the PHASE 06 ``preprocess-v1`` OpenCV pipeline —
over the PHASE 24C derived two-class **test** holdout (``data/splits_v2/test.txt``,
216 images / 390 boxes / 46 background-only images).

It matches predictions against the derived ground-truth labels, renders per-image
prediction visualisations, and writes a single machine-readable JSON summary plus
CSV detail tables.

Scope / guardrails (master_rules.md Rules 1, 3, 5, 9, 14, 15, 16, 18, 19, 20):
- Evaluation only. No training, fine-tuning, resume or weight change.
- The configured checkpoint is used as-is. v2 is never loaded, referenced or promoted.
- No dataset image, label, split, or config file is modified.
- All reads are workspace-isolated; the only writes are under ``reports/phase24e/``.
  Any transient ``labels.cache`` Ultralytics may create is removed afterwards.

Usage (from the workspace root, with the workspace venv):
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24e_real_image_detection.py
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24e_real_image_detection.py --device cpu --limit 12
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import yaml

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

PHASE = "PHASE 24E"
SCRIPT_NAME = "scripts/audit/phase24e_real_image_detection.py"
OUT_DIR = WORKSPACE_ROOT / "reports" / "phase24e"
VIZ_DIR = OUT_DIR / "visualizations"

DERIVED_ROOT = WORKSPACE_ROOT / "data" / "derived_2class"
IMAGES_DIR = DERIVED_ROOT / "images"
LABELS_DIR = DERIVED_ROOT / "labels"
TEST_SPLIT = WORKSPACE_ROOT / "data" / "splits_v2" / "test.txt"
DATASET_YAML = WORKSPACE_ROOT / "data" / "dataset_v2.yaml"
DETECTION_CONFIG = WORKSPACE_ROOT / "config" / "detection.yaml"

CLASS_NAMES = {0: "pothole", 1: "crack"}
CLASS_IDS = {v: k for k, v in CLASS_NAMES.items()}
BACKGROUND = "background"

# Expected holdout identity (independently established in PHASE 24D §5).
EXPECTED_IMAGES = 216
EXPECTED_GT_TOTAL = 390
EXPECTED_GT_POTHOLE = 98
EXPECTED_GT_CRACK = 292
EXPECTED_BACKGROUND_IMAGES = 46

# Colour palette (BGR).
COLOR_GT = (0, 220, 0)          # green  — ground truth
COLOR_PRED = {0: (0, 0, 255),   # pothole — red
              1: (0, 165, 255)}  # crack   — orange
COLOR_FP = (255, 0, 255)        # magenta — unmatched prediction (false positive)
COLOR_FN = (0, 0, 0)            # unused directly; GT-only boxes are green


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def merkle_of_files(paths: Sequence[Path]) -> str:
    """Deterministic Merkle over sorted ``name:sha256`` lines (PHASE 24C algorithm)."""
    entries = sorted(f"{p.name}:{sha256_file(p)}" for p in paths)
    h = hashlib.sha256()
    for line in entries:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest().upper()


def iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = (float(v) for v in a)
    bx1, by1, bx2, by2 = (float(v) for v in b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return float(inter / union) if union > 0 else 0.0


def stats(values: Sequence[float]) -> Optional[Dict[str, float]]:
    if not values:
        return None
    vals = [float(v) for v in values]
    return {
        "count": len(vals),
        "min": round(min(vals), 4),
        "mean": round(statistics.fmean(vals), 4),
        "median": round(statistics.median(vals), 4),
        "max": round(max(vals), 4),
    }


def load_gt_boxes(label_path: Path, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse a derived YOLO label file into pixel xyxy boxes (empty file -> [])."""
    boxes: List[Dict[str, Any]] = []
    if not label_path.is_file():
        return boxes
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return boxes
    for lineno, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) < 5:
            raise ValueError(f"{label_path.name}:{lineno} malformed label row: {line!r}")
        cls = int(float(parts[0]))
        cx, cy, w, h = (float(v) for v in parts[1:5])
        x1 = (cx - w / 2.0) * img_w
        y1 = (cy - h / 2.0) * img_h
        x2 = (cx + w / 2.0) * img_w
        y2 = (cy + h / 2.0) * img_h
        boxes.append({"cls": cls, "bbox": [x1, y1, x2, y2]})
    return boxes


# --------------------------------------------------------------------------- #
# Device selection
# --------------------------------------------------------------------------- #
def select_device(requested: str) -> Tuple[Any, str]:
    """Resolve the inference device and return ``(device, reason)``.

    ``auto`` uses CUDA only when it is available *and* at least 2 GiB is free,
    mirroring the PHASE 24D lesson that a competing GPU process can OOM the run.
    """
    import torch

    if requested == "cpu":
        return "cpu", "requested: cpu"
    if requested in ("cuda", "0", "gpu"):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is False.")
        return 0, "requested: cuda"

    # auto
    if torch.cuda.is_available():
        try:
            free_b, total_b = torch.cuda.mem_get_info()
            free_gib = free_b / (1024 ** 3)
            total_gib = total_b / (1024 ** 3)
            if free_gib >= 2.0:
                name = torch.cuda.get_device_name(0)
                return 0, f"auto: CUDA free {free_gib:.2f}/{total_gib:.2f} GiB ({name})"
            return "cpu", (
                f"auto: CUDA present but only {free_gib:.2f}/{total_gib:.2f} GiB free "
                "(<2 GiB) — using CPU to avoid OOM"
            )
        except Exception as exc:  # pragma: no cover - defensive
            return "cpu", f"auto: CUDA probe failed ({exc!r}) — using CPU"
    return "cpu", "auto: no CUDA device available"


# --------------------------------------------------------------------------- #
# Matching (per image)
# --------------------------------------------------------------------------- #
def match_image(
    gt_boxes: List[Dict[str, Any]],
    preds: List[Dict[str, Any]],
    match_iou: float,
) -> Dict[str, Any]:
    """Greedy per-class matching: highest-confidence predictions claim GT first.

    Returns matched pairs (pred idx, gt idx, class, IoU, confidence), unmatched
    prediction indices (false positives) and unmatched GT indices (missed
    detections), plus the best any-class IoU per missed GT.
    """
    used_gt: set = set()
    used_pred: set = set()
    matched: List[Dict[str, Any]] = []

    order = sorted(range(len(preds)), key=lambda i: preds[i]["conf"], reverse=True)
    for pi in order:
        p = preds[pi]
        best_gi = -1
        best_iou = 0.0
        for gi, g in enumerate(gt_boxes):
            if gi in used_gt or g["cls"] != p["cls"]:
                continue
            v = iou_xyxy(p["bbox"], g["bbox"])
            if v > best_iou:
                best_iou, best_gi = v, gi
        if best_gi >= 0 and best_iou >= match_iou:
            used_gt.add(best_gi)
            used_pred.add(pi)
            matched.append({
                "pred_idx": pi,
                "gt_idx": best_gi,
                "cls": p["cls"],
                "iou": best_iou,
                "conf": p["conf"],
            })

    # Per missed GT: nearest prediction (any class) and nearest same-class prediction.
    missed: List[Dict[str, Any]] = []
    for gi, g in enumerate(gt_boxes):
        if gi in used_gt:
            continue
        best_any_iou, best_any_cls = 0.0, None
        best_same_iou = 0.0
        for p in preds:
            v = iou_xyxy(p["bbox"], g["bbox"])
            if v > best_any_iou:
                best_any_iou, best_any_cls = v, p["cls"]
            if p["cls"] == g["cls"] and v > best_same_iou:
                best_same_iou = v
        missed.append({
            "gt_idx": gi,
            "cls": g["cls"],
            "bbox": [round(c, 2) for c in g["bbox"]],
            "best_any_iou": round(best_any_iou, 4),
            "best_any_pred_class": (CLASS_NAMES.get(best_any_cls) if best_any_cls is not None else None),
            "best_same_class_iou": round(best_same_iou, 4),
            "localized_but_missed": best_any_iou >= match_iou,
        })

    fps = [pi for pi in range(len(preds)) if pi not in used_pred]

    return {
        "matched": matched,
        "fp_pred_indices": fps,
        "missed": missed,
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _draw_box(img: np.ndarray, bbox: Sequence[float], color: Tuple[int, int, int],
              label: str, thickness: int = 2) -> None:
    x1, y1, x2, y2 = (int(round(float(c))) for c in bbox)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = max(0, x2), max(0, y2)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    ty1 = max(0, y1 - th - baseline - 3)
    cv2.rectangle(img, (x1, ty1), (x1 + tw + 4, y1), color, -1)
    cv2.putText(img, label, (x1 + 2, y1 - baseline - 1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)


def render_overlay(
    image_bgr: np.ndarray,
    gt_boxes: List[Dict[str, Any]],
    preds: List[Dict[str, Any]],
    match_info: Dict[str, Any],
    out_path: Path,
) -> None:
    """Render GT (green), matched predictions (class colour) and FPs (magenta)."""
    canvas = image_bgr.copy()
    matched_pred_idx = {m["pred_idx"]: m for m in match_info["matched"]}
    fp_set = set(match_info["fp_pred_indices"])

    for g in gt_boxes:
        _draw_box(canvas, g["bbox"], COLOR_GT, f"GT {CLASS_NAMES.get(g['cls'], g['cls'])}")

    for pi, p in enumerate(preds):
        cls_name = CLASS_NAMES.get(p["cls"], f"class_{p['cls']}")
        if pi in matched_pred_idx:
            m = matched_pred_idx[pi]
            _draw_box(canvas, p["bbox"], COLOR_PRED.get(p["cls"], (0, 255, 0)),
                      f"{cls_name} {p['conf']:.2f} iou={m['iou']:.2f}")
        elif pi in fp_set:
            _draw_box(canvas, p["bbox"], COLOR_FP, f"FP {cls_name} {p['conf']:.2f}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), canvas)


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="PHASE 24E real-image detection verification.")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                    help="Inference device. 'auto' picks CUDA only if >=2 GiB free, else CPU.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Process only the first N test images (0 = all). For smoke tests.")
    ap.add_argument("--conf", type=float, default=None,
                    help="Confidence override. Default: use config/detection.yaml (0.25).")
    ap.add_argument("--match-iou", type=float, default=0.5,
                    help="IoU threshold for a prediction<->GT match (default 0.5).")
    ap.add_argument("--no-viz", action="store_true", help="Skip writing visualisations.")
    return ap.parse_args(argv)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"[{PHASE}] Real-image application-pipeline detection verification")
    print(f"  workspace : {WORKSPACE_ROOT}")

    # -- Load the configured detection config (single source of truth) ------- #
    with open(DETECTION_CONFIG, "r", encoding="utf-8") as f:
        det_cfg = yaml.safe_load(f)
    configured_rel = det_cfg["model"]["checkpoint"]
    configured_ckpt = (WORKSPACE_ROOT / configured_rel).resolve()
    configured_model_version = det_cfg.get("metadata", {}).get("model_version", "?")

    # Guardrail: we only ever load the configured checkpoint (v1). Not v2.
    if "v2" in str(configured_ckpt).lower():
        raise RuntimeError(f"Refusing to run: configured checkpoint looks like v2 ({configured_ckpt}).")
    if "saferoute-yolo11-v1" not in str(configured_ckpt).replace("\\", "/"):
        raise RuntimeError(f"Unexpected configured checkpoint path: {configured_ckpt}")

    # -- Read + verify test split ------------------------------------------- #
    test_images = [Path(line.strip()) for line in TEST_SPLIT.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit > 0:
        test_images = test_images[: args.limit]

    missing = [p for p in test_images if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} test image(s) missing, e.g. {missing[0]}")

    # -- Integrity hashes (before) ------------------------------------------ #
    ckpt_sha_before = sha256_file(configured_ckpt)
    dataset_yaml_sha = sha256_file(DATASET_YAML)
    test_split_sha = sha256_file(TEST_SPLIT)
    det_cfg_sha = sha256_file(DETECTION_CONFIG)
    label_files = [LABELS_DIR / f"{p.stem}.txt" for p in test_images]
    missing_labels = [lp for lp in label_files if not lp.is_file()]
    if missing_labels:
        raise FileNotFoundError(f"{len(missing_labels)} label file(s) missing, e.g. {missing_labels[0]}")
    labels_merkle_before = merkle_of_files(label_files)

    # -- Device + detector (the SHIPPED application component) -------------- #
    device, device_reason = select_device(args.device)
    print(f"  device    : {device}  ({device_reason})")

    from src.detection.detector import HazardDetector  # shipped detect-v2 module

    detector = HazardDetector(checkpoint_path=configured_ckpt, device=device)
    active_conf = detector.conf_threshold if args.conf is None else float(args.conf)

    print(f"  checkpoint: {configured_ckpt.relative_to(WORKSPACE_ROOT)}")
    print(f"  ckpt sha  : {ckpt_sha_before}")
    print(f"  detector  : {detector.detector_version} / {detector.model_version}  "
          f"imgsz={detector.imgsz} conf={active_conf} iou={detector.iou_threshold} max_det={detector.max_det}")
    print(f"  holdout   : {len(test_images)} images from {TEST_SPLIT.relative_to(WORKSPACE_ROOT)}")
    print(f"  match IoU : {args.match_iou}")

    if not args.no_viz:
        VIZ_DIR.mkdir(parents=True, exist_ok=True)

    # -- Per-image inference + matching ------------------------------------- #
    per_image: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = {}
    conf_tp: Dict[str, List[float]] = {c: [] for c in CLASS_NAMES.values()}
    conf_fp: Dict[str, List[float]] = {c: [] for c in CLASS_NAMES.values()}
    conf_all_pred: Dict[str, List[float]] = {c: [] for c in CLASS_NAMES.values()}
    matched_ious: Dict[str, List[float]] = {c: [] for c in CLASS_NAMES.values()}
    timings_total: List[float] = []
    timings_infer: List[float] = []

    # confusion[pred][true] with labels [pothole, crack, background]
    labels3 = [CLASS_NAMES[0], CLASS_NAMES[1], BACKGROUND]
    confusion = [[0, 0, 0] for _ in range(3)]

    fp_rows: List[Dict[str, Any]] = []
    fn_rows: List[Dict[str, Any]] = []

    gt_counts = {c: 0 for c in CLASS_NAMES.values()}
    pred_counts = {c: 0 for c in CLASS_NAMES.values()}
    tp_counts = {c: 0 for c in CLASS_NAMES.values()}
    fp_counts = {c: 0 for c in CLASS_NAMES.values()}
    fn_counts = {c: 0 for c in CLASS_NAMES.values()}
    background_only_images = 0
    background_images_with_fp = 0

    # Class-aware confusion matrix: after per-class matching, unmatched predictions
    # and unmatched GTs are greedily paired by geometry alone (any class). A pair at
    # IoU>=match_iou with differing classes is a genuine cross-class error rather
    # than a background false positive.
    confusion_ca = [[0, 0, 0] for _ in range(3)]
    cross_class_rows: List[Dict[str, Any]] = []
    cross_pair_counts: Dict[str, int] = {}

    n = len(test_images)
    for idx, img_path in enumerate(test_images, start=1):
        stem = img_path.stem
        image_bgr = cv2.imread(str(img_path))
        if image_bgr is None:
            raise RuntimeError(f"OpenCV could not read holdout image: {img_path}")
        h, w = image_bgr.shape[:2]

        gt_boxes = load_gt_boxes(LABELS_DIR / f"{stem}.txt", w, h)
        result = detector.detect(img_path, image_id=stem, conf=args.conf)
        status = result.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

        preds = [
            {"cls": CLASS_IDS.get(d.hazard_class, -1), "conf": float(d.confidence),
             "bbox": [float(v) for v in d.bbox_xyxy], "hazard_class": d.hazard_class,
             "status": d.status}
            for d in result.detections
        ]
        # Only supported classes participate in matching (Rule 5: disclose, never fabricate).
        preds = [p for p in preds if p["cls"] in CLASS_NAMES]

        match_info = match_image(gt_boxes, preds, args.match_iou)

        # Counts per image
        img_gt = {c: 0 for c in CLASS_NAMES.values()}
        for g in gt_boxes:
            if g["cls"] in CLASS_NAMES:
                img_gt[CLASS_NAMES[g["cls"]]] += 1
                gt_counts[CLASS_NAMES[g["cls"]]] += 1
        img_pred = {c: 0 for c in CLASS_NAMES.values()}
        img_tp = {c: 0 for c in CLASS_NAMES.values()}
        img_fp = {c: 0 for c in CLASS_NAMES.values()}
        img_fn = {c: 0 for c in CLASS_NAMES.values()}

        for p in preds:
            cname = CLASS_NAMES[p["cls"]]
            img_pred[cname] += 1
            pred_counts[cname] += 1
            conf_all_pred[cname].append(p["conf"])

        for m in match_info["matched"]:
            cname = CLASS_NAMES[m["cls"]]
            img_tp[cname] += 1
            tp_counts[cname] += 1
            conf_tp[cname].append(m["conf"])
            matched_ious[cname].append(m["iou"])
            confusion[m["cls"]][m["cls"]] += 1
            confusion_ca[m["cls"]][m["cls"]] += 1

        # Class-aware pass: greedily pair the remaining (unmatched) predictions and
        # GTs by geometry alone. Differing-class pairs are cross-class errors.
        unmatched_preds = list(match_info["fp_pred_indices"])
        unmatched_gts = [m["gt_idx"] for m in match_info["missed"]]
        cross_pred_idx: set = set()
        cross_gt_idx: set = set()
        for pi in sorted(unmatched_preds, key=lambda i: preds[i]["conf"], reverse=True):
            best_gi, best_iou = -1, 0.0
            for gi in unmatched_gts:
                if gi in cross_gt_idx:
                    continue
                v = iou_xyxy(preds[pi]["bbox"], gt_boxes[gi]["bbox"])
                if v > best_iou:
                    best_iou, best_gi = v, gi
            if best_gi >= 0 and best_iou >= args.match_iou:
                cross_pred_idx.add(pi)
                cross_gt_idx.add(best_gi)
                p_cls, g_cls = preds[pi]["cls"], gt_boxes[best_gi]["cls"]
                confusion_ca[p_cls][g_cls] += 1
                pair_key = f"{CLASS_NAMES[p_cls]}->{CLASS_NAMES[g_cls]}"
                cross_pair_counts[pair_key] = cross_pair_counts.get(pair_key, 0) + 1
                cross_class_rows.append({
                    "image_id": stem,
                    "predicted_class": CLASS_NAMES[p_cls],
                    "confidence": round(preds[pi]["conf"], 4),
                    "both_classes_supported": (p_cls in CLASS_NAMES and g_cls in CLASS_NAMES),
                    "gt_class": CLASS_NAMES.get(g_cls, f"class_{g_cls}"),
                    "iou": round(best_iou, 4),
                    "pred_bbox_xyxy": [round(v, 1) for v in preds[pi]["bbox"]],
                    "gt_bbox_xyxy": [round(v, 1) for v in gt_boxes[best_gi]["bbox"]],
                })

        for pi in match_info["fp_pred_indices"]:
            p = preds[pi]
            cname = CLASS_NAMES[p["cls"]]
            img_fp[cname] += 1
            fp_counts[cname] += 1
            conf_fp[cname].append(p["conf"])
            confusion[p["cls"]][2] += 1
            if pi not in cross_pred_idx:
                confusion_ca[p["cls"]][2] += 1
            fp_rows.append({
                "image_id": stem,
                "predicted_class": cname,
                "confidence": round(p["conf"], 4),
                "bbox_xyxy": [round(v, 1) for v in p["bbox"]],
                "gt_boxes_in_image": len(gt_boxes),
                "class_aware_cross_class": pi in cross_pred_idx,
            })

        for mi in match_info["missed"]:
            if mi["cls"] not in CLASS_NAMES:
                continue
            cname = CLASS_NAMES[mi["cls"]]
            img_fn[cname] += 1
            fn_counts[cname] += 1
            confusion[2][mi["cls"]] += 1
            if mi["gt_idx"] not in cross_gt_idx:
                confusion_ca[2][mi["cls"]] += 1
            fn_rows.append({
                "image_id": stem,
                "gt_class": cname,
                "gt_bbox_xyxy": mi["bbox"],
                "best_any_iou": mi["best_any_iou"],
                "best_any_pred_class": mi["best_any_pred_class"],
                "best_same_class_iou": mi["best_same_class_iou"],
                "localized_but_missed": mi["localized_but_missed"],
                "class_aware_cross_class": mi["gt_idx"] in cross_gt_idx,
            })

        is_background = len(gt_boxes) == 0
        if is_background:
            background_only_images += 1
            if img_fp and sum(img_fp.values()) > 0:
                background_images_with_fp += 1

        timings_total.append(float(result.timing_ms.get("total", 0.0)))
        timings_infer.append(float(result.timing_ms.get("inference", 0.0)))

        if not args.no_viz:
            viz_path = VIZ_DIR / f"{stem}.jpg"
            render_overlay(image_bgr, gt_boxes, preds, match_info, viz_path)

        per_image.append({
            "image_id": stem,
            "image_path": str(img_path),
            "width": w,
            "height": h,
            "status": status,
            "is_background_only": is_background,
            "gt": img_gt,
            "pred": img_pred,
            "tp": img_tp,
            "fp": img_fp,
            "fn": img_fn,
            "predictions": [
                {"class": CLASS_NAMES.get(p["cls"], "unsupported"), "confidence": round(p["conf"], 4),
                 "bbox_xyxy": [round(v, 2) for v in p["bbox"]]}
                for p in preds
            ],
            "matched": [
                {"class": CLASS_NAMES[m["cls"]], "confidence": round(m["conf"], 4), "iou": round(m["iou"], 4)}
                for m in match_info["matched"]
            ],
        })

        if idx % 25 == 0 or idx == n:
            print(f"    processed {idx}/{n} images ...")

    # -- Aggregate ----------------------------------------------------------- #
    per_class: Dict[str, Any] = {}
    for cname in CLASS_NAMES.values():
        tp, fp, fn = tp_counts[cname], fp_counts[cname], fn_counts[cname]
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        per_class[cname] = {
            "gt_count": gt_counts[cname],
            "pred_count": pred_counts[cname],
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "matched_iou": stats(matched_ious[cname]),
            "confidence_all_predictions": stats(conf_all_pred[cname]),
            "confidence_tp": stats(conf_tp[cname]),
            "confidence_fp": stats(conf_fp[cname]),
        }

    tp_t = sum(tp_counts.values())
    fp_t = sum(fp_counts.values())
    fn_t = sum(fn_counts.values())
    micro_p = tp_t / (tp_t + fp_t) if (tp_t + fp_t) else 0.0
    micro_r = tp_t / (tp_t + fn_t) if (tp_t + fn_t) else 0.0
    micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)) if (micro_p + micro_r) else 0.0

    # Independently verify the holdout identity actually processed.
    gt_total = sum(gt_counts.values())
    checks = {
        "images_processed": len(test_images),
        "images_expected": EXPECTED_IMAGES if args.limit == 0 else len(test_images),
        "gt_boxes_total": gt_total,
        "gt_pothole": gt_counts["pothole"],
        "gt_crack": gt_counts["crack"],
        "background_only_images": background_only_images,
        "checkpoint_sha256_unchanged": True,  # set below
        "holdout_identity_ok": True,          # set below
    }
    if args.limit == 0:
        checks["holdout_identity_ok"] = bool(
            len(test_images) == EXPECTED_IMAGES
            and gt_total == EXPECTED_GT_TOTAL
            and gt_counts["pothole"] == EXPECTED_GT_POTHOLE
            and gt_counts["crack"] == EXPECTED_GT_CRACK
            and background_only_images == EXPECTED_BACKGROUND_IMAGES
        )

    # -- Integrity hashes (after) ------------------------------------------- #
    ckpt_sha_after = sha256_file(configured_ckpt)
    labels_merkle_after = merkle_of_files(label_files)
    checks["checkpoint_sha256_unchanged"] = (ckpt_sha_before == ckpt_sha_after)
    content_unchanged = (
        ckpt_sha_before == ckpt_sha_after
        and labels_merkle_before == labels_merkle_after
        and sha256_file(DATASET_YAML) == dataset_yaml_sha
        and sha256_file(TEST_SPLIT) == test_split_sha
        and sha256_file(DETECTION_CONFIG) == det_cfg_sha
    )
    checks["content_unchanged"] = content_unchanged

    # -- Confusion matrices -------------------------------------------------- #
    # (a) Per-class (VOC/COCO convention): a same-class match is a TP; cross-class
    #     overlaps are counted as an FP (background) plus an FN of the true class.
    # (b) Class-aware: leftover predictions/GTs are paired by geometry alone so a
    #     genuine "right box, wrong class" error is visible on the off-diagonal.
    confusion_matrix = {
        "convention": "per-class matching (VOC/COCO): background cell = no same-class match",
        "axis_convention": "matrix[predicted][true]; classes = [pothole, crack, background]",
        "labels": labels3,
        "matrix": confusion,
        "column_sums_true_class": [sum(confusion[r][c] for r in range(3)) for c in range(3)],
        "interpretation": {
            "tp_pothole": confusion[0][0], "tp_crack": confusion[1][1],
            "fp_pothole_on_background": confusion[0][2], "fp_crack_on_background": confusion[1][2],
            "cross_pothole_pred_on_crack": confusion[0][1], "cross_crack_pred_on_pothole": confusion[1][0],
            "fn_pothole": confusion[2][0], "fn_crack": confusion[2][1],
        },
    }
    confusion_matrix_class_aware = {
        "convention": "unmatched predictions/GTs greedily paired by geometry (any class)",
        "axis_convention": "matrix[predicted][true]; classes = [pothole, crack, background]",
        "labels": labels3,
        "matrix": confusion_ca,
        "column_sums_true_class": [sum(confusion_ca[r][c] for r in range(3)) for c in range(3)],
        "interpretation": {
            "tp_pothole": confusion_ca[0][0], "tp_crack": confusion_ca[1][1],
            "fp_pothole_on_background": confusion_ca[0][2], "fp_crack_on_background": confusion_ca[1][2],
            "cross_pothole_pred_on_crack": confusion_ca[0][1], "cross_crack_pred_on_pothole": confusion_ca[1][0],
            "fn_pothole": confusion_ca[2][0], "fn_crack": confusion_ca[2][1],
        },
    }
    cross_class_errors = {
        "total": len(cross_class_rows),
        "by_pair": cross_pair_counts,
        "note": ("Locally correct boxes with the wrong predicted class (IoU >= match threshold). "
                 "These are already counted as an FP + FN in the per-class metrics."),
        "detail_csv": "cross_class_errors.csv",
    }

    # -- Build summary ------------------------------------------------------- #
    summary = {
        "phase": PHASE,
        "script": SCRIPT_NAME,
        "generated_at_utc": timestamp,
        "workspace_root": str(WORKSPACE_ROOT),
        "mode": "evaluation-only (application detection pipeline)",
        "guardrails": {
            "training": False, "checkpoint_changed": False, "v2_promoted": False,
            "dataset_split_modified": False, "checkpoint_used_is_configured": True,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "opencv": cv2.__version__,
            "numpy": np.__version__,
        },
        "application_detector": {
            "module": "src.detection.detector.HazardDetector",
            "detector_version": detector.detector_version,
            "model_version": detector.model_version,
            "configured_model_version": configured_model_version,
            "pipeline_version": detector.pipeline.version,
            "checkpoint_path": str(configured_ckpt),
            "checkpoint_sha256_before": ckpt_sha_before,
            "checkpoint_sha256_after": ckpt_sha_after,
            "imgsz": detector.imgsz,
            "conf_threshold": active_conf,
            "conf_from_config": detector.conf_threshold,
            "iou_threshold": detector.iou_threshold,
            "max_det": detector.max_det,
            "augment": detector.augment,
            "device": str(device),
            "device_reason": device_reason,
        },
        "evaluation": {
            "dataset_config": str(DATASET_YAML),
            "dataset_config_sha256": dataset_yaml_sha,
            "detection_config": str(DETECTION_CONFIG),
            "detection_config_sha256": det_cfg_sha,
            "test_split": str(TEST_SPLIT),
            "test_split_sha256": test_split_sha,
            "derived_labels_merkle_before": labels_merkle_before,
            "derived_labels_merkle_after": labels_merkle_after,
            "match_iou_threshold": args.match_iou,
            "limit_applied": args.limit,
        },
        "holdout": {
            "images": len(test_images),
            "images_with_any_gt": len(test_images) - background_only_images,
            "background_only_images": background_only_images,
            "gt_boxes_total": gt_total,
            "gt_pothole": gt_counts["pothole"],
            "gt_crack": gt_counts["crack"],
        },
        "inference": {
            "status_counts": status_counts,
            "images_with_predictions": sum(1 for r in per_image if sum(r["pred"].values()) > 0),
            "predictions_total": sum(pred_counts.values()),
            "predictions_pothole": pred_counts["pothole"],
            "predictions_crack": pred_counts["crack"],
            "timing_ms_total": stats(timings_total),
            "timing_ms_inference": stats(timings_infer),
        },
        "overall_detection_metrics_at_operating_point": {
            "note": ("Micro precision/recall/F1 at the serving confidence (config) and "
                     f"match IoU {args.match_iou}. Predictions below the serving confidence are "
                     "not produced by the pipeline and are therefore not scored."),
            "tp": tp_t, "fp": fp_t, "fn": fn_t,
            "precision": round(micro_p, 4),
            "recall": round(micro_r, 4),
            "f1": round(micro_f1, 4),
        },
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
        "confusion_matrix_class_aware": confusion_matrix_class_aware,
        "cross_class_errors": cross_class_errors,
        "background_only_analysis": {
            "images": background_only_images,
            "images_with_false_positive": background_images_with_fp,
            "images_clean": background_only_images - background_images_with_fp,
            "false_positives": sum(1 for r in fp_rows if r["gt_boxes_in_image"] == 0),
            "clean_rate": round((background_only_images - background_images_with_fp) / background_only_images, 4)
            if background_only_images else None,
        },
        "false_positives": {
            "total": len(fp_rows),
            "by_class": {c: fp_counts[c] for c in CLASS_NAMES.values()},
            "detail_csv": "false_positives.csv",
        },
        "missed_detections": {
            "total": len(fn_rows),
            "by_class": {c: fn_counts[c] for c in CLASS_NAMES.values()},
            "localized_but_missed": sum(1 for r in fn_rows if r["localized_but_missed"]),
            "no_nearby_prediction": sum(1 for r in fn_rows if not r["localized_but_missed"]),
            "detail_csv": "missed_detections.csv",
        },
        "verification_checks": checks,
        "per_image": per_image,
    }

    # -- Write artifacts ----------------------------------------------------- #
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUT_DIR / "real_image_detection_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with open(OUT_DIR / "false_positives.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_id", "predicted_class", "confidence",
                                               "bbox_xyxy", "gt_boxes_in_image",
                                               "class_aware_cross_class"])
        writer.writeheader()
        writer.writerows(fp_rows)

    with open(OUT_DIR / "missed_detections.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_id", "gt_class", "gt_bbox_xyxy", "best_any_iou",
                                               "best_any_pred_class", "best_same_class_iou",
                                               "localized_but_missed", "class_aware_cross_class"])
        writer.writeheader()
        writer.writerows(fn_rows)

    with open(OUT_DIR / "cross_class_errors.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_id", "predicted_class", "confidence",
                                               "gt_class", "iou", "pred_bbox_xyxy", "gt_bbox_xyxy"])
        writer.writeheader()
        writer.writerows([{k: v for k, v in row.items() if k != "both_classes_supported"}
                          for row in cross_class_rows])

    # Clean any transient Ultralytics label cache to restore the derived tree.
    cache = DERIVED_ROOT / "labels.cache"
    cache_removed = False
    if cache.exists():
        cache.unlink()
        cache_removed = True

    elapsed = time.perf_counter() - started

    # -- Console report ------------------------------------------------------ #
    print("\n================ PHASE 24E — RESULTS (application pipeline) ================")
    print(f"Device               : {device}  ({device_reason})")
    print(f"Checkpoint           : {configured_ckpt.name}  sha={ckpt_sha_before[:12]}…")
    print(f"Holdout              : {len(test_images)} images | "
          f"GT pothole={gt_counts['pothole']} crack={gt_counts['crack']} "
          f"bg-only={background_only_images}")
    print(f"Predictions          : total={sum(pred_counts.values())} "
          f"(pothole={pred_counts['pothole']}, crack={pred_counts['crack']})")
    print(f"Statuses             : {status_counts}")
    print("-- Per class ---------------------------------------------------------------")
    for cname in CLASS_NAMES.values():
        pc = per_class[cname]
        iou = pc["matched_iou"]
        iou_txt = f"{iou['mean']:.3f} (min {iou['min']:.3f}, max {iou['max']:.3f})" if iou else "n/a"
        print(f"  {cname:8s} GT={pc['gt_count']:3d} Pred={pc['pred_count']:3d} "
              f"TP={pc['tp']:3d} FP={pc['fp']:3d} FN={pc['fn']:3d} | "
              f"P={pc['precision']:.3f} R={pc['recall']:.3f} F1={pc['f1']:.3f} | matched IoU mean={iou_txt}")
    print(f"-- Overall (micro)   P={micro_p:.3f} R={micro_r:.3f} F1={micro_f1:.3f}  "
          f"(TP={tp_t} FP={fp_t} FN={fn_t})")
    print(f"-- Background-only   {background_only_images} images | "
          f"with FP={background_images_with_fp} | clean={background_only_images - background_images_with_fp}")
    print(f"-- Cross-class       {len(cross_class_rows)} box(es) localized but wrong class "
          f"({cross_pair_counts})")
    print(f"Content unchanged    : {content_unchanged}")
    print(f"Visualisations       : {VIZ_DIR.relative_to(WORKSPACE_ROOT)}"
          f"{' (skipped)' if args.no_viz else f' ({len(test_images)} files)'}")
    print(f"JSON summary         : {summary_path.relative_to(WORKSPACE_ROOT)}")
    print(f"labels.cache removed : {cache_removed}")
    print(f"Elapsed              : {elapsed:.1f}s")
    print("===========================================================================")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
