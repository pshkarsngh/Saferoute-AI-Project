# SafeRoute AI — PHASE 24E: Real-Image Detection-Pipeline Verification

> **Phase:** PHASE 24E — run the *shipped application* detection pipeline on the
> PHASE 24C derived two-class **test** holdout; render prediction visualisations and
> a JSON summary; report pothole/crack separately, background-only images, false
> positives, missed detections, confidence scores and bounding-box alignment.
> **Date executed:** 2026-10-15/16 (UTC) · **Workspace:** `D:\New folder (3)` · **Branch:** `main`
> **Mode:** **Evaluation only.** No training, fine-tuning, resume, weight change,
> checkpoint change, v2 promotion, dataset/split change, dependency change,
> download, commit or push.
> **Governing rules:** `master_rules.md` Rules 1, 3, 5, 6, 7, 9, 14, 15, 16, 18, 19, 20.
> **Inputs:** `PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md`, `data/dataset_v2.yaml`,
> `data/splits_v2/test.txt`, `data/derived_2class/`.
> **Related:** `PHASE_24D_FRESH_HOLDOUT_EVALUATION.md` (Ultralytics mAP evaluation of v1/v2).

Evidence labels: **VERIFIED** (measured this phase) · **PARTIALLY VERIFIED** · **BLOCKED**.

---

## 1. Executive summary

The **actual application component** — `src.detection.detector.HazardDetector`
(module `detect-v2`, model `saferoute-yolo11-v1`, PHASE 06 `preprocess-v1` OpenCV
pipeline) — was executed on the **configured** checkpoint over the **entire** PHASE 24C
two-class test holdout (216 images, 390 boxes, 46 background-only images). Predictions
were matched to ground truth at IoU ≥ 0.5 and compared to the derived labels.

**VERIFIED.** The pipeline resolved all 216 images and all 390 ground-truth boxes with
zero skipped images, zero invalid images and zero extract/inference errors. In total it
emitted **415 predictions at the serving confidence 0.25** (pothole 149, crack 266).

| Operating point | Overall (micro) | Pothole | Crack |
|---|---|---|---|
| conf 0.25 (config) · match IoU 0.5 | P **0.586**, R **0.623**, F1 **0.604** | P 0.322 / R 0.490 / F1 0.389 | P 0.733 / R 0.668 / F1 0.699 |

- **Pothole is weak**: only **48 / 98** true potholes matched (recall 0.490) and
  **101 of the 149** pothole predictions did **not** match any same-class GT (precision 0.322).
- **Crack is comparatively strong**: **195 / 292** true cracks matched (recall 0.668),
  precision 0.733 — consistent with the PHASE 24D finding that crack is the easier class.
- **Background-only images are fragile**: of the 46 images that deliberately contain **no**
  target hazard, **36 (78.3%)** still produced at least one false positive; only 10 were clean.
- **Bounding-box alignment of matched boxes is good**: mean IoU 0.763 (pothole) and
  0.779 (crack); no matched pair below 0.506.
- **Class confusion is minimal but real**: 5 crack boxes were localized correctly but
  predicted as **pothole** (IoU 0.66–0.91); there were **no** crack-predictions on pothole GT.

> **Metric note (important):** these are **thresholded operating-point** precision/recall/F1
> at the serving confidence (0.25) and match IoU 0.5 — **not** mAP, and **not** directly
> comparable to the PHASE 24D values (v1 mAP@0.5 = 0.4842, mAP@0.5:0.95 = 0.2512), which were
> computed by Ultralytics' evaluator at conf 0.001 with its own dataset/letterbox path. See §8.

**Not done (by instruction):** no training/tuning, no checkpoint change, no promotion of v2,
no dataset/split change, no commit/push. `config/detection.yaml` still points at v1.

---

## 2. Scope and non-negotiable guardrails

In scope and executed:

- Run the **shipped** `HazardDetector` (not raw `YOLO.predict`) with `config/detection.yaml`.
- Use `data/splits_v2/test.txt` and the derived two-class labels in `data/derived_2class/labels/`.
- Match predictions to GT (per-class greedy, IoU ≥ 0.5); report per class + background.
- Write only under `reports/phase24e/`; produce visualisations for every image and a JSON summary.

Explicitly **not** done: no training/fine-tuning/resume, no weight or checkpoint change,
no v2 load/promotion/deployment, no dataset/annotation/split/config modification, no
download, no package install, no commit/push, and no use of train/val data as a substitute
for the test holdout.

