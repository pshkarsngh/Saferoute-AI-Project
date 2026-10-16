# SafeRoute AI — PHASE 24D: Fresh Holdout Evaluation (v1 vs v2)

> **Phase:** PHASE 24D — fresh evaluation of the existing v1 and v2 checkpoints on the
> PHASE 24C derived two-class test holdout.
> **Date executed:** 2026-10-15/16 (UTC) · **Workspace:** `D:\New folder (3)` · **Branch:** `main`
> **Mode:** **Evaluation only.** No training, fine-tuning, resume, weight change, promotion,
> deployment, dataset change, dependency change, download, commit or push.
> **Governing rules:** `master_rules.md` Rules 1, 3, 5, 9, 14, 15, 16, 17, 18, 19, 20.
> **Specification:** [`PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md`](PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md),
> `data/derived_2class/MANIFEST.json`, `data/derived_2class/README.md`, `data/splits_v2/SPLIT_NOTES.md`.

Evidence labels: **VERIFIED** (measured this phase) · **PARTIALLY VERIFIED** · **BLOCKED**.

---

## 1. Executive summary

Two independent, single-pass evaluations were completed on the **same** 216-image derived
**test** holdout (`data/dataset_v2.yaml`, split = `test`):

| Model | Checkpoint SHA-256 (prefix…suffix) | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall |
|---|---|---|---|---|---|
| **v1** | `61F6EDA2…8078E65` | **0.4842** | **0.2512** | 0.5360 | 0.5617 |
| **v2** | `B6354A56…DF8800BA` | **0.5790** | **0.3283** | 0.5734 | 0.7018 |

**VERIFIED.** Both runs used identical settings, the exact same holdout, resolved all 216
images and all 390 ground-truth boxes (98 pothole / 292 crack), and produced no skipped
images, bad labels, corrupt files or evaluation errors. **v2 measured higher than v1 on every
reported aggregate and per-class metric** on this holdout.

This is a **new evaluation baseline**. These numbers are **not** comparable to the historical
PHASE_09 test metrics, because the holdout membership, the label set (manhole removed), the
label representation (derived axis-aligned boxes) and the compute device all changed. See §8.

**Not done (by instruction):** no training, no tuning, no promotion/replacement of the
serving model, no commit/push. A serving-model decision requires separate approval (§12).

---

## 2. Pre-flight (rules + state preservation)

- Re-read `master_rules.md` (all 20 rules). Relevant here: 1 (workspace isolation),
  3 (one phase at a time), 5 (honest classes), 9 (missing ≠ safe), 14 (honest metrics),
  15 (dataset integrity), 16 (hardware awareness), 17 (documentation), 18 (minimal changes),
  19 (no unauthorized actions), 20 (honest demonstration).
- Read the PHASE 24C report, `data/derived_2class/README.md`, `MANIFEST.json`,
  `data/splits_v2/SPLIT_NOTES.md`, the existing evaluation script
  `scripts/evaluate_baseline.py`, the model configs (`config/training_baseline.yaml`,
  `config/training_improved.yaml`), the prior reports (`PHASE_09_report.md`,
  `PHASE_20_rdd2022_verification.md`, `PHASE_24_BASELINE_AUDIT.md`) and
  `logs/evaluation/evaluation_record.json`.
- **Preserved all existing user work.** `git status` before work: only the pre-existing
  untracked PHASE 24A/24B/24C files were present; **no tracked file was modified**.
  HEAD = `5645dcb57e3279ce059c98250e0674684eb6e9da`.
- No original or derived artifact was rewritten (proved in §10).

**Design constraint (Rule 18):** the existing `scripts/evaluate_baseline.py` is hard-wired to
`data/dataset.yaml`, to the v1 checkpoint/hash only, and it writes into the historical
`models/evaluation/` and `logs/evaluation/` directories (it would overwrite prior results).
It therefore cannot be reused as-is without violating "do not overwrite historical results".
A **new, separate** harness was created (Rule 18, new file only):
`scripts/audit/phase24d_evaluate_holdout.py`. The new harness writes **only** under
`reports/phase24d/`.

