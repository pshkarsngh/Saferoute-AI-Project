# SafeRoute AI — PHASE 24C: Derived Two-Class Dataset Construction

> **Phase:** PHASE_24C — build and validate the approved derived dataset
> **Date executed:** 2026-10-16
> **Mode:** Creates **new derived artifacts only**. No original dataset, annotation, split,
> configuration or checkpoint was modified. **No training, fine-tuning, checkpoint evaluation or
> model promotion was performed.**
> **Governing rules:** `master_rules.md` Rules 1, 5, 9, 14, 15, 17, 18, 20.
> **Specification:** [`PHASE_24B_DATASET_CLEANING_PROPOSAL.md`](PHASE_24B_DATASET_CLEANING_PROPOSAL.md)

Evidence labels: **VERIFIED** (measured this phase) · **PARTIALLY VERIFIED** · **BLOCKED**.

---

## 1. Executive summary

Implemented the six approved PHASE 24B decisions and built the derived dataset:

- **D1 (M1)** — derived **two-class** dataset (`0 pothole`, `1 crack`); the manhole class (2) is
  removed **only** in the derived labels. Originals preserved.
- **D2 (P-B)** — **date-atomic** split; the **212** images with no determinable capture date are
  **quarantined**.
- **D3** — the single **zero-area** annotation is excluded **only** in the derived dataset.
- **D4** — **one image kept per exact-duplicate group** (5 exclusions), all recorded in a manifest.
- **D5** — **DATA-YOLO** and **RDD2022** were **not touched**.
- **D6** — new artifacts in **separate paths** plus a **reproducibility manifest with source hashes**.

**Result (VERIFIED):** 1,792 derived images across train / val / test = **1,398 / 178 / 216**,
with **3,420** boxes (`pothole 1,166`, `crack 2,254`). All structural validations pass, including
**"no capture date spans more than one split."** Ultralytics' `check_det_dataset` accepts the new
`data/dataset_v2.yaml`. Source hashes are **unchanged** after generation.

**Not done (by instruction):** no training, no evaluation, no checkpoint work, no model promotion,
no commit/push. A fresh test evaluation is required before any future comparison (Rule 14) and
must be separately approved.

---

## 2. Pre-flight (rules + state preservation)

- Re-read `master_rules.md`; relevant rules: 1 (workspace isolation), 5 (honest classes),
  9 (missing ≠ safe), 14 (honest metrics), 15 (dataset integrity / no silent changes),
  17 (documentation), 18 (minimal changes), 20 (honest demonstration).
- `git status` before work: only the untracked Phase 24A/24B files were present; **no tracked
  file modified**. HEAD = `5645dcb`.
- All existing user changes preserved; nothing reset, cleaned, stashed or overwritten.

**Pre-work source hashes (recorded, re-checked after generation):**

| Source | SHA-256 |
|---|---|
| `data/dataset.yaml` | `CD502CDC…E5969E` |
| `data/splits/train.txt` | `47042901…29800C` |
| `data/splits/val.txt` | `13D992B1…48B215` |
| `data/splits/test.txt` | `46F647E0…42CA51` |

---

## 3. What was created (all NEW, separate paths)

| Path | Type | Purpose |
|---|---|---|
| `data/derived_2class/` | dir | derived dataset root |
| `data/derived_2class/images/` | **directory junction** | exposes the **original** images (`…/data/images`) — no bytes copied, originals untouched |
| `data/derived_2class/labels/` | dir (1,792 files) | derived two-class YOLO labels (classes 0/1 only) |
| `data/derived_2class/MANIFEST.json` | file | reproducibility manifest: source hashes, split rule, exclusions, validation, artifact hashes |
| `data/derived_2class/README.md` | file | derived-dataset notes + limitations |
| `data/dataset_v2.yaml` | file | **new** dataset config (original `data/dataset.yaml` untouched) |
| `data/splits_v2/train.txt`, `val.txt`, `test.txt` | files | derived split files |
| `data/splits_v2/quarantined.txt` | file | the 212 quarantined images |
| `data/splits_v2/split_manifest.csv` | file | per-image manifest (split, date, counts, decisions, image hash) |
| `data/splits_v2/SPLIT_NOTES.md` | file | split rule + limitations |
| `scripts/build_derived_dataset_v2.py` | file | the generator (read-only w.r.t. originals) |

**No original path was written.** `data/pothole_crack_manhole/**`, `data/splits/**`,
`data/dataset.yaml`, `config/**`, `models/**`, `logs/**`, `weights/**` are untouched (verified —
§7).

---

## 4. Method

The generator (`scripts/build_derived_dataset_v2.py`) performs, for each of the 2,009 source
images:

1. **Capture date** from the filename, normalized to `YYYY-MM-DD`
   (`vlcsnap-2025-02-18-…` and `20250218_…` both → `2025-02-18`). Undeterminable → `UNKNOWN`.
2. **Split (P-B):** `2025-02-18`,`2025-02-19` → train; `2025-03-16`,`2025-02-23`,`2025-02-16` →
   val; `2025-02-26` → test; **no date → quarantine**.
