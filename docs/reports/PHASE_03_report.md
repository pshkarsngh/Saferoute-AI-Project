# SafeRoute AI — PHASE_03 Completion Report

> **Phase:** PHASE_03 — Dataset Integrity, Class-Mapping & Split Audit
> **Status:** **COMPLETE** (audit + artefacts delivered; Gates A4 and the split policy were
> **decided by the user 2026-10-12** — see § G; G8/G9 evidence recorded, training still blocked)
> **Date (actual):** 2026-10-12 (audit generated 2026-10-11T19:14:11Z)
> **Workspace:** `D:\New folder (3)`
> **Record location:** `docs\reports\PHASE_03_report.md`
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) ·
> [`../phases/PHASE_03.md`](../phases/PHASE_03.md) ·
> [`../TRAINING_RULES.md`](../TRAINING_RULES.md) · [`../TRD.md`](../TRD.md)
> **Predecessor:** PHASE_02 — COMPLETE ([`PHASE_02_report.md`](./PHASE_02_report.md))
> **Next phase (PHASE_04) authorised?** **NO — awaiting review.**

This audit was **read-only**. No dataset file was modified, no split directories were
created, no packages were installed, and no training was started. The original archive MD5
is unchanged (`317862054545467FF00BE611DB8FF07E`).

---

## A. Approval / gate record

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| A1 | User approves starting PHASE_03 | **PASS** | "AUTHORIZE PHASE_03 ONLY" (2026-10-12) |
| A2 | User approves any audit script before it runs | **PASS** | User selected "Approve as specified" for the read-only script |
| A3 | Any correction (relabel/delete/re-split/dedupe) needs separate approval | **N/A** | No correction performed (read-only) |
| A4 | User accepts the class-ID mapping proposal | **PASS** | **Confirmed 2026-10-12** — pothole/crack supported; manhole → `unsupported`, never relabelled (see `reports/phase03/PHASE_03_followup_decision_record.md` § A) |

