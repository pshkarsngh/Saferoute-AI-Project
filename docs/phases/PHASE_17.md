# SafeRoute AI — Phase 17: Grounded LLM Explanation Layer

> **Phase ID:** PHASE_17
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_16`](./PHASE_16.md) — Backend API & Persistence
> **Successor:** [`PHASE_18`](./PHASE_18.md) — Frontend Integration & End-to-End Validation
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## 1. Objective

Implement the **grounded LLM explanation layer** (via local Ollama) that explains **verified
backend results** in natural language, with schema validation, entity-grounding checks,
prompt-injection resistance, and a **deterministic fallback** when Ollama is unavailable
(Rule 12; TRD §13, ARCHITECTURE §9).

The LLM explains only. It must **never** compute scores, invent routes/hazards/facilities/
measurements, or alter the deterministic ranking (Rules 7, 12).

---

## 2. Scope

### In scope
- An LLM service (e.g. `src\llm\`) that:
  - receives **only** verified backend data (routes, coverage, scoring factors, limitations);
  - produces a constrained explanation with `explanation`, `referenced_routes`,
    `referenced_hazards`, `disclosures`, `source`.
- **Schema validation** of every response.
- **Entity-grounding check:** reject any referenced route/hazard/facility not present in the
  input.
- **Prompt-injection resistance:** user text treated as data, never as instructions; LLM cannot
  trigger state-mutating actions.
- **Fallback:** deterministic, template-generated message built only from verified backend data
  when Ollama is unavailable.
- Wire the `/api/analysis/{id}/explanation` endpoint (from PHASE_16).
- Tests: grounding rejection, injection attempt, fallback path, no-score rule.

### Out of scope
- Computing or changing scores (Rule 7).
- Parsing user preferences beyond approved, documented behaviour.
- Frontend presentation (PHASE_18).
- Any LLM-produced metrics (forbidden, Rule 12, Rule 14).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_16 complete | Endpoint + verified backend payloads |
| P2 | User approves an Ollama model choice and its licence/download | Rule 19 |
| P3 | User approves installing/running Ollama locally | Rule 19 |
| P4 | Local resources sufficient for the chosen model | Rule 16 |

---

## 4. Detailed procedure

1. **Select and approve the Ollama model.** Record name, size, licence, and resource needs.
   Do not download without approval (Rule 19).
2. **Define the LLM input** exactly per ARCHITECTURE §4 (verified data only): routes, coverage,
   scoring factors (config hash, `lambda`, `H_definition`), limitations.
3. **Define the output schema** (`explanation`, `referenced_routes`, `referenced_hazards`,
   `disclosures`, `source`).
4. **Implement the service:**
   - build a system prompt that constrains the model to explain only provided data;
   - treat user text as data, never instructions (injection resistance);
   - no tool calls that mutate state.
5. **Schema validation:** reject/repair responses that do not conform; never pass malformed
   output to the API.
6. **Entity-grounding check:** verify every referenced entity exists in the input; if not,
   reject and fall back (Rule 12).
7. **Fallback path:** when Ollama is unavailable or output is rejected, return a deterministic
   template explanation built only from verified data; set `source = "fallback"`.
8. **Wire the endpoint** and set `source = "ollama" | "fallback"`.
9. **Tests (required):**
   - response referencing an unknown entity → rejected;
   - prompt-injection text in user input → does not change behaviour;
   - Ollama unavailable → fallback returned with `source="fallback"`;
   - LLM never emits or changes a score (assert score fields come from the engine).
   Record actual results (Rule 14).
10. **Document** the boundary, schema, fallback and prompt-security measures.
11. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_17. |
| A2 | User approves the Ollama model and its download/licence (Rule 19). |
| A3 | User approves running Ollama locally. |
| A4 | The LLM must not receive or return anything beyond verified data; going outside this requires an approved change (Rule 12). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Verified-only input | LLM input contains only backend-verified data. |
| V2 | Schema validation | Responses validated; malformed rejected. |
| V3 | Grounding check | Unknown entity references rejected. |
| V4 | Injection resistance | User text cannot alter instructions/behaviour. |
| V5 | Fallback works | Ollama down → deterministic fallback with `source="fallback"`. |
| V6 | No scoring | LLM neither computes nor alters scores/ranking. |
| V7 | Endpoint wired | `/explanation` returns schema-conformant output. |
| V8 | Tests pass | Tests executed and actually passing. |

---

## 7. Acceptance criteria

- [ ] Ollama model selected, approved and recorded.
- [ ] LLM receives only verified data and returns schema-validated, grounded explanations.
- [ ] Unknown entity references are rejected.
- [ ] Injection attempts do not change behaviour.
- [ ] Fallback explanation works when Ollama is unavailable.
- [ ] No score is produced or modified by the LLM.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The LLM cannot be constrained to verified data (fabrication observed).
2. Grounding checks cannot reliably reject unknown entities.
3. The fallback cannot be generated without the LLM.
4. The model choice would require an unapproved download/licence (Rule 19).
5. The LLM would need to compute or alter a score (Rule 7) — refuse.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 7 Score ownership | §5 A4, V6 |
| Rule 12 LLM boundaries | Whole phase |
| Rule 14 No LLM metrics | §2 out-of-scope, V6 |
| Rule 16 Local resources | §3 P4 |
| Rule 19 No unauthorized actions | §5 A2 |
| PRD FR-L1–FR-L3 | Whole phase |
| TRD §13 LLM integration | Whole phase |
| ARCHITECTURE §9 | §4.2–§4.7 |

---

## 10. Honesty note

Explanations are constrained summaries of verified data; the UI must mark them as *generated
from verified data* and flag when the fallback was used. The LLM is never a source of fact or
of any metric.

---

## 11. Completion report template

```
PHASE_17 — LLM Explanation Layer Report
=======================================
Date (actual):        <YYYY-MM-DD>

1. Model
   - name/size: <...>
   - licence:   <...>
   - download approved: <yes>

2. Input boundary
   - fields provided to LLM: <list>
   - verified only: <yes>

3. Output schema
   - explanation / referenced_routes / referenced_hazards / disclosures / source

4. Controls
   - schema validation: <yes>
   - entity grounding:  <yes>
   - injection resistance: <approach>
   - mutating tool calls: <none>

5. Fallback
   - trigger: <Ollama unavailable / rejected output>
   - output:  <deterministic template>
   - source value: "fallback"

6. Endpoint
   - /api/analysis/{id}/explanation: <wired + behaviour>

7. Test results (actual)
   - unknown entity rejection: <result>
   - injection attempt:        <result>
   - fallback:                 <result>
   - no-score assertion:       <result>
   - command: <exact>; passed/failed: <n>/<n>

8. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

9. Limitations / honesty note
   <LLM explains only; no metrics; UI must flag fallback>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