---

## 3. Evaluation authorization and scope

This phase authorizes **evaluation only** of the existing v1 and v2 checkpoints on the
PHASE 24C test holdout. In scope and executed:

- Use `data/dataset_v2.yaml` and its designated `test` split.
- Evaluate the **existing v1 serving checkpoint** and the **existing v2 checkpoint**
  separately on the **exact same** 216-image holdout.
- Verify the actual images and labels the pipeline loads; confirm two-class derived labels
  are used and no images are silently dropped.
- Confirm the holdout shares no image and no capture date with train or validation.
- Record paths, SHA-256 hashes, commands, parameters, software versions and timestamps.

Explicitly **not** done: no training/fine-tuning/resume, no weight modification, no
promotion/deployment/replacement, no dataset/annotation/split/config/checkpoint modification,
no download, no package install, no commit/push, and no use of train/val data as a substitute
for the test holdout.

---

## 4. Checkpoint & artifact identity verification (VERIFIED)

All identities were recomputed this phase and matched their documented values
(`PHASE_24C` report, `logs/evaluation/evaluation_record.json`, `PHASE_20` report).

### 4.1 Checkpoints

| Model | Path | SHA-256 (measured) | Expected | Match |
|---|---|---|---|---|
| v1 | `models/training/saferoute-yolo11-v1/weights/best.pt` | `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65` | same | ✅ |
| v2 | `models/training/saferoute-yolo11-v2/weights/best.pt` | `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` | same | ✅ |

Both are YOLO11n, `nc = 2`, names `{0: pothole, 1: crack}` (read from the loaded models).

### 4.2 Dataset / split / label identity

| Artifact | SHA-256 (measured) | Expected | Match |
|---|---|---|---|
| `data/dataset_v2.yaml` | `98EDD97ADDF2F72779335E6622D575C0C3B88E2C7BDF88ADAD31BDD3D62C1912` | same | ✅ |
| `data/dataset.yaml` (original, unchanged) | `CD502CDC20B732CBBE239A6F80FBA69CFD4B9451CFBE5BA26EC2AC0687E5969E` | same | ✅ |
| `data/splits_v2/train.txt` | `3DC10C151E939C283328A6E615B51BCD25607A3C2CDDEB296A9062F967CC5978` | same | ✅ |
| `data/splits_v2/val.txt` | `37D92842313D013C6030B857EC81C22FF4FD4B051AAD011AF25E89B8011621A1` | same | ✅ |
| `data/splits_v2/test.txt` | `AABA32ABA36C668145017715CC4C9190D0C58457EBE6CD66D515EF9BE0325D07` | same | ✅ |
| derived labels Merkle (1,792 files) | `0C15D6AF395335FC6FAF06A90F6261BEFFFA05A78C9A4C114B936FBB01158142` | same | ✅ |

The derived-labels Merkle was recomputed with the **same algorithm** as the PHASE 24C
generator (`sha256` over sorted `name:sha256(file)` entries) and equals the value recorded in
`MANIFEST.json`.

### 4.3 Original source integrity (VERIFIED, re-measured **after** evaluation)

| Source | Merkle / SHA-256 (measured) | Matches PHASE 24C MANIFEST |
|---|---|---|
| `data/pothole_crack_manhole/data/labels-YOLO` (2,009) | `B3446313F7D105BA23F3308C54D35FBF9D6254214B7A5DA7A39E5E4E8E03825F` | ✅ |
| `data/pothole_crack_manhole/data/labels` (polygon, 2,009) | `9E5DFC3F8323187BD8A1567679B9531CD031DD83C3C08E50FA56AED8514A2D4E` | ✅ |
| `data/pothole_crack_manhole/data/images` (2,009) | `78A84E52A3D200B83B145E59C9070A929EB72A22C51C5D89E820BF4382A048F2` | ✅ |
| `data/splits/train.txt` | `47042901B46064F16D012DB66FBA388F73889482F2E36DB6E179BADE7329800C` | ✅ |
| `data/splits/val.txt` | `13D992B1383665DA40970CD466B4FA125902250608B7178C859E52EDDB48B215` | ✅ |
| `data/splits/test.txt` | `46F647E0C102C88E2500F6304AD3F3FB9AE106B7060CEE12302A85887A42CA51` | ✅ |

