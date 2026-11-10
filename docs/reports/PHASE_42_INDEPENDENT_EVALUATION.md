# PHASE 42 — Independent YOLO11 v2 Detector Evaluation

> **Phase status:** Harness complete; real independent evaluation **NOT_ASSESSED**  
> **Date:** 2026-11-10  
> **Branch/HEAD:** `main` @ Phase 42 harness (parent `47cdb10`)  
> **Environment:** Windows 11, Python 3.12.10, torch 2.13.0+cu130, CUDA available
> (NVIDIA GeForce RTX 5050 Laptop GPU), ultralytics 8.4.163, opencv 4.14.0, numpy 2.5.3

---

## 1. Executive status

Phase 42 built an **evaluation-first, independent evaluation harness** for the
serving YOLO11 v2 detector, with negative tests written before any dataset
evaluation.

**No accuracy, safety, or deployment-readiness claim is made.** The genuine
`saferoute-yolo11-v2` checkpoint is not present in this workspace, and no
independently collected, session-disjoint dataset exists locally. Therefore the
real independent evaluation is **NOT_ASSESSED**, not PASS, CONDITIONAL, or FAIL.

What *is* verified:

- The production inference contract is asserted and matches the serving config.
- The configured checkpoint path currently holds the non-production **P0 smoke
  substitute** and is refused for a real evaluation (exit code 2).
- The evaluator, leakage checks, metrics, route replay, CLI, and their negative
  tests all execute successfully.
- The existing test baseline is preserved: **423 tests OK** (351 prior + 72 new).

The smoke substitute must never be reported as v2. No substitute weights were
loaded to produce metrics.

---

## 2. Scope and safety guardrails

Phase 42 evaluates **detector evidence reliability only**. It does not certify
SafeRoute AI as safe for public deployment.

Explicit non-changes:

- `src/risk/engine.py` is unchanged.
- The risk formulas are unchanged:
  `H_i = Σ severity / max(km, 0.1)` and `S_i = 100 · e^(−0.10 · H_i)`.
- `config/detection.yaml` and `config/hazard_severity.yaml` are unchanged.
- The serving checkpoint is never overwritten or modified by evaluation.
- `.env`, Mapillary tokens, and other secrets are not read or emitted.
- Route replay is **offline research only** and does not alter production
  recommendation behavior.

---

## 3. Readiness assessment

| Requirement | State | Evidence |
|---|---|---|
| Genuine `saferoute-yolo11-v2` serving checkpoint | **NOT AVAILABLE** | Canonical path holds the P0 smoke substitute (`sha256 19619F99…60B916D0`, 5,443,482 bytes) with `P0_SMOKE_SUBSTITUTE.json` |
| Independent, session-disjoint imagery + labels | **NOT AVAILABLE** | `data/independent/` does not exist; no separate-session road collection is present |
| Independent annotation policy + A/B QC + adjudication | **NOT AVAILABLE** | No independent manifest/QC record exists |
| Reference-corpus session/image list for leakage proof | **NOT AVAILABLE** | Only historical split manifests exist; they are not a complete reference-session registry |
| Production inference configuration | **AVAILABLE** | Verified below (`imgsz=640`, `conf=0.25`, `iou=0.45`, `max_det=300`, classes pothole/crack) |
| Single-confidence contract | **VERIFIED** | `detection.yaml inference.conf = 0.25` equals `hazard_severity.yaml thresholds.confidence_threshold = 0.25` |
| Evaluation harness | **COMPLETE** | `src/evaluation/` + `scripts/evaluate_independent.py` + 72 tests |
| Runtime environment | **AVAILABLE** | CUDA GPU present; ultralytics/OpenCV/numpy importable |

Because the first seven rows include missing checkpoint and missing data, **no
real evaluation could be executed**. This is a data/artifact availability
failure, not a detector result.

---

## 4. Production inference contract verified

| Setting | Required | Loaded | Status |
|---|---|---|---|
| `imgsz` | 640 | 640 | PASS |
| `inference.conf` | 0.25 | 0.25 | PASS |
| `inference.iou` | 0.45 | 0.45 | PASS |
| `max_det` | 300 | 300 | PASS |
| Trained classes | 0=pothole, 1=crack | 0=pothole, 1=crack | PASS |
| `hazard_severity.thresholds.confidence_threshold` | 0.25 | 0.25 | PASS |
| Checkpoint path | `models/training/saferoute-yolo11-v2/weights/best.pt` | Present but smoke substitute | **REFUSED** |

Artifact hashes recorded during this phase:

