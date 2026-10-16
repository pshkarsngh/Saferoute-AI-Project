# SafeRoute AI — PHASE 24B: Dataset Cleaning and Split-Hardening Proposal

> **Phase:** PHASE_24B — Dataset cleaning & split-hardening **proposal** (proposal-only, audit-only)
> **Date executed:** 2026-10-16
> **Mode:** Read-only. **Nothing was modified** — no image, label, split file, config, source
> file, checkpoint or model weight. No dataset/generation output was produced inside the
> dataset. No training, fine-tuning or checkpoint evaluation was started. No package installed,
> no data downloaded, nothing committed or pushed.
> **Governing rules:** `master_rules.md` Rules 1, 5, 9, 14, 15, 17, 18, 20.
> **Predecessors:** [`PHASE_24A_DATASET_AUDIT.md`](PHASE_24A_DATASET_AUDIT.md),
> [`PHASE_24_BASELINE_AUDIT.md`](PHASE_24_BASELINE_AUDIT.md)

Evidence labels: **VERIFIED** (measured from primary artifacts this phase) · **PARTIALLY
VERIFIED** · **UNVERIFIED** · **BLOCKED**.

---

## 1. Executive summary

Phase 24A proposed a "session-aware split" to stop the two dates `20250219` and `20250223`
crossing splits. This phase verified that finding and, in doing so, uncovered **two much larger
problems** and a **flaw in the Phase 24A session heuristic**:

1. **Silent, large-scale image loss during training (NEW, high severity).** Ultralytics resolves
   the label directory as `labels/` (derived from `images/`) and asserts every label's class id
   is `< num_cls`. Because `data/dataset.yaml` declares only 2 classes while the labels contain
   class `2` (manhole), **every image containing a manhole is discarded entirely** — not just the
   manhole box. Measured: **545/1406 train, 138/402 val, 76/201 test images dropped** = **759 of
   2,009 images (37.8%) never used**, taking **837 valid pothole/crack boxes with them**
   (308 potholes, 529 cracks). The training log confirms this exactly (683 dropped lines = 545
   train + 138 val). **Effective evaluated sets are 861/264/125, not 1406/402/201.**

2. **Session leakage is far larger than Phase 24A reported (corrected).** Phase 24A grouped
   `vlcsnap-*` frames by **second**, so it only saw 2 spanning dates. Normalizing all filenames
   to a calendar date reveals **4 capture dates that cross splits**:
   `2025-02-18` (581 imgs), `2025-02-19` (821 imgs), `2025-02-23` (39), `2025-03-16` (136) —
   **1,577 of 2,009 images (78.5%)** sit in date-sessions that cross splits. A further **212
   images** have **no determinable capture date** (bare `vlcsnap-NNNNN.jpg` names).

3. **Config/label-dir conflict (NEW).** Training reads `labels/` (polygon, 9-column →
   interpreted as *segmentation*) and **ignores `labels-YOLO/` entirely**; the polygon format is
   read as segments and auto-converted to boxes. This is not an error but is undocumented and
   means the project's own axis-aligned YOLO labels are unused.

4. **Proposed session-aware split.** A date-atomic 70/20/10 re-split is feasible and is
   proposed in three variants (P-A recommended). Because the two mega-sessions must occupy train,
   the current held-out images **cannot** all remain held out — **the PHASE_09 test metrics will
   not be comparable** and a single fresh test evaluation will be required (Rule 14).

5. **Degenerate annotation (confirmed).** `vlcsnap-00058` has a zero-height box **and** a
   zero-height source polygon → a genuine source defect; a correction policy is proposed.

6. **Duplicates** are benign: all 5 exact-duplicate groups are **within-split** (0 cross-split).

**This is a proposal. No change has been made. Approval decisions are listed in §11.**

---

## 2. Methodology

- Read `master_rules.md`, the Phase 24A report and evidence, `docs/TRD.md`,
  `docs/TRAINING_RULES.md`, `docs/evaluation_plan.md`, and the PHASE_02/03/07/09/20 reports.
- Inspected the installed Ultralytics `verify_image_label` source to determine the exact
  drop rule and label-path resolution.