---

## 5. Holdout identity verification (VERIFIED)

The holdout was verified independently of Ultralytics (raw split-file + label parsing) **and**
cross-checked against what the evaluation pipeline reported.

| Check | Result |
|---|---|
| Images listed in `data/splits_v2/test.txt` | **216** |
| Images whose file exists | **216** (0 missing) |
| Images with a derived label file | **216** (0 missing) |
| Derived label class ids ⊆ {0,1} | **PASS** (0 violations; class 2 absent) |
| Boxes in valid range (0≤x,y≤1; 0<w,h≤1) | **PASS** |
| Zero-area boxes | **0** |
| Ground-truth boxes total | **390** — pothole **98**, crack **292** |
| Images containing pothole / crack | **72 / 155** |
| Background-only (empty-label) images | **46** (retained per PHASE 24C M1) |
| Test image bytes vs `split_manifest.csv` SHA-256 | **216/216 match** |
| Ultralytics images evaluated | **216** (its own table) |
| Ultralytics GT instances | **390** (pothole 98, crack 292) — matches independent count |

**Silent-drop check:** Ultralytics' own counts (`Images = 216`, `Instances = 390`) and its
per-class ground-truth counts (`pothole 98`, `crack 292`) exactly equal the independent
counts, so **no image and no ground-truth box was dropped or mis-resolved**.

### 5.1 Leakage / date-grouping verification (VERIFIED)

Under the documented date-grouping rule (filename-derived date; a shared date = one
session — see §9.1):

| Split | Capture dates present | Images |
|---|---|---|
| train | `2025-02-18`, `2025-02-19` | 1,398 |
| val | `2025-02-16`, `2025-02-23`, `2025-03-16` | 178 |
| **test (holdout)** | **`2025-02-26`** | **216** |

- Stem overlap between train/val/test: **0 / 0 / 0**.
- Capture-date overlap between test and train: **none**; between test and val: **none**.
- Therefore the holdout contains **no image and no capture date** assigned to train or
  validation under the documented rule.

---

## 6. Exact commands and evaluation parameters

All commands were run from `D:\New folder (3)` using the workspace virtual environment.

```powershell
# 1) state + holdout + source integrity verification (read-only)
.\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py verify

# 2) v1 evaluation (existing serving checkpoint)
.\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py eval v1

# 3) v2 evaluation (existing checkpoint)
.\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py eval v2

# 4) v1-vs-v2 comparison artefact
.\.venv\Scripts\python.exe scripts\audit\phase24d_evaluate_holdout.py compare
```

### 6.1 Evaluation parameters (identical for both checkpoints)

| Parameter | Value |
|---|---|
| Dataset config | `data/dataset_v2.yaml` (SHA-256 `98EDD97A…C1912`) |
| Split | `test` (216 images) |
| `imgsz` | **640** |
| `batch` | **16** |
| `cache` | `False` (no label caching requested) |
| `plots` | `True` (confusion matrix + PR/F1/P/R curves) |
| `save_json` | `False` |
| `verbose` | `True` |
| `conf` (mAP) | **not overridden** → Ultralytics default **0.001** |
| `iou` (NMS) | **not overridden** → Ultralytics default **0.7** |
| `max_det` | **300** |
| **device** | **`cpu`** (see §9.2 — GPU was VRAM-saturated) |

The `compare` artefact confirms `identical_eval_settings = true` and
`same_holdout_for_both = true` (output `name`/output paths excluded as cosmetic).

