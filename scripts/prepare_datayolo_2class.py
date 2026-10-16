#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""SafeRoute AI - DATA-YOLO two-class training PREPARATION (audit + split + config).

Purpose
-------
Turn the labelled part of DATA-YOLO into a *two-class* (0=pothole, 1=crack)
training candidate **without modifying DATA-YOLO, the original labels, the
current model, or the serving configuration**.

Design / safety
---------------
* DATA-YOLO is opened READ-ONLY. Nothing is ever written under DATA-YOLO.
* Every generated artefact lives under a brand-new, isolated directory:
      data/datayolo_prep/
* Images are exposed in the prep tree as NTFS hard links (byte-identical, no
  duplication); if a hard link is not possible the file is copied. Labels are
  copied byte-for-byte from the ORIGINAL label files (never edited / remapped).
* Only images whose labels contain exclusively classes {0,1} and at least one
  box are "eligible". Images containing class 2 (open_manhole) or empty
  (background) labels are excluded and recorded with a reason.
* The existing DATA-YOLO `test/` split has no labels and is NOT used.
* Splits are grouped by source scene: two images are put in the SAME group when
  they are byte-identical OR share a base stem (strip `_aug...`), so an
  augmentation/duplicate copy can never leak across train and validation.

Usage
-----
    .venv/Scripts/python.exe scripts/prepare_datayolo_2class.py

Outputs (all NEW, all under data/datayolo_prep/):
    dataset.yaml                 two-class dataset configuration
    manifests/train.txt          grouped train image list
    manifests/val.txt            grouped val image list (all images in val groups)
    manifests/test.txt           grouped held-out list (same-source; NOT an independent
                                 benchmark - present because the SafeRoute training harness
                                 requires a `test:` key)
    manifests/val_dedup.txt      one representative per val group (unbiased metrics)
    manifest.csv                 per-eligible-image record (group, split, classes)
    original_split_audit.csv     UNTOUCHED record of every original split assignment
    MANIFEST.json                reproducibility + exclusion manifest
    images/<split>__<stem>.<ext> hard links (or copies) of the ORIGINAL images
    labels/<split>__<stem>.txt   byte-identical copies of the ORIGINAL labels
    .gitignore                   keeps the bulk materialisation out of git
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import cv2

# --------------------------------------------------------------------------- #
# paths / constants
# --------------------------------------------------------------------------- #
WORKSPACE = Path(r"D:\New folder (3)")
SRC_ROOT = WORKSPACE / "DATA-YOLO" / "Datasets" / "dataset" / "dataset"
PREP = WORKSPACE / "data" / "datayolo_prep"
PREP_IMAGES = PREP / "images"
PREP_LABELS = PREP / "labels"
PREP_MANIFESTS = PREP / "manifests"
DATASET_YAML = PREP / "dataset.yaml"

SPLITS = ("train", "valid", "test")
IMG_EXTS = (".jpg", ".jpeg", ".png")
AUG_MARKERS = ("_aug", "_jpg.rf.", "-aug-")
KEEP_CLASSES = {0, 1}          # pothole, crack
RNG_SEED = 42
VAL_FRAC = 0.15
TEST_FRAC = 0.15

PREP.mkdir(parents=True, exist_ok=True)
PREP_IMAGES.mkdir(exist_ok=True)
PREP_LABELS.mkdir(exist_ok=True)
PREP_MANIFESTS.mkdir(exist_ok=True)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def header_kind(path: Path) -> str:
    """Magic-byte sniff so we can flag ext/content mismatches (e.g. WebP .jpg)."""
    with path.open("rb") as f:
        head = f.read(12)
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return "unknown"


def base_key(stem: str) -> str:
    """Source-scene key: strip offline-augmentation / exporter suffixes."""
    b = stem
    for marker in AUG_MARKERS:
        if marker in b:
            b = b.split(marker)[0]
    return b.lower()