| Artifact | SHA-256 |
|---|---|
| `config/detection.yaml` | `22371AE8C1DA3CBA77E40EE096337915D16C0CFDDB9E7E2AF9213F4BE1B18344` |
| `config/hazard_severity.yaml` | `D11AA0F73511E4EEF4B49869D2D009F5F06048801A1B03A64ED5CDB407CDF473` |
| Configured checkpoint (smoke substitute) | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` |

Any drift in these values makes the evaluation reject or fail reproducibility.

> Observed pre-existing documentation drift: `config/hazard_severity.yaml`
> still declares `metadata.model_version: saferoute-yolo11-v1` while
> `config/detection.yaml` declares `saferoute-yolo11-v2`. It does not affect the
> confidence contract and was **not modified** in Phase 42.

---

## 5. What the harness does

### Stage A — standard Ultralytics validation

Runs `YOLO.val` on the independent split with the production `imgsz`, `conf`,
`iou`, and `max_det`. Stage A is reported with an explicit caveat: Ultralytics
validation does not necessarily apply confidence filtering/NMS exactly like the
serving pipeline, so its AP semantics are not identical to the operational
working point.

### Stage B — actual production inference (authoritative)

Runs `src.detection.detector.HazardDetector` on every independent image. This is
the real serving path (`preprocess-v1` → checkpoint → detection record →
letterbox removal → `bbox_norm` normalized to the original image). Stage B is
authoritative for operational precision/recall at `conf = 0.25`.

Stage B explicitly counts and discloses:

- unsupported-class detections (excluded, never scored as trained hazards),
- detections below the configured threshold (a parity failure),
- invalid boxes or confidences (a parity failure),
- per-image inference failures (excluded and disclosed).

### Metrics

- Per-class and overall AP50 / AP50-95 (101-point interpolation).
- Micro precision, recall, F1, TP/FP/FN at the operational threshold.
- Miss rate by class and condition.
- False positives per kilometre only when verified distance is supplied.
- Frame-level false positives plus a **heuristic** session-scoped deduplicated
  count; adjacent frames are never treated as independent observations.
- Wilson intervals and session-clustered bootstrap confidence intervals.
- `insufficient_sample` whenever class support is below the minimum.

### Gates

Seven acceptance gates: dataset independence, annotation reliability,
reproducibility, metric completeness, production parity, decision impact, and
safety honesty. Overall status precedence: any FAIL → FAIL; else any
NOT_ASSESSED → NOT_ASSESSED; else any CONDITIONAL → CONDITIONAL; else PASS.

---

## 6. Acceptance gate status for the real v2 model

No real evaluation report was produced. The gates are therefore recorded as
**NOT_ASSESSED** rather than being passed on substitute evidence.

| Gate | Status | Reason |
|---|---|---|
| Dataset independence | **NOT_ASSESSED** | No independent dataset; sessions/provenance/reference separation unverifiable |
| Annotation reliability | **NOT_ASSESSED** | No independent annotation policy, version, A/B review, or adjudication |
| Reproducibility | **NOT_ASSESSED** | Harness can hash artifacts, but no genuine checkpoint/dataset pair exists to freeze |
| Metric completeness | **NOT_ASSESSED** | No Stage B predictions and no independent ground truth |
| Production parity | **NOT_ASSESSED** | Stage B cannot run against the genuine v2 checkpoint |
| Decision impact | **NOT_ASSESSED** | No independent route metadata or replay evidence |
| Safety honesty | **NOT_ASSESSED** | No real report exists to audit |

The harness-only preflight proves the refusal path works; it does **not** convert
any gate to PASS for the real model.

---

## 7. Harness validation evidence

### Automated tests

```
python -m unittest tests.unit.test_evaluation_metrics \
  tests.unit.test_detection_matching \
  tests.unit.test_dataset_leakage \
  tests.unit.test_route_replay \
  tests.unit.test_independent_evaluator
```

Result: **72 tests OK**.

```
python -m unittest discover -s tests
```

Result: **423 tests OK in ~22 s** (351 prior baseline preserved + 72 new).

### Negative tests that pass

- Missing serving checkpoint → explicit `ModelIntegrityError`.
- P0 smoke substitute → explicit `SmokeSubstituteError`; harness-only run is
  forced to `NOT_ASSESSED` and never presented as the real model.
- Empty evaluation split → `EmptyDatasetError`; an empty evaluation cannot
  succeed.
- Missing label file → `MissingAnnotationError`; missing annotations are never
  silent negatives.
- Malformed, non-finite, non-positive, out-of-range, or inverted boxes → rejected.
  Human YOLO labels may overshoot a boundary by at most 1% because center/size
  encoding is rounded; that rounding is clamped to the image edge. Larger
  excursions and all production prediction boxes remain strictly rejected.
- Unsupported annotation/detection class → rejected or excluded and disclosed;
  never counted as a trained hazard.
- Confidence-contract drift, non-production `imgsz`, or config mutation →
  `ProductionParityError` / reproducibility FAIL.
- Below-threshold production detections and invalid prediction boxes → parity
  FAIL.
- Missing class support → `insufficient_sample`, not a fabricated perfect score.
- Evaluation does not modify the serving checkpoint or production configs
  (verified by before/after hashes in tests).

### Live preflight evidence

Default preflight (no override):

```
python scripts/evaluate_independent.py --preflight-only
→ MODEL INTEGRITY ERROR: The configured checkpoint is the non-production P0
  smoke substitute (marker: ...\P0_SMOKE_SUBSTITUTE.json).