### 6.2 Effective thresholds / conventions

Ultralytics computes two different things from the same forward pass:

- **mAP / P / R table:** computed at **conf = 0.001**, NMS **IoU = 0.7**.
- **Confusion matrix:** computed at **conf = 0.25**, match **IoU = 0.45**.

The per-class `P`/`R` reported below are the Ultralytics "best-F1" values from the PR curve
(they are **not** the thresholded confusion-matrix ratios). This distinction is stated so the
numbers are not misread.

### 6.3 Software / environment (VERIFIED)

| Item | Value |
|---|---|
| Python | 3.12.10 |
| OS | Windows-11 (`Windows-11-10.0.26300-SP0`) |
| PyTorch | 2.13.0+cu130 |
| CUDA runtime | 13.0 |
| GPU present | NVIDIA GeForce RTX 5050 Laptop GPU (8,123 MiB) |
| Ultralytics | 8.4.163 |
| OpenCV | 4.14.0 |
| NumPy | 2.5.3 |
| Num CPUs context | AMD Ryzen 7 260 (CPU used for the runs) |

---

## 7. Results (VERIFIED, measured)

Authoritative machine-readable records:
`reports/phase24d/v1_metrics.json`, `reports/phase24d/v2_metrics.json`,
`reports/phase24d/comparison.json`. Raw console transcript (with ANSI progress codes):
`reports/phase24d/v1_console.log`, `reports/phase24d/v2_console.log`.

### 7.1 Overall metrics

| Metric | v1 | v2 | Δ (v2 − v1) | Δ % |
|---|---|---|---|---|
| Precision | 0.5360 | 0.5734 | +0.0374 | +7.0% |
| Recall | 0.5617 | 0.7018 | +0.1401 | +24.9% |
| F1 | 0.5485 | 0.6311 | +0.0826 | +15.1% |
| **mAP@0.5** | **0.4842** | **0.5790** | **+0.0948** | **+19.6%** |
| **mAP@0.5:0.95** | **0.2512** | **0.3283** | **+0.0771** | **+30.7%** |

### 7.2 Per-class metrics

**Pothole (class 0):**

| Metric | v1 | v2 | Δ |
|---|---|---|---|
| Precision | 0.3498 | 0.4142 | +0.0644 |
| Recall | 0.4796 | 0.6531 | +0.1735 |
| F1 | 0.4045 | 0.5069 | +0.1024 |
| mAP@0.5 | 0.2686 | 0.3785 | +0.1099 |
| mAP@0.5:0.95 | 0.1249 | 0.1922 | +0.0673 |

**Crack (class 1):**

| Metric | v1 | v2 | Δ |
|---|---|---|---|
| Precision | 0.7221 | 0.7326 | +0.0104 |
| Recall | 0.6438 | 0.7505 | +0.1067 |
| F1 | 0.6807 | 0.7414 | +0.0607 |
| mAP@0.5 | 0.6998 | 0.7796 | +0.0798 |
| mAP@0.5:0.95 | 0.3775 | 0.4644 | +0.0870 |

### 7.3 Counts actually evaluated

| | v1 | v2 |
|---|---|---|
| Images evaluated | 216 | 216 |
| Ground-truth boxes | 390 | 390 |
| — pothole | 98 | 98 |
| — crack | 292 | 292 |
| Skipped images / invalid labels / corrupt | 0 | 0 |
| Run duration (s, CPU) | 35.81 | 28.40 |
| Per-image latency (pre / inf / post, ms) | 2.61 / 88.95 / 2.97 | 2.15 / 68.05 / 1.85 |

### 7.4 Confusion matrices (conf = 0.25, match IoU = 0.45)

**Axis convention (verified from Ultralytics source `ConfusionMatrix.process_batch`,
`matrix[predicted_class, true_class]`):** rows = **predicted**, columns = **true**; the last
row is "predicted background" (= misses/FN) and the last column is "true background" (= false
positives). Column sums reproduce the ground-truth counts exactly.

