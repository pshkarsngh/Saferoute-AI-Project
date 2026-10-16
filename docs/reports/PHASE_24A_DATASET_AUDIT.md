# SafeRoute AI — PHASE 24A: Dataset Audit and Quality Verification

> **Phase:** PHASE_24A — Dataset audit and quality verification (audit-only)
> **Date executed:** 2026-10-16
> **Mode:** Read-only. No dataset, label, split, config, checkpoint or model weight was
> modified. No training, fine-tuning or dataset generation was started.
> **Governing rules:** `master_rules.md` Rules 1, 5, 14, 15, 17, 18, 20.
> **Predecessor:** [`PHASE_24_BASELINE_AUDIT.md`](PHASE_24_BASELINE_AUDIT.md)

Evidence labels used throughout: **VERIFIED** (measured in this phase from primary
artifacts) · **PARTIALLY VERIFIED** (some evidence locally measured, some prior-reported)
· **UNVERIFIED** (claimed but not independently confirmed here) · **BLOCKED** (could not be
checked; reason stated).

---

## 1. Executive summary

This phase performed the missing consolidated dataset audit promised by Phase 24
(baseline-audit risk **R1**). The required report now exists at
`docs/reports/PHASE_24A_DATASET_AUDIT.md`.

**What was re-measured (VERIFIED against primary artifacts):**

- The **active training dataset** `data/pothole_crack_manhole/data` contains exactly
  **2,009 images**, all with a YOLO label and a polygon label (0 pairing gaps). Totals match
  PHASE_03 historical figures.
- YOLO labels: **4,737 boxes**, classes `{0 pothole: 1,261, 1 crack: 2,519, 2 manhole: 957}`.
  All converged with the COCO file's **4,737 annotations** and **0 malformed lines**, **but**
  **one zero-area / out-of-range box** was found (`labels-YOLO/vlcsnap-00058.txt`).
- Splits on disk are **1,406 / 402 / 201** (train/val/test), all targets exist, and there is
  **no filename-stem overlap** between splits and **no cross-split exact duplicate** content.
- **Residual same-session leakage remains**: two capture dates
  (`20250219`, `20250223`) contribute images to **more than one split**. 5 exact-duplicate
  groups (10 files) all sit **within** a single split (3 train, 2 test) — i.e. they inflate
  within-split redundancy but do **not** leak across splits.
- **148 / 148 unit + integration tests pass** (exit 0), including
  `test_threshold_consistency`, confirming the PHASE_22 fix holds.
- The serving checkpoint `models/training/saferoute-yolo11-v1/weights/best.pt` hash
  **matches the PHASE_09 pin exactly** (`61F6EDA2…78E65`). Class mapping is consistent with
  `data/dataset.yaml` and `config/detection.yaml` (**VERIFIED**).

**Most important new findings (not in prior audits):**

1. **Undocumented, unlicensed, untracked `DATA-YOLO/` collection (~7.4 GB, ~57,000 images)**
   exists in the workspace, is git-ignored, and is referenced by **no** project document.
   It includes 2 annotated subsets (VOC/COCO/YOLO), 1 semantic-segmentation set, 1
   classification set, ~10 image-only sets and 8 archives. Provenance/licence are **UNVERIFIED**
   → **licensing blocker for any use**.
2. **Active dataset has no local `LICENSE`/licence text** — usage evidence is
   **PARTIALLY VERIFIED** (prior-reported CC BY 4.0 for Zenodo record 18528034; bundled README
   cites a *different, superseded* DOI `10.5281/zenodo.17834373`).
3. **RDD2022 extraction is incomplete** — `Norway.zip` is present but **not extracted**, so the
   on-disk RDD2022 tree has **6 of 7** countries (30,224 paired train images re-verified).
4. **One malformed zero-area annotation** in the active set (height = 0.0).
5. **`weights/yolo26n.pt`** (5.29 MB) is still present with **unknown provenance** (R4).

**Readiness decision:** the active dataset is **READY for the next phase (cleaning/hardening
*proposal*) but NOT ready to merge unvetted data**; RDD2022 is **usable only after conversion**;
`DATA-YOLO` is **BLOCKED pending provenance/licence resolution**. No training may start until
Phase 24B (dataset cleaning proposal) and explicit user approval.

