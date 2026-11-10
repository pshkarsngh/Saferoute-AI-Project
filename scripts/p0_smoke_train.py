#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SafeRoute AI — P0 smoke-model bootstrap (NON-PRODUCTION).

Purpose
-------
The original accepted checkpoints (``saferoute-yolo11-v1`` / ``-v2``) are not
present in this workspace. To restore a *runnable* P0 environment without
pretending the originals were recovered, this script trains a short, clearly
labelled **smoke** checkpoint on the derived two-class dataset. It exists only
to verify checkpoint loading, GPU/CPU inference, threshold handling and the
end-to-end analysis path.

It is NOT a replacement for the accepted production model and must never be
reported as the original v1/v2 artifact.

Outputs (all inside the workspace, Rule 1):
    models/training/p0-smoke/weights/best.pt
    models/training/p0-smoke/P0_SMOKE_MODEL.json   (provenance + warning)
    logs/p0_smoke/train.log

Run from the workspace root:
    .\\.venv\\Scripts\\python.exe scripts\\p0_smoke_train.py
"""

from __future__ import annotations

import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATASET_YAML = WORKSPACE_ROOT / "data" / "dataset_v2.yaml"
PRETRAINED = WORKSPACE_ROOT / "yolo11n.pt"
PROJECT_DIR = WORKSPACE_ROOT / "models" / "training"
RUN_NAME = "p0-smoke"
LOG_DIR = WORKSPACE_ROOT / "logs" / "p0_smoke"

EPOCHS = 8
IMGSZ = 640
BATCH = 8
SEED = 0


def main() -> int:
    import cv2
    import numpy as np
    import torch
    import ultralytics
    import yaml
    from ultralytics import YOLO

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    if not DATASET_YAML.is_file():
        raise SystemExit(f"Dataset config missing: {DATASET_YAML}")
    with open(DATASET_YAML, "r", encoding="utf-8") as f:
        dataset_cfg = yaml.safe_load(f)

    device = 0 if torch.cuda.is_available() else "cpu"
    started = time.time()
    print(f"[P0] workspace: {WORKSPACE_ROOT}")
    print(f"[P0] dataset:   {DATASET_YAML} -> {dataset_cfg.get('names')}")
    print(f"[P0] device:    {device} ({torch.cuda.get_device_name(0) if device == 0 else 'cpu'})")
    print("[P0] NON-PRODUCTION smoke run: this checkpoint is not the accepted v1/v2 model.")

    # Ultralytics resolves the dataset YAML's relative paths against CWD, so run
    # from the workspace root explicitly.
    import os

    os.chdir(WORKSPACE_ROOT)

    model = YOLO(str(PRETRAINED if PRETRAINED.is_file() else "yolo11n.pt"))
    model.train(
        data=str(DATASET_YAML),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        device=device,
        workers=4,
        seed=SEED,
        deterministic=True,
        project=str(PROJECT_DIR),
        name=RUN_NAME,
        exist_ok=True,
        verbose=True,
    )

    best = PROJECT_DIR / RUN_NAME / "weights" / "best.pt"
    if not best.is_file():
        raise SystemExit(f"Smoke training finished but no checkpoint at {best}")

    elapsed = round(time.time() - started, 1)
    record = {
        "status": "NON_PRODUCTION_SMOKE_MODEL",
        "warning": (
            "Temporary P0 smoke checkpoint. NOT the original saferoute-yolo11-v1 "
            "or saferoute-yolo11-v2 artifact. Do not use for safety claims."
        ),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "checkpoint": str(best),
        "checkpoint_bytes": best.stat().st_size,
        "dataset_yaml": str(DATASET_YAML),
        "dataset_classes": dataset_cfg.get("names"),
        "epochs": EPOCHS,
        "imgsz": IMGSZ,
        "batch": BATCH,
        "seed": SEED,
        "device": "cuda:0" if device == 0 else "cpu",
        "gpu": torch.cuda.get_device_name(0) if device == 0 else None,
        "versions": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "ultralytics": ultralytics.__version__,
            "opencv": cv2.__version__,
            "numpy": np.__version__,
        },
    }
    (PROJECT_DIR / RUN_NAME / "P0_SMOKE_MODEL.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