**v1:**

| pred ↓ / true → | pothole | crack | background |
|---|---|---|---|
| **pothole** | 50 | 5 | 100 |
| **crack** | 0 | 202 | 87 |
| **background** | 48 | 85 | 0 |

→ TP pothole 50, TP crack 202; FN pothole 48, FN crack 85; FP 187 (100 pothole-on-background +
87 crack-on-background); cross-class confusion 5 (pothole-predicted-on-crack) + 0.

**v2:**

| pred ↓ / true → | pothole | crack | background |
|---|---|---|---|
| **pothole** | 71 | 5 | 109 |
| **crack** | 2 | 235 | 133 |
| **background** | 25 | 52 | 0 |

→ TP pothole 71, TP crack 235; FN pothole 25, FN crack 52; FP 242 (109 + 133); cross-class
confusion 5 + 2.

**Reading:** v2 detects markedly more true potholes (71 vs 50) and true cracks (235 vs 202),
and misses far fewer (FN 77 vs 133 total), at the cost of more background false positives
(242 vs 187) at conf 0.25. This is consistent with v2's higher recall/AP and slightly higher
precision (precision is measured over the full PR curve, not at this single threshold).

### 7.5 Per-class precision–recall curves

Ultralytics wrote per-class curves for both runs (available, not embedded here):

- `reports/phase24d/v1_ultralytics_test/BoxPR_curve.png`, `BoxF1_curve.png`, `BoxP_curve.png`, `BoxR_curve.png`
- `reports/phase24d/v2_ultralytics_test/BoxPR_curve.png`, `BoxF1_curve.png`, `BoxP_curve.png`, `BoxR_curve.png`
- plus `confusion_matrix.png`, `confusion_matrix_normalized.png`, and label/prediction sample grids.

---

## 8. v1-versus-v2 comparison — measured results vs interpretation

### 8.1 Measured (facts from §7)

- On the **same** 216-image holdout with **identical** settings, v2 scored **higher than v1 on
  every reported aggregate and per-class metric** (P, R, F1, mAP@0.5, mAP@0.5:0.95).
- The largest measured gaps are in **overall recall (+0.1401)**, **overall mAP@0.5:0.95
  (+0.0771, +30.7%)** and **pothole recall (+0.1735)**.
- The smallest gap is **crack precision (+0.0104)**.

### 8.2 Interpretation (clearly separated from the measurements)

- The measured direction (v2 > v1) is consistent with v2's longer/stronger training schedule,
  but this holdout **cannot** by itself establish *why*, nor that it generalises to other
  sessions. These numbers are a **measurement**, not a causal claim.
- **This is not a promotion decision.** Rule 14 and the phase brief require promotion to be a
  separate, explicitly approved step. No checkpoint was promoted, wired, replaced or deployed.

### 8.3 Why this must not be compared to the old PHASE_09 test metrics

The PHASE_09 test metrics (v1 mAP@0.5 = 0.2615 over the old `data/splits/test.txt`) are **not
directly comparable** to the values here (v1 mAP@0.5 = 0.4842), because **everything that
defines "the test set" changed**:

1. **Different membership.** Old test = 201 images from the original split; new test = the
   216-image date-atomic holdout. Only part of the old test lies in the new holdout.
2. **Different label set.** The derived dataset removes class 2 (manhole, 957 boxes) and one
   zero-area row; 336 images across the dataset became deliberate **background** images.
3. **Different label representation.** The original config resolved to the polygon `labels/`
   directory; the derived config uses axis-aligned `labels/` boxes. Ground truth for the same
   image can differ in shape/area, which changes IoU-based AP.
4. **Different compute device.** PHASE_09 used GPU; this phase used CPU (see §9.2). mAP is
   numerically stable but the run is not device-identical.
5. **Much smaller, single-session holdout.** The new holdout is **one capture date
   (`2025-02-26`)** → high variance and low scene diversity.

