# SafeRoute AI — Phase 12: Deterministic Risk Engine

> **Phase ID:** PHASE_12
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_11`](./PHASE_11.md) — Hazard Aggregation & Severity Policy
> **Successor:** [`PHASE_13`](./PHASE_13.md) — Routing Provider Selection & Adapter
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Implement the **deterministic risk engine** — the **sole owner of safety scores** (Rule 7). It
computes segment and route hazard-risk scores from verified detections, severities, segment
length and image coverage, using **documented formulas**. It must be a **pure, unit-testable
function** (identical inputs → identical outputs), independent of the LLM and of facility
counts, and must treat missing imagery as `unknown` — never as safety (Rule 9).

This phase resolves the open items `H_i` and `λ` from TRD §9 / ARCHITECTURE §7 with a
documented, approved definition.

---

## 2. Scope

### In scope
- Specify and document `H_i` (hazard aggregation per unit), `λ`, normalisation and the route
  aggregation function, in `config\risk_engine.yaml` and docs.
- Implement the candidate score `S_i = 100 × exp(-λ × H_i)` (or the agreed alternative) as a
  pure function.
- Per-segment risk from detections, severities, covered fraction and segment length.
- Route aggregation weighting segments by length/extent and coverage.
- Coverage handling: report the score **with** its coverage; insufficient coverage may suppress
  a "safe" verdict rather than inflate safety.
- De-duplication of the same physical hazard across adjacent segments where identity is
  established.
- A **config hash** recorded with every score for reproducibility.
- Unit tests: determinism, boundary/empty inputs, coverage suppression, failed readings.

### Out of scope
- Route ordering/recommendation policy (implemented with routing/comparison — PHASE_13/PHASE_16).
- LLM explanation (PHASE_17) (Rule 7, Rule 12).
- Including facility counts in the score (Rule 11).
- Presenting a "safe" verdict from insufficient coverage (Rule 9).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_11 complete | Hazard records + statuses available |
| P2 | PHASE_09/PHASE_10 complete | Detector + inference outputs |
| P3 | User approves the **formulas and parameters** (`H_i`, `λ`) | Rule 7 |
| P4 | User approves writing config + source | Rule 18 |

---

## 4. Detailed procedure

1. **Define `H_i`.** Document the function of: verified detections, severities, segment
   length/extent, covered fraction, image coverage, and acquisition status. Write the exact
   formula with units.
2. **Define `λ` and normalisation.** Record the value/derivation, the justification, and the
   range. Label as **provisional** unless backed by evidence.
3. **Define route aggregation.** Document how segment risks combine (e.g. length-weighted mean)
   and how coverage is reported alongside.
4. **Coverage rules (Rule 9).** Specify precisely:
   - missing imagery → `unknown/unassessed`; it must **not** reduce `H_i` toward safety;
   - insufficient coverage → score reported with a suppression flag; no "safe" verdict.
5. **De-duplication.** Document the identity rule to avoid double-counting across adjacent
   segments.
6. **Implement the engine** as a pure function:
   - inputs: hazard records, coverage, segment metadata, config;
   - outputs: per-segment and per-route scores + coverage + status + config hash.
7. **Compute and attach the config hash** so identical configs → identical outputs.
8. **Unit tests (required):**
   - determinism (same input → identical output across runs);
   - empty detections vs unassessed segments are distinct;
   - failed acquisition does not become a safe score;
   - insufficient coverage suppresses a "safe" verdict;
   - boundary values (all-zero coverage, zero-length segment, max severity).
   Record actual results (Rule 14).
9. **Document** the formulas, parameters, coverage rules and examples in a short document.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_12. |
| A2 | User approves the **`H_i`, `λ`, normalisation and aggregation** definitions (Rule 7). |
| A3 | User approves the coverage-suppression policy. |
| A4 | Any post-approval change to formulas requires a documented, approved update. |
| A5 | No LLM may compute or alter a score (Rule 12). |
| A6 | Facility data must not enter the score (Rule 11). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Sole ownership | No other component computes safety scores. |
| V2 | Determinism | Same inputs → byte-identical outputs. |
| V3 | Documented formulas | `H_i`, `λ`, normalisation, aggregation written down. |
| V4 | Coverage honesty | Missing/insufficient coverage → disclosed, not "safe". |
| V5 | Failure handling | Failed readings handled explicitly, not as safety. |
| V6 | Separation | No LLM and no facility counts in the score. |
| V7 | Config hash | Emitted with every score and reproducible. |
| V8 | Tests pass | Unit tests executed and actually passing. |

---

## 7. Acceptance criteria

- [ ] Documented `H_i`, `λ`, normalisation and route aggregation exist.
- [ ] A pure engine computes segment and route scores with coverage + status.
- [ ] Determinism proven by test.
- [ ] Missing/insufficient coverage never yields a "safe" verdict.
- [ ] Config hash recorded with scores.
- [ ] No LLM or facility input to the score.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. `H_i` or `λ` cannot be defined in a documented, deterministic way.
2. The engine is non-deterministic on identical inputs.
3. Missing imagery would reduce risk (forbidden by Rule 9).
4. Facility counts would affect the score without an approved requirements change (Rule 11).
5. A score would require LLM judgement (Rule 12).
6. The candidate formula cannot be validated for the dataset at hand.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 7 Deterministic score ownership | Whole phase |
| Rule 9 Missing evidence handling | §4.4, V4 |
| Rule 11 Facilities separate | §5 A6, V6 |
| Rule 12 LLM boundary | §5 A5, V6 |
| Rule 14 Test honesty | §4.8, V8 |
| Rule 17 Reproducibility (config hash) | §4.7, V7 |
| TRD §9 risk engine | Whole phase |
| ARCHITECTURE §7 | §4.1–§4.5 |

---

## 10. Honesty note

The formula is a **candidate** until validated. No score may be presented as calibrated or as a
real-world safety guarantee. Scores must always be shown **with** their coverage and
limitations.

---

## 11. Completion report template

```
PHASE_12 — Deterministic Risk Engine Report
===========================================
Date (actual):        <YYYY-MM-DD>
Engine version:       <e.g. risk-v1>

1. Formulas (documented)
   - H_i:            <definition>
   - lambda:         <value + rationale>
   - normalisation:  <definition>
   - route aggregation: <definition>

2. Coverage rules
   - missing imagery -> <status>
   - insufficient coverage -> <suppression behaviour>

3. De-duplication
   <rule>

4. Config
   - path:       config\risk_engine.yaml
   - config hash:<value>

5. Output contract
   <segment score / route score / coverage / status / config_hash fields>

6. Test results (actual)
   - determinism:      <evidence>
   - empty vs unassessed: <evidence>
   - failed handling:  <evidence>
   - coverage suppression: <evidence>
   - boundary cases:   <evidence>
   - command:          <exact>
   - passed/failed:    <n>/<n>

7. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

8. Limitations / honesty note
   <formula is provisional; scores reported with coverage only>

9. Result: COMPLETE / BLOCKED / STOPPED
   Next phase authorised? YES / NO (awaiting approval)
```