3. **Exact duplicates:** group by image SHA-256; keep the lexicographically-first member; exclude
   the others (recorded).
4. **Derived label:** keep only rows with class ∈ {0,1}; drop class-2 (manhole) rows; drop
   zero-area rows. Original labels are never written.
5. Write split files (absolute paths to `data/derived_2class/images/*.jpg`), the per-image
   manifest CSV, `dataset_v2.yaml`, and the reproducibility manifest.
6. Validate (pairing, class ids, boxes, split separation, date-atomicity, distributions) and
   re-verify source hashes.

---

## 5. Results

### 5.1 Derived split sizes and class distributions (VERIFIED)

| Split | Images | pothole boxes | crack boxes | images w/ pothole | images w/ crack |
|---|---|---|---|---|---|
| train | **1,398** | 893 | 1,662 | — | — |
| val | **178** | 175 | 300 | — | — |
| test | **216** | 98 | 292 | — | — |
| **derived total** | **1,792** | **1,166** | **2,254** | 723 | 1,190 |
| quarantined | 212 | (excluded) | (excluded) | — | — |
| excluded duplicates | 5 | (excluded) | (excluded) | — | — |
| source | 2,009 | 1,261 | 2,519 | — | — |

- **957 manhole boxes removed** across the derived labels.
- **336 derived images have empty labels** (their only boxes were manholes) → they act as
  **background** images (YOLO convention), deliberately retained per M1.
- **360 pothole/crack boxes** (95 pothole, 265 crack) sit in the 217 excluded images
  (212 quarantined + 5 duplicates) and are intentionally not in the derived splits.

### 5.2 Validation checks (VERIFIED, all pass)

From `MANIFEST.json → validation.checks`:

| Check | Result |
|---|---|
| Every kept image has an image file and a derived label | **PASS** (`missing_count = 0`) |
| Derived class ids ⊆ {0,1} | **PASS** |
| Derived boxes within valid range (0≤x,y≤1; 0<w,h≤1) | **PASS** |
| Derived zero-area boxes | **0** |
| No stem appears in more than one split | **PASS** |
| No split image is quarantined | **PASS** |
| **No capture date spans more than one split** | **PASS** |
| Dates present | `2025-02-16, 02-18, 02-19, 02-23, 02-26, 03-16` |
| Manhole boxes removed | 957 |
| Zero-area rows dropped | 1 |

Independent re-check: derived labels = 1,792 files; split line counts = 1,398 / 178 / 216 /
quarantine 212; `Select-String` for `^2 ` in derived labels → **0**; for zero-area → **0**.

### 5.3 D3 (zero-area) nuance — VERIFIED, documented

The **only** zero-area image is `vlcsnap-00058`, which has **no determinable capture date**
(`vlcsnap-00058.jpg`) and is therefore **quarantined**. Consequence: the zero-area row is dropped
by the generator's label logic **and** the image is absent from the derived splits anyway —
so the derived splits contain no zero-area box either way. **The original
`labels-YOLO/vlcsnap-00058.txt` still contains the zero-height row** (verified unchanged):

```
1 0.578125 0.718055 0.125000 0.136111
1 0.639062 0.786111 0.003125 0.000000   <- zero height, preserved in the ORIGINAL
2 0.659375 0.655555 0.128124 0.066667
```

### 5.4 D4 duplicate exclusions — VERIFIED

`MANIFEST.json → exclusions.exact_duplicate_extras`:

| Excluded | Kept (reference) |
|---|---|
| `vlcsnap-2025-02-18-17h04m14s457` | `vlcsnap-2025-02-18-17h03m41s574` |
| `vlcsnap-2025-02-18-18h30m17s408` | `vlcsnap-2025-02-18-17h11m34s646` |
| `vlcsnap-2025-02-19-14h41m49s395` | `vlcsnap-2025-02-19-14h41m29s105` |
| `vlcsnap-2025-02-19-15h03m10s511` | `vlcsnap-2025-02-19-15h02m56s842` |
| `vlcsnap-2025-02-26-20h36m04s054` | `vlcsnap-2025-02-26-20h36m03s983` |

(4 exclusions fall in train, 1 in test under the P-B date rule.)

### 5.5 Dataset-loader acceptance (VERIFIED)

`ultralytics.data.utils.check_det_dataset("data/dataset_v2.yaml")` returned
`names = {0: 'pothole', 1: 'crack'}` and resolved train/val/test to
`data/splits_v2/*.txt`. This is a **path/config** check only — it did **not** scan images, load a
model or train (no cache file was produced).

---

## 6. Reproducibility manifest (source hashes)

`data/derived_2class/MANIFEST.json` records (excerpt):