**Conclusion:** the date-aware holdout establishes a **new evaluation baseline**. Historical
mAP values under the old split must not be quoted as if they were the same measurement.

### 8.4 Filename dates are only a proxy for capture sessions

Split membership is derived from the **capture date inferred from the filename**. `vlcsnap-*`
timestamps may reflect screenshot wall-clock rather than video content time, so two files that
share a date are **assumed** to be one session. This grouping is a defensible proxy for
session-disjointness, **not** a verified session identity. Every claim of "no leakage" in §5.1
inherits this assumption. It is the best available grouping because the dataset carries no
reliable session metadata.

---

## 9. Warnings, failures and unresolved risks

### 9.1 Warnings

- **W1 (documented).** Filename-derived dates are a proxy for sessions (§8.4).
- **W2 (documented).** The holdout is a single capture date (216 images, 2025-02-26) →
  narrow scene/environment coverage; metrics have wide uncertainty and should not be treated
  as population estimates.
- **W3.** `data/dataset_v2.yaml` and split files use **absolute `D:/…` paths** (pre-existing
  style), so the workspace path is baked in (documented in PHASE 24C).
- **W4.** Ultralytics emitted an informational "Slow image access detected" warning on the
  first CPU run; it reflects the local/AV-scanned storage, not a data problem. It did not
  affect counts or metrics.
- **W5.** The console logs (`*_console.log`) are raw transcripts that contain ANSI progress
  escape codes; the authoritative numbers are in the JSON files.

### 9.2 Failure encountered and resolution (disclosed, not hidden)

- **F1 — first attempt GPU OOM.** The first v1 evaluation on the GPU failed:
  `torch.AcceleratorError: CUDA error: out of memory` during model warm-up. Cause:
  a **competing GPU process** (a running game) held ~7.1 GB of the 8.1 GB VRAM (only
  799–1,535 MiB free; see `device_selection` in the metrics JSON). This is an environment
  condition, **not** a data/checkpoint blocker.
- **Resolution.** Both checkpoints were evaluated on **CPU** (identical device for both), with
  the reason recorded in `device_selection.reason`. Metrics are valid and reproducible; the
  device differs from the historical GPU runs and is disclosed as a limitation.
- **F2 — logging-harness metadata defect (fixed).** One intermediate CPU run of v1 produced
  correct metrics but an incomplete metadata capture (ground-truth-image counts were not
  written by the harness). The harness was corrected and v1 was re-run once. The two CPU runs
  produced **identical** metrics (overall P 0.5360, R 0.5617, mAP@0.5 0.4842,
  mAP@0.5:0.95 0.2512), which also evidences determinism. Only the final run's JSON is the
  authoritative record.
- **F3 — transient Ultralytics cache.** Ultralytics always writes `data/derived_2class/labels.cache`
  when scanning labels (this is built into its dataset loader and cannot be disabled via the
  `cache` flag). It was created during evaluation and **removed afterwards**; the derived tree
  is verified restored (`derived_tree_has_no_cache_artifact: PASS`). No image, label, split,
  config or checkpoint was altered.

### 9.3 Unresolved risks / limitations

- **Outside-test-band generalisation is unmeasured:** the derived test set is a single date;
  no second independent or cross-session holdout exists.
- **CPU vs GPU difference:** metrics were computed on CPU; GPU reruns (when the GPU is free)
  should be expected to be numerically near-identical but are not run here.
- **Background false positives are high** at conf 0.25 for both models (FP 187 / 242). The
  serving confidence (0.25, `config/detection.yaml`) is not changed by this phase; downstream
  precision at that operating point deserves a separate review.
- **Old-vs-new comparability is permanently broken** by the PHASE 24B/24C decisions; any
  future comparison must use the derived holdout.

---

## 10. Files created or modified; final Git state

### 10.1 Created this phase (all NEW)