- Parsed the training log (`logs/training/saferoute-yolo11-v1/train.log`).
- Ran one new read-only analysis script (§12) computing split sizes, per-class box/image
  counts, the manhole-drop impact, capture-date session distributions, proposed split options,
  exact-duplicate groups, and the `vlcsnap-00058` defect.
- Cross-checked candidate split options in `runpy`-style inline checks (no dataset writes).
- No file under `data/`, `config/`, `models/`, `logs/`, `weights/` was written.

**Reproducibility:** all figures in this report come from
`reports/phase24b/proposal_evidence.json` (produced by the script in §12).

---

## 3. Verification of Phase 24A findings

| Phase 24A finding | Phase 24B re-check | Verdict |
|---|---|---|
| 2,009 images, 2,009 YOLO + 2,009 polygon labels | Re-confirmed 2,009 / 2,009 / 2,009 | VERIFIED |
| 4,737 boxes `{0:1261, 1:2519, 2:957}` | Re-confirmed | VERIFIED |
| Split sizes 1406 / 402 / 201, 0 stem overlap | Re-confirmed | VERIFIED |
| 0 cross-split exact duplicates; 5 groups within-split | Re-confirmed (all 5 within-split) | VERIFIED |
| 1 zero-area box `labels-YOLO/vlcsnap-00058.txt` | Re-confirmed **and** the polygon source is also degenerate | VERIFIED |
| "2 sessions spanning multiple splits" (`20250219`, `20250223`) | **Corrected/expanded to 4 date-sessions** (§5) | PARTIALLY VERIFIED — Phase 24A under-counted |
| "readiness: ready for a cleaning proposal" | Agreed, but the manhole-drop issue (§4) is a prerequisite | VERIFIED with addendum |

**Root cause of the Phase 24A under-count:** its `session_key` grouped `vlcsnap-*` frames by
**one-second buckets** (regex captured `…-17h03m41s`), so each second was its own "session" and
cross-split leakage at the date level was invisible. Phase 24B normalizes to a calendar date.

---

## 4. Finding A — silent large-scale image loss (high severity)

### 4.1 Mechanism (VERIFIED)

Ultralytics `data/utils.py::verify_image_label`:

```python
max_cls = 0 if single_cls else lb[:, 0].max()
assert max_cls < num_cls, (f"Label class {int(max_cls)} exceeds dataset class count {num_cls}. ...")
```

`num_cls` is `len(dataset.yaml names)` = **2** (pothole, crack). The dataset's label files also
contain class **2** (manhole). For any image whose label file has a class-2 row, the assert
fails → the whole `(image, label)` pair is returned as corrupt and **dropped**. This is a
whole-*image* drop, so **valid pothole/crack boxes on that image are lost too**.

**Direct log evidence (VERIFIED):** `logs/training/saferoute-yolo11-v1/train.log` contains
**683** `ignoring corrupt image/label: Label class 2 exceeds dataset class count 2` lines =
**545 (train) + 138 (val)**. Replicating the rule against both `labels/` and `labels-YOLO/`
gives identical counts, so the finding holds regardless of which label dir was read.

### 4.2 Measured impact

| Split | Images (nominal) | Manhole images dropped | **Effective images** | Pothole boxes lost | Crack boxes lost |
|---|---|---|---|---|---|
| train | 1,406 | 545 | **861** | 265 | 457 |
| val | 402 | 138 | **264** | 12 | 42 |
| test | 201 | 76 | **125** | 31 | 30 |
| **Total** | **2,009** | **759 (37.8%)** | **1,250** | **308** | **529** |

- Valid boxes lost = **837** of the 3,780 pothole+crack boxes (**22.1%**); potholes −24.4%,
  cracks −21.0%.
- The **reported PHASE_09 metrics (test mAP@0.5 = 0.2615) were computed over 125 test images,
  not 201**, and val over 264, not 402. Any statement quoting "402 / 201" is misleading.

### 4.3 Options (proposal — requires approval)

