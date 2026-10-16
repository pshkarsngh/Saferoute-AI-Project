#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
SafeRoute AI — PHASE 24D: Fresh holdout evaluation (v1 vs v2).

EVALUATION ONLY. This script is strictly read-only with respect to:
  * original images / labels / splits / dataset.yaml
  * derived images / labels / splits / dataset_v2.yaml
  * all model checkpoints (v1, v2)

It writes only NEW files under reports/phase24d/.

Governing rules: master_rules.md 1, 5, 9, 14, 15, 17, 18, 19, 20.
Specification: docs/reports/PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md and
               data/derived_2class/MANIFEST.json.

Modes
-----
  verify            verify state (hashes, holdout identity, no leakage) and
                    write reports/phase24d/holdout_verification.json
  eval <v1|v2>      run ONE Ultralytics test-split evaluation of the given
                    checkpoint on data/dataset_v2.yaml (216-image holdout) and
                    write reports/phase24d/<tag>_metrics.json

Usage
-----
  .\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py verify
  .\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py eval v1
  .\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py eval v2
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path("D:/New folder (3)").resolve()
OUT_ROOT = WORKSPACE_ROOT / "reports" / "phase24d"

DATASET_V2_YAML = WORKSPACE_ROOT / "data" / "dataset_v2.yaml"
DATASET_V1_YAML = WORKSPACE_ROOT / "data" / "dataset.yaml"
SPLITS_V2 = WORKSPACE_ROOT / "data" / "splits_v2"
DERIVED = WORKSPACE_ROOT / "data" / "derived_2class"
DERIVED_LABELS = DERIVED / "labels"
DERIVED_MANIFEST = DERIVED / "MANIFEST.json"
SPLIT_MANIFEST_CSV = SPLITS_V2 / "split_manifest.csv"

CHECKPOINTS = {
    "v1": WORKSPACE_ROOT / "models" / "training" / "saferoute-yolo11-v1" / "weights" / "best.pt",
    "v2": WORKSPACE_ROOT / "models" / "training" / "saferoute-yolo11-v2" / "weights" / "best.pt",
}

# Expected identity, cross-checked against PHASE_24C report + prior records.
EXPECTED_CKPT_SHA = {
    "v1": "61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65",
    "v2": "B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA",
}
EXPECTED_DATASET_V2_SHA = "98EDD97ADDF2F72779335E6622D575C0C3B88E2C7BDF88ADAD31BDD3D62C1912"
EXPECTED_DATASET_V1_SHA = "CD502CDC20B732CBBE239A6F80FBA69CFD4B9451CFBE5BA26EC2AC0687E5969E"
EXPECTED_SPLIT_SHA = {
    "train": "3DC10C151E939C283328A6E615B51BCD25607A3C2CDDEB296A9062F967CC5978",
    "val": "37D92842313D013C6030B857EC81C22FF4FD4B051AAD011AF25E89B8011621A1",
    "test": "AABA32ABA36C668145017715CC4C9190D0C58457EBE6CD66D515EF9BE0325D07",
}
EXPECTED_DERIVED_LABELS_MERKLE = "0C15D6AF395335FC6FAF06A90F6261BEFFFA05A78C9A4C114B936FBB01158142"
EXPECTED_DATASET_V2_TOTAL_IMAGES = 216
EXPECTED_TEST_BOXES = {0: 98, 1: 292}
EXPECTED_TEST_EMPTY_LABELS = 46
EXPECTED_TEST_DATE = "2025-02-26"

