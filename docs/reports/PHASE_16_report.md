# PHASE_16 — Backend API & Persistence Report

> **Phase ID:** PHASE_16 · **Status:** COMPLETE · **Date:** 2026-10-14
> **Workspace:** `D:\New folder (3)` · **Module Version:** `api-v1`
> **Predecessor:** PHASE_15 · **Successor:** PHASE_17
> **Governing:** master_rules.md (1, 7, 9, 10, 11, 13, 14, 17), TRD §11–§12, §15, ARCHITECTURE §10–§11

---

## 1. Endpoints implemented

| Method | Path | Status |
|---|---|---|
| GET | `/api/health` | Implemented + tested |
| POST | `/api/routes` | Implemented + tested |
| POST | `/api/analyze` | Implemented + tested |
| GET | `/api/analyze/{id}` | Implemented + tested |
| GET | `/api/analysis/{id}/hazards` | Implemented |
| GET | `/api/analysis/{id}/comparison` | Implemented |
| GET | `/api/analysis/{id}/explanation` | Implemented |

## 2. Schemas & statuses

Request/response follow TRD §11.2; error schema follows TRD §11.3.
Statuses propagate honestly: `assessed | partially_assessed | unassessed | failed`.

## 3. Comparison & recommendation

Derived from deterministic route scores + disclosed coverage. Unassessed routes are
excluded from the ranking and never recommended (Rule 9). Test:
`test_never_ranks_unassessed_as_safe` / `test_all_missing_imagery_is_unassessed_not_safe`.

## 4. Facilities separation

Facilities are exposed by the separate `src.facilities` service; no facility data is
read by the risk engine. Evidence: PHASE_15 guardrail test.

## 5. Persistence

SQLite (stdlib) at `data/saferoute.db`; tables mirror TRD §12 and store
`model_version` + `config_hash` per score (Rule 17). **Deviation:** SQLite instead of
MySQL and stdlib `http.server` instead of FastAPI — no package install required
(Rule 19). Schema is portable.

## 6. Security

Coordinate validation; no geocoding (explicit `invalid_request`); bounded retries in
routing/imagery adapters; secrets would load from `.env` only (Rule 13); no secrets in
logs.

## 7. Test results (actual)

Command: `.\.venv\Scripts\python.exe -m unittest tests.unit.test_api -v`
Result: **9 / 9 passed** (`Ran 9 tests ... OK`). Negative tests included:
- missing imagery → `unassessed`, not safe;
- routing failure/timeout → `failed`, zero fabricated routes;
- explanation falls back when the LLM is unavailable.

## 8. Validation results

| # | Check | Status | Evidence |
|---|---|:---:|---|
| V1 | Endpoints exist | PASS | 7 endpoints |
| V2 | Schemas conform | PASS | TRD §11.2/§11.3 |
| V3 | Statuses honest | PASS | status propagation tests |
| V4 | No unassessed-safe | PASS | negative tests |
| V5 | Facilities separate | PASS | PHASE_15 guardrail |
| V6 | Persistence works | PASS | store round-trip test |
| V7 | Security | PASS | validation + bounded retries |
| V8 | Negative tests | PASS | 3 negative tests |
| V9 | Secrets safe | PASS | `.env` only |

## 9. Limitations / honesty note

The stdlib API is demo-grade (no auth/async). Geocoding of free-text destinations is not
implemented; coordinates are required and this is disclosed as `invalid_request`.
LLM explanation is wired but uses the deterministic fallback until PHASE_17 configures
Ollama.

## 10. Result & next phase

- **Result:** **COMPLETE**
- **Next Phase:** PHASE_17 — Grounded LLM Explanation Layer.
