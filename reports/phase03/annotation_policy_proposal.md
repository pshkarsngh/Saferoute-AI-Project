# PHASE_03 — Annotation Handling Policy Proposal (derived labels only)

> **Status:** PROPOSAL — awaiting review. **No labels were altered or generated.**
> **Date (actual):** 2026-10-12
> **Workspace:** `D:\New folder (3)`
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) (Rules 6, 15, 18, 19) ·
> [`../phases/PHASE_03.md`](../phases/PHASE_03.md)
> **Applies to:** any future **derived** training labels (YOLO / COCO). The original dataset
> files in `data/pothole_crack_manhole/data/labels/` and `.../labels-YOLO/` are **read-only
> and must never be modified**.

---

## 1. Why a policy is needed

The PHASE_03 audit found small annotation anomalies that are **conversion/rounding artefacts**
at object edges, not corruption. They must be handled deterministically before the dataset is
used for training, without silently relabelling or discarding data (Rule 15).

### 1.1 Measured inventory (re-verified read-only)

| Anomaly | Count | Magnitude | Class breakdown |
|---|---|---|---|
| Derived YOLO box edge beyond `[0,1]` | 63 | max 0.01562 norm ≈ 10.0 px (x) / 5.6 px (y) | crack 51 · manhole 8 · pothole 4 |
| Polygon vertices outside `[0,1]` | 45 lines | max 0.01562 norm | follows the same objects |
| Zero-size derived YOLO box (`w≤0` or `h≤0`) | 1 | `h = 0.000000` | **crack** |
| Zero-extent polygon object | 1 | zero area | **crack** (same object) |
| COCO boxes beyond image bounds | 45 (+1 zero-size) | ≤ ~10 px | same objects |

Notes:
- Of the 63 beyond-bounds boxes, **18 are floating-point boundary cases** (edge within ~1e-6
  of 1.0) and 45 reflect the polygon out-of-range set. Files involved: **60 unique**.
- **Class attribution correction:** the existing completion report (`docs/reports/PHASE_03_report.md`
  § C) states the zero-size box is "object class 2 (manhole)". The file shows it is
  **class 1 (crack)**. The report should be corrected (not modified in this task).

### 1.2 The zero-area object (exact)

```
labels-YOLO/vlcsnap-00058.txt  line 2:
  1 0.639062 0.786111 0.003125 0.000000        # class 1 (crack), h = 0

labels/vlcsnap-00058.txt       line 2:
  1 0.637500 0.786111 0.640625 0.786111 0.640625 0.786111 0.637500 0.786111
  # all four vertices collinear at y = 0.786111 -> zero area (a horizontal segment)
```

This object cannot define a trainable box and is a degenerate annotation.

---

## 2. Proposed policy

### P1 — Clip geometrically justified edge overshoots in **derived** labels
For derived-label generation only:
1. Clip polygon/derived coordinates to `[0,1]` **only** when the object is genuinely at the
   image border (a vertex or box edge reaches/oversteps the frame) **and** the overshoot is
   within the documented bound (**≤ 0.01562 norm ≈ 10 px**), which covers the entire observed
   population.
2. Recompute the axis-aligned box `(cx, cy, w, h)` from the clipped corners.
3. Keep the object only if `w > 0` and `h > 0` after clipping.
4. If any overshoot exceeds the documented bound, **exclude and disclose** rather than clamp
   (never silently enlarge/clamp beyond the bound).
5. Apply the same rule consistently to derived YOLO and derived COCO boxes.
6. This is a **geometry/rounding correction, not a class relabel** (Rule 15 satisfied).

### P2 — Exclude the zero-area object from training annotations
- Exclude the single zero-area crack object (`vlcsnap-00058.txt`, line 2) from derived
  training labels. It cannot produce a valid box.
- **Do not relabel** it and **do not delete** the source file.
- Record it in an explicit **exclusion list** (`file`, `line`, `class`, `reason`).

### P3 — Preserve originals
- `data/pothole_crack_manhole/data/labels/` and `.../labels-YOLO/` remain byte-identical
  (verified: archive MD5 unchanged `317862054545467FF00BE611DB8FF07E`).
- Any derived labels must be written to a **new, separate** location — never over the
  originals.

### P4 — Disclosure & reproducibility
- Publish for any derived-label run: clip counts, class breakdown, max magnitude, the full
  per-file clip list, the exclusion list, and before/after box counts.
- Record that clipping affected only edge geometry; no object was added, removed (except the
  one excluded zero-area object) or relabelled.

### P5 — Scope interaction
- Class 2 (manhole) is out of detector scope and excluded (never relabelled). The 8 manhole
  overshoots are therefore moot for the current pothole+crack detector, but P1 still applies
  if manhole labels are ever derived for other purposes.

### P6 — Post-generation validation (when derived labels are produced)
- Assert all derived boxes satisfy `0 ≤ x1 < x2 ≤ 1`, `0 ≤ y1 < y2 ≤ 1` (i.e. `w>0`, `h>0`).
- Assert expected counts. Expected **in-scope** totals after this policy:
  pothole **1,261** · crack **2,518** (2,519 − 1 excluded zero-area object) = **3,779** boxes;
  manhole excluded from the detector.

---

## 3. What this task does NOT do

- Does **not** modify any source label.
- Does **not** generate any derived training label.
- Does **not** apply P1/P2 to the dataset (they are proposals).

---

## 4. Decisions requested

1. Approve P1 (clip rule, bound, exclude-if-exceeds) as stated, or amend.
2. Approve P2 (exclude the zero-area crack object; keep original) as stated, or amend.
3. Confirm P3–P6.
4. Optional: authorise generation of the **per-file clip list + exclusion list** now
   (a manifest only, not derived labels).
5. Optional: authorise correction of the class-attribution typo in the completion report
   (§ C: zero-size box is crack, not manhole).