---

## 2. Audit scope and methodology

**In scope**

| Dataset / artifact | Path | Purpose |
|---|---|---|
| Active training dataset | `data/pothole_crack_manhole/data` | YOLO11 baseline source |
| Active splits | `data/splits/{train,val,test}.txt` | Leakage / pairing |
| Dataset config | `data/dataset.yaml` | Class mapping |
| RDD2022 (raw) | `data/raw/RDD2022` | Candidate expansion |
| DATA-YOLO collection | `DATA-YOLO/` | Undocumented candidate data |
| Model artifacts | `models/training/**`, `weights/yolo26n.pt` | Provenance / metrics |

**Method**

- Read `master_rules.md`, `README.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`,
  `docs/TRAINING_RULES.md`, `docs/evaluation_plan.md`, `docs/reports/PHASE_24_BASELINE_AUDIT.md`
  and the PHASE_02/03/09/20/23B reports.
- Re-measured inventory, pairing, label integrity, exact duplicates (SHA-256), near-duplicates
  (OpenCV 8×8 dHash, Hamming ≤ 6), and split leakage with two reproducible read-only scripts
  (§13). No file under any dataset was written, moved, renamed or deleted.
- Re-ran the full test suite.
- Verified the serving checkpoint hash against the PHASE_09 pin.
- Cross-checked licensing claims against the reports (external verification was **not**
  re-executed — see §12).

Historical (PHASE_03) figures that this phase re-measured are labelled "re-verified"; figures
taken only from prior reports are labelled "prior-reported (historical)".

---

## 3. Dataset inventory

### 3.1 Active training dataset — VERIFIED

| Property | Value |
|---|---|
| Name | Road Damage Dataset: Potholes, Cracks, and Manholes |
| Exact path | `D:\New folder (3)\data\pothole_crack_manhole\data` |
| Images | **2,009** (all `.jpg`) |
| YOLO labels | **2,009** (`labels-YOLO/*.txt`) |
| Polygon labels | **2,009** (`labels/*.txt`, 4-point normalized quadrilaterals) |
| COCO file | `annotations_coco.json` — 2,009 images, 4,737 annotations, 3 categories |
| Annotation formats | YOLO boxes, polygon quadrilaterals, COCO JSON (all present) |
| Pairing | **complete** (0 missing both directions for YOLO and polygon) |
| Classes | `0 pothole`, `1 crack`, `2 manhole` |
| Splits | train **1,406**, val **402**, test **201** |
| Suitability | pothole ✓, crack ✓, manhole ✓ (present) — but manhole is **deliberately excluded** from the detector (unsupported, Rule 5) |
| Used for training? | **Yes** — trained `saferoute-yolo11-v1` (and v2) |
| Git tracking | Tracked (6,035 files under `data/`), excluding `data/raw/` and `data/imagery/` |

Measured counts converge three ways (images = YOLO files = polygon files; YOLO boxes = COCO
annotations = 4,737), indicating a consistent conversion pipeline.

### 3.2 RDD2022 (raw) — VERIFIED (partial extraction)

| Country | Train images | Train XML | Test images | Test XML |
|---|---|---|---|---|
| China_Drone | 2,401 | 2,401 | — | — |
| China_MotorBike | 1,977 | 1,977 | 500 | 0 (by design) |
| Czech | 2,829 | 2,829 | 709 | 0 |
| India | 7,706 | 7,706 | 1,959 | 0 |
| Japan | 10,506 | 10,506 | 2,627 | 0 |
| United_States | 4,805 | 4,805 | 1,200 | 0 |
| **Total (on disk)** | **30,224** | **30,224** | **6,995** | **0** |
| Norway | **0 (not extracted)** | — | — | — |

- Path: `data/raw/RDD2022/RDD2022`; format **Pascal VOC XML** + `label_map.pbtxt`
  (`D00/D10/D20/D40`).
- Train pairing: **perfect** (0 images without XML, 0 orphan XML).
- Test images have **no XML** (RDD2022 test annotations are withheld by the provider) → these
  test images are **not usable for supervised local evaluation** as-is.
