# SafeRoute AI — Phase 18: Frontend Integration & End-to-End Validation

> **Phase ID:** PHASE_18
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_17`](./PHASE_17.md) — Grounded LLM Explanation Layer
> **Successor:** none (final phase)
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Implement the **React frontend** and run **end-to-end validation**, including the required
**negative tests**, so the system presents routes, safety scores, coverage, hazard evidence,
facilities (separately), explanations and disclosures **honestly** (Rule 9, Rule 20;
TRD §14, §16; ARCHITECTURE §14).

This phase also produces the final, system-level evidence that distinguishes working features,
sample/simulated data and unvalidated capabilities (Rule 20).

---

## 2. Scope

### In scope
- React frontend (e.g. `frontend\`) with:
  - destination input + validation and error states;
  - route alternatives (**only those returned**) with safety scores and their basis;
  - **coverage indicators** (assessed / partial / unassessed per route/segment);
  - hazard evidence (classes, confidences, optionally annotated imagery);
  - **facilities shown separately** from the hazard score (Rule 11);
  - grounded explanations (marked *generated from verified data*, flagging fallback);
  - explicit loading/error states; prominent coverage/limitation disclosures.
- e2e tests: destination → routes → analysis → comparison → explanation.
- **negative tests (required):**
  - missing imagery → `unassessed` (not "safe");
  - invalid annotations → audit failure reported;
  - empty detections → distinct from "no hazards exist";
  - LLM unavailable → fallback explanation returned;
  - routing failure/timeout → surfaced error, no fabricated routes.
- A final **honesty pass**: label working vs sample/simulated vs unvalidated features.

### Out of scope
- Changing scoring formulas or the LLM boundary.
- Adding unrelated features or unnecessary frameworks (Rule 18).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_16/PHASE_17 complete | API + explanations available |
| P2 | PHASE_12 complete | Scores available |
| P3 | User approves installing frontend deps | Rule 19 |
| P4 | A running local backend for e2e tests | Local only |

---

## 4. Detailed procedure

1. **Install approved frontend dependencies** into the project (no global installs); record
   versions.
2. **Build the UI** under `frontend\`:
   - destination input with validation/errors;
   - route list (**exactly** those returned; fewer than four shown as fewer than four);
   - score display with its basis and **coverage**;
   - hazard evidence;
   - facilities in a separate section;
   - explanation with `source` label (ollama/fallback) and "generated from verified data"
     marking;
   - loading/error states and prominent limitation disclosures.
   The UI contains **no scoring logic**.
3. **Accessibility/UX honesty:** never colour-code an unassessed route as "safe"; make
   `unknown/unassessed` visually distinct.
4. **Wire the frontend to the backend** endpoints from PHASE_16/PHASE_17.
5. **Run e2e tests** (destination → routes → analysis → comparison → explanation) against the
   local stack; record actual results.
6. **Run the required negative tests** and record actual results (Rule 14):
   missing imagery; invalid annotations; empty detections; LLM unavailable; routing
   failure/timeout.
7. **Honesty pass (Rule 20):** produce a table classifying every capability as
   **working / sample or simulated / unvalidated**, with evidence.
8. **Final validation:** summarise all phase completion reports; confirm no fabricated claims;
   confirm the test set remained isolated and metrics come from PHASE_09.
9. **Write the completion report** (§11) and a system-level limitations statement.

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_18. |
| A2 | User approves the frontend dependency list before install (Rule 19). |
| A3 | Final acceptance of the whole system requires explicit user approval after reviewing the
       e2e and negative-test evidence and the honesty table. |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Routes honest | Only returned routes displayed; no padding. |
| V2 | Coverage honest | assessed/partial/unassessed shown per route/segment. |
| V3 | Facilities separate | Displayed separately; score unchanged. |
| V4 | Explanation marked | Shown as generated from verified data; fallback flagged. |
| V5 | No unassessed-safe | Unassessed never presented as safe. |
| V6 | E2E passes | Full flow executed end-to-end with real results. |
| V7 | Negative tests pass | All five negative tests executed and passing. |
| V8 | Honesty table | Working/sample/unvalidated classification completed. |
| V9 | No fabricated claims | No metric claimed that PHASE_09 did not measure. |
| V10 | Isolation | All artefacts inside the workspace. |

---

## 7. Acceptance criteria

- [ ] Frontend implements input, routes, scores+coverage, evidence, separate facilities,
      explanations and disclosures.
- [ ] Only returned routes are shown; no unassessed route is shown as safe.
- [ ] End-to-end flow verified with recorded results.
- [ ] All required negative tests execute with recorded results.
- [ ] A working/sample/unvalidated honesty table is produced.
- [ ] All measured metrics trace to PHASE_09; no fabricated claims.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The UI would need to fabricate coverage, routes, hazards or scores (Rule 9, Rule 10,
   Rule 14).
2. A negative test cannot pass honestly.
3. Facilities would leak into the hazard score or ranking (Rule 11).
4. Unassessed segments cannot be visually distinguished from safe ones (Rule 9).
5. Any required artefact would live outside the workspace (Rule 1).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation | V10 |
| Rule 9 Missing coverage honesty | §4.3, V2, V5 |
| Rule 10 Routing honesty | V1 |
| Rule 11 Facilities separate | §4.2, V3 |
| Rule 12 LLM boundary (display) | §4.2, V4 |
| Rule 14 Testing honesty | §4.6–§4.7, V7 |
| Rule 18 Minimal changes | §2 out-of-scope |
| Rule 20 Honest demonstration | §4.7, V8 |
| PRD FR-U1–FR-U3 | Whole phase |
| TRD §14, §16 | Whole phase |
| ARCHITECTURE §14 | Whole phase |

---

## 10. Honesty note

The frontend must not overstate capability. Estimates, plans, sample data and simulated
features are labelled as such. Detector metrics come only from PHASE_09; nothing here changes
or invents them.

---

## 11. Completion report template

```
PHASE_18 — Frontend & E2E Validation Report
===========================================
Date (actual):        <YYYY-MM-DD>

1. Frontend implemented
   - destination input/validation: <yes>
   - route alternatives (only returned): <yes>
   - scores with basis + coverage: <yes>
   - hazard evidence: <yes>
   - facilities (separate): <yes>
   - explanation labeled: <yes>
   - loading/error states: <yes>
   - no scoring logic in UI: <confirmed>

2. Honesty behaviours
   - unassessed visually distinct: <yes>
   - fewer-than-four routes shown honestly: <yes>

3. E2E tests (actual)
   - command: <exact>
   - flow: destination -> routes -> analysis -> comparison -> explanation
   - passed/failed: <n>/<n>

4. Negative tests (actual)
   - missing imagery -> unassessed: <result>
   - invalid annotations -> audit failure: <result>
   - empty detections != no hazards: <result>
   - LLM unavailable -> fallback: <result>
   - routing failure/timeout -> error, no fake routes: <result>

5. Honesty table (Rule 20)
   | Capability | Status (working / sample / unvalidated) | Evidence |

6. Metrics provenance
   - all metrics from PHASE_09: <yes>
   - test set isolation maintained: <yes>

7. Validation results
   V1 <pass/fail + evidence> ... V10 <pass/fail + evidence>

8. System limitations statement
   <what is not measurable, small-dataset caveats, unassessed coverage, provider status>

9. Result: COMPLETE / BLOCKED / STOPPED
   Final system acceptance requested: YES / NO
```