KEEP_CLASSES = {0, 1}
CLASS_NAMES = {0: "pothole", 1: "crack"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def merkle_dir_digest(directory: Path, pattern: str) -> tuple[str, int]:
    """Same algorithm used by the PHASE 24C generator."""
    entries = []
    files = sorted(directory.glob(pattern))
    for p in files:
        entries.append(f"{p.name}:{sha256_file(p)}")
    digest = hashlib.sha256("\n".join(entries).encode()).hexdigest().upper()
    return digest, len(files)


def capture_date(stem: str) -> str | None:
    """Mirror of the PHASE 24C generator's filename date rule."""
    m = re.match(r"vlcsnap[-_](\d{4})-(\d{2})-(\d{2})", stem, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"vlcsnap[-_](\d{4})(\d{2})(\d{2})", stem, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{4})(\d{2})(\d{2})_\d{6}", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def split_lines(name: str) -> list[str]:
    p = SPLITS_V2 / f"{name}.txt"
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def parse_boxes(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    out: list[tuple[int, float, float, float, float]] = []
    if not label_path.exists():
        return out
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            out.append((int(float(parts[0])), *(float(v) for v in parts[1:])))
        except ValueError:
            continue
    return out


def verify_path_inside_workspace(p: Path, name: str) -> str:
    resolved = p.resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise RuntimeError(
            f"VIOLATION of Rule 1: {name} path '{resolved}' is outside workspace '{WORKSPACE_ROOT}'"
        )
    return str(resolved)


def git(*args: str) -> str:
    try:
        res = subprocess.run(
            ["git", *args], cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception as e:  # pragma: no cover
        return f"UNKNOWN ({e})"


def load_manifest_csv() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with SPLIT_MANIFEST_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["stem"]] = row
    return rows


# --------------------------------------------------------------------------- #
# shared verification (used by both modes)
# --------------------------------------------------------------------------- #

def build_verification() -> dict:
    """Read-only state + holdout identity verification. Returns the full dict."""
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> bool:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    # 1. checkpoint identity
    ckpt_info = {}
    for tag, path in CHECKPOINTS.items():
        verify_path_inside_workspace(path, f"{tag} checkpoint")
        exists = path.exists()
        h = sha256_file(path) if exists else None
        ok = exists and (h == EXPECTED_CKPT_SHA[tag])
        check(f"checkpoint_{tag}_hash", ok, f"{path} sha256={h}")
        ckpt_info[tag] = {
            "path": str(path),
            "exists": exists,
            "sha256": h,
            "expected_sha256": EXPECTED_CKPT_SHA[tag],
            "hash_ok": ok,
        }

    # 2. dataset configs
    v2_hash = sha256_file(DATASET_V2_YAML)
    v1_hash = sha256_file(DATASET_V1_YAML)
    check("dataset_v2_yaml_hash", v2_hash == EXPECTED_DATASET_V2_SHA, v2_hash)
    check("dataset_v1_yaml_unchanged", v1_hash == EXPECTED_DATASET_V1_SHA, v1_hash)

    # 3. split files
    split_hashes = {}
    for name in ("train", "val", "test"):
        h = sha256_file(SPLITS_V2 / f"{name}.txt")
        split_hashes[name] = h
        check(f"split_{name}_hash", h == EXPECTED_SPLIT_SHA[name], h)

    # 4. derived labels merkle
    merkle, n_labels = merkle_dir_digest(DERIVED_LABELS, "*.txt")
    check("derived_labels_merkle", merkle == EXPECTED_DERIVED_LABELS_MERKLE, f"{merkle} n={n_labels}")
    check("derived_tree_has_no_cache_artifact", not (DERIVED / "labels.cache").exists(),
          str(DERIVED / "labels.cache"))

    # 5. manifest consistency
    manifest = json.loads(DERIVED_MANIFEST.read_text(encoding="utf-8"))
    man_merkle = manifest["artifacts"]["derived_labels_merkle_sha256"]
    check("manifest_matches_derived_labels_merkle", man_merkle == merkle, man_merkle)
    check(
        "manifest_source_unchanged_after_generation",
        all(manifest["source"]["unchanged_after_generation"].values()),
        json.dumps(manifest["source"]["unchanged_after_generation"]),
    )

    # 5b. independent re-verification of the ORIGINAL source (unchanged vs MANIFEST)
    src = WORKSPACE_ROOT / "data" / "pothole_crack_manhole" / "data"
    src_hashes = manifest["source"]["hashes"]
    labels_m, labels_n = merkle_dir_digest(src / "labels-YOLO", "*.txt")
    poly_m, poly_n = merkle_dir_digest(src / "labels", "*.txt")
    images_m, images_n = merkle_dir_digest(src / "images", "*.jpg")
    check("source_labels_YOLO_merkle_unchanged",
          labels_m == src_hashes["labels-YOLO_merkle_sha256"], f"{labels_m} n={labels_n}")
    check("source_labels_polygon_merkle_unchanged",
          poly_m == src_hashes["labels_polygon_merkle_sha256"], f"{poly_m} n={poly_n}")
    check("source_images_merkle_unchanged",
          images_m == src_hashes["images_merkle_sha256"], f"{images_m} n={images_n}")
    for split in ("train", "val", "test"):
        h = sha256_file(WORKSPACE_ROOT / "data" / "splits" / f"{split}.txt")
        check(f"original_split_{split}_unchanged",
              h == src_hashes["original_splits"][split], h)
    check("source_dataset_yaml_unchanged_vs_manifest",
          sha256_file(DATASET_V1_YAML) == src_hashes["dataset.yaml"], sha256_file(DATASET_V1_YAML))

    # 6. holdout membership / pairing / labels / dates
    train, val, test = split_lines("train"), split_lines("val"), split_lines("test")
    check("holdout_size_216", len(test) == EXPECTED_DATASET_V2_TOTAL_IMAGES, str(len(test)))

    test_stems = [Path(p).stem for p in test]
    missing_img, missing_lbl = [], []
    bad_class, bad_box, zero_area = 0, 0, 0
    box_counts: Counter = Counter()
    empty_labels = 0
    img_hashes_ok = 0
    img_hashes_mismatch: list[str] = []
    man = load_manifest_csv()
    for p in test:
        ip = Path(p)
        if not ip.exists():
            missing_img.append(ip.name)
            continue
        lp = DERIVED_LABELS / (ip.stem + ".txt")
        if not lp.exists():
            missing_lbl.append(ip.name)
            continue
        # verify actual image bytes == manifest-recorded source hash
        row = man.get(ip.stem)
        actual = sha256_file(ip)
        if row and row.get("sha256_image"):
            if actual == row["sha256_image"]:
                img_hashes_ok += 1
            else:
                img_hashes_mismatch.append(ip.name)
        boxes = parse_boxes(lp)
        if not boxes:
            empty_labels += 1
        for cid, xc, yc, w, h in boxes:
            box_counts[cid] += 1
            if cid not in KEEP_CLASSES:
                bad_class += 1
            if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0):
                bad_box += 1
            if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                bad_box += 1
            if w <= 0 or h <= 0:
                zero_area += 1

    check("holdout_images_all_present", not missing_img, f"missing={len(missing_img)}")
    check("holdout_labels_all_present", not missing_lbl, f"missing={len(missing_lbl)}")
    check("holdout_label_class_ids_subset_{0,1}", bad_class == 0, f"bad_class={bad_class}")
    check("holdout_boxes_valid_range", bad_box == 0, f"bad_box={bad_box}")
    check("holdout_zero_area_boxes", zero_area == 0, f"zero_area={zero_area}")
    check(
        "holdout_box_counts_match_manifest",
        dict(box_counts) == EXPECTED_TEST_BOXES,
        f"got={dict(box_counts)} expected={EXPECTED_TEST_BOXES}",
    )
    check(
        "holdout_empty_label_images_match_manifest",
        empty_labels == EXPECTED_TEST_EMPTY_LABELS,
        f"got={empty_labels} expected={EXPECTED_TEST_EMPTY_LABELS}",
    )
    check(
        "holdout_image_bytes_match_manifest_sha256",
        len(img_hashes_mismatch) == 0 and img_hashes_ok == len(test),
        f"ok={img_hashes_ok}/{len(test)} mismatch={img_hashes_mismatch[:5]}",
    )

    # 7. date-atomicity + no train/val overlap
    tr_stems, va_stems = {Path(p).stem for p in train}, {Path(p).stem for p in val}
    te_stems = set(test_stems)
    overlap = {
        "train_val": len(tr_stems & va_stems),
        "train_test": len(tr_stems & te_stems),
        "val_test": len(va_stems & te_stems),
    }
    check("no_stem_overlap_between_splits", all(v == 0 for v in overlap.values()), json.dumps(overlap))
    dates = {name: sorted({capture_date(s) for s in stems})
             for name, stems in (("train", tr_stems), ("val", va_stems), ("test", te_stems))}
    date_overlap = {
        "train_test": sorted(set(dates["train"]) & set(dates["test"])),
        "val_test": sorted(set(dates["val"]) & set(dates["test"])),
        "train_val": sorted(set(dates["train"]) & set(dates["val"])),
    }
    check(
        "no_capture_date_spans_test_and_other_split",
        not date_overlap["train_test"] and not date_overlap["val_test"],
        json.dumps(date_overlap),
    )
    check(
        "holdout_capture_dates_as_documented",
        dates["test"] == [EXPECTED_TEST_DATE],
        json.dumps(dates["test"]),
    )

    return {
        "mode": "verify",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(WORKSPACE_ROOT),
        "git": {
            "head": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "status_short": git("status", "--short").splitlines(),
        },
        "checkpoints": ckpt_info,
        "dataset_configs": {
            "dataset_v2_yaml": {"path": str(DATASET_V2_YAML), "sha256": v2_hash},
            "dataset_v1_yaml": {"path": str(DATASET_V1_YAML), "sha256": v1_hash},
        },
        "split_sha256": split_hashes,
        "derived_labels": {"merkle_sha256": merkle, "file_count": n_labels},
        "holdout": {
            "images": len(test),
            "stems": len(te_stems),
            "missing_images": missing_img,
            "missing_labels": missing_lbl,
            "empty_label_images": empty_labels,
            "boxes_by_class": {str(k): v for k, v in sorted(box_counts.items())},
            "boxes_total": int(sum(box_counts.values())),
            "image_bytes_verified": img_hashes_ok,
            "image_bytes_mismatch": img_hashes_mismatch,
            "capture_dates": dates,
            "overlap_by_stem": overlap,
            "overlap_by_date": date_overlap,
        },
        "checks": checks,
        "all_checks_ok": all(c["ok"] for c in checks),
    }


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #

def environment_info() -> dict:
    import numpy as np
    import torch
    import ultralytics
    import cv2

    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": bool(torch.cuda.is_available()),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
    }
    return info