- 7 `*.zip` archives present (including `Norway.zip`, unextracted).
- Used for training? **No** — audited only (PHASE_20). Not converted, merged or trained.
- Git tracking: **ignored** (`data/raw/` in `.gitignore`).

### 3.3 DATA-YOLO collection — VERIFIED inventory, UNVERIFIED provenance

Path: `DATA-YOLO` (git-ignored, referenced by **0** project documents). ~7.4 GB.

| Subdirectory | Files | Images | Annotation format (assessed) | Road-hazard relevance |
|---|---|---|---|---|
| `Datasets` | 7,678 | 3,554 | VOC XML (618) + YOLO `train/valid` labels + COCO JSON; also `classes/{cracks,good_road,open_manhole,pothole}` | Candidates present; mapping undocumented |
| `Datasets2` | 228 | 201 | VOC XML — **number-plate** detection (`Datacluster_number_plates`) | **Not road hazards** |
| `Road_crack` | 871 | 870 | semantic **image+mask** pairs (train/valid) | Requires conversion to detection |
| `Road_Condition_Dataset` | 1,819 | 1,819 | **classification** folders (blocked/Clean/Potholes/Smooth/traffic) | Classification only |
| `digital pollution (enhanced dataset2.2)` | 17,841 | 17,840 | image→image pairs (input/output) — enhancement | Not detection |
| `day light road images` | 14,607 | 14,607 | images only | No labels |
| `night time road images` | 16,960 | 16,960 | images only | No labels |
| `night_vision`, `rainy` | 678 / 300 | 678 / 300 | images only | No labels |
| `highway`, `mud_path`, `traffic_path`, `Fog` | — | — | images only | No labels |

- 8 `*.zip` archives (~7.07 GB) and one PDF (`Pushkar Singh Baghel.pdf`) at the root; the zips
  appear to duplicate the extracted folders (storage concern, not verified member-by-member).
- The `Datasets` subset has **3 observed label class IDs (0/1/2)** but **no local `data.yaml`**
  was found → the class-name mapping is **UNVERIFIED**.
- **No licence file, no provenance, no source URL** anywhere in the collection.
- Per Rule 19 and Rule 15, this data **must not** be converted, merged or trained on until
  provenance and licence are established and the user approves.

### 3.4 Model / training artifacts (see §9 for detail)

| Artifact | Path | Status |
|---|---|---|
| v1 serving checkpoint | `models/training/saferoute-yolo11-v1/weights/best.pt` | VERIFIED — hash matches pin |
| v2 checkpoint | `models/training/saferoute-yolo11-v2/weights/best.pt` | VERIFIED — exists, not test-evaluated |
| Stray weights | `weights/yolo26n.pt` | UNVERIFIED provenance (R4) |

---

## 4. Image and annotation integrity

### 4.1 Active dataset — VERIFIED

| Check | Result | Verdict |
|---|---|---|
| Image–YOLO label pairing | 0 images without label, 0 labels without image | VERIFIED PASS |
| Image–polygon label pairing | 0 / 0 | VERIFIED PASS |
| YOLO malformed lines | **0** | VERIFIED PASS |
| YOLO out-of-range / zero-area boxes | **1** | ⚠ VERIFIED FAIL (minor) |
| Empty label files | 0 | VERIFIED PASS |
| Polygon malformed lines | **0** | VERIFIED PASS |
| COCO bad image references | **0** | VERIFIED PASS |
| Class-vs-documented consistency | YOLO, COCO and README all agree: 0 pothole / 1 crack / 2 manhole | VERIFIED PASS |
| Undecodable images | 0 (all 2,009 decode via OpenCV) | VERIFIED PASS |

**The one defect** (`labels-YOLO/vlcsnap-00058.txt`):

```
1 0.639062 0.786111 0.003125 0.000000
```

Class `1` (crack) with **height `h = 0.000000`** → zero-area box. This is the sole
out-of-range/zero-area annotation among 4,737 boxes. It was **not** repaired (Rule 15;
audit-only). PHASE_20 recorded one `zero_area` box in **RDD2022**, so this active-dataset box
is a new observation — likely missed because PHASE_03's summary line "0 malformed" counted
format errors only, not geometric validity.

