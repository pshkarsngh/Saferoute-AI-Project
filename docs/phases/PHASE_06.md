# SafeRoute AI — Phase 06: OpenCV Preprocessing & Image-Quality Pipeline

> **Phase ID:** PHASE_06
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_05`](./PHASE_05.md) — CUDA / GPU & Training-Readiness Verification
> **Successor:** [`PHASE_07`](./PHASE_07.md) — YOLO11 Baseline Training Plan & Config Freeze
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Implement a **single, versioned, documented OpenCV pipeline** used consistently for validation,
preprocessing and inference input preparation (Rule 6, TRD §7, ARCHITECTURE §6). The pipeline
must reject or flag corrupt/empty/unreadable/unsupported images instead of silently treating
them as clean, and must never overwrite source images.

---

## 2. Scope

### In scope
- A reusable module (e.g. under `src\preprocessing\`) exposing:
  - `validate_image(path) -> ImageStatus` (decode, channels, dimensions, emptiness);
  - `preprocess(image) -> PreparedImage` (documented, deterministic transforms);
  - `prepare_inference_input(image)` consistent with the model's expectations;
  - `visualise(image, detections) -> annotated_copy`.
- A **version string** for the pipeline (e.g. `preprocess-v1`) recorded in config and logs.
- Unit tests for validation, determinism and failure handling.
- Documentation of every transform and why it is justified (Rule 6, Rule 17).
- Safe output paths for annotated artefacts; originals never written (Rule 1, TRD §7.1).

### Out of scope
- Running YOLO11 inference (PHASE_10).
- Training (PHASE_08).
- Optional CLAHE or other enhancements **unless** justified by measured evidence. Do **not**
  enable CLAHE by default (Rule 6, TRD §7.1).
- Any change to dataset files (Rule 19).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_04/PHASE_05 complete | `.venv` with OpenCV and numpy available |
| P2 | PHASE_03 complete | Known image formats/sizes in the dataset |
| P3 | User approves writing source under `src\preprocessing\` | Rule 18 |

---

## 4. Detailed procedure

1. **Define the pipeline contract** (inputs, outputs, statuses). Statuses should include at
   least: `ok`, `corrupt`, `empty`, `unreadable`, `unsupported`, `too_small` (threshold
   documented), `low_quality` (only if a documented criterion is defined).
2. **Implement validation:** read bytes, decode with OpenCV, check non-null, non-zero size,
    channel count, and minimum dimensions. Return a structured status, never raise silently.
3. **Implement preprocessing:** documented, deterministic operations only, e.g.:
   - colour space handling (keep BGR for OpenCV I/O; convert only when a consumer needs it);
   - **letterbox** resizing for inference (preserve aspect ratio; avoid distortion);
   - avoid duplicating transforms Ultralytics already performs (TRD §7.1).
   Every step documented with a rationale and a note on when it is applied.
4. **Implement inference input preparation** consistent with Ultralytics' expectations; keep it
   minimal and documented.
5. **Implement visualisation:** draw boxes/labels/confidences onto **copies**; write to a
   designated artefact path (e.g. `logs\` or `artifacts\`), never over the source.
6. **Add the pipeline version string** and load preprocessing parameters from `config\` (no
   hard-coded magic numbers).
7. **Write unit tests** (e.g. `tests\unit\test_preprocessing.py`):
   - valid image → `ok`;
   - truncated/corrupt bytes → `corrupt`/`unreadable`;
   - zero-byte file → `empty`;
   - determinism: same input → identical output;
   - original file unchanged after preprocessing.
8. **Run the tests** and record **actual** results (Rule 14). If a test fails, fix or report —
   never fabricate a pass.
9. **Document** the pipeline in a short README under `src\preprocessing\`.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_06. |
| A2 | User approves the file paths to be created (source + tests). |
| A3 | Enabling any optional enhancement (e.g. CLAHE) requires separate, evidence-based approval. |
| A4 | Installing any new package requires separate approval (Rule 19). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Single pipeline | One versioned module is the sole preprocessing path. |
| V2 | Validation robust | Corrupt/empty/unreadable/unsupported inputs are detected and classified. |
| V3 | Determinism | Identical input yields identical output. |
| V4 | Originals preserved | Source images are byte-identical after processing. |
| V5 | No silent success | Failed images are never reported as `ok`. |
| V6 | Tests pass | Unit tests executed and actually passing. |
| V7 | Config-driven | Parameters come from `config\`, not hard-coded. |
| V8 | Documented | Every transform has a documented rationale. |

---

## 7. Acceptance criteria

- [ ] A single versioned preprocessing/validation module exists and is documented.
- [ ] Failure modes are classified and never treated as clean.
- [ ] Determinism test passes with recorded output.
- [ ] Original images verified unchanged.
- [ ] Unit tests execute and their actual results are recorded.
- [ ] No dataset file modified; no unapproved dependency added.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The pipeline cannot avoid modifying source images.
2. A failure mode cannot be detected reliably.
3. A required transform would need an unjustified/undocumented step (Rule 6).
4. Tests reveal non-deterministic behaviour that cannot be explained.
5. A new dependency is required but not approved (Rule 19).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation / no overwrite | §2, V4 |
| Rule 6 OpenCV consistency | Whole phase |
| Rule 14 Testing honesty | §4.8, V6 |
| Rule 17 Documentation | §4.9 |
| Rule 18 Minimal changes | §2, §4.7 |
| TRD §7.1–§7.2 | §4.3–§4.5 |
| ARCHITECTURE §6 | Whole phase |

---

## 10. Honesty note

This phase delivers the preprocessing **module** and its tests. It does not claim any detection
quality. Optional enhancements are **off** unless separately justified by measured evidence.

---

## 11. Completion report template

```
PHASE_06 — Completion Report
============================
Date (actual):        <YYYY-MM-DD>
Pipeline version:     <e.g. preprocess-v1>

1. Files created
   - module:   <path>
   - tests:    <path>
   - docs:     <path>
   - config:   <path>

2. Transforms implemented (with rationale)
   - <transform> : <why / when>

3. Failure modes handled
   - corrupt / empty / unreadable / unsupported / too_small / low_quality: <yes/no>

4. Test results (actual)
   - command:            <exact>
   - passed/failed:      <n>/<n>
   - failures:           <details or none>

5. Determinism evidence
   - <hash/comparison result>

6. Original-image integrity
   - before/after hashes equal: <yes/no>

7. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

8. Limitations / honesty note
   <e.g. CLAHE not enabled; no metric claims>

9. Result: COMPLETE / BLOCKED / STOPPED
   Next phase authorised? YES / NO (awaiting approval)
```
