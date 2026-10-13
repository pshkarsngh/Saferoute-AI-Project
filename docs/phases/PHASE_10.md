# SafeRoute AI — Phase 10: Inference & Structured Detection Pipeline

> **Phase ID:** PHASE_10
> **Status:** Complete — executed and documented (see [`../reports/PHASE_10_report.md`](../reports/PHASE_10_report.md))
> **Predecessor:** [`PHASE_09`](./PHASE_09.md) — Model Evaluation & Checkpoint Acceptance
> **Successor:** [`PHASE_11`](./PHASE_11.md) — Hazard Aggregation & Severity Policy
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Implement a **versioned inference module** that loads the accepted checkpoint, applies the
**same** preprocessing pipeline from PHASE_06, and emits **structured detections** (model
version, image/route/segment IDs, hazard class, confidence, bounding box, status, error) per
TRD §7.3 and ARCHITECTURE §4. Inference must **never** compute safety scores and must fail
explicitly when the checkpoint is missing or an image is invalid.

---

## 2. Scope

### In scope
- A detector module (e.g. `src\detection\`) that:
  - loads the approved checkpoint from the documented workspace path;
  - reuses the exact preprocessing pipeline/version from PHASE_06;
  - runs inference and returns structured detection records;
  - handles: missing checkpoint, invalid image, empty detections, inference errors;
  - reports **only supported/trained classes** and discloses others honestly.
- Visualisation of detections onto copies written to a safe artefact path.
- Unit/integration tests for the failure paths.
- Documentation of the module and its contract.

### Out of scope
- Severity assignment and aggregation (PHASE_11).
- Risk scoring (PHASE_12).
- Any safety interpretation of detections (Rule 7, Rule 12).
- Training (PHASE_08).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_09 complete | Accepted checkpoint identified |
| P2 | PHASE_06 complete | Shared preprocessing pipeline |
| P3 | User approves writing source under `src\detection\` | Rule 18 |
| P4 | Test images available (inside workspace) | For functional checks |

---

## 4. Detailed procedure

1. **Define the detection record** (JSON-serialisable) exactly per TRD §7.3 /
   ARCHITECTURE §4:
   `model_version`, `image_id`, `route_id`, `segment_id`, `hazard_class`, `confidence`,
   `bbox_xyxy`, `bbox_norm`, `status`, `error`.
2. **Checkpoint loading:** resolve the approved checkpoint path; if absent or unreadable →
   explicit `failed` status with an error (never a silent fallback to another model;
   ARCHITECTURE §5.7).
3. **Preprocessing:** call the PHASE_06 pipeline; record the pipeline version with every result.
4. **Inference:** run the detector on preprocessed images; map class indices to the **verified**
   class names from PHASE_03/PHASE_07; map unknown indices to a disclosed
   `unsupported_class` status, never fabricate a name.
5. **Threshold handling:** apply the configured confidence threshold (value set/validated in
   PHASE_11; until then use the frozen config value and mark it provisional).
6. **Edge cases:** define and test behaviour for:
   - missing checkpoint → error status;
   - invalid/corrupt image → `failed`, excluded as evidence, disclosed;
   - empty detections → a distinct "no detections" result, **not** proof of a clean road
     (Rule 9);
   - inference runtime error → `failed` with error detail.
7. **Visualisation:** draw boxes/labels/confidences on **copies**; save to the artefact path;
   never overwrite sources (Rule 1).
8. **Tests:** unit tests for checkpoint-missing, invalid-image, empty-detection and normal
   paths; record actual results (Rule 14).
9. **Document** the module contract and limitations (including that a single uncalibrated
   monocular image cannot yield metric depth/area — TRD §7.4).
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_10. |
| A2 | User approves the file paths to be created. |
| A3 | Using a checkpoint other than the PHASE_09 accepted one requires approval. |
| A4 | Any new dependency requires separate approval (Rule 19). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Checkpoint resolved | Only the approved checkpoint loads; missing → explicit error. |
| V2 | Shared preprocessing | Inference uses the PHASE_06 pipeline version. |
| V3 | Structured output | Records contain all required fields. |
| V4 | Class honesty | Only trained classes reported; others disclosed as unsupported. |
| V5 | Failure paths | Missing checkpoint / invalid image / empty / error all handled explicitly. |
| V6 | No scoring | Inference computes no safety score. |
| V7 | Originals preserved | Source images unchanged. |
| V8 | Tests pass | Tests executed and actually passing. |

---

## 7. Acceptance criteria

- [x] A versioned inference module exists and is documented.
- [x] It reuses the shared preprocessing pipeline.
- [x] Structured detections match the documented contract.
- [x] Empty/failed cases are handled distinctly (not as "safe").
- [x] Tests execute with recorded results.
- [x] No safety score is computed.
- [x] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The approved checkpoint cannot be loaded.
2. Inference requires a class name that was never verified (Rule 5).
3. Output cannot be made structured/reproducible.
4. Inference would overwrite source images or write outside the workspace (Rule 1).
5. The module would need to compute a safety score (out of scope, Rule 7).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation / no overwrite | §4.7, V7 |
| Rule 5 Class honesty | §4.4, V4 |
| Rule 6 Shared preprocessing | §4.3, V2 |
| Rule 7 No LLM/scoring in detector | §4.6, V6 |
| Rule 9 Missing evidence handling | §4.6 |
| Rule 14 Testing honesty | §4.8, V8 |
| TRD §7 inference | Whole phase |
| ARCHITECTURE §4, §5.7, §6 | §4.1–§4.7 |

---

## 10. Honesty note

Detections are raw model outputs. This phase does not interpret them as safety. "No detections"
means the model found nothing — it is **not** evidence that the road is safe.

---

## 11. Completion report template

```
PHASE_10 — Inference Pipeline Report
====================================
Date (actual):        <YYYY-MM-DD>
Module version:       <e.g. detect-v1>
Checkpoint:           <path + hash>

1. Files created
   - module:  <path>
   - tests:   <path>
   - docs:    <path>

2. Detection record contract
   <field list>

3. Preprocessing
   - pipeline version used: <value>

4. Class handling
   - trained classes reported: <list>
   - unsupported handling:     <description>

5. Failure paths (observed)
   - missing checkpoint: <behaviour>
   - invalid image:      <behaviour>
   - empty detections:   <behaviour>
   - runtime error:      <behaviour>

6. Test results (actual)
   - command:       <exact>
   - passed/failed: <n>/<n>
   - failures:      <details or none>

7. Original-image integrity
   - unchanged: <yes/no>

8. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

9. Limitations / honesty note
   <no scoring; uncalibrated single image cannot yield depth/area>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