### 4.2 RDD2022 — VERIFIED (structural)

- 30,224 train images, 30,224 XML, 0 orphans, 0 images-without-XML (perfect pairing).
- XML parsing/class-mapping error taxonomy was performed in PHASE_20 (prior-reported:
  1 malformed `zero_area` box; `D40→pothole`, `D00/D10/D20→crack`). **Not fully re-parsed** in
  this phase (BLOCKED by scope/time: 30k XMLs) — relies on the PHASE_20 audit.

### 4.3 DATA-YOLO — PARTIALLY VERIFIED

- Annotations exist for `Datasets` (YOLO/VOC/COCO) and `Road_crack` (masks); the rest are
  image-only. Detailed per-file pairing and geometry validation was **not** performed
  (out of scope for an unapproved, unlicensed collection).

---

## 5. Class mappings and dataset compatibility

| Dataset | Native classes | Project mapping | Compatible? |
|---|---|---|---|
| Active | 0 pothole, 1 crack, 2 manhole | `0 pothole`, `1 crack`; manhole excluded → **exact match** to `data/dataset.yaml` and `config/detection.yaml` `SUPPORTED_CLASSES` | **VERIFIED YES** (for the 2 supported classes) |
| RDD2022 | D00/D10/D20/D40 (VOC) | PHASE_20 map: `D40→pothole(0)`, `D00/D10/D20→crack(1)` | Compatible **after conversion** (prior-reported) |
| DATA-YOLO `Datasets` | observed IDs 0/1/2; folder names cracks / good_road / open_manhole / pothole | Mapping **undocumented** (no `data.yaml`) | **UNVERIFIED — needs mapping validation** |
| DATA-YOLO `Road_crack` | semantic masks | Requires mask→box conversion | **Not directly usable** |
| DATA-YOLO `Road_Condition_Dataset` | classification labels | Requires bounding-box annotation | **Not directly usable** |
| DATA-YOLO image-only sets | none | — | **Not usable for detection** |

The detector's class contract (pothole/crack; manhole unsupported) is consistent across
`data/dataset.yaml`, `src/detection/detector.py` and `config/detection.yaml` — **VERIFIED**.

---

## 6. Duplicate-image analysis

**Method.** Exact duplicates by SHA-256 of file bytes; near-duplicates by OpenCV 8×8 dHash
with Hamming distance ≤ 6. Two independent scans were run: (a) a banded-bucket prefilter over
all 2,009 images, and (b) an **exhaustive in-session** scan (no bucket skipping).
**Limitation.** dHash with Hamming ≤ 6 is a heuristic; it can miss visually similar frames with
crop/scale changes and can rarely flag visually distinct frames. SHA-256 is exact for identical
bytes only.

### Active dataset — VERIFIED

| Metric | Result |
|---|---|
| Exact duplicate groups | **5** (10 files) |
| Near-duplicate pairs (dHash ≤ 6) | **153** (banded scan) |
| Undecodable images | 0 |

All 5 exact-duplicate groups are **within a single split** (3 groups in train, 2 in test) — e.g.
`vlcsnap-2025-02-18-17h03m41s574.jpg` = `vlcsnap-2025-02-18-17h04m14s457.jpg` (both train),
`vlcsnap-2025-02-19-15h02m56s842.jpg` = `vlcsnap-2025-02-19-15h03m10s511.jpg` (both test).
**No exact-duplicate pair crosses a split boundary.** This is a **minor redundancy** issue, not a
leakage issue.

### RDD2022 — prior-reported (historical)

PHASE_20 found 920 near-duplicate groups (and exact duplicates via `--hash`). Source: PHASE_20
duplicate scan. Not re-run here (BLOCKED: RDD2022 is unapproved/unconverted; no need to re-scan
before a conversion decision).

### DATA-YOLO — not evaluated (scope)

---

## 7. Train / validation / test leakage

### 7.1 Structural (VERIFIED)

