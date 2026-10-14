# YOLO11 + OpenCV Functional Verification

> **Status:** Complete · **Date:** 2026-10-14 · **Workspace:** `D:\New folder (3)`
> **Governing:** master_rules.md (4, 5, 6, 7, 9, 14, 18, 20), docs/TRAINING_RULES.md
> **Scope:** read-only audit. No retraining, no checkpoint overwrite, no dataset change.
> **Evidence:** `reports/phase21_yolo_opencv/evidence.json` (machine output).
> **Script:** `scripts/verify_yolo_opencv.py` (command: `.\.venv\Scripts\python.exe scripts\verify_yolo_opencv.py`).

## 0. Verdict summary

| # | Component | Verdict |
|---|---|---|
| 2 | OpenCV import / version / load / resize / colour / preprocess / draw | **PASS** |
| 3 | YOLO11 `best.pt` load + inference on real images | **PASS** |
| 4 | Class IDs/names, thresholds, bbox coords, dims, outputs | **PASS** (with 1 config defect, #7) |
| 5 | Full pipeline trace (image→preproc→infer→aggregate→score) | **PASS** |
| 6 | Positive + negative/control images; FP/FN on labelled test sample | **PASS** (low accuracy, disclosed) |
| 7 | Confidence-threshold consistency | **FAIL** |
| 8 | Relevant tests | **PASS** (48) + 1 new failing regression test exposing #7 |

**The single functional defect is #7 (detector `conf 0.15` vs aggregator `0.25`).**

## 1. Governing docs & configuration (read)

- `master_rules.md` — Rules 4 (YOLO11), 5 (class honesty), 6 (OpenCV), 7 (risk engine owns scores), 9 (missing ≠ safe), 14 (measured only), 20 (honesty).
- `docs/TRAINING_RULES.md` — gates G1–G13; test isolation; §8 integration.
- `config/preprocessing.yaml` (preprocess-v1), `config/detection.yaml` (detect-v2, `conf 0.15`), `config/hazard_severity.yaml` (`confidence_threshold 0.25`), `config/risk_engine.yaml` (`lambda_decay 0.10`).

## 2. OpenCV — PASS

Command output (`evidence.sections.opencv`):
- `cv2` 4.14.0, numpy 2.5.3; `imread` on a real project image OK (shape 360x640x3).
- BGR→RGB OK; `cv2.resize` to 320x320 OK; letterbox → **(640, 640, 3)**, pad `[0,140]`, ratio `[1.0,1.0]`.
- `validate_image`: real→`ok`; empty file→`empty`; 16x16→`too_small`; missing→`unreadable`.
- `prepare_inference_input` → float32 tensor shape **(3, 640, 640)**, range **[0.0, 1.0]**.
- `visualise` returns a same-shape copy and writes the annotated file; source untouched.

## 3. YOLO11 checkpoint load + inference — PASS

- Loaded `models\training\saferoute-yolo11-v1\weights\best.pt`
  sha256 `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65`
  (matches PHASE_09 accepted hash).
- Device CPU for this audit; model_version `saferoute-yolo11-v1`, detector `detect-v2`.
- Inference succeeded on 8 real images (status `success`; e.g. 6 detections on one frame).

## 4. Classes / thresholds / bbox / dims — PASS

- `SUPPORTED_CLASSES = {0: pothole, 1: crack}`; model `names = {0: pothole, 1: crack}` — consistent.
- Detection records carry `hazard_class`, `confidence ∈ [0,1]`, `bbox_xyxy` (source pixels), `bbox_norm` (clamped [0,1]), image dims; JSON-serializable.
- Inference thresholds: `imgsz 640`, `iou 0.45`, `max_det 300`, **detector `conf 0.15`**.

## 5. Full pipeline trace — PASS

On a real pothole/crack image:
`image → PreprocessingPipeline.preprocess → HazardDetector.detect (6 raw dets) →
HazardAggregator.assess_segment (3 hazards after conf/dedup) → aggregate_hazard 6.27 →
DeterministicRiskEngine.score_route → route_score 4.35, status assessed, coverage 1.0`.

- Zero-detection control (grey image): 0 hazards, coverage 1.0, **route_score 100.0**.

## 6. Positive & negative images; FP/FN on labelled test sample — PASS (low accuracy)

- **Negative control:** uniform grey image → `no_detections` (0 boxes) — no spurious positive on blank.
- **Labelled evaluation** on the **held-out `data/splits/test.txt`** (first 40 images), class-aware greedy matching at IoU 0.5, classes 0/1 only:

| Detector conf | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| 0.15 | 14 | 83 | 50 | 0.144 | 0.219 |
| 0.25 | 11 | 46 | 53 | 0.193 | 0.172 |

- Per-class @0.15: crack TP9/FP61/FN16; pothole TP5/FP22/FN34.
- **Caveat:** 40-image sample, not the full test set; greedy matching. These are measured on held-out data (no tuning). They are consistent with the low PHASE_09 metrics — **no accuracy is claimed beyond this sample.**

## 7. Confidence-threshold consistency — FAIL (root cause of "zero hazards → 100")

- **Detector** `config/detection.yaml inference.conf = 0.15`.
- **Aggregator** `config/hazard_severity.yaml thresholds.confidence_threshold = 0.25`.
- `HazardAggregator.process_detection` drops every detection with
  `confidence < 0.25` (`aggregate.py`), while the detector emits down to `0.15`.
- Measured over 15 real images: **56 raw detections @0.15 → 20 dropped (36%) → 36 kept**; observed conf range `[0.1503, 0.6959]`.
- **Why the earlier pipeline showed zero hazards and score 100:** when a fully
  covered segment's surviving detections are all `< 0.25` (or none are emitted),
  the segment has `aggregate_hazard = 0` → `H_i = 0` → `S_i = 100 * exp(0) = 100.0`.
  A 100 score therefore meant "no hazard *survived the aggregator*", not "safe road".
- Additional contributing factor: if imagery is unavailable the segment is
  `unassessed` (score `None`, not 100) — so the "100" case is specifically the
  **assessed-but-zero-surviving-hazards** case, amplified by the threshold gap.

**Recommended fix (not applied — config change needs approval):** set the
aggregator `confidence_threshold` equal to the detector `conf` (or raise the
detector `conf` to `0.25`), so no produced detection is silently discarded. The
new test `tests/unit/test_threshold_consistency.py` encodes this contract and
**currently fails**, by design, to surface the defect.

## 8. Tests — PASS (existing) + 1 failing regression test

- `.\.venv\Scripts\python.exe -m unittest tests.unit.test_preprocessing tests.unit.test_detection tests.unit.test_hazard_aggregation tests.unit.test_risk_engine tests.integration.test_end_to_end_pipeline` → **Ran 48 tests … OK**.
- Added `tests/unit/test_threshold_consistency.py` (config-only, fast). **FAILS** with:
  `AssertionError: 0.15 != 0.25 : Detector conf (0.15) != aggregator confidence_threshold (0.25)`.
- No existing test was modified to hide a failure.

## 9. Notes / PARTIALLY VERIFIED items

- The detector feeds an already-letterboxed 640x640 image into `model.predict(imgsz=640)`,
  so Ultralytics letterboxes again (identity here). Not incorrect, but double
  preprocessing is redundant — marked **PARTIALLY VERIFIED** (works, but should be
  reviewed to avoid future pad-mapping drift).
- Accuracy figures are limited to a 40-image labelled sample; full-test metrics
  for v1/v2 were **not** recomputed here. No metric is fabricated.