→ exit code 2
```

Explicit harness-only preflight:

```
python scripts/evaluate_independent.py --preflight-only --allow-smoke-substitute
→ "harness_only": true
→ "is_smoke_substitute": true
→ PREFLIGHT OK — checkpoint 19619F99...60B916D0
→ exit code 0
```

The harness-only result is labelled as describing the smoke model, not the real
`saferoute-yolo11-v2` serving model.

### End-to-end integration smoke (non-independent, harness-only)

To validate Stage B wiring with the **real production detector**, the CLI was run
once in harness-only mode on the existing derived two-class test split. That
split is same-source, not independent, so this is **not** a v2 accuracy result.
No mAP/precision/recall from it is presented as evidence.

Structural outcomes:

- overall status `NOT_ASSESSED`, `harness_only = true`;
- 216/216 images inferred, 0 inference failures;
- 26 detections across 24 images;
- 0 unsupported-class, 0 below-threshold, 0 invalid detections;
- coverage fraction 1.0;
- 390 ground-truth boxes (98 pothole, 292 crack), but 0 session ids → dataset
  independence remains `NOT_ASSESSED`;
- no verified distance metadata → FP/km correctly reported as `None`.

This confirms that YOLO center/size label parsing, production preprocessing,
letterbox removal, `bbox_norm` validation, class filtering, matching, and metric
aggregation work end to end. It does not change the real v2 status.

---

## 8. Dataset requirements for a real evaluation

When independent data is collected, it must satisfy all of the following.

### Independence

- New imagery from sessions/cameras/geography outside the training corpus.
- Whole collection sessions must remain on one side of any split; no session may
  cross train/val/test.
- Exact duplicates and DCT perceptual-hash near-duplicates are checked. A
  duplicate spanning sessions is an error; a duplicate within one session is a
  warning that frames are not independent observations.
- A reference session list and/or reference imagery must be supplied to prove
  separation from the training corpus.

### Layout and labels

```text
data/independent/
  dataset.yaml                 # path + test split + names {0: pothole, 1: crack}
  images/test/*.jpg
  labels/test/*.txt            # one .txt per image; empty file = verified negative
  manifests/
    independent_manifest.json
    collection_sessions.csv    # optional; session_id column
```

YOLO label format is `class center_x center_y width height`, normalized to the
original image. A missing label file is an error; use an empty file for a
verified negative. Class IDs outside `{0, 1}` are rejected. A boundary-touching
box may round at most 1% of the image dimension outside `[0, 1]` from center/size
encoding; that rounding is clamped to the edge. Larger excursions are rejected.

### Manifest fields

`independent_manifest.json` should record at minimum:

- `dataset_version`, `annotation_version`;
- `provenance` (collection source, dates, geography, cameras, sessions);
- `annotation` (policy/guideline path, version);
- `quality_control` (`annotator_a`, `annotator_b`, `adjudication`, agreement);
- `images[]` with `image_id`, `file`, `session_id`, `condition`,
  `route_id`, `segment_id`, `segment_length_m`, and verified `distance_km`
  where FP/km is to be reported.

Without sessions, provenance, and reference separation, the dataset-independence
gate stays NOT_ASSESSED or CONDITIONAL — never PASS.

---

## 9. How to run once real artifacts exist

```powershell
# 1. Verify the genuine checkpoint and production contract
.\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py --preflight-only

# 2. Freeze and evaluate the independent split
.\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py `
  --dataset-yaml data/independent/dataset.yaml `
  --manifest data/independent/manifests/independent_manifest.json `
  --reference-sessions data/independent/manifests/training_sessions.csv `
  --reference-image-dir data/derived_2class/images `
  --output reports/phase42_independent_evaluation.json
```

Exit codes:

- `0` — report produced (PASS / CONDITIONAL / NOT_ASSESSED)
- `1` — report produced with FAIL
- `2` — input/integrity error (missing checkpoint, smoke substitute, config
  drift, invalid/empty dataset)

The genuine checkpoint must replace the smoke substitute at
`models/training/saferoute-yolo11-v2/weights/best.pt` and the smoke marker JSON
must be removed. Any file that is not the genuine accepted artifact must not be
reported as v2.

---

## 10. Metrics the real report will contain

- Checkpoint SHA-256, config hashes, dataset image/label/combined hashes, and
  environment (Python, torch, ultralytics, OpenCV, numpy, CUDA device).
- Stage A metrics and per-class AP50, with the validation-semantics caveat.
- Stage B prediction/inference counts, failures, excluded unsupported classes,
  below-threshold and invalid detections.
- Per-class and overall AP50 / AP50-95, precision, recall, F1, TP/FP/FN.
- Miss rate by class and by condition group (daylight/night/rain/etc.).
- FP/km only with verified distance; raw and heuristic frame-deduplicated counts.
- Wilson and session-clustered bootstrap confidence intervals.
- `insufficient_sample` where class/session support is too small.
- Offline route replay: score deltas, rank changes/reversals, rank correlation,
  and research-only eligibility changes. Production recommendation remains
  untouched.

---

## 11. Known limitations and honesty notes

1. **No v2 metrics exist.** The v1/v2 checkpoints were unrecoverable after the
   environment move; the current path is a clearly marked P0 smoke substitute.
   Historical Phase 40 numbers were produced from the former
   `D:\New folder (3)` workspace and its checkpoint, not from the current file.
2. **No independent dataset exists.** The derived two-class dataset is
   same-source and is not an independent benchmark. It must not be relabelled as
   independent evidence.
3. **Stage A ≠ Stage B.** Ultralytics validation and serving inference do not
   necessarily apply `conf`/NMS identically; Stage B is authoritative.
4. **FP/km needs distance.** Frame counts are not kilometres. The deduplicated
   FP count is heuristic and is reported beside, not instead of, the raw count.
5. **No arbitrary mAP pass threshold.** Phase 42 gates on process and integrity,
   not on an invented accuracy cut-off.
6. **Small samples are marked, not hidden.** Undefined AP for a missing class is
   `None` + `insufficient_sample`, never `0.0` or `1.0` by assumption.
7. **Route replay is research-only.** It reuses the production aggregator and
   engine unchanged and does not alter production recommendations.
8. **Secrets were not accessed.** No `.env` or Mapillary token was read,
   printed, or committed.

---

## 12. Files added in Phase 42

| File | Purpose |
|---|---|
| `src/evaluation/__init__.py` | Package exports |
| `src/evaluation/matching.py` | Class-aware IoU matching, box validation |
| `src/evaluation/metrics.py` | AP, counts, FP/km, miss rate, group metrics |
| `src/evaluation/confidence_intervals.py` | Wilson intervals, session-clustered bootstrap |
| `src/evaluation/dataset_validation.py` | YOLO label parsing, explicit missing-label errors, hashing, manifest metadata |
| `src/evaluation/leakage.py` | Session-boundary, exact/near-duplicate, reference separation checks |
| `src/evaluation/evaluator.py` | Stage A/B orchestration, preflight, gates, report serialization |
| `src/evaluation/route_replay.py` | Offline GT-vs-prediction route comparison |
| `scripts/evaluate_independent.py` | CLI with preflight-only mode and exit codes |
| `tests/unit/test_evaluation_metrics.py` | Metric/uncertainty tests |
| `tests/unit/test_detection_matching.py` | Matching/box-validation tests |
| `tests/unit/test_dataset_leakage.py` | Dataset/leakage tests |
| `tests/unit/test_independent_evaluator.py` | Orchestration and negative tests |
| `tests/unit/test_route_replay.py` | Route replay tests |
| `docs/reports/PHASE_42_INDEPENDENT_EVALUATION.md` | This report |

No production model, risk engine, risk formula, or production configuration was
modified.

---

## 13. Conclusion

The Phase 42 evaluation harness is complete, tested, and ready to run. It
correctly refuses the smoke substitute, rejects config drift, and cannot silently
turn missing labels, empty datasets, unsupported classes, or invalid boxes into
favourable metrics.

The real independent evaluation of `saferoute-yolo11-v2` is **NOT_ASSESSED**:

- genuine serving checkpoint: missing;
- independent, session-disjoint dataset: missing;
- independent annotation/QC evidence: missing.

No detector accuracy, safety, or deployment claim is supported until the genuine
checkpoint and an independent dataset are supplied and evaluated with the command
in §9.
