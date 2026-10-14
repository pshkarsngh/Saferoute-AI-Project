#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PHASE_20 - Prepare a versioned YOLO dataset from RDD2022 (READ-ONLY on source).

- Converts Pascal VOC XML -> YOLO labels using a STRICT, documented mapping.
- Keeps duplicate-image groups whole (leakage-safe, fixed-seed split).
- Hardlinks source images into a NEW dataset dir (never modifies RDD2022).
- Writes dataset.yaml, split manifests and a conversion manifest.

Does NOT train. Run only after audit validation passes.

Usage:
  .\.venv\Scripts\python.exe scripts\prepare_rdd2022_yolo.py --countries India
"""

import os, sys, json, csv, random, hashlib, argparse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone

WS = r"D:\New folder (3)"
RDD = os.path.join(WS, "data", "raw", "RDD2022", "RDD2022")
DUP_CSV = os.path.join(WS, "reports", "phase20", "duplicate_groups.csv")

CLASS_MAP = {"D40": 0, "D00": 1, "D10": 1, "D20": 1}  # -> 0 pothole, 1 crack
NAMES = {0: "pothole", 1: "crack"}
SEED = 42


def log(m):
    print(m, flush=True)


def parse_voc(path):
    """Return (list of (raw_name, x1,y1,x2,y2), width, height, n_dropped)."""
    root = ET.parse(path).getroot()
    size = root.find("size")
    W = int(size.findtext("width")); H = int(size.findtext("height"))
    out = []
    for o in root.findall("object"):
        name = (o.findtext("name") or "").strip()
        b = o.find("bndbox")
        if b is None:
            continue
        try:
            x1, y1 = float(b.findtext("xmin")), float(b.findtext("ymin"))
            x2, y2 = float(b.findtext("xmax")), float(b.findtext("ymax"))
        except (TypeError, ValueError):
            continue
        out.append((name, x1, y1, x2, y2))
    return out, W, H


def load_dup_groups():
    """Map 'Country/stem.jpg' -> group_id (only multi-image groups)."""
    m = {}
    if not os.path.isfile(DUP_CSV):
        return m
    with open(DUP_CSV, encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if len(row) == 2:
                m[row[1]] = row[0]
    return m


def build_records(countries):
    dup = load_dup_groups()
    recs = []
    raw_cls = Counter(); dropped_cls = Counter(); empty = 0; zero = 0
    for country in countries:
        img_dir = os.path.join(RDD, country, "train", "images")
        xml_dir = os.path.join(RDD, country, "train", "annotations", "xmls")
        for fn in sorted(os.listdir(img_dir)):
            if not fn.lower().endswith(".jpg"):
                continue
            stem = os.path.splitext(fn)[0]
            xml = os.path.join(xml_dir, stem + ".xml")
            if not os.path.isfile(xml):
                continue
            objs, W, H = parse_voc(xml)
            lines = []
            for name, x1, y1, x2, y2 in objs:
                raw_cls[name] += 1
                if name not in CLASS_MAP:
                    dropped_cls[name] += 1
                    continue
                if x2 <= x1 or y2 <= y1:
                    zero += 1
                    continue
                cx = ((x1 + x2) / 2) / W; cy = ((y1 + y2) / 2) / H
                w = (x2 - x1) / W; h = (y2 - y1) / H
                lines.append(f"{CLASS_MAP[name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            if not lines:
                empty += 1
            key = f"{country}/{fn}"
            gid = dup.get(key, f"singleton::{key}")
            recs.append({"country": country, "file": fn, "stem": stem,
                         "img": os.path.join(img_dir, fn), "lines": lines, "group": gid})
    log(f"records={len(recs)} empty_after_map={empty} zero_area={zero} dropped={dict(dropped_cls)}")
    return recs, raw_cls, dropped_cls, empty, zero


def split_groups(recs, ratios=(0.8, 0.1, 0.1)):
    groups = defaultdict(list)
    for r in recs:
        groups[r["group"]].append(r)
    keys = sorted(groups.keys())
    random.Random(SEED).shuffle(keys)
    targets = [r * len(recs) for r in ratios]
    cur = [0, 0, 0]; assign = {}
    for g in keys:
        s = max(range(3), key=lambda k: (targets[k] - cur[k]))
        assign[g] = s
        cur[s] += len(groups[g])
    for r in recs:
        r["split"] = ["train", "val", "test"][assign[r["group"]]]
    counts = Counter(r["split"] for r in recs)
    log(f"split images {dict(counts)} (groups kept whole)")
    return counts

