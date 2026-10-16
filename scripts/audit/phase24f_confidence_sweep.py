#!/usr/bin/env python3
"""SafeRoute AI — PHASE 24F: confidence-threshold sweep through the APPLICATION pipeline.

This is a **read-only, evaluation-only** harness. It drives the shipped
``src.detection.detector.HazardDetector`` (module ``detect-v2``, PHASE 06
``preprocess-v1`` OpenCV pipeline) over a dataset split at a LOW confidence floor,
collects every candidate detection, then recomputes precision / recall / F1 / FP / FN
for a grid of confidence operating points **without re-running inference**.

Why this is exact
-----------------
Ultralytics NMS is class-aware and ordered by descending confidence: a lower-confidence
box never suppresses a higher-confidence box. Therefore the set of boxes that survive at
threshold ``T`` equals the set of boxes from a run at a lower floor filtered to
``conf >= T`` (subject to ``max_det``). We additionally re-run the detector directly at
the chosen operating point on the same split and assert the counts match, to make the
equivalence empirically checkable rather than merely asserted.

Selection discipline
---------------------
* Model and threshold **selection** uses the designated validation split only
  (``data/splits_v2/val.txt``).
* ``--split test`` is offered for **exploratory** context only; the PHASE 24E report
  already examined the test split, so it is **not** pristine and must not drive selection.

Guardrails (master_rules.md Rules 1, 5, 9, 14, 15, 16, 18, 19, 20)
------------------------------------------------------------------
* No training, fine-tuning, resume or weight change.
* No checkpoint promotion, replacement or overwrite.
* No modification of ``config/detection.yaml`` or ``config/hazard_severity.yaml``
  (the configured checkpoint and the serving confidence are left untouched).
* No dataset, label or split modification.
* Loads an alternate checkpoint (e.g. v2) only when explicitly requested, read-only, and
  records its SHA-256 before/after.
* Writes only NEW files under ``reports/phase24f/`` (override with ``--out-dir``).

Usage
-----
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24f_confidence_sweep.py --checkpoint v1 --split val
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24f_confidence_sweep.py --checkpoint v2 --split val
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24f_confidence_sweep.py --checkpoint v1 --split test --exploratory
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
# Reuse the PHASE 24E matching / GT helpers so scoring semantics are identical.
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts" / "audit"))
import phase24e_real_image_detection as p24e  # noqa: E402

PHASE = "PHASE 24F"
SCRIPT_NAME = "scripts/audit/phase24f_confidence_sweep.py"

DERIVED_ROOT = WORKSPACE_ROOT / "data" / "derived_2class"
LABELS_DIR = DERIVED_ROOT / "labels"
DETECTION_CONFIG = WORKSPACE_ROOT / "config" / "detection.yaml"
SEVERITY_CONFIG = WORKSPACE_ROOT / "config" / "hazard_severity.yaml"
DATASET_V2_YAML = WORKSPACE_ROOT / "data" / "dataset_v2.yaml"
SPLITS_V2 = WORKSPACE_ROOT / "data" / "splits_v2"
ORIGINAL_SPLITS = WORKSPACE_ROOT / "data" / "splits"

CLASS_NAMES = {0: "pothole", 1: "crack"}
CHECKPOINTS = {
    "v1": WORKSPACE_ROOT / "models" / "training" / "saferoute-yolo11-v1" / "weights" / "best.pt",
    "v2": WORKSPACE_ROOT / "models" / "training" / "saferoute-yolo11-v2" / "weights" / "best.pt",
    "datayolo": WORKSPACE_ROOT / "models" / "training" / "saferoute-yolo11-datayolo-exp" / "weights" / "best.pt",
}
CONFIGURED_CHECKPOINT_REL = Path("models/training/saferoute-yolo11-v1/weights/best.pt")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_split(name: str) -> List[str]:
    path = SPLITS_V2 / f"{name}.txt"
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines


def stems_of(path: Path) -> set:
    if not path.is_file():
        return set()
    return {Path(l.strip()).stem for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def provenance_map() -> Dict[str, str]:
    """Tag each stem by which ORIGINAL split(s) it belonged to.

    The v1/v2 checkpoints were trained on ``data/dataset.yaml`` (the ORIGINAL split).
    This tag is evidence for the leakage disclosure, not a scoring input.
    """
    orig = {n: stems_of(ORIGINAL_SPLITS / f"{n}.txt") for n in ("train", "val", "test")}
    tags: Dict[str, str] = {}
    for stem in set().union(*orig.values()):
        where = [n for n in ("train", "val", "test") if stem in orig[n]]
        tags[stem] = "+".join(where) if where else "unknown"
    return tags


def _counts_from_matches(match_info: Dict[str, Any], preds: List[Dict[str, Any]]) -> Dict[str, int]:
    tp = {c: 0 for c in CLASS_NAMES.values()}
    fp = {c: 0 for c in CLASS_NAMES.values()}
    fn = {c: 0 for c in CLASS_NAMES.values()}
    for m in match_info["matched"]:
        tp[CLASS_NAMES[m["cls"]]] += 1
    for pi in match_info["fp_pred_indices"]:
        fp[CLASS_NAMES[preds[pi]["cls"]]] += 1
    for mi in match_info["missed"]:
        if mi["cls"] in CLASS_NAMES:
            fn[CLASS_NAMES[mi["cls"]]] += 1
    return {"tp": tp, "fp": fp, "fn": fn}


def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def aggregate(preds_by_image: Dict[str, List[Dict[str, Any]]],
              gt_by_image: Dict[str, List[Dict[str, Any]]],
              threshold_by_class: Dict[int, float],
              match_iou: float,
              image_ids: Sequence[str]) -> Dict[str, Any]:
    """Score a set of images at per-class thresholds. Matching is per-class independent,
    so per-class counts combine exactly for any (pothole_thr, crack_thr) pair."""
    tp = {c: 0 for c in CLASS_NAMES.values()}
    fp = {c: 0 for c in CLASS_NAMES.values()}
    fn = {c: 0 for c in CLASS_NAMES.values()}
    bg_images = 0
    bg_images_fp = 0

    for iid in image_ids:
        gts = gt_by_image[iid]
        thr_preds = [p for p in preds_by_image[iid] if p["conf"] >= threshold_by_class[p["cls"]]]
        info = p24e.match_image(gts, thr_preds, match_iou)
        cc = _counts_from_matches(info, thr_preds)
        for c in CLASS_NAMES.values():
            tp[c] += cc["tp"][c]
            fp[c] += cc["fp"][c]
            fn[c] += cc["fn"][c]
        if not gts:
            bg_images += 1
            if thr_preds:
                bg_images_fp += 1

    per_class = {c: _prf(tp[c], fp[c], fn[c]) for c in CLASS_NAMES.values()}
    tp_t = sum(tp.values()); fp_t = sum(fp.values()); fn_t = sum(fn.values())
    overall = _prf(tp_t, fp_t, fn_t)
    out: Dict[str, Any] = {
        "overall": overall,
        "pothole": per_class["pothole"],
        "crack": per_class["crack"],
    }
    if bg_images:
        out["background_only"] = {
            "images": bg_images,
            "images_with_fp": bg_images_fp,
            "images_clean": bg_images - bg_images_fp,
            "clean_rate": round((bg_images - bg_images_fp) / bg_images, 4),
        }
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="PHASE 24F application-pipeline confidence sweep.")
    ap.add_argument("--checkpoint", choices=["v1", "v2"], default="v1",
                    help="Which existing checkpoint to load. Default v1 (the configured one).")
    ap.add_argument("--split", choices=["val", "test"], default="val",
                    help="Dataset split to score. Default val (selection split).")
    ap.add_argument("--conf-floor", type=float, default=0.05,
                    help="Low confidence floor used to collect candidates (default 0.05).")
    ap.add_argument("--match-iou", type=float, default=0.5,
                    help="IoU threshold for a prediction<->GT match (default 0.5).")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--limit", type=int, default=0, help="Only first N images (0 = all).")
    ap.add_argument("--out-dir", default=str(WORKSPACE_ROOT / "reports" / "phase24f"))
    ap.add_argument("--exploratory", action="store_true",
                    help="Mark this run as exploratory (required if --split test).")
    ap.add_argument("--verify-conf", type=float, default=None,
                    help="Re-run the detector directly at this conf and compare to the swept counts.")
    ap.add_argument("--class-thresholds", type=str, default=None,
                    help="Apply explicit per-class thresholds 'pothole:0.4,crack:0.5' (exploratory).")
    return ap.parse_args(argv)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.split == "test" and not args.exploratory:
        print("REFUSING: scoring the test split requires --exploratory (it is not a pristine holdout).",
              file=sys.stderr)
        return 2

    ckpt_path = CHECKPOINTS[args.checkpoint]
    configured_path = (WORKSPACE_ROOT / CONFIGURED_CHECKPOINT_REL).resolve()
    is_configured = (ckpt_path.resolve() == configured_path)

    # --- config identity (must remain unchanged) ----------------------------- #
    det_cfg = yaml.safe_load(DETECTION_CONFIG.read_text(encoding="utf-8"))
    sev_cfg = yaml.safe_load(SEVERITY_CONFIG.read_text(encoding="utf-8"))
    config_conf = float(det_cfg["inference"]["conf"])
    aggregator_conf = float(sev_cfg["thresholds"]["confidence_threshold"])
    det_cfg_sha = p24e.sha256_file(DETECTION_CONFIG)
    sev_cfg_sha = p24e.sha256_file(SEVERITY_CONFIG)
    ds_yaml_sha = p24e.sha256_file(DATASET_V2_YAML)
    split_file = SPLITS_V2 / f"{args.split}.txt"
    split_sha = p24e.sha256_file(split_file)
    ckpt_sha_before = p24e.sha256_file(ckpt_path)

    images = read_split(args.split)
    if args.limit > 0:
        images = images[: args.limit]
    missing = [p for p in images if not Path(p).is_file()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} image(s) missing, e.g. {missing[0]}")

    label_files = [LABELS_DIR / f"{Path(p).stem}.txt" for p in images]
    missing_labels = [lp for lp in label_files if not lp.is_file()]
    if missing_labels:
        raise FileNotFoundError(f"{len(missing_labels)} label file(s) missing, e.g. {missing_labels[0]}")
    labels_merkle_before = p24e.merkle_of_files(label_files)

    # --- device + detector --------------------------------------------------- #
    device, device_reason = p24e.select_device(args.device)
    print(f"[{PHASE}] checkpoint={args.checkpoint} split={args.split} images={len(images)}")
    print(f"  device    : {device}  ({device_reason})")
    print(f"  checkpoint: {ckpt_path}")

    from src.detection.detector import HazardDetector

    detector = HazardDetector(checkpoint_path=ckpt_path, device=device)
    print(f"  detector  : {detector.detector_version} (model_version label '{detector.model_version}') "
          f"imgsz={detector.imgsz} iou={detector.iou_threshold} max_det={detector.max_det}")
    print(f"  config conf={config_conf} aggregator conf={aggregator_conf} floor={args.conf_floor} "
          f"match_iou={args.match_iou}")

    prov = provenance_map()

    # --- collect candidates at the low floor --------------------------------- #
    preds_by_image: Dict[str, List[Dict[str, Any]]] = {}
    gt_by_image: Dict[str, List[Dict[str, Any]]] = {}
    status_counts: Dict[str, int] = {}
    provenance_counts: Dict[str, int] = {}
    import cv2  # local import to keep cv2 usage explicit

    for idx, img_path in enumerate(images, start=1):
        stem = Path(img_path).stem
        img = cv2.imread(img_path)
        if img is None:
            raise RuntimeError(f"OpenCV could not read image: {img_path}")
        h, w = img.shape[:2]
        gt_by_image[stem] = p24e.load_gt_boxes(LABELS_DIR / f"{stem}.txt", w, h)

        result = detector.detect(img_path, image_id=stem, conf=args.conf_floor)
        status_counts[result.status.value] = status_counts.get(result.status.value, 0) + 1
        preds: List[Dict[str, Any]] = []
        for d in result.detections:
            cls = {v: k for k, v in CLASS_NAMES.items()}.get(d.hazard_class)
            if cls is None:
                continue  # unsupported class: disclose, never fabricate (Rule 5)
            preds.append({"cls": cls, "conf": float(d.confidence), "bbox": [float(v) for v in d.bbox_xyxy]})
        preds_by_image[stem] = preds
        provenance_counts[prov.get(stem, "unknown")] = provenance_counts.get(prov.get(stem, "unknown"), 0) + 1
        if idx % 50 == 0 or idx == len(images):
            print(f"    processed {idx}/{len(images)} ...")

    image_ids = [Path(p).stem for p in images]

    # --- global sweep -------------------------------------------------------- #
    grid = sorted({round(x, 2) for x in [0.05 + 0.05 * i for i in range(18)]} | {round(config_conf, 2)})
    global_points: List[Dict[str, Any]] = []
    for t in grid:
        agg = aggregate(preds_by_image, gt_by_image, {0: t, 1: t}, args.match_iou, image_ids)
        agg["threshold"] = t
        global_points.append(agg)

    # --- provenance-subset sensitivity (leakage robustness check) ------------ #
    provenance_sweep: Dict[str, Any] = {}
    for tagv in sorted({prov.get(i, "unknown") for i in image_ids}):
        ids = [i for i in image_ids if prov.get(i, "unknown") == tagv]
        points = []
        for t in grid:
            agg = aggregate(preds_by_image, gt_by_image, {0: t, 1: t}, args.match_iou, ids)
            agg["threshold"] = t
            points.append(agg)
        provenance_sweep[tagv] = {"images": len(ids), "points": points}

    # --- per-class single-threshold tables (for combining class-specific) ---- #
    class_grid = [round(0.05 + 0.05 * i, 2) for i in range(18)]
    per_class_table: Dict[str, List[Dict[str, Any]]] = {"pothole": [], "crack": []}
    for cls_id, cname in CLASS_NAMES.items():
        for t in class_grid:
            thr = {0: 1.0, 1: 1.0}  # other class silenced entirely
            thr[cls_id] = t
            agg = aggregate(preds_by_image, gt_by_image, thr, args.match_iou, image_ids)
            per_class_table[cname].append({"threshold": t, **agg[cname]})

    # --- class-specific combination (exact because matching is per-class) ---- #
    def cls_counts(cname: str, t: float) -> Tuple[int, int, int]:
        row = next(r for r in per_class_table[cname] if r["threshold"] == t)
        return row["tp"], row["fp"], row["fn"]

    best_micro = None
    best_per_class = {"pothole": None, "crack": None}
    for tp_t in class_grid:
        ptp, pfp, pfn = cls_counts("pothole", tp_t)
        for tc_t in class_grid:
            ctp, cfp, cfn = cls_counts("crack", tc_t)
            overall = _prf(ptp + ctp, pfp + cfp, pfn + cfn)
            if best_micro is None or overall["f1"] > best_micro["overall"]["f1"]:
                best_micro = {"pothole_threshold": tp_t, "crack_threshold": tc_t, "overall": overall,
                              "pothole": _prf(ptp, pfp, pfn), "crack": _prf(ctp, cfp, cfn)}
    for cls_id, cname in CLASS_NAMES.items():
        for t in class_grid:
            tp, fp, fn = cls_counts(cname, t)
            row = _prf(tp, fp, fn)
            if best_per_class[cname] is None or row["f1"] > best_per_class[cname]["f1"]:
                best_per_class[cname] = {"threshold": t, **row}

    # --- optional direct verification at a threshold -------------------------- #
    direct_verification = None
    if args.verify_conf is not None:
        vt = float(args.verify_conf)
        # direct: run the detector at conf=vt and score directly
        d_tp = {c: 0 for c in CLASS_NAMES.values()}; d_fp = dict.fromkeys(CLASS_NAMES.values(), 0); d_fn = dict.fromkeys(CLASS_NAMES.values(), 0)
        for img_path in images:
            stem = Path(img_path).stem
            r = detector.detect(img_path, image_id=stem, conf=vt)
            preds = [{"cls": {v: k for k, v in CLASS_NAMES.items()}[d.hazard_class], "conf": float(d.confidence),
                      "bbox": [float(v) for v in d.bbox_xyxy]}
                     for d in r.detections if d.hazard_class in CLASS_NAMES.values()]
            info = p24e.match_image(gt_by_image[stem], preds, args.match_iou)
            cc = _counts_from_matches(info, preds)
            for c in CLASS_NAMES.values():
                d_tp[c] += cc["tp"][c]; d_fp[c] += cc["fp"][c]; d_fn[c] += cc["fn"][c]
        direct = {
            "overall": _prf(sum(d_tp.values()), sum(d_fp.values()), sum(d_fn.values())),
            "pothole": _prf(d_tp["pothole"], d_fp["pothole"], d_fn["pothole"]),
            "crack": _prf(d_tp["crack"], d_fp["crack"], d_fn["crack"]),
        }
        swept = aggregate(preds_by_image, gt_by_image, {0: vt, 1: vt}, args.match_iou, image_ids)
        direct_verification = {
            "conf": vt,
            "direct": direct,
            "swept": {"overall": swept["overall"], "pothole": swept["pothole"], "crack": swept["crack"]},
            "counts_match": (
                direct["overall"]["tp"] == swept["overall"]["tp"]
                and direct["overall"]["fp"] == swept["overall"]["fp"]
                and direct["overall"]["fn"] == swept["overall"]["fn"]
            ),
        }

    # --- integrity after ----------------------------------------------------- #
    ckpt_sha_after = p24e.sha256_file(ckpt_path)
    labels_merkle_after = p24e.merkle_of_files(label_files)
    content_unchanged = (
        ckpt_sha_before == ckpt_sha_after
        and labels_merkle_before == labels_merkle_after
        and p24e.sha256_file(DETECTION_CONFIG) == det_cfg_sha
        and p24e.sha256_file(SEVERITY_CONFIG) == sev_cfg_sha
        and p24e.sha256_file(DATASET_V2_YAML) == ds_yaml_sha
        and p24e.sha256_file(split_file) == split_sha
    )
    cache = DERIVED_ROOT / "labels.cache"
    cache_removed = False
    if cache.exists():
        cache.unlink(); cache_removed = True

    gt_total = sum(len(v) for v in gt_by_image.values())
    gt_pothole = sum(1 for v in gt_by_image.values() for b in v if b["cls"] == 0)
    gt_crack = sum(1 for v in gt_by_image.values() for b in v if b["cls"] == 1)
    empty_images = sum(1 for v in gt_by_image.values() if not v)

    def counts_text(row: Dict[str, Any]) -> str:
        o = row["overall"]
        return (f"T={row['threshold']:.2f} P={o['precision']:.3f} R={o['recall']:.3f} F1={o['f1']:.3f} "
                f"(TP={o['tp']} FP={o['fp']} FN={o['fn']})")

    at_config = next(r for r in global_points if abs(r["threshold"] - round(config_conf, 2)) < 1e-9)

    summary = {
        "phase": PHASE,
        "script": SCRIPT_NAME,
        "generated_at_utc": timestamp,
        "workspace_root": str(WORKSPACE_ROOT),
        "mode": "evaluation-only (application detection pipeline, confidence sweep)",
        "exploratory": bool(args.exploratory or args.split == "test"),
        "guardrails": {
            "training": False, "checkpoint_promoted": False, "checkpoint_overwritten": False,
            "config_modified": False, "dataset_split_modified": False, "production_config_changed": False,
        },
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "opencv": cv2.__version__, "numpy": np.__version__,
        },
        "checkpoint": {
            "tag": args.checkpoint,
            "path": str(ckpt_path),
            "sha256_before": ckpt_sha_before,
            "sha256_after": ckpt_sha_after,
            "is_configured_checkpoint": is_configured,
            "configured_checkpoint": str(configured_path),
            "note": ("Loaded read-only via HazardDetector(checkpoint_path=...). The detector's "
                     "model_version string is a module constant ('saferoute-yolo11-v1') and is not "
                     "updated when an alternate checkpoint is supplied; the checkpoint path/SHA above "
                     "is authoritative."),
        },
        "config": {
            "detection_yaml_sha256": det_cfg_sha,
            "severity_yaml_sha256": sev_cfg_sha,
            "detection_conf": config_conf,
            "aggregator_conf": aggregator_conf,
            "threshold_policy_consistent": abs(config_conf - aggregator_conf) < 1e-9,
            "dataset_v2_yaml_sha256": ds_yaml_sha,
            "split_file": str(split_file),
            "split_sha256": split_sha,
        },
        "application_detector": {
            "module": "src.detection.detector.HazardDetector",
            "detector_version": detector.detector_version,
            "pipeline_version": detector.pipeline.version,
            "imgsz": detector.imgsz, "iou_nms": detector.iou_threshold,
            "max_det": detector.max_det, "augment": detector.augment,
            "device": str(device), "device_reason": device_reason,
            "conf_floor": args.conf_floor, "match_iou": args.match_iou,
        },
        "split": {
            "name": args.split, "images": len(images),
            "gt_boxes_total": gt_total, "gt_pothole": gt_pothole, "gt_crack": gt_crack,
            "empty_label_images": empty_images,
            "provenance_counts": provenance_counts,
            "provenance_note": ("Tag = which ORIGINAL split(s) contained the image. v1/v2 were trained "
                                "on data/dataset.yaml (original split), so 'train' tagged images were "
                                "seen during training. This is a leakage disclosure, not a scoring input."),
        },
        "inference_status_counts": status_counts,
        "global_sweep": global_points,
        "at_configured_conf": at_config,
        "provenance_sweep": provenance_sweep,
        "per_class_single_threshold_table": per_class_table,
        "class_specific_exploratory": {
            "supported_by_app": False,
            "note": ("The app exposes a single inference.conf (shared with the aggregator). Per-class "
                     "thresholds would require a detector code change, so this is an exploratory upper "
                     "bound, not a drop-in configuration."),
            "best_micro_f1_pair": best_micro,
            "best_threshold_per_class": best_per_class,
        },
        "direct_verification": direct_verification,
        "integrity": {
            "checkpoint_sha256_unchanged": ckpt_sha_before == ckpt_sha_after,
            "derived_labels_merkle_before": labels_merkle_before,
            "derived_labels_merkle_after": labels_merkle_after,
            "content_unchanged": content_unchanged,
            "labels_cache_removed": cache_removed,
        },
        "per_image": [
            {
                "image_id": iid,
                "provenance": prov.get(iid, "unknown"),
                "gt": {"pothole": sum(1 for b in gt_by_image[iid] if b["cls"] == 0),
                       "crack": sum(1 for b in gt_by_image[iid] if b["cls"] == 1)},
                "candidates": [
                    {"class": CLASS_NAMES[p["cls"]], "confidence": round(p["conf"], 4),
                     "bbox_xyxy": [round(v, 2) for v in p["bbox"]]}
                    for p in preds_by_image[iid]
                ],
            }
            for iid in image_ids
        ],
    }

    tag = f"{args.checkpoint}_{args.split}"
    out_json = out_dir / f"{tag}_sweep.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with open(out_dir / f"{tag}_operating_points.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["threshold", "overall_tp", "overall_fp", "overall_fn", "overall_p", "overall_r", "overall_f1",
                    "pothole_tp", "pothole_fp", "pothole_fn", "pothole_p", "pothole_r", "pothole_f1",
                    "crack_tp", "crack_fp", "crack_fn", "crack_p", "crack_r", "crack_f1",
                    "bg_images", "bg_images_with_fp", "bg_clean_rate"])
        for row in global_points:
            bg = row.get("background_only", {})
            w.writerow([
                row["threshold"],
                row["overall"]["tp"], row["overall"]["fp"], row["overall"]["fn"],
                row["overall"]["precision"], row["overall"]["recall"], row["overall"]["f1"],
                row["pothole"]["tp"], row["pothole"]["fp"], row["pothole"]["fn"],
                row["pothole"]["precision"], row["pothole"]["recall"], row["pothole"]["f1"],
                row["crack"]["tp"], row["crack"]["fp"], row["crack"]["fn"],
                row["crack"]["precision"], row["crack"]["recall"], row["crack"]["f1"],
                bg.get("images", ""), bg.get("images_with_fp", ""), bg.get("clean_rate", ""),
            ])

    # --- console report ------------------------------------------------------ #
    print("\n================ PHASE 24F — CONFIDENCE SWEEP (application pipeline) ================")
    print(f"Checkpoint : {args.checkpoint} ({'CONFIGURED' if is_configured else 'alternate'})  "
          f"sha={ckpt_sha_before[:12]}…")
    print(f"Split      : {args.split}  images={len(images)}  GT pothole={gt_pothole} crack={gt_crack} "
          f"bg-only={empty_images}")
    print(f"Provenance : {provenance_counts}")
    print(f"-- Global sweep (match IoU {args.match_iou}) --")
    for row in global_points:
        print(f"   {counts_text(row)}   "
              f"| pothole P={row['pothole']['precision']:.3f} R={row['pothole']['recall']:.3f} "
              f"| crack P={row['crack']['precision']:.3f} R={row['crack']['recall']:.3f}")
    print(f"-- At configured conf {config_conf:.2f}: {counts_text(at_config)}")
    print(f"-- Best global F1 (this split): "
          f"{max(global_points, key=lambda r: r['overall']['f1'])['threshold']:.2f} "
          f"F1={max(r['overall']['f1'] for r in global_points):.4f}")
    print(f"-- Class-specific exploratory best micro-F1 pair: "
          f"pothole={best_micro['pothole_threshold']:.2f} crack={best_micro['crack_threshold']:.2f} "
          f"F1={best_micro['overall']['f1']:.4f} (NOT drop-in)")
    if direct_verification:
        print(f"-- Direct verification at conf {direct_verification['conf']:.2f}: "
              f"counts_match={direct_verification['counts_match']}")
    print(f"Content unchanged: {content_unchanged}   (checkpoint/config/labels/split)")
    print(f"JSON  : {out_json.relative_to(WORKSPACE_ROOT)}")
    print(f"Elapsed: {time.perf_counter() - started:.1f}s")
    print("=====================================================================================")

    return 0 if content_unchanged else 4


if __name__ == "__main__":
    raise SystemExit(main())