- Split sizes: **train 1,406 / val 402 / test 201** (= 2,009 total, no gap or overlap).
- Every split target path exists on disk (0 missing).
- Filename-stem overlap between any two splits: **0**.
- Cross-split **exact** duplicate content groups: **0**.
- Cross-split **near**-duplicate pairs (both dHash scans): **0**.

So by filename, exact bytes and dHash content, the splits are **clean**.

### 7.2 Same-capture-session leakage (VERIFIED — residual risk)

Grouping images by capture date from the filename heuristic reveals **2 sessions spanning
multiple splits**:

| Session (date) | train | val | test | Total |
|---|---|---|---|---|
| `20250219` | 36 | 19 | 5 | 60 |
| `20250223` | 8 | 16 | 15 | 39 |

Images captured on the **same day** (likely the same drive/session) are distributed across
train, val and test. Even where individual frames are not near-duplicates (dHash > 6), frames
from one session are highly correlated (same road, weather, camera). This is the residual
leakage flagged by PHASE_03 and left open as risk **R6**.

- 1,907 of 2,009 images (94.9%) are `vlcsnap-*` **video frames**; 102 are timestamp-named
  (`20250216_/20250219_/20250223_...`). Video-frame corpora are inherently session-correlated.
- **The leakage is NOT proven absent** merely because filenames/splits do not overlap; the two
  spanning dates above are direct evidence of residual cross-split session mixing.

**Conclusion:** no *duplicate-level* leakage; **1,910 of 2,009 images (95.1%)** sit in
date-sessions confined to a single split, while **99 images** — those on the two spanning dates
(`20250219` = 60, `20250223` = 39) — carry same-session cross-split risk.

---

## 8. Licensing and provenance

| Dataset | Licence (claimed) | Local licence evidence | Verdict |
|---|---|---|---|
| Active (Road Damage Dataset) | **CC BY 4.0** (prior-reported for Zenodo record **18528034**) | **No** `LICENSE` file; `README.md` has no licence text; COCO `info/licenses` absent; README cites DOI **`17834373`** (superseded) | **PARTIALLY VERIFIED** — attribution mandatory; commercial use permitted by CC BY 4.0 *if* the prior-reported record attribution is correct |
| RDD2022 | FigShare record `21431547` filed **CC BY 4.0**; creators' sekilab README states **CC BY-SA 4.0** | No licence file in extracted tree or archives | **PARTIALLY VERIFIED** — project conservative policy adopts the **stricter CC BY-SA 4.0** (share-alike ⇒ derivative model/data redistribution constrained); attribution required |
| DATA-YOLO | **none** | No licence file, no source URL, no provenance anywhere in the tree | **BLOCKED / UNRESOLVED** — usage rights unknown |
| Mapillary imagery | CC-BY-SA 4.0 (hardcoded) | per-image licence/attribution not fetched (PHASE_23A) | **PARTIALLY VERIFIED** |

**Key provenance facts (VERIFIED):**

- Bundled dataset README (`data/pothole_crack_manhole/data/README.md`) cites
  `https://doi.org/10.5281/zenodo.17834373`. PHASE_02 reports identify the approved record as
  **`18528034`** (concept `17834372`). **These DOIs differ** and must not be conflated; the
  README DOI is **superseded/stale**. This was already documented in
  `PHASE_02_completion_report.md` and remains **open**.
- `README.md` states the data is "intended for object detection research and evaluation"; this
  alone does **not** constitute a licence.
- Archive identity: `data/raw/data.zip` SHA-256 =
  `C7B7247C611EFA0A12EB8B998583DA496F90C9B4859E9E1DE2C1B06ADBB80CEF` (matches
  `data/pothole_crack_manhole/data` structure: `images/`, `labels/`, `labels-YOLO/`,
  `annotations_coco.json`, README, 2 conversion scripts — no `LICENSE` member).
- **Rule 13:** no secrets found in any dataset/artifact inspected; nothing was written to logs.

The licence of a **research article** (DOI citation) is distinct from the licence of the
**dataset**; the project must not infer dataset permission from the citation. **No licensing
policy was changed in this phase.**

---

## 9. Existing model and training-artifact review

