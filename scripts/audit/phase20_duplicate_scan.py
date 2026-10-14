#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PHASE_20 - RDD2022 duplicate-image scan (READ-ONLY).

Computes exact (sha256) and near-duplicate (dHash + banded LSH) groups across
the RDD2022 train images so splits can keep duplicate groups intact.

READ-ONLY: never writes under data\. Outputs only to reports\phase20\.

Usage:
  .\.venv\Scripts\python.exe scripts\audit\phase20_duplicate_scan.py
"""

import os
import sys
import json
import csv
import hashlib
from collections import defaultdict
from datetime import datetime, timezone

import cv2

WS = r"D:\New folder (3)"
DATA = os.path.join(WS, "data", "raw", "RDD2022", "RDD2022")
OUT_DIR = os.path.join(WS, "reports", "phase20")
COUNTRIES = ["China_Drone", "China_MotorBike", "Czech", "India",
             "Japan", "United_States"]
NEAR_HAMMING = 6  # dHash hamming distance threshold for near-duplicates


def log(m):
    print(m, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def dhash(gray, size=8):
    r = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = 0
    for v in (r[:, 1:] > r[:, :-1]).ravel():
        bits = (bits << 1) | int(v)
    return bits


class DSU:
    def __init__(self, items):
        self.p = {x: x for x in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    recs = []  # (key, path, sha, dhash)
    for country in COUNTRIES:
        img_dir = os.path.join(DATA, country, "train", "images")
        if not os.path.isdir(img_dir):
            continue
        files = sorted(f for f in os.listdir(img_dir) if f.lower().endswith(".jpg"))
        for i, fn in enumerate(files):
            p = os.path.join(img_dir, fn)
            key = f"{country}/{fn}"
            try:
                sha = sha256_file(p)
                im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                if im is None:
                    log(f"unreadable {key}")
                    continue
                dh = dhash(im)
            except Exception as e:
                log(f"error {key}: {e}")
                continue
            recs.append((key, p, sha, dh))
            if (i + 1) % 2000 == 0:
                log(f"  {country}: {i+1}/{len(files)}")
        log(f"[{country}] indexed {len(files)}")
    log(f"indexed total {len(recs)}")

    dsu = DSU([r[0] for r in recs])
    # exact duplicates
    by_sha = defaultdict(list)
    for key, _p, sha, _d in recs:
        by_sha[sha].append(key)
    exact_groups = [v for v in by_sha.values() if len(v) > 1]
    for g in exact_groups:
        for other in g[1:]:
            dsu.union(g[0], other)

    # near duplicates via 8x8bit banded LSH (pigeonhole for hamming <= 6)
    bands = defaultdict(list)
    for key, _p, _sha, dh in recs:
        for b in range(8):
            band = (dh >> (b * 8)) & 0xFF
            bands[(b, band)].append((key, dh))
    cand = set()
    for lst in bands.values():
        if len(lst) < 2 or len(lst) > 400:  # skip degenerate giant buckets
            continue
        for i in range(len(lst)):
            ki, di = lst[i]
            for j in range(i + 1, len(lst)):
                kj, dj = lst[j]
                if bin(di ^ dj).count("1") <= NEAR_HAMMING:
                    cand.add((ki, kj))
    for a, b in cand:
        dsu.union(a, b)
    log(f"exact_groups={len(exact_groups)} near_pairs={len(cand)}")
    return recs, dsu, exact_groups


if __name__ == "__main__":
    recs, dsu, exact_groups = main()
    groups = defaultdict(list)
    for key, _p, _sha, _dh in recs:
        groups[dsu.find(key)].append(key)
    content_groups = sorted((sorted(v) for v in groups.values()), key=lambda g: (-len(g), g[0]))
    multi = [g for g in content_groups if len(g) > 1]
    summary = {
        "phase": "PHASE_20",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "near_hamming": NEAR_HAMMING,
        "indexed_images": len(recs),
        "exact_duplicate_groups": len(exact_groups),
        "exact_duplicate_images": sum(len(g) for g in exact_groups),
        "content_groups": len(content_groups),
        "multi_image_groups": len(multi),
        "images_in_multi_groups": sum(len(g) for g in multi),
        "largest_groups": [g[:20] for g in multi[:15]],
    }
    with open(os.path.join(OUT_DIR, "duplicate_scan.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(OUT_DIR, "duplicate_groups.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group_id", "member"])
        for gi, g in enumerate(multi):
            for m in g:
                w.writerow([gi, m])
    log("SUMMARY " + json.dumps(summary))


