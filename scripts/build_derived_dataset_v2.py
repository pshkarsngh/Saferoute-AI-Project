"""SafeRoute AI — PHASE 24C: build the approved derived two-class dataset.

Master rules: Rules 1, 5, 9, 14, 15, 17, 18, 20.

Approved decisions implemented (from PHASE_24B report):
  D1 (M1): derived TWO-class (pothole=0, crack=1) dataset; originals preserved.
  D2 (P-B): date-atomic split; the 212 date-unknown images are QUARANTINED.
  D3: the single zero-area annotation is dropped ONLY in the derived labels.
  D4: keep one image per confirmed exact-duplicate group; record every exclusion.
  D5: DATA-YOLO and RDD2022 remain excluded (not touched at all).
  D6: derived artifacts live in SEPARATE paths; a reproducibility manifest with
      source hashes is written.

Read-only w.r.t. every original artifact:
  * data/pothole_crack_manhole/**, data/splits/**, data/dataset.yaml, config/**,
    models/**, logs/**, weights/**  are NEVER written.
  * Only these NEW paths are created:
        data/derived_2class/           (images junction + derived labels)
        data/splits_v2/                (split files + manifest + notes)
        data/dataset_v2.yaml           (new dataset config; original untouched)

Split rule (date-atomic, P-B):
    train = {2025-02-18, 2025-02-19}
    val   = {2025-03-16, 2025-02-23, 2025-02-16}
    test  = {2025-02-26}
    QUARANTINE = every image with no determinable capture date

Usage:
  .venv/Scripts/python.exe scripts/build_derived_dataset_v2.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SRC = WORKSPACE / "data" / "pothole_crack_manhole" / "data"
SRC_IMAGES = SRC / "images"
SRC_LABELS = SRC / "labels-YOLO"          # axis-aligned boxes (source of truth here)
SRC_POLY = SRC / "labels"                 # polygon labels (referenced, not read for boxes)
ORIG_SPLITS = WORKSPACE / "data" / "splits"
ORIG_DATASET_YAML = WORKSPACE / "data" / "dataset.yaml"

DERIVED = WORKSPACE / "data" / "derived_2class"
DERIVED_IMAGES = DERIVED / "images"
DERIVED_LABELS = DERIVED / "labels"
SPLITS_V2 = WORKSPACE / "data" / "splits_v2"
DATASET_V2_YAML = WORKSPACE / "data" / "dataset_v2.yaml"

# date -> split (P-B)
DATE_TO_SPLIT = {
    "2025-02-18": "train",
    "2025-02-19": "train",
    "2025-03-16": "val",
    "2025-02-23": "val",
    "2025-02-16": "val",
    "2025-02-26": "test",
}
QUARANTINE = "quarantine"
KEEP_CLASSES = {0, 1}          # pothole, crack
DROP_CLASSES = {2}             # manhole -> removed only in the derived dataset


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def capture_date(stem: str) -> str | None:
    """Normalized YYYY-MM-DD, or None when undeterminable from the filename."""
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


def parse_boxes(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    out: list[tuple[int, float, float, float, float]] = []
    if not label_path.exists():
        return out
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            out.append((int(parts[0]), *(float(v) for v in parts[1:])))
        except ValueError:
            continue
    return out


def make_images_junction(link: Path, target: Path) -> str:
    """Expose the original images dir under the derived root via a directory
    junction (no privilege needed, no bytes duplicated, no original modified)."""
    if link.exists():
        return "already-present"
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return "symlink"
    except OSError:
        pass
    res = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"could not create images junction: {res.stdout} {res.stderr}")
    return "junction"


def merkle_dir_digest(directory: Path, pattern: str) -> tuple[str, int]:
    """Stable digest over sorted (name, sha256) pairs of a directory's files."""
    entries = []
    files = sorted(directory.glob(pattern))
    for p in files:
        entries.append(f"{p.name}:{sha256_file(p)}")
    digest = hashlib.sha256("\n".join(entries).encode()).hexdigest().upper()
    return digest, len(files)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    if not SRC_LABELS.is_dir():
        print("ERROR: source labels dir missing:", SRC_LABELS, file=sys.stderr)
        return 2

    # ---- 0. source-state snapshot (for the reproducibility manifest) ------
    source_hashes = {
        "README.md": sha256_file(SRC / "README.md"),
        "annotations_coco.json": sha256_file(SRC / "annotations_coco.json"),
        "dataset.yaml": sha256_file(ORIG_DATASET_YAML),
        "original_splits": {n: sha256_file(ORIG_SPLITS / f"{n}.txt")
                            for n in ("train", "val", "test")},
        "script": sha256_file(Path(__file__).resolve()),
    }
    labels_digest_before, n_labels = merkle_dir_digest(SRC_LABELS, "*.txt")
    poly_digest_before, n_poly = merkle_dir_digest(SRC_POLY, "*.txt")
    source_hashes["labels-YOLO_merkle_sha256"] = labels_digest_before
    source_hashes["labels-YOLO_file_count"] = n_labels
    source_hashes["labels_polygon_merkle_sha256"] = poly_digest_before
    source_hashes["labels_polygon_file_count"] = n_poly
    images_digest_before, n_images = merkle_dir_digest(SRC_IMAGES, "*.jpg")
    source_hashes["images_merkle_sha256"] = images_digest_before
    source_hashes["images_file_count"] = n_images

    stems = sorted(p.stem for p in SRC_LABELS.glob("*.txt"))

    # ---- 1. exact-duplicate groups; choose keeper -------------------------
    sha_to_stems: dict[str, list[str]] = defaultdict(list)
    image_sha: dict[str, str] = {}
    for s in stems:
        img = SRC_IMAGES / f"{s}.jpg"
        h = sha256_file(img)
        image_sha[s] = h
        sha_to_stems[h].append(s)

    dup_keeper: dict[str, str] = {}     # stem -> keeper stem (for non-keepers)
    for h, group in sha_to_stems.items():
        if len(group) > 1:
            keeper = sorted(group)[0]
            for member in group:
                if member != keeper:
                    dup_keeper[member] = keeper

    # ---- 2. classify every image -----------------------------------------
    rows = []
    for s in stems:
        date = capture_date(s)
        split = DATE_TO_SPLIT.get(date, QUARANTINE) if date else QUARANTINE
        boxes = parse_boxes(SRC_LABELS / f"{s}.txt")
        n_p = sum(1 for b in boxes if b[0] == 0)
        n_c = sum(1 for b in boxes if b[0] == 1)
        n_m = sum(1 for b in boxes if b[0] in DROP_CLASSES)
        n_zero = sum(1 for b in boxes if b[3] <= 0 or b[4] <= 0)

        exclude_reason = None
        kept = True
        if split == QUARANTINE:
            kept = False
            exclude_reason = "quarantined_unknown_capture_date"
        elif s in dup_keeper:
            kept = False
            exclude_reason = f"exact_duplicate_of:{dup_keeper[s]}"

        rows.append({
            "stem": s,
            "capture_date": date or "UNKNOWN",
            "split": split,
            "kept": kept,
            "exclude_reason": exclude_reason or "",
            "n_pothole_src": n_p,
            "n_crack_src": n_c,
            "n_manhole_dropped": n_m,
            "n_zero_area_dropped": n_zero,
            "sha256_image": image_sha[s],
            "keeper_of": dup_keeper.get(s, ""),
        })

    # ---- 3. create derived layout ----------------------------------------
    DERIVED.mkdir(parents=True, exist_ok=True)
    DERIVED_LABELS.mkdir(parents=True, exist_ok=True)
    SPLITS_V2.mkdir(parents=True, exist_ok=True)
    junction_kind = make_images_junction(DERIVED_IMAGES, SRC_IMAGES)

    # ---- 4. write derived (two-class) labels for KEPT images --------------
    kept_stems = [r["stem"] for r in rows if r["kept"]]
    for r in rows:
        if not r["kept"]:
            continue
        s = r["stem"]
        boxes = parse_boxes(SRC_LABELS / f"{s}.txt")
        lines = []
        for cid, xc, yc, w, h in boxes:
            if cid not in KEEP_CLASSES:      # D1: drop manhole (class 2)
                continue
            if w <= 0 or h <= 0:             # D3: drop zero-area (only vlcsnap-00058)
                continue
            lines.append(f"{cid} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
        (DERIVED_LABELS / f"{s}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))

    # ---- 5. split files ---------------------------------------------------
    split_members: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for r in rows:
        if r["kept"] and r["split"] in split_members:
            split_members[r["split"]].append(r["stem"])
    for name, members in split_members.items():
        members.sort()
        lines = [str(DERIVED_IMAGES / f"{s}.jpg") for s in members]
        (SPLITS_V2 / f"{name}.txt").write_text("\n".join(lines) + "\n")

    quarantined = sorted(r["stem"] for r in rows if r["split"] == QUARANTINE)
    (SPLITS_V2 / "quarantined.txt").write_text("\n".join(quarantined) + "\n")

    # ---- 6. per-image manifest CSV ---------------------------------------
    manifest_csv = SPLITS_V2 / "split_manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---- 7. dataset_v2.yaml ----------------------------------------------
    DATASET_V2_YAML.write_text(
        "# SafeRoute AI — derived TWO-class dataset configuration (PHASE 24C)\n"
        "# Derived from the approved PHASE_24B decisions (M1 + P-B).\n"
        "# Originals are NOT modified. Do not overwrite data/dataset.yaml.\n"
        "# Rules: master_rules.md 1, 5, 9, 14, 15, 17, 18, 20.\n"
        "\n"
        f"path: {DERIVED.as_posix()}\n"
        "\n"
        f"train: {(SPLITS_V2 / 'train.txt').as_posix()}\n"
        f"val: {(SPLITS_V2 / 'val.txt').as_posix()}\n"
        f"test: {(SPLITS_V2 / 'test.txt').as_posix()}\n"
        "\n"
        "# Derived two-class mapping: manhole (class 2) removed only in the\n"
        "# derived labels; the original annotation is preserved unchanged.\n"
        "names:\n"
        "  0: pothole\n"
        "  1: crack\n",
        encoding="utf-8",
    )

    # ---- 8. validate ------------------------------------------------------
    validation = validate(rows, split_members, quarantined)

    # ---- 9. reproducibility manifest -------------------------------------
    manifest = {
        "phase": "PHASE_24C",
        "generator_script": str(Path(__file__).resolve()),
        "generator_script_sha256": source_hashes["script"],
        "approved_decisions": ["M1 two-class derived dataset", "P-B date-atomic split",
                               "quarantine unknown-date images", "drop zero-area in derived only",
                               "keep one per exact-duplicate group", "DATA-YOLO/RDD2022 excluded"],
        "source": {
            "dataset_root": str(SRC),
            "path": str(SRC),
            "hashes": source_hashes,
        },
        "split_rule": {"date_to_split": DATE_TO_SPLIT, "quarantine": "undeterminable capture date"},
        "artifacts": {
            "dataset_v2_yaml": str(DATASET_V2_YAML),
            "dataset_v2_yaml_sha256": sha256_file(DATASET_V2_YAML),
            "splits_dir": str(SPLITS_V2),
            "split_file_sha256": {n: sha256_file(SPLITS_V2 / f"{n}.txt")
                                  for n in ("train", "val", "test")},
            "quarantined_file_sha256": sha256_file(SPLITS_V2 / "quarantined.txt"),
            "split_manifest_csv": str(manifest_csv),
            "split_manifest_csv_sha256": sha256_file(manifest_csv),
            "derived_labels_dir": str(DERIVED_LABELS),
            "derived_labels_merkle_sha256": merkle_dir_digest(DERIVED_LABELS, "*.txt")[0],
            "images_exposure": {"path": str(DERIVED_IMAGES), "kind": junction_kind,
                                "target": str(SRC_IMAGES),
                                "note": "junction/symlink to the ORIGINAL images; no copy"},
        },
        "counts": {
            "source_images": n_images,
            "derived_kept_images": len(kept_stems),
            "quarantined_images": len(quarantined),
            "excluded_exact_duplicates": len(dup_keeper),
            "split_sizes": {k: len(v) for k, v in split_members.items()},
        },
        "exclusions": {
            "quarantined": quarantined,
            "exact_duplicate_extras": {s: k for s, k in sorted(dup_keeper.items())},
            "zero_area_rows_dropped_in_derived": [
                r["stem"] for r in rows if r["n_zero_area_dropped"] > 0
            ],
        },
        "validation": validation,
    }
    (DERIVED / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # verify source digests unchanged after generation
    after_labels, _ = merkle_dir_digest(SRC_LABELS, "*.txt")
    after_images, _ = merkle_dir_digest(SRC_IMAGES, "*.jpg")
    manifest["source"]["unchanged_after_generation"] = {
        "labels-YOLO": after_labels == labels_digest_before,
        "images": after_images == images_digest_before,
        "dataset_yaml": sha256_file(ORIG_DATASET_YAML) == source_hashes["dataset.yaml"],
    }
    (DERIVED / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ---- 10. console summary ---------------------------------------------
    print("derived root      :", DERIVED)
    print("images exposure   :", junction_kind, "->", SRC_IMAGES)
    print("kept images       :", len(kept_stems))
    print("split sizes       :", {k: len(v) for k, v in split_members.items()})
    print("quarantined       :", len(quarantined))
    print("dup extras dropped:", len(dup_keeper))
    print("validation        :", json.dumps(validation["checks"], indent=2))
    print("source unchanged  :", manifest["source"]["unchanged_after_generation"])
    return 0


def validate(rows, split_members, quarantined) -> dict:
    """Validate pairing, class ids, boxes, split separation, distributions."""
    kept = {r["stem"]: r for r in rows if r["kept"]}
    checks: dict = {}

    # pairing: every split image has a derived label file
    missing = []
    for name, members in split_members.items():
        for s in members:
            img = DERIVED_IMAGES / f"{s}.jpg"
            lbl = DERIVED_LABELS / f"{s}.txt"
            if not img.exists():
                missing.append(f"image:{s}")
            if not lbl.exists():
                missing.append(f"label:{s}")
    checks["kept_images_with_image_and_label"] = (len(missing) == 0)
    checks["missing_count"] = len(missing)

    # class ids + bbox validity in derived labels
    bad_class = 0
    bad_box = 0
    total_boxes = 0
    zero_area = 0
    per_class = defaultdict(int)
    images_with = defaultdict(int)
    empty = 0
    for s in kept:
        boxes = parse_boxes(DERIVED_LABELS / f"{s}.txt")
        if not boxes:
            empty += 1
        present = set()
        for cid, xc, yc, w, h in boxes:
            total_boxes += 1
            per_class[cid] += 1
            present.add(cid)
            if cid not in KEEP_CLASSES:
                bad_class += 1
            if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                bad_box += 1
            if w <= 0 or h <= 0:
                zero_area += 1
        for c in present:
            images_with[c] += 1
    checks["derived_class_ids_subset_of_{0,1}"] = (bad_class == 0)
    checks["derived_boxes_in_valid_range"] = (bad_box == 0)
    checks["derived_zero_area_boxes"] = zero_area
    checks["derived_empty_label_images"] = empty

    # split separation: no stem in >1 split; none in split and quarantine
    all_split = [s for m in split_members.values() for s in m]
    checks["no_stem_in_multiple_splits"] = (len(all_split) == len(set(all_split)))
    checks["no_split_image_quarantined"] = (len(set(all_split) & set(quarantined)) == 0)

    # date-atomic invariant
    date_buckets: dict[str, set[str]] = defaultdict(set)
    for s, r in kept.items():
        date_buckets[r["capture_date"]].add(r["split"])
    checks["no_capture_date_spans_multiple_splits"] = all(
        len(v) == 1 for v in date_buckets.values()
    )
    checks["dates_present"] = sorted(date_buckets.keys())

    # manhole removed
    checks["manhole_boxes_removed_total"] = sum(r["n_manhole_dropped"] for r in rows)
    checks["zero_area_rows_dropped_total"] = sum(r["n_zero_area_dropped"] for r in rows)

    return {
        "checks": checks,
        "derived_totals": {
            "images": len(kept),
            "boxes": total_boxes,
            "boxes_by_class": dict(sorted(per_class.items())),
            "images_with_class": dict(sorted(images_with.items())),
        },
        "per_split": {
            name: {
                "images": len(split_members[name]),
                "boxes_by_class": _split_class_counts(split_members[name]),
            }
            for name in split_members
        },
    }


def _split_class_counts(members: list[str]) -> dict:
    counts = defaultdict(int)
    for s in members:
        for cid, *_ in parse_boxes(DERIVED_LABELS / f"{s}.txt"):
            counts[cid] += 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    sys.exit(main())
