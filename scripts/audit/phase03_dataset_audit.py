#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PHASE_03 - Dataset Integrity, Class-Mapping & Split Audit (SafeRoute AI).

READ-ONLY GUARANTEE
  * Opens dataset files read-only.
  * Never writes, renames, deletes or moves anything under data\.
  * Writes ONLY under  reports\phase03\  inside the workspace.

Requires only already-present packages: Python stdlib + numpy + cv2.
No installation, no network access.

Approved under PHASE_03 Gate A2 (2026-10-12).
"""

import os
import sys
import json
import csv
import hashlib
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
import cv2

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
WS        = r"D:\New folder (3)"
DATA      = os.path.join(WS, "data", "pothole_crack_manhole", "data")
IMG_DIR   = os.path.join(DATA, "images")
YOLO_DIR  = os.path.join(DATA, "labels-YOLO")
POLY_DIR  = os.path.join(DATA, "labels")
COCO_PATH = os.path.join(DATA, "annotations_coco.json")
OUT_DIR   = os.path.join(WS, "reports", "phase03")

NAMES         = {0: "pothole", 1: "crack", 2: "manhole"}
PY_TO_NAMES   = {0: "pothole", 1: "crack"}
NEAR_HAMMING  = 5          # dHash Hamming distance threshold for near-duplicates
TIME_GAP_SEC  = 2          # same-date capture gap used as an extra leakage-cluster signal
SPLIT_RATIOS  = (0.70, 0.20, 0.10)
SEED          = 42


def log(msg):
    print(msg, flush=True)


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def list_files(d, exts):
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, n) for n in os.listdir(d)
        if os.path.splitext(n)[1].lower() in exts
    )


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(gray, size=8):
    """64-bit difference hash."""
    r = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = 0
    for v in (r[:, 1:] > r[:, :-1]).ravel():
        bits = (bits << 1) | int(v)
    return bits


def parse_ts(name):
    try:
        d, t = name.split("_")
        return datetime.strptime(d + t, "%Y%m%d%H%M%S")
    except Exception:
        return None


class DSU:
    def __init__(self, items):
        self.p = {x: x for x in items}

    def find(self, x):
        p = self.p
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def parse_yolo(path):
    rows, malformed, oor, zero, beyond = [], [], [], [], []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) != 5:
                malformed.append([os.path.basename(path), i, s])
                continue
            try:
                cid = int(parts[0])
                cx, cy, w, h = (float(x) for x in parts[1:])
            except ValueError:
                malformed.append([os.path.basename(path), i, s])
                continue
            if not all(0.0 <= v <= 1.0 for v in (cx, cy, w, h)):
                oor.append([os.path.basename(path), i, s])
            if w <= 0 or h <= 0:
                zero.append([os.path.basename(path), i, s])
            if (cx - w / 2.0) < -1e-9 or (cx + w / 2.0) > 1 + 1e-9 \
               or (cy - h / 2.0) < -1e-9 or (cy + h / 2.0) > 1 + 1e-9:
                beyond.append([os.path.basename(path), i, s])
            rows.append((cid, cx, cy, w, h))
    return rows, malformed, oor, zero, beyond


def parse_poly(path):
    rows, malformed, oor, zero = [], [], [], 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) != 9:
                malformed.append([os.path.basename(path), i, s])
                continue
            try:
                cid = int(parts[0])
                vals = [float(x) for x in parts[1:]]
            except ValueError:
                malformed.append([os.path.basename(path), i, s])
                continue
            if not all(0.0 <= v <= 1.0 for v in vals):
                oor.append([os.path.basename(path), i, s])
            xs, ys = vals[0::2], vals[1::2]
            if max(xs) == min(xs) or max(ys) == min(ys):
                zero += 1
            rows.append(cid)
    return rows, malformed, oor, zero


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    R = {
        "phase": "PHASE_03",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": WS,
        "dataset_dir": DATA,
        "read_only": True,
        "versions": {
            "python": sys.version,
            "numpy": np.__version__,
            "cv2": cv2.__version__,
        },
        "config": {
            "near_hamming": NEAR_HAMMING,
            "time_gap_sec": TIME_GAP_SEC,
            "split_ratios": SPLIT_RATIOS,
            "seed": SEED,
        },
    }

    # -- 1. Enumerate ------------------------------------------------------
    imgs = list_files(IMG_DIR, {".jpg", ".jpeg", ".png"})
    yolo = list_files(YOLO_DIR, {".txt"})
    poly = list_files(POLY_DIR, {".txt"})
    R["counts"] = {
        "images": len(imgs),
        "labels_yolo": len(yolo),
        "labels_poly": len(poly),
        "splits_present": [],   # no train/val/test folders exist
    }
    log(f"[1] images={len(imgs)} labels-YOLO={len(yolo)} labels-poly={len(poly)}")

    img_stems = {stem(p) for p in imgs}
    yolo_stems = {stem(p) for p in yolo}
    poly_stems = {stem(p) for p in poly}

    # -- 2. Pairing --------------------------------------------------------
    R["pairing"] = {
        "images_without_yolo_label": sorted(img_stems - yolo_stems),
        "yolo_labels_without_image": sorted(yolo_stems - img_stems),
        "images_without_poly_label": sorted(img_stems - poly_stems),
        "poly_labels_without_image": sorted(poly_stems - img_stems),
    }
    log(f"[2] unpaired: images_no_yolo={len(R['pairing']['images_without_yolo_label'])} "
        f"yolo_no_image={len(R['pairing']['yolo_labels_without_image'])} "
        f"images_no_poly={len(R['pairing']['images_without_poly_label'])} "
        f"poly_no_image={len(R['pairing']['poly_labels_without_image'])}")

    # -- 3. Decode + dims + hashes + dHash ---------------------------------
    dims = Counter()
    decode_fail = []
    sha = {}
    dh = {}
    dims_by_stem = {}
    exact = defaultdict(list)
    for p in imgs:
        s = stem(p)
        im = cv2.imread(p, cv2.IMREAD_COLOR)
        if im is None:
            decode_fail.append(os.path.basename(p))
            continue
        dims[f"{im.shape[1]}x{im.shape[0]}"] += 1
        dims_by_stem[s] = (im.shape[1], im.shape[0])
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        dh[s] = dhash(gray)
        h = sha256_file(p)
        sha[s] = h
        exact[h].append(os.path.basename(p))
    R["decode"] = {
        "decoded_ok": len(imgs) - len(decode_fail),
        "failures": decode_fail,
        "dimensions": dict(dims),
    }
    R["exact_duplicate_groups"] = [v for v in exact.values() if len(v) > 1]
    R["exact_duplicate_image_count"] = sum(len(v) for v in exact.values() if len(v) > 1)
    log(f"[3] decoded_ok={R['decode']['decoded_ok']} fail={len(decode_fail)} dims={dict(dims)} "
        f"exact_dup_groups={len(R['exact_duplicate_groups'])}")

    # -- 4/5/6. Parse annotations -----------------------------------------
    malformed, oor, zero, beyond, bad_cls = [], [], [], [], []
    box_by_cls = Counter()
    img_by_cls = Counter()
    empty_labels = []
    per_image_boxes = {}   # stem -> Counter(class_id)
    for p in yolo:
        s = stem(p)
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            raw = [ln.strip() for ln in f if ln.strip()]
        per_image_boxes[s] = Counter()
        if not raw:
            empty_labels.append(os.path.basename(p))
        rows, m, o, z, b = parse_yolo(p)
        malformed += m
        oor += o
        zero += z
        beyond += b
        for (cid, cx, cy, w, h) in rows:
            box_by_cls[cid] += 1
            per_image_boxes[s][cid] += 1
        for cid in per_image_boxes[s].keys():
            img_by_cls[cid] += 1
        for (cid, *_rest) in rows:
            if cid not in NAMES:
                bad_cls.append([os.path.basename(p), cid])

    p_malformed, p_oor, p_zero, p_bad = [], [], 0, []
    for p in poly:
        rows, m, o, z = parse_poly(p)
        p_malformed += m
        p_oor += o
        p_zero += z
        for cid in rows:
            if cid not in NAMES:
                p_bad.append([os.path.basename(p), cid])

    R["annotations"] = {
        "malformed_yolo_lines": malformed[:100],
        "malformed_yolo_count": len(malformed),
        "out_of_range_yolo_count": len(oor),
        "out_of_range_yolo_samples": oor[:100],
        "zero_size_yolo_count": len(zero),
        "zero_size_yolo_samples": zero[:100],
        "beyond_image_bounds_yolo_count": len(beyond),
        "beyond_image_bounds_yolo_samples": beyond[:100],
        "invalid_class_id_yolo_count": len(bad_cls),
        "invalid_class_id_yolo_values": sorted({c for _, c in bad_cls}),
        "malformed_poly_count": len(p_malformed),
        "out_of_range_poly_count": len(p_oor),
        "zero_size_poly_count": p_zero,
        "invalid_class_id_poly_count": len(p_bad),
        "invalid_class_id_poly_values": sorted({c for _, c in p_bad}),
    }
    R["class_hist"] = {
        "boxes_by_id": {int(k): v for k, v in sorted(box_by_cls.items())},
        "boxes_by_name": {NAMES.get(k, str(k)): v for k, v in sorted(box_by_cls.items())},
        "images_by_name": {NAMES.get(k, str(k)): v for k, v in sorted(img_by_cls.items())},
        "total_boxes": sum(box_by_cls.values()),
    }
    R["empty_labels"] = {"count": len(empty_labels), "files": empty_labels}
    log(f"[4-6] malformed={len(malformed)} oor={len(oor)} zero={len(zero)} "
        f"beyond={len(beyond)} bad_cls={len(bad_cls)} empty={len(empty_labels)}")
    log(f"      boxes_by_name={R['class_hist']['boxes_by_name']}")

    # -- COCO reconcile + path safety -------------------------------------
    with open(COCO_PATH, "r", encoding="utf-8") as f:
        coco = json.load(f)
    cats = {c["id"]: c.get("name") for c in coco.get("categories", [])}
    img_by_id = {im["id"]: im for im in coco.get("images", [])}
    c_box = Counter()
    c_bad_bbox = 0
    c_bad_ref = 0
    c_bad_cat = 0
    for a in coco.get("annotations", []):
        cid = a.get("category_id")
        c_box[cid] += 1
        if cid not in cats:
            c_bad_cat += 1
        im = img_by_id.get(a.get("image_id"))
        if im is None:
            c_bad_ref += 1
            continue
        x, y, w, h = a.get("bbox", [0, 0, 0, 0])
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > im["width"] + 0.5 or y + h > im["height"] + 0.5:
            c_bad_bbox += 1
    unsafe_names = [
        im["file_name"] for im in coco.get("images", [])
        if os.path.isabs(im["file_name"]) or ".." in im["file_name"].replace("\\", "/").split("/")
    ]
    R["coco"] = {
        "images": len(coco.get("images", [])),
        "annotations": len(coco.get("annotations", [])),
        "categories": cats,
        "boxes_by_name": {cats.get(k, str(k)): v for k, v in sorted(c_box.items())},
        "bad_bbox_count": c_bad_bbox,
        "bad_image_refs": c_bad_ref,
        "bad_category_refs": c_bad_cat,
        "unsafe_file_names": unsafe_names,
        "has_info": "info" in coco,
        "has_licenses": "licenses" in coco,
    }
    R["reconcile"] = {
        "total_boxes_yolo": sum(box_by_cls.values()),
        "total_boxes_coco": len(coco.get("annotations", [])),
        "per_class_boxes_yolo_vs_coco": {
            NAMES.get(k, str(k)): [box_by_cls.get(k, 0), c_box.get(k, 0)] for k in sorted(set(list(box_by_cls) + list(c_box)))
        },
        "images_yolo_vs_coco": [len(imgs), len(coco.get("images", []))],
    }
    log(f"[coco] images={R['coco']['images']} anns={R['coco']['annotations']} "
        f"bad_bbox={c_bad_bbox} bad_ref={c_bad_ref} unsafe_names={len(unsafe_names)}")

    # -- 7. Duplicates (exact + near via dHash, union-find) ---------------
    keys = [s for s in img_stems if s in dh]
    dsu = DSU(keys)
    # exact via sha
    by_sha = defaultdict(list)
    for s in keys:
        by_sha[sha[s]].append(s)
    for group in by_sha.values():
        for other in group[1:]:
            dsu.union(group[0], other)
    # near via dhash (O(n^2), n~2009)
    kd = [(s, dh[s]) for s in keys]
    for i in range(len(kd)):
        si, di = kd[i]
        for j in range(i + 1, len(kd)):
            sj, dj = kd[j]
            if bin(di ^ dj).count("1") <= NEAR_HAMMING:
                dsu.union(si, sj)
    # capture-time clustering (same date, adjacent <= TIME_GAP_SEC)
    ts = sorted(((parse_ts(s), s) for s in keys if parse_ts(s) is not None), key=lambda x: x[0])
    for (t1, s1), (t2, s2) in zip(ts, ts[1:]):
        if t1.date() == t2.date() and (t2 - t1).total_seconds() <= TIME_GAP_SEC:
            dsu.union(s1, s2)
    groups = defaultdict(list)
    for s in keys:
        groups[dsu.find(s)].append(s)
    content_groups = sorted((sorted(v) for v in groups.values()), key=lambda g: (-len(g), g[0]))
    dup_groups = [g for g in content_groups if len(g) > 1]
    R["duplicates"] = {
        "content_groups_total": len(content_groups),
        "multi_image_groups": len(dup_groups),
        "images_in_multi_groups": sum(len(g) for g in dup_groups),
        "exact_only_groups": len(R["exact_duplicate_groups"]),
        "largest_groups": [g[:20] for g in dup_groups[:20]],
    }
    log(f"[7] content_groups={len(content_groups)} multi_groups={len(dup_groups)} "
        f"images_in_multi={R['duplicates']['images_in_multi_groups']}")

    # -- 8. Leakage assessment (no splits exist) --------------------------
    R["leakage"] = {
        "source_splits_present": False,
        "policy_documented": "not documented (single-pool dataset)",
        "cross_split_overlap": "n/a - no source splits",
        "content_grouping_applied": True,
        "grouping_signals": [
            "exact byte duplicate (sha256)",
            f"near duplicate (dHash hamming <= {NEAR_HAMMING})",
            f"same-date capture adjacency (<= {TIME_GAP_SEC}s) as source/session signal",
        ],
        "residual_risk": (
            "Frames from the same capture run may still be visually distinct yet share a "
            "source/session/road segment; filenames encode capture time only, so true "
            "session/device/segment identity is NOT provable from the data. The proposed "
            "split keeps content/time groups intact to reduce leakage; residual risk noted."
        ),
    }

    # -- 9. Path safety ----------------------------------------------------
    def inside_ws(p):
        return os.path.abspath(p).lower().startswith(os.path.abspath(WS).lower())

    R["path_safety"] = {
        "dataset_dir_inside_workspace": inside_ws(DATA),
        "coco_unsafe_file_names": unsafe_names,
        "external_references": [],
    }

    # -- 10. Proposed (group-aware) split ---------------------------------
    rng = random.Random(SEED)
    order = content_groups[:]
    rng.shuffle(order)
    targets = [r * len(keys) for r in SPLIT_RATIOS]
    cur = [0, 0, 0]
    assign = {}
    for g in order:
        s = max(range(3), key=lambda k: (targets[k] - cur[k]))
        for name in g:
            assign[name] = ["train", "val", "test"][s]
        cur[s] += len(g)
    split_counts = Counter(assign.values())
    # per-class per-split boxes
    per_split_cls = {sp: Counter() for sp in ("train", "val", "test")}
    for s, boxes in per_image_boxes.items():
        sp = assign.get(s)
        if sp is None:
            continue
        for cid, n in boxes.items():
            per_split_cls[sp][NAMES.get(cid, str(cid))] += n
    R["proposed_split"] = {
        "method": "group-aware (content+time groups kept intact), deterministic seed",
        "seed": SEED,
        "ratios_target": SPLIT_RATIOS,
        "images_per_split": dict(split_counts),
        "boxes_per_class_per_split": {k: dict(v) for k, v in per_split_cls.items()},
        "created_on_disk": False,
    }
    log(f"[10] proposed_split images={dict(split_counts)} (NOT created on disk)")

    # -- Write outputs -----------------------------------------------------
    with open(os.path.join(OUT_DIR, "dataset_audit.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, indent=2, ensure_ascii=False)

    with open(os.path.join(OUT_DIR, "split_manifest_proposal.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stem", "image_file", "sha256", "dhash_hex", "width", "height",
                    "boxes_pothole", "boxes_crack", "boxes_manhole", "proposed_split"])
        for s in sorted(keys):
            b = per_image_boxes.get(s, Counter())
            wh = dims_by_stem.get(s, ("", ""))
            w.writerow([s, s + ".jpg", sha[s], format(dh[s], "016x"),
                        wh[0], wh[1], b.get(0, 0), b.get(1, 0), b.get(2, 0), assign.get(s, "")])

    write_markdown(R, content_groups)
    write_class_mapping(R)
    log(f"[out] wrote reports to {OUT_DIR}")
    return 0


def write_markdown(R, content_groups):
    L = []
    a = L.append
    a("# PHASE_03 — Dataset Audit Report (measured)")
    a("")
    a(f"- Generated (UTC): {R['generated_utc']}")
    a(f"- Dataset: `{R['dataset_dir']}`")
    a(f"- Read-only: {R['read_only']}")
    a(f"- Versions: Python {R['versions']['python'].split()[0]}, numpy {R['versions']['numpy']}, cv2 {R['versions']['cv2']}")
    a(f"- Config: near_hamming={R['config']['near_hamming']}, time_gap_sec={R['config']['time_gap_sec']}, seed={R['config']['seed']}")
    a("")
    a("## 1. Counts")
    a(f"- images: {R['counts']['images']}")
    a(f"- labels-YOLO: {R['counts']['labels_yolo']}")
    a(f"- labels (polygon): {R['counts']['labels_poly']}")
    a("- train/val/test: **none present** (single pool)")
    a("")
    a("## 2. Pairing")
    a(f"- images without YOLO label: {len(R['pairing']['images_without_yolo_label'])}")
    a(f"- YOLO labels without image: {len(R['pairing']['yolo_labels_without_image'])}")
    a(f"- images without polygon label: {len(R['pairing']['images_without_poly_label'])}")
    a(f"- polygon labels without image: {len(R['pairing']['poly_labels_without_image'])}")
    a("")
    a("## 3. Decode")
    a(f"- decoded ok: {R['decode']['decoded_ok']}")
    a(f"- failures: {len(R['decode']['failures'])} {R['decode']['failures'][:20]}")
    a(f"- dimensions: {R['decode']['dimensions']}")
    a("")
    a("## 4. Annotations")
    an = R["annotations"]
    a(f"- malformed YOLO lines: {an['malformed_yolo_count']}")
    a(f"- out-of-range YOLO boxes: {an['out_of_range_yolo_count']}")
    a(f"- zero-size YOLO boxes: {an['zero_size_yolo_count']}")
    a(f"- beyond-image-bounds YOLO boxes: {an['beyond_image_bounds_yolo_count']}")
    a(f"- invalid class-id YOLO: {an['invalid_class_id_yolo_count']} {an['invalid_class_id_yolo_values']}")
    a(f"- malformed polygon lines: {an['malformed_poly_count']}")
    a(f"- out-of-range polygon: {an['out_of_range_poly_count']}")
    a(f"- zero-extent polygon: {an['zero_size_poly_count']}")
    a(f"- invalid class-id polygon: {an['invalid_class_id_poly_count']} {an['invalid_class_id_poly_values']}")
    a("")
    a("## 5. Actual format & class IDs")
    a("- format: YOLO txt (`labels-YOLO/`) + normalized polygon txt (`labels/`) + COCO JSON")
    a(f"- IDs found (YOLO boxes): {R['class_hist']['boxes_by_id']}")
    a(f"- boxes by name: {R['class_hist']['boxes_by_name']}")
    a(f"- images containing each class: {R['class_hist']['images_by_name']}")
    a(f"- names provenance: bundled `README.md` and COCO `categories` ({R['coco']['categories']})")
    a("")
    a("## 6. Class mapping proposal (see class_mapping_proposal.md)")
    a("")
    a("## 7. Empty labels")
    a(f"- images with 0 objects: {R['empty_labels']['count']}")
    a("")
    a("## 8. Duplicates / near-duplicates")
    d = R["duplicates"]
    a(f"- exact duplicate groups: {d['exact_only_groups']}")
    a(f"- content groups (exact+near+time): {d['content_groups_total']}")
    a(f"- multi-image groups: {d['multi_image_groups']} ({d['images_in_multi_groups']} images)")
    a("")
    a("## 9. Split integrity & leakage")
    a(f"- source policy: {R['leakage']['policy_documented']}")
    a(f"- cross-split overlap: {R['leakage']['cross_split_overlap']}")
    a(f"- grouping signals: {R['leakage']['grouping_signals']}")
    a(f"- residual risk: {R['leakage']['residual_risk']}")
    a("")
    a("## 10. Proposed split (NOT created)")
    ps = R["proposed_split"]
    a(f"- method: {ps['method']} (seed {ps['seed']})")
    a(f"- images per split: {ps['images_per_split']}")
    a(f"- boxes per class per split: {ps['boxes_per_class_per_split']}")
    a(f"- created on disk: {ps['created_on_disk']}")
    a("")
    a("## 11. COCO reconciliation")
    rc = R["reconcile"]
    a(f"- total boxes YOLO vs COCO: {rc['total_boxes_yolo']} vs {rc['total_boxes_coco']}")
    a(f"- images YOLO vs COCO: {rc['images_yolo_vs_coco']}")
    a(f"- per-class [YOLO, COCO]: {rc['per_class_boxes_yolo_vs_coco']}")
    a(f"- COCO bad bbox / bad ref / bad category: {R['coco']['bad_bbox_count']} / {R['coco']['bad_image_refs']} / {R['coco']['bad_category_refs']}")
    a(f"- COCO has info/licenses: {R['coco']['has_info']} / {R['coco']['has_licenses']}")
    a("")
    a("## 12. Path safety")
    a(f"- dataset inside workspace: {R['path_safety']['dataset_dir_inside_workspace']}")
    a(f"- unsafe file names: {len(R['path_safety']['coco_unsafe_file_names'])}")
    a("")
    with open(os.path.join(OUT_DIR, "dataset_audit_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def write_class_mapping(R):
    L = []
    a = L.append
    a("# PHASE_03 — Class Mapping Proposal")
    a("")
    a("Actual dataset classes (from `labels-YOLO/`, `labels/`, `annotations_coco.json`, `README.md`):")
    a("")
    a("| id | actual name | proposed SafeRoute class | supported? | boxes |")
    a("|---|---|---|---|---|")
    bh = R["class_hist"]["boxes_by_name"]
    a(f"| 0 | pothole | `pothole` | yes | {bh.get('pothole', 0)} |")
    a(f"| 1 | crack | `crack` | yes | {bh.get('crack', 0)} |")
    a(f"| 2 | manhole | **`unsupported`** (excluded; never relabelled) | no | {bh.get('manhole', 0)} |")
    a("")
    a("Project target classes NOT covered by this dataset (0 instances):")
    a("`damaged_patch`, `waterlogging`, `uneven_surface`, `speed_bump`, `other`.")
    a("")
    a("Initial detector scope: **pothole + crack only**.")
    a("")
    with open(os.path.join(OUT_DIR, "class_mapping_proposal.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
