"""PHASE_24B — Dataset cleaning & split-hardening proposal (read-only analysis).

Master rules: Rules 1, 5, 9, 14, 15, 17, 18, 20.
Proposal-only: writes evidence JSON to reports/phase24b/ and NOTHING else.
No dataset, label, split, config or checkpoint is modified.

Computes:
  1. Current nominal split sizes + per-class box/image counts.
  2. "Manhole-drop" impact: images containing a class-2 (manhole) label are
     silently discarded by Ultralytics during training/eval; quantify images
     and valid pothole/crack labels lost.
  3. Effective (post-drop) split sizes and per-class counts.
  4. Capture-date session distribution per split (date-level atomicity).
  5. Three proposed session-aware split options (A/B/C) with sizes + classes.
  6. Exact-duplicate groups and their split membership.
  7. The vlcsnap-00058 degenerate annotation (YOLO + polygon source).

Usage:
  .venv/Scripts/python.exe scripts/audit/phase24b_split_proposal.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
ROOT = WORKSPACE / "data" / "pothole_crack_manhole" / "data"
YOLO_DIR = ROOT / "labels-YOLO"
OUT = WORKSPACE / "reports" / "phase24b" / "proposal_evidence.json"


def split_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for name in ("train", "val", "test"):
        for ln in (WORKSPACE / "data" / "splits" / f"{name}.txt").read_text().splitlines():
            ln = ln.strip()
            if ln:
                m[Path(ln).stem] = name
    return m


def capture_date(stem: str) -> str | None:
    """Best-effort capture date normalized to YYYY-MM-DD; None if undeterminable."""
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


def load_boxes(stem: str) -> list[tuple[int, float, float, float, float]]:
    p = YOLO_DIR / f"{stem}.txt"
    out: list[tuple[int, float, float, float, float]] = []
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        parts = line.split()
        if len(parts) == 5:
            try:
                out.append((int(parts[0]), *(float(v) for v in parts[1:])))
            except ValueError:
                pass
    return out


def summarize(stems: list[str]) -> dict:
    images = 0
    boxes = defaultdict(int)
    images_with = defaultdict(int)
    empty = 0
    zero_area = 0
    for s in stems:
        boxes_here = load_boxes(s)
        images += 1
        if not boxes_here:
            empty += 1
        present = set()
        for cid, xc, yc, w, h in boxes_here:
            boxes[cid] += 1
            present.add(cid)
            if w <= 0 or h <= 0:
                zero_area += 1
        for c in present:
            images_with[c] += 1
    return {
        "images": images,
        "boxes_by_class": dict(sorted(boxes.items())),
        "images_with_class": dict(sorted(images_with.items())),
        "empty_label_images": empty,
        "zero_area_boxes": zero_area,
    }


def main() -> int:
    smap = split_map()
    all_stems = sorted(p.stem for p in YOLO_DIR.glob("*.txt"))

    splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    unassigned: list[str] = []
    for s in all_stems:
        sp = smap.get(s)
        if sp in splits:
            splits[sp].append(s)
        else:
            unassigned.append(s)

    # --- 1/2/3: nominal, manhole-drop, effective --------------------------
    manhole_images = {sp: [s for s in splits[sp] if any(b[0] == 2 for b in load_boxes(s))]
                      for sp in splits}
    effective = {sp: [s for s in splits[sp] if s not in set(manhole_images[sp])] for sp in splits}
    manhole_set = {sp: set(v) for sp, v in manhole_images.items()}

    # valid labels lost inside manhole-containing images
    lost = {}
    for sp in splits:
        lb = defaultdict(int)
        for s in manhole_set[sp]:
            for cid, *_ in load_boxes(s):
                if cid in (0, 1):
                    lb[cid] += 1
        lost[sp] = dict(sorted(lb.items()))

    # --- 4: capture-date session distribution -----------------------------
    date_of = {s: capture_date(s) for s in all_stems}
    dates: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in all_stems:
        d = date_of[s] or "UNKNOWN"
        dates[d][smap.get(s, "unassigned")] += 1
    spanning = {d: dict(v) for d, v in dates.items()
                if len([k for k in v if k in ("train", "val", "test")]) > 1}
    unknown_dates = [s for s in all_stems if date_of[s] is None]

    # --- 5: proposed session-aware options --------------------------------
    # Atomic rule: every determinable capture date lives wholly in ONE split.
    # Dates already wholly in one split keep their split. The two spanning
    # dates are reassigned as a block.
    single_split_dates = {d: next(iter(v)) for d, v in dates.items()
                          if d != "UNKNOWN" and len([k for k in v if k in ("train", "val", "test")]) == 1}
    span_dates = sorted(spanning.keys())

    def build(assign: dict[str, str]) -> dict:
        new = {"train": [], "val": [], "test": [], "QUARANTINE": []}
        for s in all_stems:
            key = date_of[s] if date_of[s] is not None else "UNKNOWN"
            if key in assign:
                target = assign[key]
            else:
                target = single_split_dates.get(key, "train")
            new[target].append(s)
        return new

    options = {
        # P-A: date-atomic 70/20/10; holdout = the single known date 2025-02-26;
        # the two mega-sessions forced into train; unknown-date images into val.
        "P-A_recommended": {
            "2025-02-18": "train",
            "2025-02-19": "train",
            "2025-03-16": "val",
            "2025-02-23": "val",
            "2025-02-16": "val",
            "UNKNOWN": "val",
            "2025-02-26": "test",
        },
        # P-B: same, but unknown-date images quarantined (excluded from all splits).
        "P-B_quarantine_unknown": {
            "2025-02-18": "train",
            "2025-02-19": "train",
            "2025-03-16": "val",
            "2025-02-23": "val",
            "2025-02-16": "val",
            "2025-02-26": "test",
            "UNKNOWN": "QUARANTINE",
        },
    }

    def eff_summary(stems: list[str]) -> dict:
        """Summarize only images that survive the Ultralytics class-2 drop."""
        kept = [s for s in stems if not any(b[0] == 2 for b in load_boxes(s))]
        return summarize(kept)

    result: dict = {
        "phase": "PHASE_24B",
        "mode": "read-only proposal; nothing modified",
        "totals": {
            "images": len(all_stems),
            "splits": {k: len(v) for k, v in splits.items()},
            "unassigned_images": unassigned,
        },
        "date_session": {
            "dates_determinable": len([d for d in dates if d != "UNKNOWN"]),
            "unknown_date_images": len(unknown_dates),
            "unknown_date_examples": sorted(unknown_dates)[:15],
            "date_split_distribution": {d: dict(v) for d, v in sorted(dates.items())},
            "spanning_dates": spanning,
            "single_split_dates_count": len(single_split_dates),
        },
        "current": {sp: summarize(splits[sp]) for sp in splits},
        "manhole_drop": {
            "explanation": "Ultralytics verify_image_label asserts max class < num_cls; "
                           "any image with a class-2 label fails and is dropped entirely.",
            "manhole_images_per_split": {sp: len(manhole_images[sp]) for sp in splits},
            "valid_labels_lost_in_dropped_images": lost,
        },
        "effective_after_manhole_drop": {sp: summarize(effective[sp]) for sp in splits},
    }

    props = {}
    for name, assign in options.items():
        new = build(assign)
        props[name] = {
            "reassignment": assign,
            "nominal": {sp: summarize(new[sp]) for sp in ("train", "val", "test")},
            "effective_after_manhole_drop": {
                sp: eff_summary(new[sp]) for sp in ("train", "val", "test")
            },
            "quarantined_images": len(new.get("QUARANTINE", [])),
        }

    # P-C: minimal change — keep current splits, session leakage unchanged.
    props["P-C_keep_current_splits"] = {
        "reassignment": {"all dates": "unchanged (current train/val/test)"},
        "nominal": {sp: summarize(splits[sp]) for sp in splits},
        "effective_after_manhole_drop": {sp: eff_summary(splits[sp]) for sp in splits},
        "quarantined_images": 0,
    }
    result["proposed_options"] = props

    # --- 6: exact-duplicate groups + split membership ---------------------
    sha_to_files: dict[str, list[str]] = defaultdict(list)
    for s in all_stems:
        p = ROOT / "images" / f"{s}.jpg"
        h = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"
        sha_to_files[h].append(s)
    dup_groups = []
    for h, files in sha_to_files.items():
        if len(files) > 1:
            dup_groups.append({
                "sha256": h,
                "files": sorted(files),
                "split_of_each": [smap.get(f) for f in sorted(files)],
                "crosses_split": len({smap.get(f) for f in files}) > 1,
            })
    result["duplicate_groups"] = {
        "count": len(dup_groups),
        "crosses_split_count": sum(1 for g in dup_groups if g["crosses_split"]),
        "groups": dup_groups,
    }

    # --- 7: vlcsnap-00058 degenerate annotation ---------------------------
    result["degenerate_annotation"] = {
        "stem": "vlcsnap-00058",
        "split": smap.get("vlcsnap-00058"),
        "yolo_label": (YOLO_DIR / "vlcsnap-00058.txt").read_text().splitlines(),
        "polygon_label": (ROOT / "labels" / "vlcsnap-00058.txt").read_text().splitlines(),
        "coords_label": (ROOT / "annotations_coco.json").exists(),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("evidence:", OUT)
    print("current nominal:", result["totals"]["splits"])
    print("manhole images per split:", result["manhole_drop"]["manhole_images_per_split"])
    print("valid labels lost:", lost)
    print("effective images:", {sp: result["effective_after_manhole_drop"][sp]["images"] for sp in splits})
    print("spanning dates:", spanning)
    print("unknown-date images:", len(unknown_dates))
    for name, p in props.items():
        print(f"{name}: nominal={ {sp: p['nominal'][sp]['images'] for sp in ('train','val','test')} } "
              f"effective={ {sp: p['effective_after_manhole_drop'][sp]['images'] for sp in ('train','val','test')} } "
              f"quarantined={p.get('quarantined_images')}")
    print("duplicate groups:", result["duplicate_groups"]["count"],
          "crossing:", result["duplicate_groups"]["crosses_split_count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