```
scripts/audit/phase24d_evaluate_holdout.py        (new evaluation harness; read-only w.r.t. data/models)
reports/phase24d/holdout_verification.json
reports/phase24d/v1_metrics.json
reports/phase24d/v2_metrics.json
reports/phase24d/comparison.json
reports/phase24d/v1_console.log
reports/phase24d/v2_console.log
reports/phase24d/v1_ultralytics_test/             (plots + sample grids)
reports/phase24d/v2_ultralytics_test/             (plots + sample grids)
docs/reports/PHASE_24D_FRESH_HOLDOUT_EVALUATION.md  (this report)
```

### 10.2 Modified / deleted

- **Modified:** none. No original or derived dataset file, annotation, split, config or
  checkpoint was written.
- **Deleted:** `data/derived_2class/labels.cache` — a transient file **created by**
  Ultralytics during evaluation, removed to restore the derived tree (it did not exist before
  PHASE 24D).

### 10.3 Final `git status --short`

```
?? data/dataset_v2.yaml
?? data/derived_2class/
?? data/splits_v2/
?? docs/reports/PHASE_24A_DATASET_AUDIT.md
?? docs/reports/PHASE_24B_DATASET_CLEANING_PROPOSAL.md
?? docs/reports/PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md
?? docs/reports/PHASE_24_BASELINE_AUDIT.md
?? reports/phase24a/
?? reports/phase24b/
?? reports/phase24d/
?? scripts/audit/phase24a_dataset_audit.py
?? scripts/audit/phase24a_session_leakage.py
?? scripts/audit/phase24b_split_proposal.py
?? scripts/audit/phase24d_evaluate_holdout.py
?? scripts/build_derived_dataset_v2.py
```

- `git diff --stat` → **empty** (0 tracked files changed).
- HEAD unchanged at `5645dcb57e3279ce059c98250e0674684eb6e9da`; **nothing committed or pushed**.
- All pre-existing untracked user files preserved.

### 10.4 Hash-unchanged confirmation

- **Checkpoints:** v1 `61F6EDA2…8078E65`, v2 `B6354A56…DF8800BA` — both re-measured after the
  runs and **unchanged**.
- **Original data:** images / `labels-YOLO` / polygon `labels` Merkles and the original
  `train/val/test` split hashes and `data/dataset.yaml` — all re-measured after the runs and
  **unchanged** (§4.3).
- **Derived data:** derived labels Merkle, MANIFEST.json and README.md **unchanged**; no
  `labels.cache` remains (§9.2 F3).

---

## 11. Validation checks run on the generated deliverables

`scripts/audit/phase24d_evaluate_holdout.py verify` — **all 30 checks PASS**, including
checkpoint hashes, dataset/split hashes, derived-labels Merkle, source integrity, holdout
identity (216 images / 390 boxes / 46 backgrounds), image-byte matching against
`split_manifest.csv`, and date/stem non-overlap.

Report/output validity checks:

| Check | Result |
|---|---|
| `holdout_verification.json` parses and `all_checks_ok = true` | **PASS** |
| `v1_metrics.json`, `v2_metrics.json` parse; contain overall + per-class + confusion matrix | **PASS** |
| `comparison.json` parses; `identical_eval_settings = true`, `same_holdout_for_both = true` | **PASS** |
| Confusion-matrix column sums equal ground-truth counts (98 / 292) for both models | **PASS** |
| Both metrics JSON report `images_evaluated = 216`, `gt_boxes_total = 390` | **PASS** |
| Both metrics JSON report `data_integrity.content_unchanged = true` | **PASS** |
| Report file exists with all required sections | **PASS** |

## 12. Stop condition

Both authorized evaluations, verification and reporting are complete. **No training,
fine-tuning, model promotion, deployment or PHASE 25 work was started.** The v2 checkpoint,
although measured higher on this holdout, remains **not wired and not promoted**
(`config/detection.yaml` still references v1). Any promotion, retraining, dataset change, or
follow-on phase requires **separate explicit approval**.