| Model | Path | Dataset/split used | Metrics | Provenance |
|---|---|---|---|---|
| **v1 (serving)** | `models/training/saferoute-yolo11-v1/weights/best.pt` | Active dataset (train/val = 1,406/402), **test evaluated once** | **VERIFIED** via PHASE_09 record + `results.csv`: test mAP@0.5 = **0.2615**; val mAP@0.5 = 0.2731 (PHASE_09) / best epoch 0.27821 | SHA-256 = `61F6EDA2…78E65` — **matches the PHASE_09 pin exactly** |
| **v2 (improved attempt)** | `models/training/saferoute-yolo11-v2/weights/best.pt` | Same active dataset; `config/training_improved.yaml` (150 ep, AdamW, cos_lr) | **VALIDATION only**: best mAP@0.5 = **0.28707** @ epoch 104 (final epoch 144 = 0.25516) | SHA-256 = `B6354A56…8800BA`; **never test-evaluated** (R3) |
| **Stray** | `weights/yolo26n.pt` | unknown | none | SHA-256 = `9B09CC8B…4FEF`; **provenance unknown** (R4) |

**Verified consistency checks**

- **Class mapping matches the inference pipeline:** `data/dataset.yaml` (`0 pothole, 1 crack`),
  `src/detection/detector.py` `SUPPORTED_CLASSES = {0: pothole, 1: crack}` and
  `config/detection.yaml` agree. Serving config still points at **v1** — **VERIFIED**.
- **Metrics reproducibility:** v1 metrics previously measured (PHASE_09) are reflected in the
  persisted `evaluation_record.json` and `results.csv`. Reproduction was **not** re-run here
  (no evaluation job was launched, per phase constraints) → **PARTIALLY VERIFIED**.
- **Threshold policy:** `test_threshold_consistency` passes (detector conf == aggregator
  threshold == 0.25) — the PHASE_22 P0 defect remains fixed.
- No checkpoint, config or weight was modified; all three artifact hashes are recorded above so
  future phases can detect drift.

**Concerns**

- v2 trained to a higher **validation** score than v1 but has **no held-out test evaluation**, so
  no promotion claim can be made (Rule 14) — **UNVERIFIED for test**.
- `results.csv` best (0.27821) vs the PHASE_09 record val overall (0.2731) differ slightly
  because the evaluation script evaluates the saved `best.pt` while `results.csv` reports the
  best epoch's metrics; both are within expected variance — noted, not an error.
- RDD2022 is **not** part of either training run (neither converted nor merged) — **VERIFIED**.

---

## 10. Issues classified by severity

| ID | Severity | Issue | Status | Evidence |
|---|---|---|---|---|
| **I-1** | **High** | `DATA-YOLO/` (~7.4 GB, ~57k images) is undocumented, untracked, and has **no licence or provenance** | BLOCKED | §3.3, §8; 0 doc references |
| **I-2** | **High** | Residual **same-session cross-split leakage** (2 dates: `20250219`, `20250223`) | VERIFIED (R6) | §7.2 |
| **I-3** | Medium | Active dataset has **no local licence text**; README DOI (`17834373`) ≠ approved record (`18528034`) | PARTIALLY VERIFIED | §8; PHASE_02_completion_report.md |
| **I-4** | Medium | RDD2022 licence **conflict** (CC BY 4.0 vs CC BY-SA 4.0) | PARTIALLY VERIFIED | §8; PHASE_20 |
| **I-5** | Medium | v2 checkpoint exists but is **not test-evaluated** and not wired | UNVERIFIED (R3) | §9 |
| **I-6** | Medium | **1 zero-area annotation** (`labels-YOLO/vlcsnap-00058.txt`) | VERIFIED | §4.1 |
| **I-7** | Medium | `COMPLETE_PROJECT_AUDIT.md` is **stale** (says 119 tests/1 fail; B1/B2 open) | VERIFIED (R2) | §12 |
| **I-8** | Low | `weights/yolo26n.pt` present with **unknown provenance** | UNVERIFIED (R4) | §9 |
| **I-9** | Low | RDD2022 `Norway.zip` **not extracted** (6/7 countries on disk) | VERIFIED | §3.2 |
| **I-10** | Low | 8 `DATA-YOLO/*.zip` (~7.07 GB) appear to duplicate extracted folders | VERIFIED (inventory) | §3.3 |
| **I-11** | Low | 5 within-split exact-duplicate groups (redundancy, not leakage) | VERIFIED | §6 |
| **I-12** | Info | Metrics/completion percentages are judgements, not measurements | (R8) | §12 |