def is_aug(stem: str) -> bool:
    return any(m in stem for m in AUG_MARKERS)


def parse_label(path: Path):
    """Return (rows, malformed, bad_class, out_of_range, empty)."""
    rows, malformed, bad_class, oob = [], 0, 0, 0
    if not path.is_file():
        return rows, malformed, bad_class, oob, True
    raw = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not raw:
        return rows, malformed, bad_class, oob, True
    for ln in raw:
        parts = ln.split()
        if len(parts) != 5:
            malformed += 1
            continue
        try:
            cid = int(parts[0])
            xc, yc, w, h = (float(v) for v in parts[1:])
        except ValueError:
            malformed += 1
            continue
        if cid < 0 or cid > 99:
            bad_class += 1
            continue
        if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
            oob += 1
        rows.append((cid, xc, yc, w, h))
    return rows, malformed, bad_class, oob, False


# --------------------------------------------------------------------------- #
# 1. enumerate + audit every labelled-set image
# --------------------------------------------------------------------------- #
def enumerate_images(split: str) -> list[Path]:
    d = SRC_ROOT / split / "images"
    if not d.is_dir():
        return []
    out = []
    for name in sorted(os.listdir(d)):
        p = d / name
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            out.append(p)
    return out


def main() -> int:
    import random

    audit_rows: list[dict] = []
    eligible: list[dict] = []          # dicts with stem, split, path, label rows, sha
    image_sha: dict[tuple[str, str], str] = {}

    counts = {
        "images_total": 0, "labels_present": 0, "labels_missing": 0,
        "empty_labels": 0, "malformed_rows": 0, "bad_class_rows": 0,
        "out_of_range_rows": 0, "undecodable": 0, "header_mismatch": 0,
    }
    exclusions = defaultdict(list)

    for split in SPLITS:
        for img in enumerate_images(split):
            counts["images_total"] += 1
            stem = img.stem
            lbl = SRC_ROOT / split / "labels" / f"{stem}.txt"
            rows, malformed, bad_class, oob, empty = parse_label(lbl)

            counts["malformed_rows"] += malformed
            counts["bad_class_rows"] += bad_class
            counts["out_of_range_rows"] += oob
            if lbl.is_file():
                counts["labels_present"] += 1
            else:
                counts["labels_missing"] += 1

            # decode + magic check
            shar = sha256_file(img)
            image_sha[(split, stem)] = shar
            hk = header_kind(img)
            ext_kind = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(img.suffix[1:].lower(), "?")
            hm = (hk != ext_kind)
            if hm:
                counts["header_mismatch"] += 1
            im = cv2.imread(str(img))
            decode_ok = im is not None
            if not decode_ok:
                counts["undecodable"] += 1
            dims = f"{im.shape[1]}x{im.shape[0]}" if decode_ok else "NA"

            classes = sorted({r[0] for r in rows})
            n_p = sum(1 for r in rows if r[0] == 0)
            n_c = sum(1 for r in rows if r[0] == 1)
            n_m = sum(1 for r in rows if r[0] == 2)
            n_other = sum(1 for r in rows if r[0] not in KEEP_CLASSES)
            n_zero_area = sum(1 for r in rows if r[3] <= 0 or r[4] <= 0)

            if not lbl.is_file():
                counts["empty_labels"] += 1
                reason = "unlabelled_test_split" if split == "test" else "missing_label"
                excl = True
            elif empty:
                counts["empty_labels"] += 1
                reason = "empty_background_label"
                excl = True
            elif not decode_ok:
                reason = "undecodable_image"
                excl = True
            elif n_other > 0:
                reason = "contains_class2_manhole" if 2 in classes else "contains_unsupported_class"
                excl = True
            else:
                reason = ""
                excl = False

            row = {
                "original_split": split,
                "stem": stem,
                "base_key": base_key(stem),
                "is_aug": is_aug(stem),
                "image_path": str(img),
                "label_present": lbl.is_file(),
                "sha256": shar,
                "decode_ok": decode_ok,
                "dims": dims,
                "header_kind": hk,
                "ext_matches_header": (not hm),
                "classes": ",".join(str(c) for c in classes),
                "n_boxes": len(rows),
                "n_pothole": n_p,
                "n_crack": n_c,
                "n_manhole": n_m,
                "n_zero_area": n_zero_area,
                "malformed_rows": malformed,
                "bad_class_rows": bad_class,
                "out_of_range_rows": oob,
                "eligible": (not excl),
                "exclusion_reason": reason,
            }
            audit_rows.append(row)

            if excl:
                exclusions[reason].append(f"{split}/{stem}")
            else:
                eligible.append({
                    "split": split, "stem": stem, "base_key": base_key(stem),
                    "is_aug": is_aug(stem), "sha256": shar, "path": img,
                    "n_pothole": n_p, "n_crack": n_c,
                })

    # --------------------------------------------------------------------- #
    # 2. group eligible images (union-find by identical bytes OR base stem)
    # --------------------------------------------------------------------- #
    n = len(eligible)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_hash: dict[str, int] = {}
    by_base: dict[str, int] = {}
    for i, e in enumerate(eligible):
        h = e["sha256"]
        if h in by_hash:
            union(i, by_hash[h])
        else:
            by_hash[h] = i
        b = e["base_key"]
        if b in by_base:
            union(i, by_base[b])
        else:
            by_base[b] = i

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    # stable, human-readable group ids
    group_order = sorted(groups.keys(), key=lambda r: min(eligible[i]["base_key"] for i in groups[r]))
    group_id_of = {}
    group_rows = []
    for gid, root in enumerate(group_order, start=1):
        members = sorted(groups[root], key=lambda i: (eligible[i]["split"], eligible[i]["stem"]))
        for i in members:
            group_id_of[i] = gid
        group_rows.append({"group_id": gid, "members": members})

    # --------------------------------------------------------------------- #
    # 3. grouped train / val / test split (group granularity, deterministic)
    # --------------------------------------------------------------------- #
    rng = random.Random(RNG_SEED)
    order = list(range(len(group_rows)))
    rng.shuffle(order)

    total = n
    target_val = VAL_FRAC * total
    target_test = TEST_FRAC * total
    running_val = 0
    running_test = 0
    val_groups: set[int] = set()
    test_groups: set[int] = set()
    for gi in order:
        size = len(group_rows[gi]["members"])
        if running_test < target_test:
            test_groups.add(gi)
            running_test += size
        elif running_val < target_val:
            val_groups.add(gi)
            running_val += size
    if not test_groups:                      # pathological fallback
        test_groups.add(order[0])
    if not val_groups:
        val_groups.add(next(gi for gi in order if gi not in test_groups))

    assigned = {}
    for gi in range(len(group_rows)):
        if gi in test_groups:
            s = "test"
        elif gi in val_groups:
            s = "val"
        else:
            s = "train"
        for i in group_rows[gi]["members"]:
            assigned[i] = s

    # --------------------------------------------------------------------- #
    # 4. materialise the isolated prep dataset (hard links + label copies)
    # --------------------------------------------------------------------- #
    link_kind = {"hardlink": 0, "copy": 0}
    # Labels are placed under a per-ASSIGNED-split sub-directory so the train /
    # val / test label caches (<dir>.cache) can never collide: Ultralytics writes
    # the cache next to the first label file. Images mirror the same layout so the
    # standard `images` -> `labels` path substitution still resolves correctly.
    for stale in list(PREP_IMAGES.glob("*")) + list(PREP_LABELS.glob("*")):
        if stale.is_file():
            stale.unlink()
    (PREP / "labels.cache").unlink(missing_ok=True)
    prep_name = {}
    for i, e in enumerate(eligible):
        s = e["split"]              # ORIGINAL split (kept in the file name for traceability)
        asplit = assigned[i]        # ASSIGNED split (train / val / test)
        stem = e["stem"]
        ext = e["path"].suffix.lower()
        (PREP_IMAGES / asplit).mkdir(exist_ok=True)
        (PREP_LABELS / asplit).mkdir(exist_ok=True)
        dst_img = PREP_IMAGES / asplit / f"{s}__{stem}{ext}"
        dst_lbl = PREP_LABELS / asplit / f"{s}__{stem}.txt"
        prep_name[i] = dst_img
        if not dst_img.exists():
            try:
                os.link(e["path"], dst_img)
                link_kind["hardlink"] += 1
            except OSError:
                shutil.copy2(e["path"], dst_img)
                link_kind["copy"] += 1
        if not dst_lbl.exists():
            shutil.copy2(SRC_ROOT / s / "labels" / f"{stem}.txt", dst_lbl)

    # --------------------------------------------------------------------- #
    # 5. write the manifests / config / manifests
    # --------------------------------------------------------------------- #
    train_imgs = [prep_name[i] for i in range(n) if assigned[i] == "train"]
    val_imgs = [prep_name[i] for i in range(n) if assigned[i] == "val"]
    test_imgs = [prep_name[i] for i in range(n) if assigned[i] == "test"]

    # dedup val: one representative per val group (prefer a non-aug original)
    val_dedup = []
    for gi, g in enumerate(group_rows):
        if gi not in val_groups:
            continue
        members = g["members"]
        non_aug = [i for i in members if not eligible[i]["is_aug"]]
        pick = sorted(non_aug or members, key=lambda i: eligible[i]["stem"])[0]
        val_dedup.append(prep_name[pick])

    def write_list(path: Path, items: list[Path]):
        path.write_text("\n".join(str(p) for p in sorted(items)) + ("\n" if items else ""),
                        encoding="utf-8")

    write_list(PREP_MANIFESTS / "train.txt", train_imgs)
    write_list(PREP_MANIFESTS / "val.txt", val_imgs)
    write_list(PREP_MANIFESTS / "test.txt", test_imgs)
    write_list(PREP_MANIFESTS / "val_dedup.txt", val_dedup)

    DATASET_YAML.write_text(
        "# SafeRoute AI - DATA-YOLO two-class PREPARED dataset configuration\n"
        "# GENERATED by scripts/prepare_datayolo_2class.py (do not hand-edit).\n"
        "# Two-class mapping: 0=pothole, 1=crack. open_manhole (class 2) images are\n"
        "# EXCLUDED (never relabelled). DATA-YOLO originals are NOT modified.\n"
        "# This config is SEPARATE from data/dataset.yaml (serving v2) and must not\n"
        "# overwrite it.\n"
        "#\n"
        "# NOTE on `test`: DATA-YOLO's own test/ split is UNLABELLED and unusable.\n"
        "# `test` here is a same-source scene-grouped held-out list, NOT an\n"
        "# independent benchmark. It exists because the SafeRoute training harness\n"
        "# (scripts/train_baseline.py) requires a `test:` key. Do not report it as a\n"
        "# trustworthy generalisation metric.\n"
        "\n"
        f"path: {PREP.as_posix()}\n"
        "\n"
        f"train: {(PREP_MANIFESTS / 'train.txt').as_posix()}\n"
        f"val: {(PREP_MANIFESTS / 'val.txt').as_posix()}\n"
        f"test: {(PREP_MANIFESTS / 'test.txt').as_posix()}\n"
        "\n"
        "names:\n"
        "  0: pothole\n"
        "  1: crack\n",
        encoding="utf-8",
    )

    (PREP / ".gitignore").write_text(
        "# Bulk materialisation (regenerate with scripts/prepare_datayolo_2class.py)\n"
        "images/\n"
        "labels/\n"
        "*.cache\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------------------- #
    # 6. per-image manifest CSV + original-split audit CSV
    # --------------------------------------------------------------------- #
    with (PREP / "original_split_audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(audit_rows, key=lambda r: (r["original_split"], r["stem"])))

    with (PREP / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["original_split", "stem", "base_key", "group_id", "group_size",
                    "is_aug", "assigned_split", "n_pothole", "n_crack", "sha256"])
        for i in sorted(range(n), key=lambda k: (assigned[k], eligible[k]["split"], eligible[k]["stem"])):
            e = eligible[i]
            w.writerow([e["split"], e["stem"], e["base_key"], group_id_of[i],
                        len(groups[find(i)]), e["is_aug"], assigned[i],
                        e["n_pothole"], e["n_crack"], e["sha256"]])

    # --------------------------------------------------------------------- #
    # 7. validation
    # --------------------------------------------------------------------- #
    in_train = {str(p) for p in train_imgs}
    in_val = {str(p) for p in val_imgs}
    in_test = {str(p) for p in test_imgs}

    def mirror_label(img_path: Path) -> Path:
        """Reproduce Ultralytics' `images` -> `labels` path substitution."""
        return Path(str(img_path).replace(os.sep + "images" + os.sep,
                                          os.sep + "labels" + os.sep, 1)).with_suffix(".txt")

    checks = {
        "no_image_in_two_splits": len(in_train & in_val) == 0 and len(in_train & in_test) == 0 and len(in_val & in_test) == 0,
        "every_manifest_image_exists": all(p.exists() for p in train_imgs + val_imgs + test_imgs + val_dedup),
        "every_manifest_label_exists": all(mirror_label(p).exists()
                                           for p in train_imgs + val_imgs + test_imgs + val_dedup),
        "manifests_only_two_classes": True,
        "no_group_spans_splits": True,
        "val_dedup_is_subset_of_val": set(map(str, val_dedup)) <= in_val,
        "all_eligible_assigned_once": len(in_train | in_val | in_test) == n,
    }
    # label class check + group separation
    for p in train_imgs + val_imgs + test_imgs:
        for ln in mirror_label(p).read_text().splitlines():
            if ln.strip() and int(ln.split()[0]) not in KEEP_CLASSES:
                checks["manifests_only_two_classes"] = False
    split_of_group = {}
    for i in range(n):
        g = find(i)
        if g in split_of_group and split_of_group[g] != assigned[i]:
            checks["no_group_spans_splits"] = False
        split_of_group[g] = assigned[i]

    # --------------------------------------------------------------------- #
    # 8. class distribution per assigned split
    # --------------------------------------------------------------------- #
    def dist(idxs):
        boxes = {0: 0, 1: 0}
        imgs_with = {0: 0, 1: 0}
        for i in idxs:
            e = eligible[i]
            boxes[0] += e["n_pothole"]
            boxes[1] += e["n_crack"]
            if e["n_pothole"]:
                imgs_with[0] += 1
            if e["n_crack"]:
                imgs_with[1] += 1
        return {"images": len(idxs), "boxes": boxes, "images_with_class": imgs_with}

    train_idx = [i for i in range(n) if assigned[i] == "train"]
    val_idx = [i for i in range(n) if assigned[i] == "val"]
    test_idx = [i for i in range(n) if assigned[i] == "test"]

    # cross-source leakage diagnostic: if we had used the ORIGINAL split verbatim
    orig_val_idx = [i for i in range(n) if eligible[i]["split"] == "valid"]
    orig_train_groups = {find(i) for i in range(n) if eligible[i]["split"] == "train"}
    leaked = sum(1 for i in orig_val_idx if find(i) in orig_train_groups)

    # --------------------------------------------------------------------- #
    # 9. reproducibility manifest
    # --------------------------------------------------------------------- #
    source_hashes = {
        "generator_script": sha256_file(Path(__file__).resolve()),
        "dataset_yaml": sha256_file(DATASET_YAML),
        "manifests": {p.name: sha256_file(p) for p in sorted(PREP_MANIFESTS.glob("*.txt"))},
        "manifest_csv": sha256_file(PREP / "manifest.csv"),
        "original_split_audit_csv": sha256_file(PREP / "original_split_audit.csv"),
    }
    manifest = {
        "stage": "DATA-YOLO two-class training preparation",
        "source": {
            "dataset_root": str(SRC_ROOT),
            "read_only": True,
            "note": "DATA-YOLO is never written; prep tree is isolated.",
        },
        "split_rule": {
            "grouping": "union of (identical sha256) OR (identical base stem after stripping _aug*)",
            "assignment": f"random.Random(seed={RNG_SEED}); ~{VAL_FRAC:.0%} val + ~{TEST_FRAC:.0%} test "
                          f"of eligible images at scene-group granularity; remainder train",
            "test_caveat": "the grouped test list is SAME-SOURCE (not an independent benchmark); "
                           "it only satisfies the training harness requirement for a `test:` key.",
        },
        "counts": {
            **counts,
            "eligible_images": n,
            "groups": len(group_rows),
            "split_sizes": {"train": len(train_idx), "val": len(val_idx),
                            "test": len(test_idx), "val_dedup": len(val_dedup)},
            "materialisation": link_kind,
        },
        "class_distribution": {"train": dist(train_idx), "val": dist(val_idx),
                               "test": dist(test_idx)},
        "exclusions_by_reason": {k: {"count": len(v), "examples": v[:8]}
                                 for k, v in sorted(exclusions.items())},
        "original_split_leakage_diagnostic": {
            "note": "If the original train/valid assignment were reused verbatim, these "
                    "eligible val images would share a scene-group with train.",
            "eligible_val_images": len(orig_val_idx),
            "leaking_into_train": leaked,
            "leak_fraction": round(leaked / len(orig_val_idx), 4) if orig_val_idx else 0.0,
        },
        "validation": checks,
        "artifacts": {k: (str(v) if not isinstance(v, dict) else v)
                      for k, v in source_hashes.items()},
        "outputs": {
            "dataset_yaml": str(DATASET_YAML),
            "manifests_dir": str(PREP_MANIFESTS),
            "manifest_csv": str(PREP / "manifest.csv"),
            "original_split_audit_csv": str(PREP / "original_split_audit.csv"),
            "images_dir": str(PREP_IMAGES),
            "labels_dir": str(PREP_LABELS),
        },
    }
    (PREP / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # --------------------------------------------------------------------- #
    # 10. summary
    # --------------------------------------------------------------------- #
    print("DATA-YOLO labelled set        :", SRC_ROOT)
    print("images total                  :", counts["images_total"])
    print("  labels present / missing    :", counts["labels_present"], "/", counts["labels_missing"])
    print("  empty labels                :", counts["empty_labels"])
    print("  malformed / bad-class / oob :", counts["malformed_rows"], "/", counts["bad_class_rows"], "/", counts["out_of_range_rows"])
    print("  undecodable / header-mism   :", counts["undecodable"], "/", counts["header_mismatch"])
    print("eligible (pure pothole/crack) :", n)
    print("groups (scenes)               :", len(group_rows))
    print("split sizes                   :", {"train": len(train_idx), "val": len(val_idx),
                                               "test": len(test_idx), "val_dedup": len(val_dedup)})
    print("class dist train              :", dist(train_idx))
    print("class dist val                :", dist(val_idx))
    print("class dist test               :", dist(test_idx))
    print("exclusions                    :", {k: len(v) for k, v in sorted(exclusions.items())})
    print("original-split leak diagnostic:", manifest["original_split_leakage_diagnostic"])
    print("validation checks             :", json.dumps(checks, indent=2))
    print("materialisation               :", link_kind)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