**Audit tooling (approved):** `D:\New folder (3)\scripts\audit\phase03_dataset_audit.py`
(Python 3.12.10, numpy 2.5.3, cv2 5.0.0; read-only; writes only under `reports\phase03\`).
Supplementary leakage analyses were read-only and are listed in § I.

**Commands used (exact):**
```
py -3.12 -c "import sys, numpy, cv2; print('python', sys.version.split()[0]); print('numpy', numpy.__version__); print('cv2', cv2.__version__)"
py -3.12 "D:\New folder (3)\scripts\audit\phase03_dataset_audit.py"
py -3.12 -   # supplementary read-only analyses (overshoot magnitudes, source families, session gaps, date/class distribution, polygon reconciliation)
Get-FileHash 'D:\New folder (3)\data\raw\data.zip' -Algorithm MD5
```

**Generated artefacts (inside workspace):**
- `reports\phase03\dataset_audit_report.md` (human-readable)
- `reports\phase03\dataset_audit.json` (machine-readable, full detail)
- `reports\phase03\class_mapping_proposal.md`
- `reports\phase03\split_manifest_proposal.csv` (content-group-aware)
- `reports\phase03\split_manifest_proposal_sessionaware.csv` (session-aware; recommended)
- this report: `docs\reports\PHASE_03_report.md`

---

## B. PHASE_03 — Dataset Integrity Audit Report (§11 template, filled)

```
PHASE_03 — Dataset Integrity Audit Report
=========================================
Date (actual):          2026-10-12
Dataset path:           D:\New folder (3)\data\pothole_crack_manhole\data
Audit sampled?          all images (2,009) — no sampling

1. Counts
   - train images/labels: 0/0   (no train split exists)
   - val   images/labels: 0/0   (no val split exists)
   - test  images/labels: 0/0   (no test split exists)
   - total:               2,009 images / 2,009 labels-YOLO / 2,009 polygon labels
                           (single pool; source provides no split)

2. Pairing
   - images without YOLO label: 0
   - YOLO labels without image: 0
   - images without polygon label: 0
   - polygon labels without image: 0

3. Decode
   - decoded ok:  2,009 / 2,009
   - failures:    0
   - dimensions:  all 640x360

4. Annotations
   - malformed YOLO lines: 0
   - out-of-range YOLO values (cx,cy,w,h outside [0,1]): 0
   - zero-size YOLO boxes (w<=0 or h<=0): 1
   - derived-box edges beyond image bounds: 63 (max overshoot 0.01562 norm ~= 10 px)
   - malformed polygon lines: 0
   - polygon vertices outside [0,1]: 45 lines (max overshoot 0.01562)
   - zero-extent polygon objects: 1
   - invalid class IDs (YOLO / polygon): 0 / 0

5. Actual format & class IDs
   - format:  YOLO txt (labels-YOLO/) + normalized polygon txt (labels/) + COCO JSON
   - IDs found (boxes): 0: 1261, 1: 2519, 2: 957  (total 4,737)
   - names provenance: bundled README.md and COCO categories {0:pothole, 1:crack, 2:manhole}

6. Class mapping proposal (actual ID -> SafeRoute class)
   id | actual name | proposed SafeRoute class              | supported? | boxes
   0  | pothole     | pothole                               | yes        | 1261
   1  | crack       | crack                                 | yes        | 2519
   2  | manhole     | unsupported (excluded; NEVER relabelled) | no      | 957
   Project target classes with 0 instances (NOT covered): damaged_patch, waterlogging,
   uneven_surface, speed_bump, other.  Initial detector scope: pothole + crack ONLY.

7. Empty labels
   - images with 0 objects: 0

8. Duplicates / near-duplicates
   - exact byte-identical groups: 5 (10 images)
   - content groups (exact + dHash<=5 + <=2s session): 118 multi-image groups, 356 images
   - session-aware groups (exact + dHash<=5 + <=5s session): 240 multi-image groups,
     1,592 images, largest group 59

9. Split integrity & leakage
   - policy: not documented by source (single pool of 2,009)
   - source splits present: none
   - leakage found (cross-split): n/a (no source splits)
   - POTENTIAL leakage: HIGH — 1,907/2,009 (94.9%) are video frames (vlcsnap-*),
     median inter-frame gap 2 s, concentrated on 2 capture days

10. Test isolation
   - test used for training/selection? No (nothing trained). Proposed split isolates groups.

11. Path safety
   - references outside approved location: none
   - unsafe COCO file names (absolute / ..): 0

12. Files modified
   - none (audit is read-only; archive MD5 unchanged)

13. Validation results
   V1  PASS  counts recorded (2,009 / 2,009 / 2,009; no splits present)
   V2  PASS  pairing complete (0 unpaired images, 0 orphan labels)
   V3  PASS  all 2,009 images decode; 0 failures
   V4  PASS  no malformed lines; anomalies enumerated (1 zero-size box; 63 edge
             overshoots; 45 polygon out-of-range; 1 zero-extent polygon) — policy pending
   V5  PASS  actual IDs recorded; proposal maps each to a SafeRoute class or "unsupported"
   V6  PASS  per-class box and image counts recorded
   V7  PASS  duplicate / near-duplicate findings recorded
   V8  PASS  no source splits; potential leakage assessed (content + session grouping)
   V9  PASS  proposed test set isolated by group; no training performed
   V10 PASS  no reference resolves outside D:\New folder (3)
   V11 PASS  no dataset file modified (archive MD5 unchanged)

14. Gate status
   G3 PASS  G4 PASS  G5 PASS  G6 PASS  G7 PASS  G8 PASS*  G9 PASS*
   (* G8/G9: leakage checked, decisions recorded 2026-10-12 — whole-capture-day holdout
   (test = 2025-02-26); residual disclosed, split NOT leakage-free; see § G)

15. Limitations / honesty note
   - Report is a coverage/integrity audit only; it does NOT assert annotation correctness,
     balance, or real-world adequacy.
   - Class coverage is partial: only pothole & crack are supported; manhole is unsupported;
     5 target classes are entirely absent.
   - Leakage cannot be fully eliminated from filenames alone (see § D).
   - Anomaly handling policy APPROVED 2026-10-12 (P1–P6; clip ≤0.01562, exclude-and-disclose above;
     exclusions recorded); applied only in future derived labels.

16. Result: COMPLETE
    Next phase authorised? NO (awaiting explicit PHASE_04 authorisation; A4 + split policy decided 2026-10-12, training still blocked)
```

---

## C. Annotation anomaly detail (measured)

| Anomaly | Count | Magnitude | Notes |
|---|---|---|---|
| Malformed YOLO/polygon lines | 0 | — | all lines parse as 5 / 9 tokens |
| Values outside `[0,1]` (YOLO) | 0 | — | `cx,cy,w,h` all in range |
| Zero-size YOLO box | 1 | `h = 0.000000` | zero-area crack object in `vlcsnap-00058.txt`; excluded from future derived training labels because it cannot produce a valid bounding box; original annotation preserved; cracks remain in scope for the initial detector |
| Derived YOLO box edge beyond image | 63 | ≤ 0.01562 norm (≈10 px) | polygon→axis-aligned bbox rounding at edges |
| Polygon vertices outside `[0,1]` | 45 lines | ≤ 0.01562 | same rounding source |
| Zero-extent polygon object | 1 | zero area | matches the single degenerate box |
| COCO boxes beyond image bounds | 45 (+1 zero-size) | ≤ 10 px | conversion rounding; consistent with YOLO anomalies |

None of these are corruption; they are conversion/rounding artefacts at object edges.
**No correction was made.** A documented handling policy (e.g. clamp or drop, with
disclosure) is required before training — **open decision, not part of this phase.**

---

## D. Duplicates & leakage (measured)

**Source composition**
- Total images: 2,009. **`vlcsnap-*` video frames: 1,907 (94.9%)**; camera photos
  (`YYYYMMDD_HHMMSS`): 102. Of the `vlcsnap` frames, 1,559 carry a timestamp
  (`vlcsnap-YYYY-MM-DD-HHhMMmSSs…`); 348 are numerically named (`vlcsnap-00001…`) with
  **no timestamp**.
- Capture days (timestamped): 2025-02-16 (3), 2025-02-18 (581), 2025-02-19 (821),
  2025-02-23 (39), 2025-02-26 (217); 348 frames have no date.

**Duplicates**
- Exact byte-identical (SHA-256): **5 groups / 10 images**, e.g.
  `vlcsnap-2025-02-19-14h41m29s105.jpg` ≡ `…14h41m49s395.jpg` (20 s apart),
  `vlcsnap-2025-02-26-20h36m03s983.jpg` ≡ `…20h36m04s054.jpg`.
- Near-duplicate (64-bit dHash, Hamming ≤ 5): 117 multi-image groups / 354 images.
- Session union (≤ 5 s, same source stream): 240 multi-image groups / 1,592 images
  (largest 59) — i.e. **most video frames belong to small same-scene bursts.**

**Leakage assessment**
- Median inter-frame gap is **2 s**; many frames are consecutive video frames of the same
  road pass. A naive random split would place near-identical / same-scene frames in both
  train and test → **severe leakage**.
- Content-hash grouping alone (117 groups) **under-captures** the problem; session grouping
  is required. The proposed split therefore keeps **whole content/session groups intact**.
- **Residual risk (stated honestly):** source session/video identity is *not* recoverable
  from filenames with certainty (348 frames have no timestamp; a day can contain multiple
  passes and one pass can span groups). Residual leakage cannot be reduced to zero from the
  available metadata alone.

---

## E. Proposed splits (NOT created on disk)

Two read-only proposals were generated; **neither creates directories or moves files**.

| Proposal | Grouping | train / val / test (images) | pothole boxes | crack boxes | manhole boxes |
|---|---|---|---|---|---|
| `split_manifest_proposal.csv` (baseline) | exact + dHash ≤ 5 + ≤ 2 s | 1,406 / 402 / 201 | 863 / 264 / 134 | 1,741 / 537 / 241 | 697 / 172 / 88 |
| **`split_manifest_proposal_sessionaware.csv` (recommended)** | exact + dHash ≤ 5 + ≤ 5 s | **1,391 / 387 / 231** | 925 / 229 / 107 | 1,755 / 502 / 262 | 637 / 195 / 125 |

- Deterministic (`seed = 42`), group-aware at 70 / 20 / 10; per-image SHA-256, dHash, source
  family, capture time, group id and proposed split are recorded in the CSV manifests.
- **Stricter alternative (not computed):** hold out entire capture days for val/test (e.g.
  test = 2025-02-23, val = 2025-02-26). This gives stronger leakage isolation but leaves a
  very small, less representative test set (02-23: 39 images, 0 manhole).

**Recommended policy (requires your approval):** session/source-aware grouping as in the
session-aware manifest, with the final grouping threshold and the treatment of the 348
timestamp-less frames decided explicitly before PHASE_08. The initial detector remains
**pothole + crack only**; `manhole` is excluded, never relabelled.

---

## F. Class mapping proposal (Gate A4 — acceptance requested)

| id | actual | proposed SafeRoute class | supported? | boxes | images containing it |
|---|---|---|---|---|---|
| 0 | pothole | `pothole` | yes | 1,261 | 795 |
| 1 | crack | `crack` | yes | 2,519 | 1,375 |
| 2 | manhole | **`unsupported`** (excluded; **never** relabelled as pothole/crack) | no | 957 | 759 |

Target classes **not covered by this dataset (0 instances):** `damaged_patch`,
`waterlogging`, `uneven_surface`, `speed_bump`, `other`. They are reported as **absent** and
must not be claimed as detectable.

**Cross-format reconciliation (exact):** polygon objects 4,737 = YOLO boxes 4,737 =
COCO annotations 4,737; per class: pothole 1,261 · crack 2,519 · manhole 957 in all three.

---

## G. Decisions & remaining actions (status as of 2026-10-12)

1. **Gate A4 — CONFIRMED (2026-10-12).** pothole/crack supported; manhole → `unsupported`,
   never relabelled.
2. **Split policy — DECIDED (2026-10-12): whole-capture-day holdout**, untimed block co-located
   with 2025-03-16; **train 1,402 / val 390 / test 217** (test = 2025-02-26); ~0.8 % ratio
   deviation accepted; measured residual disclosed (session ≤300 s = 0; dHash test↔train
   ≤6 = 0, ≤8 = 5, ≤10 = 41 pairs; total dHash 6/8/10 = 7/66/298). **Not leakage-free.** Recorded
   in `reports/phase03/PHASE_03_followup_decision_record.md` § A.
3. **Anomaly-handling policy — APPROVED (2026-10-12)** P1–P6 (clip ≤ bound 0.01562; exclude-and-
   disclose above bound; zero-area + boundary exclusions recorded).
4. **Attribution (CC BY 4.0)** remains mandatory for any use of this dataset.
5. **Remaining before training (each needs its own approval):** generate derived labels under the
   approved policy (P1–P6); write the adopted day-holdout split manifest; then G10–G13 checks;
   then a separate training authorisation.

---

## H. Compliance / no-modification statement

- All operations stayed inside `D:\New folder (3)` (Rule 1).
- No dataset file was modified, moved, relabelled or deleted; dataset counts unchanged
  (2,009 images / 2,009 labels-YOLO / 2,009 polygon labels); archive MD5 unchanged
  (`317862054545467FF00BE611DB8FF07E`) (Rules 15, 18, 19; V11).
- No packages installed; no virtual environment created; no split directories created;
  no training started (Rules 3, 4, 19).
- Only new files created: the approved audit script and the report artefacts listed in § A.
- Read-only tooling used existing packages only (Python 3.12, numpy, cv2); no network use.

---

## I. Evidence appendix — supplementary read-only analyses

1. **Interpreter/packages:** Python 3.12.10, numpy 2.5.3, cv2 5.0.0 (`py -3.12`).
2. **Overshoot magnitudes** (read-only, dataset re-read): YOLO beyond-bounds = 63 lines,
   max 0.01562 norm; polygon out-of-range = 45 lines, max 0.01562; COCO beyond = 45 boxes,
   max 10.0 px (plus 1 zero-size box = the audit's 46 "bad bbox").
3. **Source families:** images 2,009 → `vlcsnap` 1,907 (timestamped 1,559; numeric 348),
   camera 102.
4. **Session gaps (vlcsnap):** min 0 s, median 2 s, p75 4 s, p90 11 s, p95 21 s.
5. **Grouping comparison:** base (exact+near) 1,772 groups / 117 multi / 354 images;
   session ≤5 s → 657 groups / 240 multi / 1,592 images (max 59); ≤30 s → 430 groups;
   ≤60 s → 408 groups (max 445, chaining).
6. **Capture-day class distribution** (timestamped [+ numeric]):
   `02-16` 3 imgs [ph 5, cr 12, mh 2]; `02-18` 581 [168, 897, 253]; `02-19` 821 [729, 773, 498];
   `02-23` 39 [105, 47, 0]; `02-26` 217 [98, 294, 115]; untimed 348 [156, 496, 89].
7. **Polygon reconciliation:** 2,009 files, 4,737 objects, per class {pothole 1261, crack
   2519, manhole 957}, 0 malformed.