| Item | SHA-256 / value |
|---|---|
| generator script | `B68F04C0…CFB539` |
| source `README.md` | `49B98FBC…3B013F0A` |
| source `annotations_coco.json` | `9F5E7FC0…A584F367` |
| source `dataset.yaml` | `CD502CDC…E5969E` |
| source splits (train/val/test) | `47042901…` / `13D992B1…` / `46F647E0…` |
| source `labels-YOLO` Merkle (2,009 files) | `B3446313…03825F` |
| source polygon `labels` Merkle (2,009 files) | `9E5DFC3F…14A2D4E` |
| source `images` Merkle (2,009 files) | `78A84E52…2A048F2` |
| derived `dataset_v2.yaml` | `98EDD97A…D62C1912` |
| derived splits (train/val/test) | `3DC10C15…` / `37D92842…` / `AABA32AB…` |
| derived `split_manifest.csv` | `05E71172…AA36202` |
| derived labels Merkle (1,792 files) | `0C15D6AF…01158142` |

**Source integrity after generation:** `labels-YOLO` unchanged = **true**, `images` unchanged =
**true**, `dataset.yaml` unchanged = **true**.

---

## 7. Limitations (honest) and flags

1. **Filename-derived dates (flagged, as required).** Split membership depends on the capture
   date inferred from the filename. `vlcsnap-*` timestamps may be *screenshot wall-clock*, not
   video content time, so two files sharing a date are **assumed** to be one session — a
   defensible proxy, **not a verified session identity**. Everything downstream inherits this
   assumption.
2. **212 images quarantined** with undeterminable sessions (`vlcsnap-NNNNN.jpg`); they are unused
   and cannot be proven disjoint from the splits.
3. **Metrics are not comparable to PHASE_09.** Membership changed, so test mAP@0.5 = 0.2615
   (computed over 125 effectively-used images) does **not** transfer. A fresh single test
   evaluation is required (Rule 14) — **not performed here**.
4. **Images are exposed via a junction** to the original folder; hash/dedup evidence refers to
   the original bytes. If the derived tree is moved off the same volume, the junction must be
   recreated.
5. **336 background-only images** — retained per M1; they contribute no positives. This is a
   deliberate choice to be confirmed at training time.
6. **DATA-YOLO / RDD2022 excluded** (§8).
7. **Pre-existing absolute-path style** is used in `dataset_v2.yaml` and split files (matching the
   original), so the workspace path is baked in (pre-existing limitation, documented).

---

## 8. DATA-YOLO / RDD2022 (D5) — untouched

| Source | Status | Blocker |
|---|---|---|
| `DATA-YOLO/` (~7.4 GB) | **not touched** | provenance + licence unresolved |
| RDD2022 (`data/raw/RDD2022`) | **not touched** | licence conflict (CC BY 4.0 vs CC BY-SA 4.0) + no VOC→YOLO conversion |

Both remain out of scope (Rule 15 / Rule 19).

---

## 9. Commands and scripts used

| # | Command | Purpose | Exit |
|---|---|---|---|
| 1 | `git status --short` / `git log --oneline -1` | state + preservation | 0 |
| 2 | `.\.venv\Scripts\python.exe scripts\build_derived_dataset_v2.py` | build + validate derived dataset | 0 |
| 3 | `.\.venv\Scripts\python.exe -c "check_det_dataset('data/dataset_v2.yaml')"` | config/path acceptance (no model, no train) | 0 |
| 4 | PowerShell `Get-ChildItem` / `Select-String` / `Get-FileHash` | independent artifact verification | 0 |

**Not run (by instruction):** `scripts/train_baseline.py`, `scripts/evaluate_baseline.py`, any
checkpoint load/eval, the unit/integration test suite (no source code changed). No download, no
package install.

---

## 10. Files changed and final Git status

**Created this phase (all new, untracked):**
```
scripts/build_derived_dataset_v2.py
data/dataset_v2.yaml
data/derived_2class/            (images junction, labels/, MANIFEST.json, README.md)
data/splits_v2/                 (train.txt, val.txt, test.txt, quarantined.txt,
                                 split_manifest.csv, SPLIT_NOTES.md)
docs/reports/PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md
```

**Final `git status --short`:**
```
?? docs/reports/PHASE_24A_DATASET_AUDIT.md
?? docs/reports/PHASE_24B_DATASET_CLEANING_PROPOSAL.md
?? docs/reports/PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md
?? docs/reports/PHASE_24_BASELINE_AUDIT.md
?? reports/phase24a/
?? reports/phase24b/
?? scripts/audit/phase24a_dataset_audit.py
?? scripts/audit/phase24a_session_leakage.py
?? scripts/audit/phase24b_split_proposal.py
?? scripts/build_derived_dataset_v2.py
?? data/dataset_v2.yaml
?? data/derived_2class/
?? data/splits_v2/
```

**Modified:** none (0 tracked files changed). **Checkpoints unchanged:** v1
`61F6EDA2…78E65`, v2 `B6354A56…8800BA`. Nothing committed or pushed.

---

## 11. Next step (requires separate approval)

Requested separately, **not performed**:

1. **Fresh evaluation (Rule 14):** one test evaluation of the **v1 serving checkpoint** on the
   new holdout (`data/dataset_v2.yaml`, test = 216 images) to establish a new comparable baseline,
   and a matching evaluation of **v2** on the same holdout.
2. Only after that, consider policy/training changes.

**Stop point honored.** No dataset change to originals, no training, no evaluation, no promotion,
no commit. Awaiting explicit approval before any model evaluation or training.
