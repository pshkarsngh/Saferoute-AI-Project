# PHASE_17 — Grounded LLM Explanation Layer Report

> **Phase ID:** PHASE_17 · **Status:** COMPLETE (fallback path) · **Date:** 2026-10-14
> **Workspace:** `D:\New folder (3)` · **Module Version:** `llm-v1`
> **Predecessor:** PHASE_16 · **Successor:** PHASE_18
> **Governing:** master_rules.md (7, 12, 14, 16, 19), TRD §13, ARCHITECTURE §9

---

## 1. Model

- **Ollama integration:** implemented but **disabled by default**.
- **Active path:** deterministic **fallback** (`source="fallback"`).
- **Download:** none performed (Rule 19). Enabling Ollama requires explicit approval.

## 2. Input boundary

Only verified backend data is passed. No raw imagery/user free-text is treated as
instructions. Verified fields: routes, coverage, scores, hazards, limitations.

## 3. Output schema

`ExplanationResult`: `explanation, referenced_routes, referenced_hazards, disclosures,
source`.

## 4. Controls

- Schema validation (malformed output rejected).
- Entity grounding (unknown route/hazard references rejected → fallback).
- Prompt-injection resistance (user text treated as data).
- No mutating tool calls; no score production.

## 5. Fallback

Trigger: Ollama unavailable / disabled / rejected output. Output: deterministic template
built only from verified data; `source="fallback"`.

## 6. Endpoint

`GET /api/analysis/{id}/explanation` returns the stored explanation object.

## 7. Test results (actual)

Command: `.\.venv\Scripts\python.exe -m unittest tests.unit.test_llm_explainer -v`
Result: **6 / 6 passed** (`Ran 6 tests ... OK`).

- Unknown entity rejection: PASS
- Injection attempt: PASS (no behaviour change)
- Fallback: PASS
- No-score assertion: PASS

## 8. Validation results

| # | Check | Status |
|---|---|:---:|
| V1 | Verified-only input | PASS |
| V2 | Schema validation | PASS |
| V3 | Grounding check | PASS |
| V4 | Injection resistance | PASS |
| V5 | Fallback works | PASS |
| V6 | No scoring | PASS |
| V7 | Endpoint wired | PASS |
| V8 | Tests pass | PASS (6/6) |

## 9. Limitations / honesty note

Active explanations use the deterministic fallback; Ollama is optional and unapproved.
Explanations are constrained summaries of verified data, not safety guarantees. The UI
must flag fallback usage.

## 10. Result & next phase

- **Result:** **COMPLETE** (fallback; Ollama optional pending approval)
- **Next Phase:** PHASE_18 — Frontend Integration & End-to-End Validation.
