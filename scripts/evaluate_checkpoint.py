#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""SafeRoute AI — checkpoint evaluation (accuracy measurement).

Evaluates ANY YOLO checkpoint on the audited derived two-class dataset and
writes a reproducible JSON record. This exists so a candidate can be compared
honestly against the historical v2 reference on the SAME held-out test split.

Rules followed:
  * Rule 14 — report measured metrics only; never fabricate mAP/P/R/F1.
  * Rule 15 — dataset identity (config + split hashes) recorded.
  * Rule 17 — provenance, environment and limitations recorded.
  * Rule 18 — read-only with respect to datasets, configs and serving weights.
  * Rule 20 — the record states whether the checkpoint is a smoke substitute.

Usage (from the workspace root):
  .\.venv\Scripts\python.exe scripts\evaluate_checkpoint.py \
      --checkpoint models/training/_tmp_v3_candidate/candidate_v3/weights/best.pt \
      --data data/dataset_v2.yaml \
      --out reports/phase45_v3_candidate_eval.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Reported (not reproduced here) reference from PHASE_24D, same dataset/splits.
REFERENCE_V2 = {
    "source": "reports/phase24d/v2_metrics.json (REPORTED, checkpoint now missing)",
    "overall": {
        "precision": 0.573405,
        "recall": 0.701783,
        "f1": 0.631131,
        "mAP50": 0.579049,
        "mAP50_95": 0.328326,
    },
    "pothole": {"mAP50": 0.3785, "mAP50_95": 0.192203},
    "crack": {"mAP50": 0.779598, "mAP50_95": 0.464449},
}