| Option | Description | Pros | Cons |
|---|---|---|---|
| **M1 (recommended)** | Generate a **derived label set** that removes class-2 rows (e.g. `labels-YOLO-2class/`), keep all images, point a new `dataset_v2.yaml` at it | Recovers all 837 valid boxes; training uses 100% of images; no originals touched | New derived artifact to version; manhole no longer a label anywhere |
| M2 | Add `2: manhole` to `names` and train a **3-class** detector | No data loss; manhole becomes a supported class | Scope/policy change (Rule 5); detector contract must change end-to-end |
| M3 | Keep current behaviour (whole-image drop) | Zero change | 37.8% data wasted; metrics computed on reduced sets; misleading unless documented |

**M1 is recommended** and is a prerequisite for the split work to be meaningful. **M3 must at
minimum be documented loudly** if the user prefers no new artifacts.

---

## 5. Finding B — capture-session leakage (corrected scope)

**Method.** Assign each image a capture date from its filename, normalized to `YYYY-MM-DD`
(both `vlcsnap-2025-02-18-…` and `20250218_…` forms). Treat each date as one session (the
conservative, leakage-averse choice). **Limitation:** `vlcsnap-*` timestamps may be the
*snapshot wall-clock*, not the video content time (an exact-duplicate pair was saved ~1h19m
apart), so two files with the same date are **not guaranteed** to be the same drive.

### 5.1 Date distribution (VERIFIED)

| Capture date | train | val | test | Total | Crosses split? |
|---|---|---|---|---|---|
| 2025-02-16 | 3 | 0 | 0 | 3 | no |
| **2025-02-18** | 326 | 226 | 29 | **581** | **YES** |
| **2025-02-19** | 513 | 155 | 153 | **821** | **YES** |
| **2025-02-23** | 8 | 16 | 15 | **39** | **YES** |
| **2025-03-16** | 127 | 5 | 4 | **136** | **YES** |
| 2025-02-26 | 217 | 0 | 0 | 217 | no |
| **UNKNOWN** (bare `vlcsnap-NNNNN`) | 212 | 0 | 0 | **212** | n/a (no date) |

- **4 dates cross splits**; **1,577 images (78.5%)** are in cross-split date-sessions.
- The task brief named `20250219` and `20250223`; the analysis shows **`2025-02-18` and
  `2025-03-16` also cross splits** (previously missed). All four must be handled.
- **212 images have no determinable date** — their session cannot be proven disjoint from any
  split; this is an irreducible limitation of the filenames.

### 5.2 Why "preserve the current test set" and "session-atomic" conflict

The two largest sessions (`2025-02-18` = 581 ≈ 28.9%, `2025-02-19` = 821 ≈ 40.9%) are each
larger than the 10% test target and the 20% val target, so **both must go to train** in any
70/20/10 date-atomic split. Consequently the images currently in test (which belong to those
same dates) **cannot all stay held out** without either (a) making test huge or (b) leaving
same-session images in train. This is an inherent, documented trade-off.

---

## 6. Proposed split options and class distributions

All options are **date-atomic** (no date crosses splits). `UNKNOWN` is treated as one block.
Per-class figures below are **nominal** (before the manhole drop); effective figures assume
Finding A is fixed (M1); if M3 is kept, subtract the drops.

### 6.1 Option P-A (RECOMMENDED)

**Assignment:** train = {2025-02-18, 2025-02-19}; val = {UNKNOWN, 2025-03-16, 2025-02-23,
2025-02-16}; test = {2025-02-26}.

| Split | Images | pothole boxes | crack boxes | manhole boxes | images w/ pothole | images w/ crack |
|---|---|---|---|---|---|---|
| train | **1,402** (69.8%) | 897 | 1,670 | 751 | 580 | 867 |
| val | **390** (19.4%) | 266 | 555 | 91 | 143 | 352 |
| test | **217** (10.8%) | 98 | 294 | 115 | 72 | 156 |

- **With M1** (label fix adopted) the split keeps **all 1,402 / 390 / 217** images.
  **With M3** (no fix) the Ultralytics drop applies → effective **810 / 309 / 131**.
- Held-out test = a **single, well-defined capture date** (`2025-02-26`) — the strongest session
  holdout available.
- Residual risk: the 212 `UNKNOWN`-date images sit in val and *could* share a session with train
  or test (undeterminable).

### 6.2 Option P-B — quarantine the unknown-date images

**Assignment:** as P-A but `UNKNOWN` (212) is **excluded** from all splits.

