# SafeRoute AI — Phase 11: Hazard Aggregation & Severity Policy

> **Phase ID:** PHASE_11
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_10`](./PHASE_10.md) — Inference & Structured Detection Pipeline
> **Successor:** [`PHASE_12`](./PHASE_12.md) — Deterministic Risk Engine
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Turn raw structured detections into **hazard records** with a **documented, testable severity
policy**, a **configurable confidence threshold**, and a **documented de-duplication rule**
(TRD §8, ARCHITECTURE §7). Severity is decided by configuration + detection attributes — never
by the LLM or arbitrary judgement (Rule 7, Rule 12). This produces the inputs the deterministic
risk engine consumes in PHASE_12; it does **not** compute a safety score itself.

---

## 2. Scope

### In scope
- `config\hazard_severity.yaml`: a class → base-severity table, optionally modulated by
  confidence and/or normalised bbox area **within documented bounds**.
- A configurable **confidence threshold** (validated, not hard-coded arbitrarily).
- A documented **de-duplication / overlap rule** (e.g. IoU-based NMS beyond the model's own
  NMS) as a configurable, validated parameter.
- An aggregation service (e.g. `src\risk\aggregate.py` or `src\hazards\`) that:
  - consumes structured detections + coverage/segment info;
  - emits hazard records with severity from the policy;
  - attaches `status` ∈ `assessed | partially_assessed | unassessed | failed`.
- The **detection → hazard record contract** from TRD §8.1.
- Unit tests: severity mapping, thresholding, de-duplication, and status propagation.

### Out of scope
- Computing any safety score (PHASE_12) (Rule 7).
- Interpreting results as "safe"/"unsafe" for users (frontend/LLM later).
- LLM involvement of any kind (Rule 12).
- Training (PHASE_08).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_10 complete | Structured detections available |
| P2 | PHASE_03 class mapping | Severity keys align with verified class names |
| P3 | User approves writing config + source | Rule 18 |
| P4 | User approves the **severity policy** values | Rule 7 |

---

## 4. Detailed procedure

1. **Define the severity policy** in `config\hazard_severity.yaml`. For each supported class,
   record a base severity and, if used, the confidence/area modulation formula with explicit
   bounds. Every value must be explainable from configuration + detection attributes.
2. **Justify the policy.** Record the rationale and explicitly label it as a documented,
   **provisional policy** (not an empirically calibrated safety model) unless evidence exists.
3. **Confidence threshold.** Define the value and where it lives in config. Validate it against
   a small sample (e.g. inspect detections around the threshold) and record the reasoning.
4. **De-duplication rule.** Define IoU threshold (or equivalent) and the tie-break; document and
   make it configurable. Validate on overlapping-detection examples where identifiable.
5. **Implement aggregation:**
   - map detection class → severity via policy;
   - filter by confidence threshold;
   - apply de-duplication;
   - produce hazard records per TRD §8.1 including `status` and `error`.
6. **Status propagation:** define and test `assessed | partially_assessed | unassessed |
   failed`, including the rule that **missing imagery is not zero risk** (Rule 9).
7. **Tests:** unit tests for severity mapping, boundary confidence values, de-duplication
   behaviour, and status propagation. Record actual results (Rule 14).
8. **Document** the policy, threshold and de-dup rule with examples.
9. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_11. |
| A2 | User approves the **severity policy values** (they are a modelling choice, Rule 7). |
| A3 | User approves the confidence threshold and de-duplication rule. |
| A4 | Any change to the policy after approval requires a documented, approved update. |
| A5 | No LLM may be used to set severity (Rule 12). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Policy config-driven | Severity comes solely from `hazard_severity.yaml`. |
| V2 | Explainable | Each severity value traceable to config + attributes. |
| V3 | Threshold validated | Threshold value validated and recorded. |
| V4 | De-dup documented | Rule + parameter recorded and configurable. |
| V5 | Contract conforms | Output matches TRD §8.1. |
| V6 | Statuses complete | All four statuses handled and tested. |
| V7 | Unknown stays unknown | Missing evidence → unassessed/failed, never zero risk. |
| V8 | No LLM, no score | No LLM involvement; no safety score computed. |
| V9 | Tests pass | Tests executed and actually passing. |

---

## 7. Acceptance criteria

- [ ] `config\hazard_severity.yaml` exists with a documented, approved policy.
- [ ] Confidence threshold and de-duplication rule are documented and configurable.
- [ ] Aggregation produces hazard records conforming to the documented contract.
- [ ] Statuses propagate correctly, including "missing ≠ safe".
- [ ] Tests execute with recorded results.
- [ ] No safety score is computed; no LLM involved.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. A severity value cannot be justified from configuration + attributes (Rule 7).
2. De-duplication cannot be defined defensibly for the available evidence.
3. Missing/failed statuses cannot be distinguished from "no hazards".
4. The policy would require LLM judgement (Rule 12).
5. Computing the score would be required to proceed (belongs to PHASE_12).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 5 Class honesty | §4.1, V1 |
| Rule 7 Deterministic, config-driven severity | Whole phase |
| Rule 9 Missing evidence handling | §4.6, V7 |
| Rule 12 LLM boundary | §5 A5, V8 |
| Rule 14 Testing honesty | §4.7, V9 |
| TRD §8 severity & aggregation | Whole phase |
| ARCHITECTURE §7 | §4.1–§4.4 |

---

## 10. Honesty note

The severity policy is a **documented engineering choice**, not an empirically calibrated
road-safety model. It must be labelled as such until validated with real evidence. It never
converts missing imagery into an implicit "zero hazard".

---

## 11. Completion report template

```
PHASE_11 — Hazard Aggregation & Severity Report
===============================================
Date (actual):        <YYYY-MM-DD>
Policy version:       <e.g. severity-v1>

1. Severity policy (config)
   <class -> base severity (+ modulation) + rationale>

2. Confidence threshold
   - value:     <value>
   - location:  <config path>
   - validation:<evidence>

3. De-duplication rule
   - method:    <IoU/NMS/other>
   - parameter: <value>
   - rationale: <...>

4. Hazard record contract
   <fields, matching TRD §8.1>

5. Status handling
   - assessed / partially_assessed / unassessed / failed: <behaviour>
   - missing imagery -> <status> (not zero risk)

6. Test results (actual)
   - command:       <exact>
   - passed/failed: <n>/<n>
   - failures:      <details or none>

7. Validation results
   V1 <pass/fail + evidence> ... V9 <pass/fail + evidence>

8. Limitations / honesty note
   <policy is provisional, not a calibrated safety model>

9. Result: COMPLETE / BLOCKED / STOPPED
   Next phase authorised? YES / NO (awaiting approval)
```
