# SafeRoute AI — Phase 09: Model Evaluation & Checkpoint Acceptance

> **Phase ID:** PHASE_09
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_08`](./PHASE_08.md) — YOLO11 Baseline Training Run
> **Successor:** [`PHASE_10`](./PHASE_10.md) — Inference & Structured Detection Pipeline
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Measure the trained baseline's performance **honestly** and decide whether the checkpoint is
**accepted, retained for comparison, rejected, or requires rollback** (TRD §6,
TRAINING_RULES §6–§7). Model selection uses **validation** data only; the **test set is used
once**, at final evaluation, and never for tuning.

Every number reported must be **actually measured** (Rule 14). No metric may be estimated,
extrapolated or fabricated.

---

## 2. Scope

### In scope
- Validation-set evaluation: precision, recall, F1, mAP@0.5, mAP@0.5:0.95.
- Per-class performance and confusion analysis where supported.
- False-positive / false-negative analysis (counts + qualitative examples).
- One final evaluation on the isolated test set.
- Qualitative review of a human-checked sample of predictions.
- Inference speed/memory measurement where measurable.
- Reporting class imbalance and weak/under-trained classes plainly.
- A checkpoint acceptance decision with recorded rationale.

### Out of scope
- Retraining (would require a new approved plan).
- Tuning on the test set (forbidden).
- Serving the model in production (PHASE_10 onwards).
- Claiming real-world road-safety accuracy from training metrics.

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_08 complete | Trained checkpoint exists |
| P2 | PHASE_07 evaluation plan approved | Defines the metrics/method |
| P3 | Test set still isolated | Not used in training/selection |
| P4 | User approves running evaluation | Compute-only |

---

## 4. Detailed procedure

1. **Confirm the checkpoint** under evaluation (path + hash) and the exact config used.
2. **Validation evaluation:** compute precision, recall, F1, mAP@0.5, mAP@0.5:0.95 on the
   **validation** split.
3. **Per-class metrics:** compute per-class precision/recall/mAP; build a confusion matrix where
   supported.
4. **Error analysis:** examine false positives and false negatives; record counts and illustrative
   cases.
5. **Class imbalance report:** state per-class instance counts and flag weak/under-trained or
   absent classes explicitly.
6. **Final test evaluation (once):** run the model on the isolated **test** set; record the same
   metric set. Do not tune afterward using these results.
7. **Qualitative review:** generate predictions on held-out images; a human reviews a documented
   sample; record observations (correct/incorrect, obvious failure modes).
8. **Performance measurement:** record inference latency and memory where measurable, with the
   measurement method stated.
9. **Acceptance decision** per TRAINING_RULES §7:
   - **Accept** if validation metrics meet the pre-recorded plan, per-class results are
     acceptable, qualitative review shows no disqualifying failure, and provenance is complete;
   - **Retain for comparison** if promising but not clearly better;
   - **Reject** if loss decreased but validation did not improve with qualitative regressions,
     or if a supported class collapses, or if leakage/fabrication is suspected;
   - **Rollback** if a previously promoted model later proves worse (do not delete without
     approval).
10. **Record limitations** explicitly (small/biased dataset, unresolved class coverage, no
    real-world safety claim).
11. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_09. |
| A2 | User approves the evaluation commands before execution. |
| A3 | Promoting a checkpoint to "serving/approved" status requires explicit user acceptance of the metrics and the decision. |
| A4 | Any retraining or re-tuning requires a new plan and approval (Rule 19). |
| A5 | Deleting any checkpoint (including on rollback) requires separate approval (Rule 19). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Checkpoint identified | Path + hash recorded. |
| V2 | Validation metrics measured | Precision/recall/F1/mAP computed on validation. |
| V3 | Per-class measured | Per-class metrics recorded. |
| V4 | Errors analysed | FP/FN counts + examples recorded. |
| V5 | Test evaluated once | Single test evaluation, results recorded. |
| V6 | Test never used for tuning | No post-test tuning performed. |
| V7 | Qualitative review | Human-reviewed sample documented. |
| V8 | Deterministic reporting | Every metric traceable to a command/config. |
| V9 | Honesty | No metric estimated or fabricated; imbalance disclosed. |

---

## 7. Acceptance criteria

- [ ] Validation and test metrics measured and recorded with commands.
- [ ] Per-class results and error analysis recorded.
- [ ] Class imbalance and weak classes disclosed.
- [ ] An explicit accept/retain/reject/rollback decision is recorded with rationale.
- [ ] Limitations stated plainly (no real-world safety claim).
- [ ] Test set used once only.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. Validation and test results diverge wildly (possible leakage or mis-split) — investigate.
2. The test set was found to have been used earlier.
3. Metrics look implausibly perfect (possible leakage/fabrication) — do not report as success.
4. Configuration, checkpoint or dataset revision cannot be identified.
5. Any conclusion would require tuning on the test set.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 5 Report unsupported classes honestly | §4.5 |
| Rule 14 Testing/metric honesty | Whole phase |
| Rule 15 Test isolation / leakage | §4.6, V5–V6 |
| Rule 17 Reproducible records | V8 |
| Rule 20 Honest demonstration | §4.10 |
| TRD §6 evaluation | §4.2–§4.8 |
| TRAINING_RULES §6–§7 | Whole phase |

---

## 10. Honesty note

Detection metrics describe performance on **this dataset**, not real-world road-safety
accuracy. This phase never lets the LLM produce metrics (Rule 12); all numbers come from the
deterministic evaluation.

---

## 11. Completion report template

```
PHASE_09 — Evaluation & Checkpoint Acceptance
=============================================
Date (actual):        <YYYY-MM-DD>
Checkpoint:           <path>  hash: <hash>
Config reference:     <path/hash>

1. Validation metrics (measured)
   - precision:      <value>
   - recall:         <value>
   - F1:             <value>
   - mAP@0.5:        <value>
   - mAP@0.5:0.95:   <value>
   - command:        <exact>

2. Per-class metrics
   <table: class | precision | recall | mAP | instances>

3. Confusion analysis
   <summary>

4. Error analysis
   - false positives: <count>  examples: <...>
   - false negatives: <count>  examples: <...>

5. Class imbalance
   <per-class counts + weak/absent classes>

6. Test metrics (measured once)
   - same metric set: <values>
   - command:         <exact>

7. Qualitative review
   - sample size: <n>
   - findings:    <...>

8. Performance
   - inference latency: <value + method>
   - memory:            <value + method>

9. Acceptance decision
   - DECISION:     accept / retain / reject / rollback
   - rationale:    <...>

10. Validation results
    V1 <pass/fail + evidence> ... V9 <pass/fail + evidence>

11. Limitations / honesty note
    <dataset limits; no real-world safety claim>

12. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