| Split | Images | pothole boxes | crack boxes |
|---|---|---|---|
| train | 1,402 | 897 | 1,670 |
| val | **178** (9.9% of 1,797) | — | — |
| test | **217** (12.1% of 1,797) | 98 | 294 |

- Most conservative for leakage; **val becomes small** and 212 images go unused pending a
  provenance decision. With M3 (no label fix) the drop applies → effective train 810 / val 161 /
  test 131; with M1 the nominal 1,402 / 178 / 217 hold.

### 6.3 Option P-C — keep current splits (minimal change)

| Split | Images | pothole | crack | manhole |
|---|---|---|---|---|
| train | 1,406 | 896 | 1,864 | 701 |
| val | 402 | 226 | 481 | 165 |
| test | 201 | 139 | 174 | 91 |

- **Maximum comparability** with PHASE_09, but the 4-date leakage remains. Suitable only as a
  stop-gap.

### 6.4 Recommendation

Adopt **P-A** together with the **M1** label fix. P-A yields near-ideal proportions
(69.8 / 19.4 / 10.8), a clean single-date holdout, and eliminates all *determinable* session
leakage; the only residual is the 212 undated images (disclosed). P-B is the fallback if the
user prefers zero ambiguity in the holdout at the cost of a smaller val and 212 unused images.

---

## 7. Split-manifest design (proposal)

No manifest is created in this phase. The proposed design (for a future approved phase):

- `data/splits_v2/train.txt`, `val.txt`, `test.txt` — same absolute-path line format as the
  current `data/splits/*.txt` (so `data/dataset_v2.yaml` can reuse it), **new files only**;
  existing `data/splits/*` are left untouched.
- `data/splits_v2/split_manifest.csv` — one row per image:
  `stem, capture_date, session_key, split, has_manhole, n_pothole, n_crack, n_manhole, sha256`.
- `data/splits_v2/SPLIT_NOTES.md` — the atomic-date rule, the `UNKNOWN` handling, the zone/file
  exclusions, and the evidence hash.
- Determinism: the assignment is a **fixed, explicit date→split table** (not random), so the
  split is reproducible without a seed.
- `data/dataset_v2.yaml` — points `path` at the dataset, uses the derived `labels-YOLO-2class/`
  (M1) and the new split files, and records `names: {0: pothole, 1: crack}`.

**Integrity guard (recommended):** a small verification step asserting that for every capture
date, all its images resolve to exactly one split, and that no split file line is missing on
disk.

---

## 8. Conflict review (task 7)

| ID | Conflict | Evidence | Severity | Recommendation |
|---|---|---|---|---|
| **C-1** | `dataset.yaml names` has 2 classes but labels contain class 2 → whole-image drop | §4; train log 683 lines | **High** | Adopt M1 (derived 2-class labels) |
| **C-2** | `dataset.yaml` has no explicit label dir → Ultralytics reads `labels/` (polygon) and **ignores `labels-YOLO/`** | Ultralytics `img2label_paths`; polygon read as segments | Medium | Document; in v2 specify intent explicitly |
| **C-3** | `evaluate_baseline.py` reports split sizes from the split **files** (402 / 201) but evaluates the **post-drop** sets (264 / 125) | PHASE_09 report wording vs §4 | Medium | Report actual evaluated counts in future runs |
| **C-4** | Proposed re-split changes test membership → PHASE_09 metrics not comparable | §5.2, §6 | Medium | One fresh test evaluation on the new holdout (Rule 14) |
| **C-5** | Absolute `D:/New folder (3)/...` paths in `dataset.yaml`, split files and scripts | `data/dataset.yaml`, split files | Low | Workspace-relative paths in v2 (pre-existing) |
| **C-6** | `labels-YOLO/` is unused, so the "YOLO labels validated" claim (PHASE_03 G6) refers to files training does not read | §4, PHASE_03 | Low | Clarify which labels training consumes |

---

## 9. `vlcsnap-00058` degenerate annotation (task 5)

**Evidence (VERIFIED).**