---

## 11. Recommended remediation plan

**Phase 24B — Dataset cleaning & split-hardening *proposal* (no deletion; audit-only).**

1. **I-6:** propose a documented fix for the zero-area box (re-annotate or exclude the single
   line) — record the decision; do **not** edit the dataset without approval (Rule 15).
2. **I-2:** propose a **session-aware** split that keeps whole capture dates in a single split,
   eliminating the `20250219` / `20250223` cross-split mixing. Report the resulting
   train/val/test sizes and per-class totals for approval. Do not overwrite existing splits.
3. **I-11:** document the 5 within-split duplicate groups; propose deduplication policy.

**Phase 24C — Accuracy baseline plan (stop before training — Rule 19).**

4. **I-5:** evaluate v2 on the **frozen test split** (single run) to make a promotion decision
   (Rule 14). Do not wire v2 into `config/detection.yaml` until the test result is reviewed.
5. Propose whether to convert RDD2022 (India subset is most relevant to the intended
   operating region) — **stop before conversion/training**.

**Provenance / hygiene actions (may need user decision, not code).**

6. **I-1:** decide the fate of `DATA-YOLO/` (document provenance & licence, or exclude/remove
   with explicit approval). Do **not** use it until resolved.
7. **I-3:** record the licence resolution for the active dataset (confirm record `18528034` /
   CC BY 4.0) and correct the stale DOI note; do not change licensing policy unilaterally.
8. **I-4:** confirm the RDD2022 licence posture (CC BY-SA 4.0 conservative default) before any
   conversion.
9. **I-8:** identify the origin of `weights/yolo26n.pt` or quarantine it.
10. **I-7:** refresh `COMPLETE_PROJECT_AUDIT.md` to the current tree (148/0; B1/B2 fixed).

**Nothing in this plan is executed in Phase 24A.**

---

## 12. Limitations and unresolved questions

1. **External licence verification not re-executed.** The active dataset's CC BY 4.0 and
   RDD2022's FigShare CC BY 4.0 attribution are **prior-reported** (PHASE_02 / PHASE_20); no
   Zenodo/FigShare API lookup was performed here (would require network use; nothing was
   downloaded). **Licence verdicts for those two remain PARTIALLY VERIFIED.**
2. **RDD2022 not fully re-parsed.** 30k XMLs were **not** re-validated in this phase; the
   PHASE_20 structural audit is relied upon (folder-level pairing *was* re-measured).
3. **DATA-YOLO zip contents not inspected.** Only listings/sizes were read; members were not
   extracted or validated.
4. **dHash near-duplicate detection is heuristic** (Hamming ≤ 6); it can miss transformed
   duplicates and can rarely over-flag. Session heuristic is filename/date-based — it cannot
   prove two drives were "different sessions" or that two same-day drives are "the same".
5. **Cutoff/date of prior audits:** `COMPLETE_PROJECT_AUDIT.md` (2026-10-14) is stale.
6. **Open questions:** (a) Is the active dataset's approved record genuinely 18528034? (b) What
   is the intended action for `DATA-YOLO/`? (c) Should RDD2022 test images (no labels) ever be
   used? (d) Which enhancement/segmentation sets, if any, are in scope for the detector?

---

## 13. Commands and scripts used

All commands run from `D:\New folder (3)` with the workspace venv; **read-only** w.r.t. datasets.

| # | Command | Purpose | Exit |
|---|---|---|---|
| 1 | `git status --short` | Confirm pre-existing changes; record untracked files | 0 |
| 2 | `.\.venv\Scripts\python.exe scripts\audit\phase24a_dataset_audit.py` | Full inventory, pairing, label integrity, duplicates, splits, RDD2022, DATA-YOLO, model artifacts → `reports/phase24a/audit_evidence.json` | 0 |
| 3 | `.\.venv\Scripts\python.exe scripts\audit\phase24a_session_leakage.py` | Session heuristic + exhaustive in-session dHash leakage → `reports/phase24a/session_leakage.json` | 0 |
| 4 | `.\.venv\Scripts\python.exe -m unittest discover -s tests -t .` | Full test suite | **0 (148 tests OK)** |
| 5 | `Select-String ... labels-YOLO\*.txt` | Locate the out-of-range box | 0 |
| 6 | `Get-FileHash` / `sha256_file` | Checkpoint + archive hashes | 0 |

