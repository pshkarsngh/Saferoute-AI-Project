#!/usr/bin/env python3
"""SafeRoute AI — PHASE 24F supplement: LEAKAGE-CONTROLLED holdout evaluation.

Motivation (measured, see PHASE_24F report)
-------------------------------------------
The v1/v2 checkpoints were trained on the ORIGINAL random split
(``data/dataset.yaml`` -> ``data/splits/*.txt``). The PHASE 24C derived splits
were rebuilt date-atomic, which *reshuffled* images across splits:

* derived ``test``  = capture date 2025-02-26 -> **all 216 images were in the
  original TRAIN split** (original train contains all 217 of that date).
* derived ``val``   = 138/178 images were in the original TRAIN split.

So neither derived ``test`` nor derived ``val`` is a clean holdout for v1/v2.
The ONLY images v1/v2 never saw are those in the ORIGINAL ``val``/``test``
splits (601 images; 561 of them now fall inside derived ``train`` and 40 inside
derived ``val``).

This harness evaluates the shipped application pipeline on that leakage-free
set, read-only. It performs NO training, changes NO checkpoint, config, dataset
or split, and writes only NEW files under ``reports/phase24f_verify_clean/``.

It reuses the PHASE 24E matching code and the PHASE 24F aggregation so scoring
semantics are identical to the rest of the sweep.

Usage
-----
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24f_clean_holdout.py --checkpoint v1
    .\\.venv\\Scripts\\python.exe scripts\\audit\\phase24f_clean_holdout.py --checkpoint v2
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts" / "audit"))
import phase24e_real_image_detection as p24e  # noqa: E402
import phase24f_confidence_sweep as p24f  # noqa: E402

OUT_DIR = WORKSPACE_ROOT / "reports" / "phase24f_verify_clean"
LABELS_DIR = WORKSPACE_ROOT / "data" / "derived_2class" / "labels"
ORIGINAL_SPLITS = WORKSPACE_ROOT / "data" / "splits"
DERIVED_SPLITS = WORKSPACE_ROOT / "data" / "splits_v2"
CONFIG_FLOOR = 0.05
MATCH_IOU = 0.5
GRID = [round(0.05 + 0.05 * i, 2) for i in range(18)]


def stems_of(p: Path) -> set:
    return {Path(l.strip()).stem for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


def unseen_image_paths() -> List[Path]:
    """All derived images whose stem was in the ORIGINAL val or test split."""
    unseen = stems_of(ORIGINAL_SPLITS / "val.txt") | stems_of(ORIGINAL_SPLITS / "test.txt")
    paths: List[Path] = []
    for split in ("train", "val", "test"):
        for line in (DERIVED_SPLITS / f"{split}.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            if Path(line).stem in unseen:
                paths.append(Path(line))
    return paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", choices=["v1", "v2"], required=True)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    ckpt = p24f.CHECKPOINTS[args.checkpoint]
    ckpt_before = p24e.sha256_file(ckpt)

    images = unseen_image_paths()
    if args.limit > 0:
        images = images[: args.limit]
    label_files = [LABELS_DIR / f"{p.stem}.txt" for p in images]
    missing = [str(p) for p in images if not p.is_file()]
    missing_lbl = [str(l) for l in label_files if not l.is_file()]
    if missing or missing_lbl:
        raise FileNotFoundError(f"missing images={len(missing)} labels={len(missing_lbl)}")
    merkle_before = p24e.merkle_of_files(label_files)

    device, device_reason = p24e.select_device(args.device)
    print(f"[PHASE 24F-CLEAN] checkpoint={args.checkpoint} images={len(images)} device={device} ({device_reason})")

    from src.detection.detector import HazardDetector

    detector = HazardDetector(checkpoint_path=ckpt, device=device)
    print(f"  detector {detector.detector_version} imgsz={detector.imgsz} iou={detector.iou_threshold} "
          f"max_det={detector.max_det} floor={CONFIG_FLOOR}")

    import cv2

    preds_by_image: Dict[str, List[Dict[str, Any]]] = {}
    gt_by_image: Dict[str, List[Dict[str, Any]]] = {}
    for idx, p in enumerate(images, start=1):
        stem = p.stem
        img = cv2.imread(str(p))
        if img is None:
            raise RuntimeError(f"cannot read {p}")
        h, w = img.shape[:2]
        gt_by_image[stem] = p24e.load_gt_boxes(LABELS_DIR / f"{stem}.txt", w, h)
        r = detector.detect(str(p), image_id=stem, conf=CONFIG_FLOOR)
        cls_map = {v: k for k, v in p24f.CLASS_NAMES.items()}
        preds_by_image[stem] = [
            {"cls": cls_map[d.hazard_class], "conf": float(d.confidence),
             "bbox": [float(v) for v in d.bbox_xyxy]}
            for d in r.detections if d.hazard_class in cls_map
        ]
        if idx % 100 == 0 or idx == len(images):
            print(f"    processed {idx}/{len(images)} ...")

    image_ids = [p.stem for p in images]

    global_points = []
    for t in GRID:
        agg = p24f.aggregate(preds_by_image, gt_by_image, {0: t, 1: t}, MATCH_IOU, image_ids)
        agg["threshold"] = t
        global_points.append(agg)

    # direct verification at the serving conf 0.25
    vt = 0.25
    dtp = {c: 0 for c in p24f.CLASS_NAMES.values()}
    dfp = dict.fromkeys(p24f.CLASS_NAMES.values(), 0)
    dfn = dict.fromkeys(p24f.CLASS_NAMES.values(), 0)
    for p in images:
        stem = p.stem
        r = detector.detect(str(p), image_id=stem, conf=vt)
        cls_map = {v: k for k, v in p24f.CLASS_NAMES.items()}
        preds = [{"cls": cls_map[d.hazard_class], "conf": float(d.confidence),
                  "bbox": [float(v) for v in d.bbox_xyxy]}
                 for d in r.detections if d.hazard_class in cls_map]
        info = p24e.match_image(gt_by_image[stem], preds, MATCH_IOU)
        cc = p24f._counts_from_matches(info, preds)
        for c in p24f.CLASS_NAMES.values():
            dtp[c] += cc["tp"][c]; dfp[c] += cc["fp"][c]; dfn[c] += cc["fn"][c]
    direct = {
        "overall": p24f._prf(sum(dtp.values()), sum(dfp.values()), sum(dfn.values())),
        "pothole": p24f._prf(dtp["pothole"], dfp["pothole"], dfn["pothole"]),
        "crack": p24f._prf(dtp["crack"], dfp["crack"], dfn["crack"]),
    }
    at_config = next(p for p in global_points if abs(p["threshold"] - 0.25) < 1e-9)

    ckpt_after = p24e.sha256_file(ckpt)
    merkle_after = p24e.merkle_of_files(label_files)

    gt_pothole = sum(1 for v in gt_by_image.values() for b in v if b["cls"] == 0)
    gt_crack = sum(1 for v in gt_by_image.values() for b in v if b["cls"] == 1)
    empty_images = sum(1 for v in gt_by_image.values() if not v)

    summary = {
        "phase": "PHASE 24F (leakage-controlled supplement)",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "evaluation-only (application pipeline, leakage-free subset)",
        "exploratory": False,
        "guardrails": {"training": False, "checkpoint_promoted": False, "checkpoint_overwritten": False,
                       "config_modified": False, "dataset_split_modified": False,
                       "production_config_changed": False},
        "checkpoint": {"tag": args.checkpoint, "path": str(ckpt), "sha256_before": ckpt_before,
                       "sha256_after": ckpt_after, "is_configured_checkpoint":
                       ckpt.resolve() == (WORKSPACE_ROOT / p24f.CONFIGURED_CHECKPOINT_REL).resolve()},
        "application_detector": {"module": "src.detection.detector.HazardDetector",
                                 "imgsz": detector.imgsz, "iou_nms": detector.iou_threshold,
                                 "max_det": detector.max_det, "conf_floor": CONFIG_FLOOR,
                                 "match_iou": MATCH_IOU, "device": str(device), "device_reason": device_reason},
        "clean_set_definition": ("stems present in data/splits/val.txt or data/splits/test.txt "
                                 "(the ORIGINAL splits); none of these were in the v1/v2 training data"),
        "split": {"name": "leakage_free (original val+test)", "images": len(images),
                  "gt_boxes_total": gt_pothole + gt_crack, "gt_pothole": gt_pothole,
                  "gt_crack": gt_crack, "background_only_images": empty_images},
        "global_sweep": global_points,
        "at_configured_conf": at_config,
        "direct_verification_at_0.25": {"direct": direct,
                                        "swept": {"overall": at_config["overall"],
                                                  "pothole": at_config["pothole"],
                                                  "crack": at_config["crack"]},
                                        "counts_match": (
                                            direct["overall"]["tp"] == at_config["overall"]["tp"]
                                            and direct["overall"]["fp"] == at_config["overall"]["fp"]
                                            and direct["overall"]["fn"] == at_config["overall"]["fn"])},
        "integrity": {"checkpoint_sha256_unchanged": ckpt_before == ckpt_after,
                      "derived_labels_merkle_before": merkle_before,
                      "derived_labels_merkle_after": merkle_after,
                      "content_unchanged": ckpt_before == ckpt_after and merkle_before == merkle_after},
        "per_image": [{"image_id": iid, "gt_pothole": sum(1 for b in gt_by_image[iid] if b["cls"] == 0),
                       "gt_crack": sum(1 for b in gt_by_image[iid] if b["cls"] == 1),
                       "candidates": [{"class": p24f.CLASS_NAMES[c["cls"]], "confidence": round(c["conf"], 4)}
                                      for c in preds_by_image[iid]]} for iid in image_ids],
    }

    out_json = OUT_DIR / f"{args.checkpoint}_clean_sweep.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(OUT_DIR / f"{args.checkpoint}_clean_operating_points.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["threshold", "overall_tp", "overall_fp", "overall_fn", "overall_p", "overall_r", "overall_f1",
                    "pothole_tp", "pothole_fp", "pothole_fn", "pothole_p", "pothole_r", "pothole_f1",
                    "crack_tp", "crack_fp", "crack_fn", "crack_p", "crack_r", "crack_f1"])
        for row in global_points:
            w.writerow([row["threshold"], row["overall"]["tp"], row["overall"]["fp"], row["overall"]["fn"],
                        row["overall"]["precision"], row["overall"]["recall"], row["overall"]["f1"],
                        row["pothole"]["tp"], row["pothole"]["fp"], row["pothole"]["fn"],
                        row["pothole"]["precision"], row["pothole"]["recall"], row["pothole"]["f1"],
                        row["crack"]["tp"], row["crack"]["fp"], row["crack"]["fn"],
                        row["crack"]["precision"], row["crack"]["recall"], row["crack"]["f1"]])

    print(f"\n[CLEAN] {args.checkpoint}: images={len(images)} gt pothole={gt_pothole} crack={gt_crack} bg={empty_images}")
    for row in global_points:
        if row["threshold"] in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35):
            o = row["overall"]
            print(f"   T={row['threshold']:.2f} P={o['precision']:.3f} R={o['recall']:.3f} F1={o['f1']:.3f} "
                  f"(TP={o['tp']} FP={o['fp']} FN={o['fn']})")
    print(f"   counts_match={summary['direct_verification_at_0.25']['counts_match']} "
          f"content_unchanged={summary['integrity']['content_unchanged']} "
          f"elapsed={time.perf_counter() - t0:.1f}s")
    return 0 if summary["integrity"]["content_unchanged"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