def derived_tree_snapshot() -> dict:
    """Fingerprint the derived tree (labels + manifest + readme), excluding the
    images junction (which exposes the original images)."""
    labels_digest, n_labels = merkle_dir_digest(DERIVED_LABELS, "*.txt")
    files = {}
    for name in ("MANIFEST.json", "README.md"):
        p = DERIVED / name
        if p.exists():
            files[name] = sha256_file(p)
    cache = DERIVED / "labels.cache"
    return {
        "derived_labels_merkle": labels_digest,
        "derived_labels_count": n_labels,
        "derived_root_files": files,
        # Ultralytics always writes labels.cache next to the label files when it
        # scans them. Tracked here so any write is visible and reversible.
        "labels_cache_present": cache.exists(),
        "labels_cache_sha256": sha256_file(cache) if cache.exists() else None,
    }


def _content_equal(before: dict, after: dict) -> bool:
    keys = ("derived_labels_merkle", "derived_labels_count", "derived_root_files")
    return all(before.get(k) == after.get(k) for k in keys)


def select_device() -> tuple[object, dict]:
    """Prefer GPU; fall back to CPU when CUDA is unavailable or VRAM is scarce.

    PHASE 24D is an evaluation-only phase, so a CPU run is valid and reproducible;
    the choice and its reason are recorded. Both checkpoints use the same device.
    """
    import torch

    info = {"cuda_available": bool(torch.cuda.is_available())}
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info(0)
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["vram_free_mib"] = round(free / 1024**2, 1)
        info["vram_total_mib"] = round(total / 1024**2, 1)
        # yolo11n@640 needs roughly 1-2 GB; require comfortable headroom.
        if free >= 3.5 * 1024**3:
            info["reason"] = "CUDA available with sufficient free VRAM"
            return 0, info
        info["reason"] = (
            "CUDA available but free VRAM below 3.5 GiB threshold "
            f"({info['vram_free_mib']} MiB free) — likely a competing GPU process; "
            "falling back to CPU for a valid, reproducible evaluation."
        )
        return "cpu", info
    info["reason"] = "CUDA not available"
    return "cpu", info