Existing scripts used/referenced (not re-run): `scripts/audit/phase03_dataset_audit.py`,
`scripts/audit/phase20_rdd2022_audit.py`, `scripts/audit/phase20_duplicate_scan.py`,
`scripts/evaluate_baseline.py`.

**New scripts created by this phase (safe, read-only):**
`scripts/audit/phase24a_dataset_audit.py`, `scripts/audit/phase24a_session_leakage.py`.

---

## 14. Evidence supporting key counts and conclusions

- **Machine-readable evidence:** `reports/phase24a/audit_evidence.json`,
  `reports/phase24a/session_leakage.json` (all raw counts used in this report).
- **Active dataset:** 2,009 images / 2,009 YOLO / 2,009 polygon; 4,737 boxes
  `{0:1261, 1:2519, 2:957}`; COCO 2,009/4,737/3 categories; 0 malformed; **1 zero-area**
  (`labels-YOLO/vlcsnap-00058.txt`); splits 1406/402/201; 0 stem overlap; 0 cross-split exact
  dup; 0 cross-split near dup; 5 exact groups (all within-split); 153 near pairs.
- **Leakage:** spanning sessions `20250219 {train 36, val 19, test 5}` and
  `20250223 {train 8, val 16, test 15}`; 1,907/2,009 vlcsnap video frames.
- **RDD2022:** 30,224 train images = 30,224 XML (6 countries); 6,995 test images (0 XML);
  `Norway.zip` unextracted.
- **DATA-YOLO:** 13 subdirs (~57k images) + 8 zips (~7.07 GB) + 1 PDF; 0 doc references; 0
  licence files.
- **Checkpoints:** v1 `61F6EDA2…78E65` (= PHASE_09 pin, VERIFIED); v2 `B6354A56…8800BA`;
  `weights/yolo26n.pt` `9B09CC8B…4FEF`. v1 results.csv best val mAP@0.5 = 0.27821 (epoch 39);
  v2 best val mAP@0.5 = 0.28707 (epoch 104).
- **Tests:** `Ran 148 tests ... OK`, exit 0.
- **Docs:** PHASE_02_completion_report.md (DOI mismatch, no local licence), PHASE_03 (classes,
  leakage), PHASE_09 (metrics), PHASE_20 (RDD2022 licence/pairing), PHASE_24_BASELINE_AUDIT
  (R1–R8).

---

## 15. Final readiness decision for the next phase

| Item | Decision |
|---|---|
| Active training dataset (`pothole_crack_manhole`) | **READY for the next phase (cleaning/split-hardening *proposal*)** — structurally sound (perfect pairing, valid YOLO/COCO, clean splits by content), with two documented open items: 1 zero-area box (I-6) and residual same-session cross-split leakage (I-2). No baseline retrain needed to proceed with a proposal. |
| RDD2022 | **NOT READY for training** — usable only **after** a validated VOC→YOLO conversion and licence confirmation; not converted or merged. |
| DATA-YOLO | **BLOCKED** — no provenance/licence; must not be used or converted. |
| Model artifacts | v1 serving is **verified consistent**; v2 remains **UNVERIFIED for test**. No promotion authorized. |

**Next recommended action:** begin **Phase 24B** to (a) propose a session-aware split that
removes the `20250219`/`20250223` cross-split mixing, (b) propose a documented fix for the
single zero-area box, and (c) produce a deduplication policy for the 5 within-split duplicate
groups — all as **proposals only, no file changes**.

**Stop point honored:** Phase 24A is audit-only. No training was started, no dataset/label/
split/config/checkpoint was modified, and no Phase 24B work was begun. Awaiting explicit user
review and approval before the next step.
