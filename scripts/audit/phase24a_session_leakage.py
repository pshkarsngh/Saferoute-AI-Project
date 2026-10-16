"""PHASE_24A supplementary — capture-session and within-split near-duplicate analysis.

Complements phase24a_dataset_audit.py, whose banded dHash prefilter skips
degenerate buckets (large same-video bursts). This script:

  1. Groups images into capture sessions using filename heuristics
     (vlcsnap timestamps, Image##### sequences, frame_#### sequences).
  2. Reports session distribution per split and sessions spanning >1 split
     (same-sequence cross-split leakage risk, Rule 15).
  3. Runs an exhaustive pairwise dHash comparison inside each session group
     (no bucket skipping) and counts within-split and cross-split
     near-duplicate pairs.

Read-only. Evidence written to reports/phase24a/session_leakage.json.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
OUT = WORKSPACE / "reports" / "phase24a" / "session_leakage.json"

sys.path.insert(0, str(WORKSPACE / "scripts" / "audit"))
from phase24a_dataset_audit import dhash_gray, hamming  # noqa: E402


def session_key(name: str) -> str:
    """Capture-session heuristic. Conservative: same key ~= same video/sequence."""
    stem = Path(name).stem
    low = stem.lower()
    if low.startswith("vlcsnap"):
        # vlcsnap-2025-02-16-16h43m25s929 -> drop sub-second part
        m = re.match(r"(vlcsnap-\d{4}-\d{2}-\d{2}-\d{2}h\d{2}m\d{2}s)\d*", low)
        if m:
            return m.group(1)
    m = re.match(r"(image)(\d+)$", low)
    if m:
        # sequential numbered frames: bucket into groups of 500
        return f"{m.group(1)}_block_{int(m.group(2)) // 500}"
    m = re.match(r"(frame_)(\d+)$", low)
    if m:
        return f"{m.group(1)}block_{int(m.group(2)) // 500}"
    m = re.match(r"(.*?)[\s_]*\((\d+)\)$", stem)
    if m:
        return f"{m.group(1)}_block_{int(m.group(2)) // 500}"
    m = re.match(r"(.+?)_?\d{4,}$", stem)
    if m:
        return m.group(1)
    return stem


def main() -> int:
    root = WORKSPACE / "data" / "pothole_crack_manhole" / "data" / "images"
    images = sorted(p for p in root.iterdir() if p.suffix.lower() == ".jpg")

    split_map: dict[str, str] = {}
    for name in ("train", "val", "test"):
        for ln in (WORKSPACE / "data" / "splits" / f"{name}.txt").read_text().splitlines():
            ln = ln.strip()
            if ln:
                split_map[Path(ln).stem] = name

    sessions: dict[str, list[str]] = defaultdict(list)
    hashes: dict[str, int] = {}
    undecodable: list[str] = []
    for p in images:
        sessions[session_key(p.name)].append(p.name)
        dh = dhash_gray(p)
        if dh is None:
            undecodable.append(p.name)
        else:
            hashes[p.name] = dh

    # session x split matrix
    spanning: list[dict] = []
    session_split: dict[str, dict[str, int]] = {}
    for key, names in sessions.items():
        dist: dict[str, int] = defaultdict(int)
        for n in names:
            s = split_map.get(Path(n).stem)
            dist[s or "unknown"] += 1
        session_split[key] = dict(dist)
        if len([k for k in dist if k in ("train", "val", "test")]) > 1:
            spanning.append({"session": key, "distribution": dict(dist)})

    # exhaustive within-session near-dup scan
    within_pairs = 0
    cross_pairs = 0
    cross_examples: list[list[str]] = []
    within_examples: list[list[str]] = []
    skipped_sessions: list[str] = []
    for key, names in sessions.items():
        names = [n for n in names if n in hashes]
        if len(names) > 400:
            skipped_sessions.append(f"{key} ({len(names)} images)")
            continue
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if hamming(hashes[names[i]], hashes[names[j]]) <= 6:
                    sa = split_map.get(Path(names[i]).stem)
                    sb = split_map.get(Path(names[j]).stem)
                    if sa != sb:
                        cross_pairs += 1
                        if len(cross_examples) < 10:
                            cross_examples.append([names[i], sa, names[j], sb])
                    else:
                        within_pairs += 1
                        if len(within_examples) < 5:
                            within_examples.append([names[i], names[j], sa])

    out = {
        "phase": "PHASE_24A-supplementary",
        "method": "filename session heuristic + exhaustive in-session dHash hamming<=6",
        "session_heuristic": "vlcsnap timestamp (second precision); Image/frame/Name(n) "
                             "sequences bucketed per 500 frames; other names by prefix",
        "images": len(images),
        "undecodable": undecodable,
        "sessions_total": len(sessions),
        "session_size_histogram": {
            "1": sum(1 for v in sessions.values() if len(v) == 1),
            "2-10": sum(1 for v in sessions.values() if 2 <= len(v) <= 10),
            "11-100": sum(1 for v in sessions.values() if 11 <= len(v) <= 100),
            "101-400": sum(1 for v in sessions.values() if 101 <= len(v) <= 400),
            ">400": sum(1 for v in sessions.values() if len(v) > 400),
        },
        "sessions_spanning_multiple_splits": spanning,
        "within_split_near_pairs": within_pairs,
        "cross_split_near_pairs_exhaustive": cross_pairs,
        "cross_split_examples": cross_examples,
        "within_split_examples": within_examples,
        "sessions_skipped_too_large": skipped_sessions,
        "interpretation": "cross-split near pairs found by this exhaustive in-session "
                          "scan indicate residual same-sequence leakage across splits; "
                          "sessions skipped (>400 imgs) are large video bursts whose "
                          "cross-split status was NOT verified here.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("sessions:", len(out["sessions_total"] and sessions))
    print("spanning sessions:", len(spanning))
    print("within-split near pairs:", within_pairs, "| cross-split near pairs:", cross_pairs)
    print("skipped:", skipped_sessions)
    print("evidence:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