`labels-YOLO/vlcsnap-00058.txt`:
```
1 0.578125 0.718055 0.125000 0.136111
1 0.639062 0.786111 0.003125 0.000000   <- zero height
2 0.659375 0.655555 0.128124 0.066667
```
Source polygon `labels/vlcsnap-00058.txt` row 2:
```
1 0.637500 0.786111 0.640625 0.786111 0.640625 0.786111 0.637500 0.786111
```
All four y-values are `0.786111` → the **source polygon itself is zero-height** (a degenerate
quad, not a conversion artefact). So the YOLO `h=0` is faithful to a defective source label.

**Proposed policy (no edit made):**

- **Recommended:** treat the row as a **mis-annotated duplicate of the valid crack above it**
  (they overlap at y≈0.786) and propose **excluding that single row** from the derived
  `labels-YOLO-2class/` at generation time, with a documented manifest entry
  (`vlcsnap-00058: excluded degenerate crack row`). Do **not** edit the original.
- **Alternative:** leave it; Ultralytics tolerates zero-area boxes (it does not fail on
  `w=0/h=0`; only class-range fails), so it currently trains as a degenerate box. Not
  recommended, but harmless.
- **Not recommended:** deleting the line in place (violates Rule 15 "do not silently repair").

---

## 10. Duplicate policy (task 6)

**Evidence (VERIFIED):** 5 exact (SHA-256) duplicate groups, 10 files; **all within-split**
(3 groups in train, 2 in test); **0 cross-split exact duplicates**. Example:
`vlcsnap-2025-02-19-14h41m29s105.jpg` = `vlcsnap-2025-02-19-14h41m49s395.jpg` (both test).

**Proposed policy (no edit made):**

- Prefer **keep-one-per-group** in the *derived* split/label set: keep the lexicographically
  first file of each group, drop the rest, and record all members + the kept file in
  `split_manifest.csv` (so nothing is lost from the record).
- Because every group is within-split, this is a **redundancy** fix, not a leakage fix; it is
  optional and independent of the session work.
- Do **not** delete files from the original dataset (Rule 15).

---

## 11. Test-set holdout and evaluation comparability (task 8)

- **Conceptual holdout preserved:** P-A's test set is a **complete, single capture date**
  (`2025-02-26`, 217 images) — a stronger, well-defined session holdout than the current test set
  (201 images drawn from four dates that also appear in train/val).
- **Comparability is broken and must be disclosed:** P-A/P-B reassign many images, including
  images currently in test (the current test images of `2025-02-18/19/23/16` move to train or
  val). Therefore **the PHASE_09 test mAP@0.5 = 0.2615 cannot be compared** with any future
  metric on the new splits.
- **Required follow-up (rule 14):** after approval and dataset regeneration, run **one** fresh
  evaluation of the **v1 serving checkpoint** on the new holdout to establish a new comparable
  baseline, and (separately) evaluate v2 on the same holdout. No evaluation was run in this
  phase.
- If the user requires strict comparability instead, **P-C** preserves the old splits and the old
  metrics, at the cost of retaining the session leakage (documented).

---

## 12. DATA-YOLO / RDD2022 blockers (task 9)

Neither was merged, converted or touched. Status from PHASE_24A, restated for the decision log:

| Source | Provenance | Licence | Conversion status | Blocker |
|---|---|---|---|---|
| `DATA-YOLO/` (~7.4 GB, ~57k images, 13 subsets) | **unknown** — no source URL, no README beyond an empty one, 0 project references | **none found** | not converted; `Datasets` class-mapping undocumented (no `data.yaml`); `Road_crack` is segmentation masks; `Road_Condition_Dataset` is classification | **BLOCKED** — provenance + licence unresolved (Rule 15) |
| RDD2022 (`data/raw/RDD2022`, 30,224 paired train images, 6 of 7 countries) | FigShare record 21431547 | **conflicting**: CC BY 4.0 (FigShare) vs **CC BY-SA 4.0** (creators) → project adopts the stricter | not converted (VOC→YOLO needed); test images have no XML | **BLOCKED for use** — licence confirmation + validated conversion required (Rule 15, 19) |

**Recommendation:** keep both **out of scope** for Phase 24C. Resolve `DATA-YOLO` provenance or
exclude it; confirm the RDD2022 licence posture before any conversion proposal. No merge in this
phase.

---

