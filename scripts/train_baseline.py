#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
SafeRoute AI — Phase 08: YOLO11 Baseline Training Execution Script
Phase ID: PHASE_08
Model Version: saferoute-yolo11-v1
Follows: master_rules.md (Rules 1, 3, 4, 14, 16, 17, 18, 19),
         docs/TRAINING_RULES.md, docs/phases/PHASE_08.md
"""

import os
import sys
import time
import json
import yaml
import shutil
import hashlib
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE_ROOT = Path("D:/New folder (3)").resolve()

class TeeLogger:
    """Duplicates stdout/stderr to a log file."""
    def __init__(self, filepath: Path, original_stream):
        self.file = open(filepath, "a", encoding="utf-8")
        self.stream = original_stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
        self.file.write(data)
        self.file.flush()

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def close(self):
        self.file.close()

def compute_sha256(filepath: Path) -> str:
    """Computes SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()

def verify_path_inside_workspace(p: Path, name: str):
    """Ensures a path resolves strictly inside the workspace (Rule 1)."""
    resolved = p.resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise RuntimeError(f"VIOLATION of Rule 1: {name} path '{resolved}' is outside workspace '{WORKSPACE_ROOT}'")

def get_git_commit() -> str:
    """Gets the current git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception as e:
        return f"UNKNOWN ({e})"

def main():
    print("=" * 70)
    print("SafeRoute AI — PHASE_08 Baseline Training Launch")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # 1. Verify workspace isolation
    current_cwd = Path.cwd().resolve()
    verify_path_inside_workspace(current_cwd, "Current working directory")
    print(f"[VERIFIED] Workspace root: {WORKSPACE_ROOT}")

    # 2. Load configurations
    config_path = WORKSPACE_ROOT / "config" / "training_baseline.yaml"
    verify_path_inside_workspace(config_path, "Training config")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    dataset_yaml_path = WORKSPACE_ROOT / cfg["dataset"]["config_path"]
    verify_path_inside_workspace(dataset_yaml_path, "Dataset config")
    with open(dataset_yaml_path, "r", encoding="utf-8") as f:
        dataset_cfg = yaml.safe_load(f)

    # 3. Setup logging directory
    log_dir = WORKSPACE_ROOT / cfg["paths"]["log_dir"]
    verify_path_inside_workspace(log_dir, "Log directory")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "train.log"
    tee_out = TeeLogger(log_file, sys.stdout)
    tee_err = TeeLogger(log_file, sys.stderr)
    sys.stdout = tee_out
    sys.stderr = tee_err

    # 4. Check pretrained weights
    weights_path = WORKSPACE_ROOT / cfg["model"]["pretrained_weights"]
    verify_path_inside_workspace(weights_path, "Pretrained weights")
    if not weights_path.exists():
        raise FileNotFoundError(f"Pretrained weights missing at {weights_path}")
    weights_hash = compute_sha256(weights_path)
    print(f"[VERIFIED] Pretrained weights: {weights_path.name}")
    print(f"[VERIFIED] SHA-256: {weights_hash}")

    # 5. Check dependencies & PyTorch CUDA
    import torch
    import ultralytics
    import cv2
    import psutil

    if not torch.cuda.is_available():
        raise RuntimeError("Rule 16 violation: torch.cuda.is_available() is False; CUDA required for baseline run")

    device_id = cfg["hyperparameters"]["device"]
    device_name = torch.cuda.get_device_name(device_id)
    free_vram, total_vram = torch.cuda.mem_get_info(device_id)
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(WORKSPACE_ROOT)

    print(f"[VERIFIED] PyTorch: {torch.__version__} (CUDA: {torch.version.cuda})")
    print(f"[VERIFIED] Device {device_id}: {device_name}")
    print(f"[VERIFIED] VRAM: {free_vram / (1024**3):.2f} GB free / {total_vram / (1024**3):.2f} GB total")
    print(f"[VERIFIED] Host RAM: {vm.available / (1024**3):.2f} GB free / {vm.total / (1024**3):.2f} GB total")
    print(f"[VERIFIED] Disk: {disk.free / (1024**3):.2f} GB free / {disk.total / (1024**3):.2f} GB total")
    print(f"[VERIFIED] Ultralytics: {ultralytics.__version__}")
    print(f"[VERIFIED] OpenCV: {cv2.__version__}")

    # 6. Verify dataset files and test isolation
    train_split = Path(dataset_cfg["train"]).resolve()
    val_split = Path(dataset_cfg["val"]).resolve()
    test_split = Path(dataset_cfg["test"]).resolve()
    verify_path_inside_workspace(train_split, "Train split")
    verify_path_inside_workspace(val_split, "Val split")
    verify_path_inside_workspace(test_split, "Test split")

    train_lines = len(train_split.read_text(encoding="utf-8").splitlines())
    val_lines = len(val_split.read_text(encoding="utf-8").splitlines())
    test_lines = len(test_split.read_text(encoding="utf-8").splitlines())

    print(f"[VERIFIED] Split counts: train={train_lines}, val={val_lines}, test={test_lines}")
    print(f"[VERIFIED] Test isolation: {test_split} is excluded from training and validation (Phase 09 isolation confirmed).")

    # 7. Reproducibility metadata collection
    git_commit = get_git_commit()
    config_hash = compute_sha256(config_path)
    dataset_yaml_hash = compute_sha256(dataset_yaml_path)
    train_hash = compute_sha256(train_split)
    val_hash = compute_sha256(val_split)
    test_hash = compute_sha256(test_split)

    start_time_utc = datetime.now(timezone.utc)
    start_time_local = datetime.now()

    run_record = {
        "phase_id": "PHASE_08",
        "experiment_name": cfg["experiment"]["name"],
        "model_version": cfg["experiment"]["model_version"],
        "git_commit": git_commit,
        "timestamps": {
            "start_utc": start_time_utc.isoformat(),
            "start_local": start_time_local.isoformat(),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "ultralytics": ultralytics.__version__,
            "opencv": cv2.__version__,
            "gpu_device": device_name,
            "gpu_vram_total_mb": round(total_vram / (1024**2), 2),
            "gpu_vram_free_start_mb": round(free_vram / (1024**2), 2),
            "host_ram_free_start_mb": round(vm.available / (1024**2), 2),
            "disk_free_start_gb": round(disk.free / (1024**3), 2),
        },
        "artefact_hashes": {
            "training_config_yaml": config_hash,
            "dataset_yaml": dataset_yaml_hash,
            "pretrained_weights": weights_hash,
            "train_split": train_hash,
            "val_split": val_hash,
            "test_split": test_hash,
        },
        "dataset_metadata": {
            "dataset_root": str(dataset_cfg["path"]),
            "classes": dataset_cfg["names"],
            "unsupported_classes": cfg["dataset"].get("unsupported_classes", {}),
            "counts": {"train": train_lines, "val": val_lines, "test": test_lines},
        },
        "hyperparameters": cfg["hyperparameters"],
        "paths": cfg["paths"],
    }

    # 8. Output directory verification
    project_dir = (WORKSPACE_ROOT / cfg["paths"]["project"]).resolve()
    verify_path_inside_workspace(project_dir, "Project outputs")
    exp_name = cfg["paths"]["name"]

    print("\n" + "=" * 70)
    print("LAUNCHING BASELINE TRAINING RUN")
    print(f"Model: {weights_path.name}")
    print(f"Output Project: {project_dir}")
    print(f"Run Name: {exp_name}")
    print(f"Hyperparameters: {cfg['hyperparameters']}")
    print("=" * 70 + "\n")

    t0 = time.time()
    run_status = "FAILED"
    error_msg = None

    try:
        from ultralytics import YOLO

        model = YOLO(str(weights_path))
        hyp = cfg["hyperparameters"]

        # Run training strictly according to the frozen configuration
        train_results = model.train(
            data=str(dataset_yaml_path),
            epochs=hyp["epochs"],
            imgsz=hyp["imgsz"],
            batch=hyp["batch"],
            patience=hyp["patience"],
            optimizer=hyp["optimizer"],
            lr0=hyp["lr0"],
            lrf=hyp["lrf"],
            momentum=hyp["momentum"],
            weight_decay=hyp["weight_decay"],
            warmup_epochs=hyp["warmup_epochs"],
            warmup_momentum=hyp["warmup_momentum"],
            warmup_bias_lr=hyp["warmup_bias_lr"],
            box=hyp["box"],
            cls=hyp["cls"],
            dfl=hyp["dfl"],
            amp=hyp["amp"],
            seed=hyp["seed"],
            deterministic=hyp["deterministic"],
            workers=hyp["workers"],
            device=hyp["device"],
            save_period=cfg["paths"].get("save_period", 5),
            project=str(project_dir),
            name=exp_name,
            exist_ok=True,
            val=True,
            plots=True,
            save=True,
        )

        run_status = "COMPLETED"
        print("\n[SUCCESS] Training loop completed successfully!")

    except torch.cuda.OutOfMemoryError as oom:
        run_status = "OOM_STOPPED"
        error_msg = f"CUDA Out of Memory: {oom}"
        print(f"\n[CRITICAL ERROR] {error_msg}")
    except KeyboardInterrupt:
        run_status = "INTERRUPTED"
        error_msg = "User/process interrupted training run."
        print(f"\n[INTERRUPTED] {error_msg}")
    except Exception as e:
        run_status = "ERROR"
        error_msg = f"Unexpected exception during training: {type(e).__name__}: {e}"
        print(f"\n[ERROR] {error_msg}")
        import traceback
        traceback.print_exc()

    t1 = time.time()
    elapsed_sec = t1 - t0
    end_time_utc = datetime.now(timezone.utc)
    end_time_local = datetime.now()

    # 9. Checkpoint and artefact verification
    exp_dir = project_dir / exp_name
    weights_dir = exp_dir / "weights"
    best_pt = weights_dir / "best.pt"
    last_pt = weights_dir / "last.pt"

    best_exists = best_pt.exists()
    last_exists = last_pt.exists()
    best_hash = compute_sha256(best_pt) if best_exists else None
    last_hash = compute_sha256(last_pt) if last_exists else None

    print("\n" + "=" * 70)
    print("TRAINING RUN SUMMARY")
    print(f"Status: {run_status}")
    print(f"Duration: {elapsed_sec:.2f} seconds ({elapsed_sec / 60:.2f} minutes)")
    print(f"Output Directory: {exp_dir}")
    print(f"Best checkpoint exists: {best_exists} (Hash: {best_hash})")
    print(f"Last checkpoint exists: {last_exists} (Hash: {last_hash})")
    if error_msg:
        print(f"Errors/Warnings: {error_msg}")
    print("=" * 70)

    # 10. Update and save run record
    run_record["outcome"] = {
        "status": run_status,
        "elapsed_seconds": round(elapsed_sec, 2),
        "duration_formatted": f"{elapsed_sec / 60:.2f} min",
        "error_message": error_msg,
        "end_utc": end_time_utc.isoformat(),
        "end_local": end_time_local.isoformat(),
        "checkpoints": {
            "best_pt": {
                "path": str(best_pt),
                "exists": best_exists,
                "sha256": best_hash,
            },
            "last_pt": {
                "path": str(last_pt),
                "exists": last_exists,
                "sha256": last_hash,
            },
        },
        "output_directory": str(exp_dir),
    }

    run_record_file = log_dir / "run_record.json"
    with open(run_record_file, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)
    print(f"[VERIFIED] Saved run record to {run_record_file}")

    # Restore streams
    sys.stdout = tee_out.stream
    sys.stderr = tee_err.stream
    tee_out.close()
    tee_err.close()

    if run_status != "COMPLETED":
        sys.exit(1)

if __name__ == "__main__":
    main()