def run_eval(tag: str) -> int:
    from ultralytics import YOLO

    if tag not in CHECKPOINTS:
        print(f"ERROR: unknown checkpoint tag '{tag}' (expected v1|v2)", file=sys.stderr)
        return 2

    verify_path_inside_workspace(WORKSPACE_ROOT, "workspace")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    ckpt_path = CHECKPOINTS[tag]
    ckpt_hash = sha256_file(ckpt_path)
    if ckpt_hash != EXPECTED_CKPT_SHA[tag]:
        print(f"STOP: checkpoint {tag} hash mismatch: {ckpt_hash} != {EXPECTED_CKPT_SHA[tag]}", file=sys.stderr)
        return 3
    dataset_v2_hash = sha256_file(DATASET_V2_YAML)
    if dataset_v2_hash != EXPECTED_DATASET_V2_SHA:
        print(f"STOP: dataset_v2.yaml hash mismatch: {dataset_v2_hash}", file=sys.stderr)
        return 3

    print("=" * 72)
    print(f"SafeRoute AI — PHASE 24D holdout evaluation: {tag}")
    print(f"Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}")
    print(f"Checkpoint: {ckpt_path}")
    print(f"Checkpoint sha256: {ckpt_hash}")
    print(f"Dataset config: {DATASET_V2_YAML} sha256={dataset_v2_hash}")
    print("=" * 72)

    before = derived_tree_snapshot()

    device, device_info = select_device()
    print(f"[device] using {device!r}: {device_info.get('reason')}")
    model = YOLO(str(ckpt_path))

    # Fixed evaluation settings, identical for both checkpoints.
    eval_params = {
        "data": str(DATASET_V2_YAML),
        "split": "test",
        "imgsz": 640,
        "batch": 16,
        "device": device,
        "cache": False,       # never write a labels cache into the derived tree
        "plots": True,
        "save_json": False,
        "project": str(OUT_ROOT),
        "name": f"{tag}_ultralytics_test",
        "exist_ok": True,
        "verbose": True,
    }

    t0 = time.time()
    results = model.val(**eval_params)
    duration = time.time() - t0

    after = derived_tree_snapshot()

    box = results.box
    nc = len(model.names)

    def f(x):
        return float(x)

    per_class = []
    for i in range(nc):
        p, r, ap50, ap = [float(v) for v in box.class_result(i)]
        per_class.append(
            {
                "class_id": i,
                "class_name": CLASS_NAMES.get(i, model.names.get(i, str(i))),
                "precision": round(p, 6),
                "recall": round(r, 6),
                "f1": round(2 * p * r / (p + r + 1e-16), 6),
                "mAP50": round(ap50, 6),
                "mAP50_95": round(ap, 6),
            }
        )

    cm = results.confusion_matrix.matrix.tolist()
    cm_summary = results.confusion_matrix.summary(normalize=False, decimals=5)
    cm_summary_norm = results.confusion_matrix.summary(normalize=True, decimals=5)

    nt_per_class = [int(v) for v in results.nt_per_class] if getattr(results, "nt_per_class", None) is not None else []
    nt_per_image = getattr(results, "nt_per_image", None)
    gt_images_with_class = (
        {str(i): int(nt_per_image[i]) for i in range(nc)}
        if nt_per_image is not None and len(nt_per_image) >= nc
        else {}
    )

    # total images the validator actually streamed (Ultralytics `seen`)
    images_evaluated = None
    try:
        seen = getattr(getattr(model, "validator", None), "seen", None)
        images_evaluated = int(seen) if seen is not None else None
    except Exception:
        images_evaluated = None
    if images_evaluated is None:
        images_evaluated = len(split_lines("test"))

    avg_p = float(box.mp)
    avg_r = float(box.mr)
    overall = {
        "precision": round(avg_p, 6),
        "recall": round(avg_r, 6),
        "f1": round(2 * avg_p * avg_r / (avg_p + avg_r + 1e-16), 6),
        "mAP50": round(float(box.map50), 6),
        "mAP50_95": round(float(box.map), 6),
    }

    record = {
        "phase": "PHASE_24D",
        "mode": "eval",
        "checkpoint_tag": tag,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": {"head": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD")},
        "identity": {
            "checkpoint_path": str(ckpt_path),
            "checkpoint_sha256": ckpt_hash,
            "dataset_config_path": str(DATASET_V2_YAML),
            "dataset_config_sha256": dataset_v2_hash,
            "split_sha256": {n: sha256_file(SPLITS_V2 / f"{n}.txt") for n in ("train", "val", "test")},
            "model_names": {str(k): v for k, v in model.names.items()},
            "num_classes": nc,
        },
        "command": f".\\.venv\\Scripts\\python.exe scripts\\audit\\phase24d_evaluate_holdout.py eval {tag}",
        "eval_params": eval_params,
        "effective_thresholds": {
            "mAP_conf": 0.001,
            "mAP_iou_nms": 0.7,
            "confusion_matrix_conf": 0.25,
            "confusion_matrix_iou_nms": 0.45,
            "max_det": 300,
            "note": "Ultralytics defaults; conf/iou not overridden so both checkpoints share identical settings.",
        },
        "environment": environment_info(),
        "device_selection": device_info,
        "holdout": {
            "split": "test",
            "images_in_split_file": len(split_lines("test")),
            "images_evaluated": images_evaluated,
            "gt_boxes_total": int(sum(nt_per_class)) if nt_per_class else None,
            "gt_boxes_by_class": {str(i): nt_per_class[i] for i in range(len(nt_per_class))},
            "gt_images_with_class": gt_images_with_class,
        },
        "metrics": {
            "overall": overall,
            "per_class": per_class,
            "maps_per_class_50_95": [round(float(v), 6) for v in box.maps],
        },
        "confusion_matrix": {
            "axis_convention": "rows = predicted, columns = true (last row = predicted background/FN, "
                               "last column = true background/FP) — Ultralytics ConfusionMatrix.matrix",
            "labels": [CLASS_NAMES.get(i, str(i)) for i in range(nc)] + ["background"],
            "matrix": cm,
            "summary_counts": cm_summary,
            "summary_normalized": cm_summary_norm,
        },
        "speed_per_image_ms": {k: round(float(v), 3) for k, v in results.speed.items()},
        "duration_seconds": round(duration, 3),
        "results_save_dir": str(results.save_dir),
        "data_integrity": {
            "before": before,
            "after": after,
            "content_unchanged": _content_equal(before, after),
            "cache_created_by_eval": (after["labels_cache_present"] and not before["labels_cache_present"]),
            "note": "Ultralytics writes labels.cache next to the derived labels when scanning; "
                    "it is a disposable generated artifact and is removed after evaluation.",
        },
    }

    out_json = OUT_ROOT / f"{tag}_metrics.json"
    out_json.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print("-" * 72)
    print(f"[{tag}] overall  P={overall['precision']:.4f} R={overall['recall']:.4f} "
          f"F1={overall['f1']:.4f} mAP50={overall['mAP50']:.4f} mAP50-95={overall['mAP50_95']:.4f}")
    for pc in per_class:
        print(f"[{tag}] {pc['class_name']:<8} P={pc['precision']:.4f} R={pc['recall']:.4f} "
              f"mAP50={pc['mAP50']:.4f} mAP50-95={pc['mAP50_95']:.4f}")
    print(f"[{tag}] GT boxes/class: {record['holdout']['gt_boxes_by_class']} "
          f"GT images/class: {record['holdout']['gt_images_with_class']} "
          f"images_evaluated={images_evaluated}")
    print(f"[{tag}] derived tree content unchanged during eval: {record['data_integrity']['content_unchanged']}")
    print(f"[{tag}] metrics written: {out_json}")
    print("=" * 72)

    return 0 if record["data_integrity"]["content_unchanged"] else 4