## 13. Risks

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | Finding A (manhole drop) remains unfixed → 37.8% data wasted, misleading metrics | High | Adopt M1 |
| R-2 | Session leakage persists if P-C chosen | High | Adopt P-A/P-B |
| R-3 | 212 images with undeterminable session may contaminate the holdout | Medium | P-B quarantine, or disclose |
| R-4 | `vlcsnap` date ≠ content-session assumption may over/under-merge | Medium | Document; refine with near-dup clustering later |
| R-5 | Metrics incomparability after re-split | Medium | Fresh single test evaluation (Rule 14) |
| R-6 | Derived label/split artifacts add versioning burden | Low | Manifest + hash |
| R-7 | New split "looks" fine but still has hidden leakage (date proxy) | Medium | Keep exact-dup + manifest checks; disclose residual |
| R-8 | Held-out test size changes vs current (P-A/P-B = 217; P-C = 201) | Low | Choose per approval |

---

## 14. Approval decisions required

Please approve/decline each (no defaults will be applied):

1. **Manhole handling (Finding A):** adopt **M1** (derived 2-class labels, recover 837 boxes),
   **M2** (3-class detector), or **M3** (keep + document) — **recommend M1**.
2. **Split strategy:** **P-A** (recommended), **P-B**, or **P-C**.
3. **`UNKNOWN`-date images (212):** keep in val (P-A), quarantine (P-B), or place in train.
4. **`vlcsnap-00058` degenerate row:** exclude-in-derived (recommended) or leave as-is.
5. **Duplicate groups:** apply keep-one-per-group in the derived set (optional) or leave.
6. **Fresh evaluation:** authorize **one** test-set evaluation of v1 (and separately v2) on the
   new holdout once the dataset is regenerated (Rule 14).
7. **`DATA-YOLO` / RDD2022:** confirm they remain **out of scope** (recommended).
8. **Artifact location:** confirm the new derived artifacts (`data/splits_v2/`,
   `data/dataset_v2.yaml`, derived labels) may be created in a future approved phase.

---

## 15. Commands and scripts used (task: run only safe checks)

| # | Command | Purpose | Exit |
|---|---|---|---|
| 1 | `git status --short` / `git log --oneline -1` | State + preservation | 0 |
| 2 | `.\.venv\Scripts\python.exe scripts\audit\phase24b_split_proposal.py` | All Phase 24B measurements → `reports/phase24b/proposal_evidence.json` | 0 |
| 3 | inline Python (`.venv`): replicate the manhole-drop rule on `labels/` and `labels-YOLO/` | Confirm 545/138/76 | 0 |
| 4 | `Select-String train.log -Pattern 'ignoring corrupt'` | 683 lines = 545+138 | 0 |
| 5 | source read: `.venv\Lib\site-packages\ultralytics\data\utils.py` | Confirm the drop rule + label-path resolution | 0 |

**Test suite:** not re-run in this phase (no code changed; PHASE_24A already ran
`148 tests OK`). No checkpoint evaluation was performed.

**New script created (read-only):** `scripts/audit/phase24b_split_proposal.py`.
**No dataset, label, split, config, source, checkpoint or weight was modified.**

---

## 16. Final Git status

```
?? docs/reports/PHASE_24A_DATASET_AUDIT.md     (Phase 24A, pre-existing this session)
?? docs/reports/PHASE_24B_DATASET_CLEANING_PROPOSAL.md   (this phase)
?? docs/reports/PHASE_24_BASELINE_AUDIT.md     (pre-existing, untouched)
?? reports/phase24a/                            (Phase 24A evidence)
?? reports/phase24b/                            (this phase evidence)
?? scripts/audit/phase24a_dataset_audit.py
?? scripts/audit/phase24a_session_leakage.py
?? scripts/audit/phase24b_split_proposal.py
```

All pre-existing changes preserved; nothing committed or pushed. Checkpoints unchanged
(v1 `61F6EDA2…78E65`, v2 `B6354A56…8800BA`).

---

**Stop point honored:** this is a proposal only. No dataset change, no manifest written into the
dataset, no training, no evaluation, no downloads, no installs. **Awaiting explicit approval**
before implementing any dataset change or starting training.