**Design constraint (Rule 18):** PHASE 24D's harness (`phase24d_evaluate_holdout.py`) is
an Ultralytics `val()` mAP harness and does not exercise the application pipeline. A new,
separate harness was created — `scripts/audit/phase24e_real_image_detection.py` — which
imports and drives `src.detection.detector.HazardDetector`. It writes **only** under
`reports/phase24e/` and never touches the PHASE 24D outputs.

---

## 3. Exact command(s) executed

All commands were run from `D:\New folder (3)` using the workspace virtual environment.

```powershell
# 0) Relevant verification test suite (detection + preprocessing + consistency + end-to-end)
.\.venv\Scripts\python.exe -m unittest tests.unit.test_detection tests.unit.test_detection_outcome `
    tests.unit.test_preprocessing tests.unit.test_threshold_consistency `
    tests.integration.test_end_to_end_pipeline

# 1) Smoke test on the first 12 holdout images (device auto -> CPU because the GPU was busy)
.\.venv\Scripts\python.exe scripts\audit\phase24e_real_image_detection.py --device auto --limit 12

# 2) Full run over the 216-image PHASE 24C test holdout
.\.venv\Scripts\python.exe scripts\audit\phase24e_real_image_detection.py --device auto
```

### 3.1 Evaluation parameters (from `config/detection.yaml`, unchanged)

| Parameter | Value |
|---|---|
| Pipeline | `src.detection.detector.HazardDetector` (`detect-v2`), `preprocess-v1` |
| Checkpoint | `models/training/saferoute-yolo11-v1/weights/best.pt` (the configured one) |
| `imgsz` | 640 |
| `conf` | **0.25** (from config; equals `config/hazard_severity.yaml`) |
| `iou` (NMS) | 0.45 |
| `max_det` | 300 |
| `augment` | false |
| Match IoU (scoring) | **0.5** |
| Device | **cpu** (see §7.2) |

### 3.2 Software / environment (VERIFIED)

| Item | Value |
|---|---|
| Python | 3.12.10 |
| OS | Windows-11 (`Windows-11-10.0.26300-SP0`) |
| PyTorch | 2.13.0+cu130 |
| Ultralytics | 8.4.163 |
| OpenCV | 4.14.0 |
| NumPy | 2.5.3 |
| GPU present | NVIDIA GeForce RTX 5050 Laptop GPU (7.93 GiB) — **busy**, see §7.2 |

---

## 4. Holdout identity verification (VERIFIED)

Verified independently inside the harness (raw split-file + label parsing) and asserted
by `verification_checks.holdout_identity_ok = true`:

| Check | Result |
|---|---|
| Images in `data/splits_v2/test.txt` | **216** |
| Images whose file exists / decoded | **216** (0 missing, 0 unreadable) |
| Images with a derived label file | **216** |
| Ground-truth boxes total | **390** — pothole **98**, crack **292** |
| Background-only (empty-label) images | **46** |
| Checkpoint SHA-256 unchanged after run | **true** |
| Config / split / labels content unchanged after run | **true** |

Hashes recorded this phase:

| Artifact | SHA-256 / Merkle (measured) |
|---|---|
| v1 checkpoint `best.pt` | `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65` |
| `data/dataset_v2.yaml` | `98EDD97ADDF2F72779335E6622D575C0C3B88E2C7BDF88ADAD31BDD3D62C1912` |
| `data/splits_v2/test.txt` | `AABA32ABA36C668145017715CC4C9190D0C58457EBE6CD66D515EF9BE0325D07` |
| `config/detection.yaml` | `B1119A466412B759F06CF841E32556EF2E0007FB8F5A4A260316AACFD99231EF` |
| Derived test-labels Merkle (216 files) | `1519313E262BF5B48D8E6C5989E1D45E878D5419C1916741A4F340A459A732C2` |

The checkpoint hash matches the PHASE 24D/24C documented v1 value, and the labels Merkle
was identical before and after the run.

---

## 5. Methodology (matching protocol)

1. For each image, GT boxes are parsed from the derived YOLO labels (normalized
   `cls cx cy w h` → pixel `xyxy` using the image dimensions).
2. The shipped `HazardDetector.detect(path, conf=<config>)` is called (the exact application
   path — OpenCV validation, PHASE 06 letterbox preprocessing, YOLO predict, box
   rescaling back to source pixels). Only supported classes (`pothole`, `crack`) are scored.