SMOKE_MARKERS = ("P0_SMOKE_SUBSTITUTE.json", "P0_SMOKE_MODEL.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def inside_workspace(path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        raise SystemExit(f"Rule 1 violation: {label} '{resolved}' is outside {WORKSPACE_ROOT}")
    return resolved


def smoke_marker(checkpoint: Path) -> Optional[Path]:
    for directory in (checkpoint.parent, checkpoint.parent.parent):
        for name in SMOKE_MARKERS:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def class_metrics(results, class_id: int) -> Dict[str, float]:
    """Per-class P/R/mAP, tolerant across Ultralytics minor versions."""
    box = results.box
    try:
        p, r, ap50, ap = box.class_result(class_id)
        return {
            "precision": round(float(p), 6),
            "recall": round(float(r), 6),
            "mAP50": round(float(ap50), 6),
            "mAP50_95": round(float(ap), 6),
        }
    except Exception:
        pass
    p = float(box.p[class_id]) if hasattr(box, "p") else 0.0
    r = float(box.r[class_id]) if hasattr(box, "r") else 0.0
    ap50 = float(box.ap50[class_id]) if hasattr(box, "ap50") else 0.0
    ap = float(box.maps[class_id]) if hasattr(box, "maps") else 0.0
    return {
        "precision": round(p, 6),
        "recall": round(r, 6),
        "mAP50": round(ap50, 6),
        "mAP50_95": round(ap, 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data", default="data/dataset_v2.yaml")
    parser.add_argument("--split", default="test", choices=["val", "test", "train"])
    parser.add_argument("--imgsz", type=int, default=768)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--conf", type=float, default=0.001,
                        help="mAP confidence floor (0.001 is the standard evaluation floor)")
    parser.add_argument("--device", default="0")
    parser.add_argument("--out", required=True)
    parser.add_argument("--plots", action="store_true")
    args = parser.parse_args()

    checkpoint = inside_workspace(Path(args.checkpoint), "checkpoint")
    if not checkpoint.is_file():
        raise SystemExit(f"Checkpoint not found: {checkpoint}")
    data_path = inside_workspace(Path(args.data), "dataset config")
    out_path = inside_workspace(Path(args.out), "output report")

    import torch
    import ultralytics
    import yaml
    from ultralytics import YOLO

    with open(data_path, "r", encoding="utf-8") as handle:
        data_cfg = yaml.safe_load(handle) or {}

    split_hashes = {}
    split_counts = {}
    for split_name in ("train", "val", "test"):
        rel = data_cfg.get(split_name)
        if not rel:
            continue
        split_file = (WORKSPACE_ROOT / rel).resolve()
        if split_file.is_file():
            split_hashes[split_name] = sha256(split_file)
            split_counts[split_name] = sum(
                1 for line in split_file.read_text(encoding="utf-8").splitlines() if line.strip()
            )

    device = args.device if torch.cuda.is_available() else "cpu"
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else platform.processor()

    marker = smoke_marker(checkpoint)
    ckpt_hash = sha256(checkpoint)

    model = YOLO(str(checkpoint))
    started = datetime.now(timezone.utc)
    results = model.val(
        data=str(data_path),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        conf=args.conf,
        device=device,
        project=str(WORKSPACE_ROOT / "models" / "evaluation"),
        name=f"candidate_{args.split}",
        exist_ok=True,
        plots=args.plots,
        verbose=False,
    )
    finished = datetime.now(timezone.utc)

    box = results.box
    precision = float(box.mp)
    recall = float(box.mr)
    f1 = 2 * precision * recall / (precision + recall + 1e-16)
    names: List[str] = [data_cfg.get("names", {}).get(i, str(i)) for i in range(len(box.ap50))]

    per_class = []
    for class_id, name in enumerate(names):
        metrics = class_metrics(results, class_id)
        metrics["class_id"] = class_id
        metrics["class_name"] = name
        per_class.append(metrics)

    def overall(key: str) -> float:
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mAP50": float(box.map50),
            "mAP50_95": float(box.map),
        }[key]

    record: Dict[str, Any] = {
        "phase": "ACCURACY-EVAL",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": {
            "path": str(checkpoint.relative_to(WORKSPACE_ROOT.resolve())),
            "sha256": ckpt_hash,
            "bytes": checkpoint.stat().st_size,
            "smoke_marker": str(marker.relative_to(WORKSPACE_ROOT.resolve())) if marker else None,
            "is_smoke_substitute": marker is not None,
            "note": (
                "P0 smoke substitute — metrics describe pipeline behaviour only and "
                "must not be presented as validated model accuracy."
                if marker is not None
                else "No smoke marker beside checkpoint."
            ),
        },
        "dataset": {
            "config_path": str(data_path.relative_to(WORKSPACE_ROOT.resolve())),
            "config_sha256": sha256(data_path),
            "split": args.split,
            "split_sha256": split_hashes,
            "split_counts": split_counts,
            "classes": data_cfg.get("names"),
        },
        "evaluation": {
            "imgsz": args.imgsz,
            "batch": args.batch,
            "conf_floor": args.conf,
            "started_utc": started.isoformat(),
            "finished_utc": finished.isoformat(),
            "duration_seconds": round((finished - started).total_seconds(), 2),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "device": device_name,
            "ultralytics": ultralytics.__version__,
        },
        "metrics": {
            "overall": {
                "precision": round(precision, 6),
                "recall": round(recall, 6),
                "f1": round(f1, 6),
                "mAP50": round(float(box.map50), 6),
                "mAP50_95": round(float(box.map), 6),
            },
            "per_class": per_class,
            "speed_per_image_ms": {k: round(float(v), 3) for k, v in results.speed.items()},
            "confusion_matrix": results.confusion_matrix.matrix.tolist(),
        },
        "reference_v2_reported": REFERENCE_V2,
        "limitations": [
            "Test split is used ONCE for final reporting; model selection must use val.",
            "Dataset is a single dashcam source; metrics do not generalise to other cities/cameras.",
            "No independent dataset exists (data/independent/ absent); Phase 42 remains NOT_ASSESSED.",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    ref = REFERENCE_V2["overall"]
    print("=" * 68)
    print(f"Checkpoint : {record['checkpoint']['path']}")
    print(f"Smoke      : {record['checkpoint']['is_smoke_substitute']}")
    print(f"Split      : {args.split} ({split_counts.get(args.split, '?')} images)")
    print("-" * 68)
    print(f"mAP50      : {record['metrics']['overall']['mAP50']:.4f}   "
          f"(v2 reported {ref['mAP50']:.4f})")
    print(f"mAP50-95   : {record['metrics']['overall']['mAP50_95']:.4f}   "
          f"(v2 reported {ref['mAP50_95']:.4f})")
    print(f"Precision  : {record['metrics']['overall']['precision']:.4f}   "
          f"(v2 reported {ref['precision']:.4f})")
    print(f"Recall     : {record['metrics']['overall']['recall']:.4f}   "
          f"(v2 reported {ref['recall']:.4f})")
    print("-" * 68)
    for entry in per_class:
        print(f"{entry['class_name']:<10} mAP50={entry['mAP50']:.4f}  "
              f"mAP50-95={entry['mAP50_95']:.4f}  P={entry['precision']:.4f}  R={entry['recall']:.4f}")
    print("=" * 68)
    print(f"Report written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
