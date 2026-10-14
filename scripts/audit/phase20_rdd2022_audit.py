#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PHASE_20 - RDD2022 archive & annotation audit (READ-ONLY).

Reads the extracted RDD2022 Pascal VOC dataset and reports integrity,
class mapping, pairing, duplicates and leakage-group signals.

READ-ONLY GUARANTEE
  * Opens dataset files read-only; never writes/renames/deletes under data\.
  * Writes ONLY under reports\phase20\ inside the workspace.

Usage:
  .\.venv\Scripts\python.exe scripts\audit\phase20_rdd2022_audit.py [--dhash]
"""

import os
import sys
import json
import hashlib
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone

WS = r"D:\New folder (3)"
DATA = os.path.join(WS, "data", "raw", "RDD2022", "RDD2022")
OUT_DIR = os.path.join(WS, "reports", "phase20")

# RDD2022 -> project class mapping (see PHASE_20 report section 5).
CLASS_MAP = {"D40": "pothole", "D00": "crack", "D10": "crack", "D20": "crack"}
PROJECT_NAMES = {0: "pothole", 1: "crack"}
COUNTRIES = ["China_Drone", "China_MotorBike", "Czech", "India",
             "Japan", "Norway", "United_States"]


def log(m):
    print(m, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_voc(path):
    """Parse a Pascal VOC XML; return (objects, size, errors)."""
    objs, errs = [], []
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        return [], None, [f"parse_error:{type(e).__name__}:{e}"]
    size = root.find("size")
    wh = None
    if size is not None:
        try:
            wh = (int(size.findtext("width")), int(size.findtext("height")))
        except Exception:
            errs.append("bad_size")
    for o in root.findall("object"):
        name = (o.findtext("name") or "").strip()
        b = o.find("bndbox")
        if b is None:
            errs.append(f"missing_bndbox:{name}")
            continue
        try:
            x1, y1 = float(b.findtext("xmin")), float(b.findtext("ymin"))
            x2, y2 = float(b.findtext("xmax")), float(b.findtext("ymax"))
        except (TypeError, ValueError):
            errs.append(f"bad_coords:{name}")
            continue
        if x2 <= x1 or y2 <= y1:
            errs.append(f"zero_area:{name}")
        if wh and (x1 < -1 or y1 < -1 or x2 > wh[0] + 1 or y2 > wh[1] + 1):
            errs.append(f"out_of_bounds:{name}")
        objs.append(name)
    return objs, wh, errs


def session_key(country, filename):
    """Best-effort capture-session key: strip a trailing numeric frame index."""
    stem = os.path.splitext(filename)[0]
    i = len(stem)
    while i > 0 and (stem[i - 1].isdigit() or stem[i - 1] in "-_."):
        i -= 1
    base = stem[:i] or stem
    return f"{country}::{base}"


def main():
    do_hash = "--dhash" in sys.argv or "--hash" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    R = {
        "phase": "PHASE_20",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": DATA,
        "read_only": True,
        "class_map": CLASS_MAP,
        "countries": {},
        "totals": {},
    }
    raw_cls = Counter()
    proj_cls = Counter()
    unknown = Counter()
    malformed = Counter()
    all_stems = Counter()
    session_sizes = defaultdict(int)
    duplicate_shas = defaultdict(list)

    for country in COUNTRIES:
        base = os.path.join(DATA, country)
        tr_img = os.path.join(base, "train", "images")
        tr_xml = os.path.join(base, "train", "annotations", "xmls")
        te_img = os.path.join(base, "test", "images")
        c = {"train_images": 0, "train_xmls": 0, "test_images": 0,
             "paired": 0, "images_without_xml": 0, "xml_without_image": 0}
        if not os.path.isdir(base):
            R["countries"][country] = {"present": False}
            continue
        imgs = [f for f in os.listdir(tr_img) if f.lower().endswith(".jpg")] if os.path.isdir(tr_img) else []
        xmls = [f for f in os.listdir(tr_xml) if f.lower().endswith(".xml")] if os.path.isdir(tr_xml) else []
        tests = [f for f in os.listdir(te_img) if f.lower().endswith(".jpg")] if os.path.isdir(te_img) else []
        c["train_images"], c["train_xmls"], c["test_images"] = len(imgs), len(xmls), len(tests)
        img_stems = {os.path.splitext(f)[0] for f in imgs}
        xml_stems = {os.path.splitext(f)[0] for f in xmls}
        c["paired"] = len(img_stems & xml_stems)
        c["images_without_xml"] = len(img_stems - xml_stems)
        c["xml_without_image"] = len(xml_stems - img_stems)
        for f in imgs:
            all_stems[os.path.splitext(f)[0]] += 1
            session_sizes[session_key(country, f)] += 1
            if do_hash:
                duplicate_shas[sha256_file(os.path.join(tr_img, f))].append(f"{country}/{f}")
        for f in xmls:
            objs, wh, errs = parse_voc(os.path.join(tr_xml, f))
            for e in errs:
                malformed[e.split(":")[0]] += 1
            for name in objs:
                raw_cls[name] += 1
                if name in CLASS_MAP:
                    proj_cls[CLASS_MAP[name]] += 1
                else:
                    unknown[name] += 1
        R["countries"][country] = c
        log(f"[{country}] train_img={len(imgs)} train_xml={len(xmls)} test_img={len(tests)} paired={c['paired']}")

    R["totals"] = {
        "train_images": sum(c.get("train_images", 0) for c in R["countries"].values()),
        "train_xmls": sum(c.get("train_xmls", 0) for c in R["countries"].values()),
        "test_images": sum(c.get("test_images", 0) for c in R["countries"].values()),
        "boxes_by_raw_class": dict(sorted(raw_cls.items())),
        "boxes_by_project_class": dict(sorted(proj_cls.items())),
        "unknown_classes": dict(sorted(unknown.items())),
        "malformed": dict(sorted(malformed.items())),
        "duplicate_filename_stems": sum(1 for v in all_stems.values() if v > 1),
    }
    if do_hash:
        dups = [v for v in duplicate_shas.values() if len(v) > 1]
        R["totals"]["exact_duplicate_groups"] = len(dups)
        R["totals"]["exact_duplicate_images"] = sum(len(v) for v in dups)
    R["session_groups"] = {
        "groups": len(session_sizes),
        "largest": sorted(session_sizes.values(), reverse=True)[:10],
    }
    R["proposed_class_mapping"] = {"project_id_0": "pothole", "project_id_1": "crack"}

    with open(os.path.join(OUT_DIR, "rdd2022_audit.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, indent=2, ensure_ascii=False)
    log(f"[out] wrote {os.path.join(OUT_DIR, 'rdd2022_audit.json')}")
    log(f"[totals] {json.dumps(R['totals'])}")
    return R


if __name__ == "__main__":
    main()