3. **Per-class greedy matching**: predictions sorted by confidence; a prediction matches the
   highest-IoU **same-class** ground-truth box with IoU ≥ 0.5. Unmatched predictions are
   **false positives**; unmatched GT boxes are **missed detections** (FN).
4. Per missed GT, the nearest prediction of *any* class is recorded to distinguish
   "no nearby prediction" from "localized but not matched".
5. An additional **class-aware** pass greedily pairs leftover predictions/GTs by geometry
   alone (any class), exposing "right box, wrong class" errors on the off-diagonal.

This is the standard VOC/COCO per-class convention: cross-class overlaps count as an FP
plus an FN in the headline per-class metrics, and are additionally surfaced as cross-class errors.

---

## 6. Results (VERIFIED, measured)

Authoritative machine-readable records: `reports/phase24e/real_image_detection_summary.json`
(plus `false_positives.csv`, `missed_detections.csv`, `cross_class_errors.csv` and
`visualizations/`). Raw console transcript: `reports/phase24e/console.log`.

### 6.1 Per-class and overall metrics at the serving operating point

| Class | GT | Pred | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| pothole | 98 | 149 | 48 | 101 | 50 | 0.322 | 0.490 | 0.389 |
| crack | 292 | 266 | 195 | 71 | 97 | 0.733 | 0.668 | 0.699 |
| **overall (micro)** | 390 | 415 | **243** | **172** | **147** | **0.586** | **0.623** | **0.604** |

### 6.2 Inference throughput / statuses

| | Value |
|---|---|
| Images processed | 216 |
| Status `success` (≥1 detection) | 202 |
| Status `no_detections` (0 detections) | 14 |
| Predictions total | 415 (pothole 149, crack 266) |
| Per-image total latency (ms) | min 101.0 / mean 186.5 / median 161.3 / max **3516.8** |
| Per-image inference latency (ms) | min 97.4 / mean 182.6 / median 157.7 / max **3512.7** |

The single ~3.5 s maximum is a first-image warm-up / storage-access outlier on CPU (the
dataset folder is virus-scanned, the same "slow image access" note as PHASE 24D W4); the
median is 161 ms.

### 6.3 Confusion matrices

**Axis convention:** `matrix[predicted][true]`; classes `[pothole, crack, background]`.

**(a) Per-class (VOC/COCO) — a same-class match is a TP; cross-class overlap is FP + FN:**

| pred ↓ / true → | pothole | crack | background |
|---|---|---|---|
| **pothole** | 48 | 0 | 101 |
| **crack** | 0 | 195 | 71 |
| **background** | 50 | 97 | 0 |

Column sums: `[98, 292, 172]` (= GT pothole, GT crack, FP total). Row sums equal prediction counts.

**(b) Class-aware — leftover predictions/GTs paired by geometry alone (exposes class confusion):**

| pred ↓ / true → | pothole | crack | background |
|---|---|---|---|
| **pothole** | 48 | **5** | 96 |
| **crack** | 0 | 195 | 71 |
| **background** | 50 | **92** | 0 |

**Reading:** the model has **no** crack-on-pothole confusion and only **5** pothole-on-crack
confusions (crack GT that it boxed as a pothole). The dominant error is **background false
positives**: 96 pothole + 71 crack predictions land on no GT box at all.

### 6.4 Background-only image analysis (the deliberate 46)

| | Value |
|---|---|
| Background-only images | **46** |
| Images with ≥1 false positive | **36** |
| Images that were clean (0 detections) | **10** |
| Clean rate | **0.2174 (21.7%)** |
| False positives on background-only images | **55** of the 172 total FPs |

This is the clearest failure mode: on genuinely hazard-free frames the pipeline still
fires ~78% of the time — the same high-background-FP behaviour PHASE 24D flagged for v1 at
conf 0.25.

### 6.5 Cross-class errors (detail: `cross_class_errors.csv`)

| Image | Pred | Conf | GT | IoU |
|---|---|---|---|---|
| `vlcsnap-2025-02-26-20h34m36s821` | pothole | 0.4222 | crack | 0.784 |
| `vlcsnap-2025-02-26-20h35m40s539` | pothole | 0.5777 | crack | 0.872 |
| `vlcsnap-2025-02-26-20h36m41s285` | pothole | 0.3609 | crack | 0.910 |
| `vlcsnap-2025-02-26-20h39m22s097` | pothole | 0.8322 | crack | 0.875 |
| `vlcsnap-2025-02-26-20h40m30s059` | pothole | 0.3771 | crack | 0.660 |

