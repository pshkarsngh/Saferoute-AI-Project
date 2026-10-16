"""PHASE_24A — Dataset audit and quality verification (read-only).

Master rules: Rules 1, 14, 15, 17, 18, 20.

This script NEVER modifies any dataset, label, split, config or checkpoint.
It writes evidence JSON only to <workspace>/reports/phase24a/.

Sections:
  A. Active training dataset (data/pothole_crack_manhole/data) — inventory,
     pairing, YOLO label integrity, exact/near duplicates, split leakage.
  B. RDD2022 raw tree (data/raw/RDD2022) — re-measured inventory + pairing.
  C. DATA-YOLO tree — per-subdirectory inventory and format classification.
  D. Model/training artifacts — hashes, pinned-checkpoint verification,
     v1/v2 training results read from existing results.csv.

Usage:
  .venv/Scripts/python.exe scripts/audit/phase24a_dataset_audit.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WORKSPACE / "reports" / "phase24a"

# Pinned serving checkpoint (PHASE_09 evaluation_record.json, re-verified here).
PINNED_V1_BEST_SHA256 = "61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def dhash_gray(path: Path, hash_size: int = 8) -> int | None:
    """dHash via OpenCV; returns None if the image cannot be decoded."""
    import cv2  # local import: section C/D of the audit can run without it

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    img = cv2.resize(img, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = img[:, 1:] > img[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Section A — active dataset
# ---------------------------------------------------------------------------

def audit_active_dataset() -> dict:
    root = WORKSPACE / "data" / "pothole_crack_manhole" / "data"
    images_dir = root / "images"
    yolo_dir = root / "labels-YOLO"
    poly_dir = root / "labels"

    images = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMG_EXTS)
    yolo_labels = sorted(p for p in yolo_dir.glob("*.txt"))
    poly_labels = sorted(p for p in poly_dir.glob("*.txt"))

    image_stems = {p.stem for p in images}
    yolo_stems = {p.stem for p in yolo_labels}
    poly_stems = {p.stem for p in poly_labels}

    # -- YOLO label integrity ------------------------------------------------
    class_counts: dict[int, int] = defaultdict(int)
    malformed_lines = 0
    out_of_range = 0
    zero_area = 0
    empty_label_files = 0
    total_boxes = 0
    malformed_examples: list[str] = []
    for lp in yolo_labels:
        text = lp.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            empty_label_files += 1
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            parts = line.split()
            if len(parts) != 5:
                malformed_lines += 1
                if len(malformed_examples) < 5:
                    malformed_examples.append(f"{lp.name}:{lineno} fields={len(parts)}")
                continue
            try:
                cid = int(parts[0])
                xc, yc, w, h = (float(v) for v in parts[1:])
            except ValueError:
                malformed_lines += 1
                continue
            class_counts[cid] += 1
            total_boxes += 1
            if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                out_of_range += 1
            if w <= 0.0 or h <= 0.0:
                zero_area += 1

    # -- polygon label integrity --------------------------------------------
    poly_malformed = 0
    poly_boxes = 0
    for lp in poly_labels:
        text = lp.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        for line in text.splitlines():
            parts = line.split()
            if len(parts) != 9:
                poly_malformed += 1
                continue
            try:
                [float(v) for v in parts]
            except ValueError:
                poly_malformed += 1
                continue
            poly_boxes += 1

    # -- COCO annotations (existence + basic parse) --------------------------
    coco_path = root / "annotations_coco.json"
    coco_info: dict = {"exists": coco_path.exists()}
    if coco_path.exists():
        try:
            coco = json.loads(coco_path.read_text(encoding="utf-8"))
            coco_info.update(
                images=len(coco.get("images", [])),
                annotations=len(coco.get("annotations", [])),
                categories=coco.get("categories", []),
                bad_image_refs=sum(
                    1
                    for a in coco.get("annotations", [])
                    if a.get("image_id")
                    not in {i.get("id") for i in coco.get("images", [])}
                ),
            )
        except (json.JSONDecodeError, OSError) as exc:
            coco_info["parse_error"] = str(exc)

    # -- duplicates (SHA-256 exact + dHash near) -----------------------------
    hash_to_files: dict[str, list[str]] = defaultdict(list)
    dhash_to_files: dict[int, list[str]] = {}
    undecodable: list[str] = []
    for img in images:
        hash_to_files[sha256_file(img)].append(img.name)
        dh = dhash_gray(img)
        if dh is None:
            undecodable.append(img.name)
        else:
            dhash_to_files.setdefault(dh, []).append(img.name)

    exact_groups = {h: fs for h, fs in hash_to_files.items() if len(fs) > 1}

    # near-duplicates: bucketed dHash scan (pigeonhole: hamming<=6 with 2 bands of 4)
    near_pairs: set[tuple[str, str]] = set()
    bands = 4
    band_bits = 8 // bands
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    keys = list(dhash_to_files.keys())
    for idx, hv in enumerate(keys):
        for b in range(bands):
            buckets[(b, (hv >> (b * band_bits)) & ((1 << band_bits) - 1))].append(idx)
    for bucket in buckets.values():
        if len(bucket) > 300:  # skip degenerate buckets (video-frame bursts)
            continue
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                a, b = keys[bucket[i]], keys[bucket[j]]
                if (a, b) in near_pairs or (b, a) in near_pairs:
                    continue
                if hamming(a, b) <= 6:
                    fa = dhash_to_files[a][0]
                    fb = dhash_to_files[b][0]
                    if fa != fb:
                        near_pairs.add((fa, fb))

    # -- splits --------------------------------------------------------------
    def read_split(name: str) -> list[str]:
        p = WORKSPACE / "data" / "splits" / f"{name}.txt"
        return [ln.strip().replace("\\", "/") for ln in p.read_text().splitlines() if ln.strip()]

    splits = {name: read_split(name) for name in ("train", "val", "test")}
    split_stems = {name: {Path(p).stem for p in paths} for name, paths in splits.items()}
    missing_targets = {
        name: [p for p in paths if not Path(p).exists()] for name, paths in splits.items()
    }

    overlap = {}
    for a in ("train", "val", "test"):
        for b in ("train", "val", "test"):
            if a < b:
                overlap[f"{a}_vs_{b}"] = len(split_stems[a] & split_stems[b])

    # cross-split exact-content leakage (by sha256)
    stem_to_sha = {p.stem: sha256_file(p) for p in images}
    sha_to_stems: dict[str, set[str]] = defaultdict(set)
    for stem, sha in stem_to_sha.items():
        sha_to_stems[sha].add(stem)

    def split_of(stem: str) -> str | None:
        for name, stems in split_stems.items():
            if stem in stems:
                return name
        return None

    cross_exact = 0
    cross_exact_examples: list[list[str]] = []
    for sha, stems in sha_to_stems.items():
        locs = {split_of(s) for s in stems} - {None}
        if len(locs) > 1:
            cross_exact += 1
            if len(cross_exact_examples) < 10:
                cross_exact_examples.append(sorted(stems))

    # cross-split near-duplicates (dHash<=6, different split)
    cross_near = 0
    cross_near_examples: list[list[str]] = []
    stem_to_name = {p.stem: p.name for p in images}
    for fa, fb in near_pairs:
        sa, sb = Path(fa).stem, Path(fb).stem
        la, lb = split_of(sa), split_of(sb)
        if la and lb and la != lb:
            cross_near += 1
            if len(cross_near_examples) < 10:
                cross_near_examples.append([fa, la, fb, lb])

    # capture-session heuristic: vlcsnap video frames — consecutive names
    vlcsnap = sum(1 for p in images if p.name.lower().startswith("vlcsnap"))
    other_names = sorted(p.name for p in images if not p.name.lower().startswith("vlcsnap"))

    return {
        "root": str(root),
        "counts": {
            "images": len(images),
            "yolo_label_files": len(yolo_labels),
            "polygon_label_files": len(poly_labels),
            "image_extension_breakdown": {
                ext: sum(1 for p in images if p.suffix.lower() == ext)
                for ext in sorted({p.suffix.lower() for p in images})
            },
        },
        "pairing": {
            "images_without_yolo_label": len(image_stems - yolo_stems),
            "yolo_labels_without_image": len(yolo_stems - image_stems),
            "images_without_polygon_label": len(image_stems - poly_stems),
            "polygon_labels_without_image": len(poly_stems - image_stems),
        },
        "yolo_label_integrity": {
            "total_boxes": total_boxes,
            "class_counts": dict(sorted(class_counts.items())),
            "malformed_lines": malformed_lines,
            "malformed_examples": malformed_examples,
            "out_of_range_boxes": out_of_range,
            "zero_area_boxes": zero_area,
            "empty_label_files": empty_label_files,
        },
        "polygon_label_integrity": {
            "total_boxes": poly_boxes,
            "malformed_lines": poly_malformed,
        },
        "coco_annotations": coco_info,
        "duplicates": {
            "exact_duplicate_groups": len(exact_groups),
            "exact_duplicate_files": sum(len(fs) for fs in exact_groups.values()),
            "exact_examples": dict(list(exact_groups.items())[:5]),
            "near_duplicate_pairs_dhash_le6": len(near_pairs),
            "undecodable_images": undecodable,
            "near_dup_method": "8x8 dHash, banded-bucket prefilter, hamming<=6 (heuristic)",
        },
        "splits": {
            "sizes": {k: len(v) for k, v in splits.items()},
            "missing_targets_on_disk": {k: len(v) for k, v in missing_targets.items()},
            "stem_overlaps_between_splits": overlap,
            "cross_split_exact_content_groups": cross_exact,
            "cross_split_exact_examples": cross_exact_examples,
            "cross_split_near_duplicate_pairs": cross_near,
            "cross_split_near_examples": cross_near_examples,
        },
        "capture_sequence": {
            "vlcsnap_video_frame_names": vlcsnap,
            "non_vlcsnap_names": other_names[:20],
            "non_vlcsnap_count": len(other_names),
        },
    }


# ---------------------------------------------------------------------------
# Section B — RDD2022 raw tree
# ---------------------------------------------------------------------------

def audit_rdd2022() -> dict:
    root = WORKSPACE / "data" / "raw" / "RDD2022" / "RDD2022"
    result: dict = {"root": str(root), "countries": {}}
    if not root.exists():
        return {"error": "RDD2022 tree missing"}
    for country_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        entry: dict = {}
        for split_dir in sorted(p for p in country_dir.iterdir() if p.is_dir()):
            images = sorted((split_dir / "images").glob("*")) if (split_dir / "images").exists() else []
            xmls = (
                sorted((split_dir / "annotations" / "xmls").glob("*.xml"))
                if (split_dir / "annotations" / "xmls").exists()
                else []
            )
            img_stems = {p.stem for p in images if p.suffix.lower() in IMG_EXTS}
            xml_stems = {p.stem for p in xmls}
            entry[split_dir.name] = {
                "images": len(img_stems),
                "xml_annotations": len(xml_stems),
                "images_without_xml": len(img_stems - xml_stems),
                "xml_without_images": len(xml_stems - img_stems),
            }
        zips = sorted(country_dir.glob("*.zip"))
        entry["zip_archives"] = {z.name: round(z.stat().st_size / (1 << 20), 1) for z in zips}
        result["countries"][country_dir.name] = entry
    # label map
    lm = WORKSPACE / "data" / "raw" / "RDD2022" / "label_map.pbtxt"
    result["label_map_exists"] = lm.exists()
    return result


# ---------------------------------------------------------------------------
# Section C — DATA-YOLO tree
# ---------------------------------------------------------------------------

def classify_dir(dirpath: Path) -> dict:
    files = [p for p in dirpath.rglob("*") if p.is_file()]
    exts: dict[str, int] = defaultdict(int)
    for f in files:
        exts[f.suffix.lower()] += 1
    label_dirs = [d for d in dirpath.rglob("*") if d.is_dir() and d.name.lower() == "labels"]
    images_dirs = [d for d in dirpath.rglob("*") if d.is_dir() and d.name.lower() == "images"]
    has_yolo_label = any(
        p.suffix.lower() == ".txt" and len(p.stem) > 0
        for d in label_dirs
        for p in d.iterdir()
        if p.is_file()
    ) if label_dirs else False
    masks = exts.get(".png", 0)
    jsons = exts.get(".json", 0)
    xmls = exts.get(".xml", 0)
    if jsons and not has_yolo_label:
        fmt = "COCO/JSON-based" if jsons else "unknown"
    elif xmls:
        fmt = "VOC/XML-based"
    elif has_yolo_label:
        fmt = "YOLO detection labels present"
    elif masks and exts.get(".jpg", 0):
        fmt = "paired image+mask (segmentation)"
    else:
        fmt = "images only (no annotations found)"
    images_total = sum(exts.get(e, 0) for e in IMG_EXTS)
    return {
        "files_total": len(files),
        "images_total": images_total,
        "extension_breakdown": dict(sorted(exts.items())),
        "format_assessment": fmt,
        "label_dirs": [str(d.relative_to(WORKSPACE)) for d in label_dirs[:5]],
        "images_dirs": [str(d.relative_to(WORKSPACE)) for d in images_dirs[:5]],
    }


def audit_data_yolo() -> dict:
    root = WORKSPACE / "DATA-YOLO"
    result: dict = {"root": str(root), "subdirs": {}}
    if not root.exists():
        return {"error": "DATA-YOLO tree missing"}
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        result["subdirs"][sub.name] = classify_dir(sub)
    zips = {}
    for z in sorted(root.glob("*.zip")):
        zips[z.name] = round(z.stat().st_size / (1 << 20), 1)
    result["zip_archives_MB"] = zips
    pdfs = {p.name: round(p.stat().st_size / (1 << 20), 2) for p in root.glob("*.pdf")}
    result["documents"] = pdfs
    return result


# ---------------------------------------------------------------------------
# Section D — model & training artifacts
# ---------------------------------------------------------------------------

def audit_model_artifacts() -> dict:
    v1_best = WORKSPACE / "models" / "training" / "saferoute-yolo11-v1" / "weights" / "best.pt"
    v2_best = WORKSPACE / "models" / "training" / "saferoute-yolo11-v2" / "weights" / "best.pt"
    stray = WORKSPACE / "weights" / "yolo26n.pt"

    def info(p: Path) -> dict:
        if not p.exists():
            return {"exists": False}
        return {
            "exists": True,
            "size_mb": round(p.stat().st_size / (1 << 20), 2),
            "sha256": sha256_file(p).upper(),
        }

    v1 = info(v1_best)
    v2 = info(v2_best)
    y26 = info(stray)
    if v1.get("sha256"):
        v1["matches_pinned_ph09"] = v1["sha256"] == PINNED_V1_BEST_SHA256

    # training results (read-only CSV parse)
    def last_row(csv_path: Path) -> dict | None:
        if not csv_path.exists():
            return None
        lines = [ln for ln in csv_path.read_text().splitlines() if ln.strip()]
        if len(lines) < 2:
            return None
        header = [h.strip() for h in lines[1].split(",")] if lines[1].startswith("epoch") or True else []
        # ultralytics results.csv: line0 header, line1 repeated header row
        hdr = [h.strip() for h in lines[0].split(",")]
        try:
            vals = [v.strip() for v in lines[-1].split(",")]
            best = {}
            for h, v in zip(hdr, vals):
                if h in ("metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)",
                         "metrics/mAP50-95(B)", "epoch"):
                    best[h] = v
            return {"header_epoch_count": len(lines) - 2, "last_row_selected_metrics": best}
        except Exception as exc:  # pragma: no cover - defensive
            return {"parse_error": str(exc)}

    def best_epoch_metrics(csv_path: Path, metric: str) -> dict | None:
        if not csv_path.exists():
            return None
        lines = [ln for ln in csv_path.read_text().splitlines() if ln.strip()]
        hdr = [h.strip() for h in lines[0].split(",")]
        if metric not in hdr:
            return None
        mi = hdr.index(metric)
        ei = hdr.index("epoch") if "epoch" in hdr else 0
        best = None
        for ln in lines[1:]:
            parts = [p.strip() for p in ln.split(",")]
            try:
                val = float(parts[mi])
            except (ValueError, IndexError):
                continue
            if best is None or val > best[0]:
                best = (val, parts[ei])
        return {"best_value": best[0], "epoch": best[1]} if best else None

    v1_csv = WORKSPACE / "models" / "training" / "saferoute-yolo11-v1" / "results.csv"
    v2_csv = WORKSPACE / "models" / "training" / "saferoute-yolo11-v2" / "results.csv"

    return {
        "v1_best": v1,
        "v2_best": v2,
        "stray_weights_dir_yolo26n": y26,
        "v1_results_csv": {
            "exists": v1_csv.exists(),
            "last_row": last_row(v1_csv),
            "best_map50": best_epoch_metrics(v1_csv, "metrics/mAP50(B)"),
        },
        "v2_results_csv": {
            "exists": v2_csv.exists(),
            "last_row": last_row(v2_csv),
            "best_map50": best_epoch_metrics(v2_csv, "metrics/mAP50(B)"),
        },
        "note": "v2 validation metrics read from results.csv are VALIDATION-split "
                "figures only; v2 has never been test-evaluated (R3, UNVERIFIED for test).",
        "checkpoint_files_untouched": True,
    }


# ---------------------------------------------------------------------------

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    evidence: dict = {
        "phase": "PHASE_24A",
        "mode": "read-only audit; no dataset/label/split/config/checkpoint modified",
        "workspace": str(WORKSPACE),
    }
    print("[A] active dataset ...", flush=True)
    evidence["active_dataset"] = audit_active_dataset()
    print("[B] RDD2022 ...", flush=True)
    evidence["rdd2022"] = audit_rdd2022()
    print("[C] DATA-YOLO ...", flush=True)
    evidence["data_yolo"] = audit_data_yolo()
    print("[D] model artifacts ...", flush=True)
    evidence["model_artifacts"] = audit_model_artifacts()
    evidence["duration_seconds"] = round(time.time() - started, 1)

    out = OUT_DIR / "audit_evidence.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"evidence written: {out}")
    # concise stdout summary
    a = evidence["active_dataset"]
    print("A counts:", a["counts"])
    print("A pairing:", a["pairing"])
    print("A yolo integrity:", {k: v for k, v in a["yolo_label_integrity"].items() if k != "malformed_examples"})
    print("A duplicates:", {k: v for k, v in a["duplicates"].items() if k not in ("exact_examples",)})
    print("A splits:", a["splits"]["sizes"], "overlaps:", a["splits"]["stem_overlaps_between_splits"])
    print("A cross-split exact:", a["splits"]["cross_split_exact_content_groups"],
          "near:", a["splits"]["cross_split_near_duplicate_pairs"])
    print("D:", evidence["model_artifacts"]["v1_best"], evidence["model_artifacts"]["v2_best"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