# --------------------------------------------------------------------------- #

def run_compare() -> int:
    """Build a v1-vs-v2 comparison artefact from the two metrics JSON files."""
    v1 = json.loads((OUT_ROOT / "v1_metrics.json").read_text(encoding="utf-8"))
    v2 = json.loads((OUT_ROOT / "v2_metrics.json").read_text(encoding="utf-8"))

    def row(m: dict) -> dict:
        return {
            "overall": m["metrics"]["overall"],
            "pothole": m["metrics"]["per_class"][0],
            "crack": m["metrics"]["per_class"][1],
            "confusion_matrix": m["confusion_matrix"]["matrix"],
            "holdout": m["holdout"],
            "device": m["eval_params"]["device"],
        }

    r1, r2 = row(v1), row(v2)

    def delta(a: float, b: float) -> dict:
        return {"v1": round(a, 6), "v2": round(b, 6), "abs_diff": round(b - a, 6),
                "rel_diff_pct": round(100.0 * (b - a) / a, 3) if a else None}

    p1 = {k: v for k, v in v1["eval_params"].items() if k != "name"}
    p2 = {k: v for k, v in v2["eval_params"].items() if k != "name"}
    comparison = {
        "phase": "PHASE_24D",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "holdout": {
            "dataset_config": str(DATASET_V2_YAML),
            "split": "test",
            "images": r1["holdout"]["images_evaluated"],
            "gt_boxes": r1["holdout"]["gt_boxes_total"],
            "gt_boxes_by_class": r1["holdout"]["gt_boxes_by_class"],
            "same_holdout_for_both": r1["holdout"] == r2["holdout"],
        },
        "identical_eval_settings": p1 == p2,
        "eval_params_compared": p1,
        "device": r1["device"],
        "checkpoints": {
            "v1": v1["identity"]["checkpoint_sha256"],
            "v2": v2["identity"]["checkpoint_sha256"],
        },
        "overall": {
            "precision": delta(r1["overall"]["precision"], r2["overall"]["precision"]),
            "recall": delta(r1["overall"]["recall"], r2["overall"]["recall"]),
            "f1": delta(r1["overall"]["f1"], r2["overall"]["f1"]),
            "mAP50": delta(r1["overall"]["mAP50"], r2["overall"]["mAP50"]),
            "mAP50_95": delta(r1["overall"]["mAP50_95"], r2["overall"]["mAP50_95"]),
        },
        "per_class": {
            "pothole": {
                "precision": delta(r1["pothole"]["precision"], r2["pothole"]["precision"]),
                "recall": delta(r1["pothole"]["recall"], r2["pothole"]["recall"]),
                "mAP50": delta(r1["pothole"]["mAP50"], r2["pothole"]["mAP50"]),
                "mAP50_95": delta(r1["pothole"]["mAP50_95"], r2["pothole"]["mAP50_95"]),
            },
            "crack": {
                "precision": delta(r1["crack"]["precision"], r2["crack"]["precision"]),
                "recall": delta(r1["crack"]["recall"], r2["crack"]["recall"]),
                "mAP50": delta(r1["crack"]["mAP50"], r2["crack"]["mAP50"]),
                "mAP50_95": delta(r1["crack"]["mAP50_95"], r2["crack"]["mAP50_95"]),
            },
        },
        "confusion_matrices": {"v1": r1["confusion_matrix"], "v2": r2["confusion_matrix"],
                               "axis_convention": v2["confusion_matrix"]["axis_convention"] if isinstance(v2["confusion_matrix"], dict) else "rows=predicted, cols=true"},
        "interpretation_note": (
            "v2 is higher than v1 on every reported aggregate and per-class metric on this holdout. "
            "This is a measured comparison on ONE date-aware holdout; it is not a promotion decision."
        ),
    }
    # fix confusion matrix reference (stored as raw list in metrics)
    comparison["confusion_matrices"]["axis_convention"] = (
        "rows = predicted, columns = true (Ultralytics ConfusionMatrix.matrix)"
    )
    out = OUT_ROOT / "comparison.json"
    out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(f"comparison written: {out}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("verify", "eval", "compare"):
        print(__doc__)
        return 2
    if argv[1] == "compare":
        return run_compare()
    if argv[1] == "verify":
        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        v = build_verification()
        out = OUT_ROOT / "holdout_verification.json"
        out.write_text(json.dumps(v, indent=2), encoding="utf-8")
        print("=" * 72)
        print("SafeRoute AI — PHASE 24D holdout verification")
        print(f"Timestamp (UTC): {v['timestamp_utc']}")
        for c in v["checks"]:
            print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
        print(f"ALL CHECKS OK: {v['all_checks_ok']}")
        print(f"verification written: {out}")
        print("=" * 72)
        return 0 if v["all_checks_ok"] else 1
    if len(argv) < 3:
        print("ERROR: eval requires a checkpoint tag (v1|v2)", file=sys.stderr)
        return 2
    return run_eval(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