All 5 are `pothole → crack`.

### 6.6 Confidence scores

| Class | Set | n | min | mean | median | max |
|---|---|---|---|---|---|---|
| pothole | all predictions | 149 | 0.251 | 0.486 | 0.472 | 0.870 |
| pothole | TP | 48 | 0.257 | 0.494 | 0.486 | 0.808 |
| pothole | FP | 101 | 0.251 | 0.483 | 0.422 | 0.870 |
| crack | all predictions | 266 | 0.252 | 0.544 | 0.528 | 0.932 |
| crack | TP | 195 | 0.252 | 0.586 | 0.588 | 0.932 |
| crack | FP | 71 | 0.253 | 0.430 | 0.388 | 0.855 |

**Reading:** crack TP confidences are clearly higher than crack FP confidences
(mean 0.586 vs 0.430) — confidence is informative for crack. For **pothole** the TP and FP
confidence distributions are almost identical (mean 0.494 vs 0.483; FP median even lower),
so **confidence does not separate pothole TPs from FPs** at this operating point, and some
false positives reach high confidence (max 0.870).

### 6.7 Bounding-box alignment (matched pairs)

| Class | n matched | min IoU | mean IoU | median IoU | max IoU |
|---|---|---|---|---|---|
| pothole | 48 | 0.573 | 0.763 | 0.762 | 0.936 |
| crack | 195 | 0.506 | 0.779 | 0.802 | 0.960 |

When the pipeline does localize a hazard, the box is well aligned — median IoU ≈ 0.76–0.80.

### 6.8 Missed detections (detail: `missed_detections.csv`)

| | Value |
|---|---|
| Missed detections total | **147** (pothole 50, crack 97) |
| Localized but not matched (nearest prediction IoU ≥ 0.5) | **5** (all the cross-class pothole→crack cases) |
| No nearby prediction (nearest any-class IoU < 0.5) | **142** |

**Reading:** the overwhelming majority of misses are **genuine non-detections**, not
localization drift — the pipeline simply produced no overlapping box. Only 5 misses had a
good geometric box (of the wrong class).

---

## 7. Points of honest disclosure

### 7.1 These metrics are not mAP and not comparable to PHASE 24D directly

The numbers here are **single-threshold** precision/recall/F1 at the *serving* confidence
(0.25) and a **different match IoU (0.5** vs Ultralytics' 0.45 confusion-matrix IoU). They
are a *deployment operating-point* measurement of the application pipeline, whereas PHASE 24D
reported Ultralytics mAP computed at conf 0.001. They answer different questions and must
not be compared head-to-head. The qualitative picture agrees with PHASE 24D (crack ≫ pothole,
large background FP volume).

### 7.2 Device: CPU (disclosed, not hidden)

`--device auto` was selected. At run time the GPU held only **1.33–1.74 GiB of 7.93 GiB**
free (a competing process — the same environment condition PHASE 24D hit), below the
harness' 2 GiB CUDA safety margin, so the run used **CPU** with the reason recorded in
`application_detector.device_reason`. CPU vs GPU can change detections slightly; this is a
disclosed limitation. A GPU rerun (when the GPU is free) would need its own record.

### 7.3 Single-session holdout

The holdout is one capture date (`2025-02-26`, 216 images) — narrow scene/environment
coverage. These are measurements on that holdout, not population estimates.

### 7.4 Per-class matching convention

Headline FP/FN use per-class matching (VOC/COCO). Cross-class overlaps therefore appear as
an FP + FN there; §6.5 and the class-aware matrix (§6.3b) surface them explicitly.

---

## 8. Files created or modified; final Git state

### 8.1 Created this phase (all NEW)

```
scripts/audit/phase24e_real_image_detection.py          (new harness; read-only w.r.t. data/models/config)
reports/phase24e/real_image_detection_summary.json      (full machine-readable summary incl. per-image)
reports/phase24e/false_positives.csv                    (172 rows + header)
reports/phase24e/missed_detections.csv                  (147 rows + header)
reports/phase24e/cross_class_errors.csv                 (5 rows + header)
reports/phase24e/console.log                            (raw console transcript)
reports/phase24e/visualizations/                        (216 annotated JPEGs; GT green, matches class-coloured, FPs magenta)
docs/reports/PHASE_24E_REAL_IMAGE_DETECTION.md          (this report)
```

### 8.2 Modified / deleted

- **Modified:** none. No dataset, annotation, split, config or checkpoint file was written.
- **Deleted:** none. No transient `labels.cache` was produced by the application pipeline
  (it does not use the Ultralytics dataset loader), so nothing needed cleanup.

### 8.3 Final `git status --short`

```
?? data/dataset_v2.yaml
?? data/derived_2class/
?? data/splits_v2/
?? docs/reports/PHASE_24A_DATASET_AUDIT.md
?? docs/reports/PHASE_24B_DATASET_CLEANING_PROPOSAL.md
?? docs/reports/PHASE_24C_DERIVED_DATASET_CONSTRUCTION.md
?? docs/reports/PHASE_24D_FRESH_HOLDOUT_EVALUATION.md
?? docs/reports/PHASE_24E_REAL_IMAGE_DETECTION.md
?? docs/reports/PHASE_24_BASELINE_AUDIT.md
?? reports/phase24a/
?? reports/phase24b/
?? reports/phase24d/
?? reports/phase24e/
?? scripts/audit/phase24a_dataset_audit.py
?? scripts/audit/phase24a_session_leakage.py
?? scripts/audit/phase24b_split_proposal.py
?? scripts/audit/phase24d_evaluate_holdout.py
?? scripts/audit/phase24e_real_image_detection.py
?? scripts/build_derived_dataset_v2.py
```

- `git diff --stat` → **empty** (0 tracked files changed).
- HEAD unchanged at `5645dcb57e3279ce059c98250e0674684eb6e9da`; **nothing committed or pushed**.
- All pre-existing untracked user files preserved.

### 8.4 Hash-unchanged confirmation

- **Checkpoint (v1):** `61F6EDA2…8078E65` — re-measured after the run, **unchanged**.
- **Derived test labels (216):** Merkle `1519313E…732C2` — identical before and after.
- **`data/dataset_v2.yaml`, `data/splits_v2/test.txt`, `config/detection.yaml`:** hashes
  re-measured after the run, **unchanged**.
- `verification_checks.content_unchanged = true`.

---

## 9. Validation checks run

Relevant application test suite (detection + preprocessing + threshold consistency + E2E):

```
Ran 34 tests in 20.799s
OK
LASTEXITCODE=0
```

Report/output validity checks:

| Check | Result |
|---|---|
| `holdout_identity_ok` (216 imgs / 390 boxes / 98 pothole / 292 crack / 46 bg) | **PASS** |
| `checkpoint_sha256_unchanged` | **PASS** |
| `content_unchanged` (config/split/labels/checkpoint) | **PASS** |
| Confusion-matrix column sums reproduce GT counts (98 / 292) | **PASS** |
| Per-class TP+FP == prediction count; TP+FN == GT count (both classes) | **PASS** |
| `per_image` records == 216; Σtp=243, Σfp=172, Σfn=147 == headline | **PASS** |
| 216 visualisation JPEGs written | **PASS** |
| CSV row counts (FP 172, FN 147, cross-class 5) match JSON | **PASS** |

---

## 10. Conclusion and stop condition

The application detection pipeline was exercised end-to-end on the authorized PHASE 24C
test holdout and its real results are now recorded. Measurement summary: **crack detection is
usable at the serving threshold (P 0.733 / R 0.668), pothole detection is weak
(P 0.322 / R 0.490), and background false positives are the dominant error (36/46
hazard-free images still produced detections).** Matched boxes are well aligned
(median IoU ≈ 0.76–0.80) and class confusion is minimal (5 pothole→crack boxes).

**No training, fine-tuning, checkpoint change, v2 promotion, deployment or dataset/split
change was performed.** `config/detection.yaml` still references v1. Any promotion,
retraining, threshold change, dataset change, or follow-on phase (e.g. PHASE 25) requires
**separate explicit approval**.

### Pending / not claimed

- No GPU-device rerun (GPU was busy; CPU run disclosed).
- No mAP recomputation on the application pipeline (PHASE 24D mAP stands separately).
- No threshold sweep, calibration or mitigation of the background false positives
  (would be a new, separately-approved phase).
- No second independent / cross-session holdout exists.
