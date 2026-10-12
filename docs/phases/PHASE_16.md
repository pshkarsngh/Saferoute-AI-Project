# SafeRoute AI — Phase 16: Backend API & Persistence

> **Phase ID:** PHASE_16
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_15`](./PHASE_15.md) — Facilities Lookup Service
> **Successor:** [`PHASE_17`](./PHASE_17.md) — Grounded LLM Explanation Layer
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## 1. Objective

Implement the **FastAPI backend** and **MySQL persistence** that orchestrate the validation →
routing → imagery → preprocessing → detection → aggregation → risk → comparison pipeline, expose
the endpoints and schemas from TRD §11, propagate **honest statuses**
(`assessed | partially_assessed | unassessed | failed`), and store auditable records
(TRD §11–§12, ARCHITECTURE §10).

The backend performs **all** structured calculations. It does not compute safety scores outside
the risk engine (Rule 7) and does not include facilities in the score (Rule 11).

---

## 2. Scope

### In scope
- FastAPI application with endpoints:
  `POST /api/routes`, `POST /api/analyze`, `GET /api/analyze/{id}`,
  `GET /api/analysis/{id}/hazards`, `GET /api/analysis/{id}/comparison`,
  `GET /api/analysis/{id}/explanation`, `GET /api/health`.
- Request/response schemas and the error schema from TRD §11.2–§11.3.
- Orchestration calling the adapters/services from earlier phases.
- Input validation, timeouts and bounded retries; rate limits where applicable (TRD §15).
- Route comparison + recommendation derived from deterministic results (Rule 10, Rule 9).
- MySQL schema/migrations per TRD §12 / ARCHITECTURE §10, storing config hash + model version.
- Config/secrets loading from `.env` only (Rule 13); structured, secret-free logs.
- API tests (contract, status values, error schema, negative cases).

### Out of scope
- LLM explanation implementation (PHASE_17) — a placeholder endpoint may return the fallback
  text until then.
- Frontend (PHASE_18).
- Any change to detector/risk formulas.

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_13–PHASE_15 complete | Adapters + facilities available |
| P2 | PHASE_12 complete | Risk engine available |
| P3 | User approves installing backend/DB packages | Rule 19 |
| P4 | User approves DB setup (local MySQL) | Rule 19 |
| P5 | Secrets plan approved (`.env`) | Rule 13 |

---

## 4. Detailed procedure

1. **Install approved backend dependencies** (e.g. `fastapi`, `uvicorn`, DB driver) into `.venv`
   only; pin versions (Rule 1, Rule 18).
2. **Scaffold the app** under `src\api\`. Load config from `config\` and secrets from `.env`
   (never committed) (Rule 13).
3. **Implement schemas** exactly per TRD §11.2–§11.3, including the analysis status values and
   error schema.
4. **Implement orchestration** for `POST /api/analyze`:
   routes → segmentation → imagery → preprocessing → detection → aggregation → risk →
   comparison; propagate `assessed | partially_assessed | unassessed | failed`.
5. **Comparison + recommendation:** derive from deterministic scores + **disclosed coverage**;
   never present an unassessed route as safe; never pad routes (Rule 9, Rule 10).
6. **Facilities separation:** expose facilities via a distinct field/path, never inside the
   score (Rule 11).
7. **Persistence (MySQL):** create the schema and migrations per TRD §12; store
   search/routes/segments/imagery_refs/detections/model_versions/scores (with config hash)/
   analysis_history. Minimise personal data (Rule 13).
8. **Validation/security:** input types/ranges/string bounds; file-upload restrictions where
   relevant; bounded retries with backoff; rate limits; safe storage inside the workspace;
   no path traversal (TRD §15).
9. **Logging:** structured, secret-free, inside `logs\`; record model version, config hash and
   coverage per analysis (Rule 17).
10. **Tests (required):**
    - contract tests for every endpoint and status value;
    - error-schema tests;
    - **negative tests:** missing imagery → `unassessed` (not safe); invalid annotations →
      audit failure; empty detections distinct from "no hazards"; routing failure/timeout →
      surfaced error with no fabricated routes.
    Record actual results (Rule 14).
11. **Document** endpoints, schemas, setup and DB migration steps.
12. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_16. |
| A2 | User approves the package list (backend + DB) before install (Rule 19). |
| A3 | User approves creating/initialising the local MySQL database. |
| A4 | Secrets stored only in `.env`; `.env.example` documents names (Rule 13). |
| A5 | No scoring logic outside the risk engine; no facilities in the score (Rule 7, Rule 11). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Endpoints exist | All TRD §11.1 endpoints implemented. |
| V2 | Schemas conform | Requests/responses/errors match TRD §11. |
| V3 | Statuses honest | assessed/partial/unassessed/failed propagate correctly. |
| V4 | No unassessed-safe | Unassessed routes never shown as safe. |
| V5 | Facilities separate | Not inside the score or ranking. |
| V6 | Persistence works | Records written with model version + config hash. |
| V7 | Security | Validation, timeouts, retries, no secrets in logs. |
| V8 | Negative tests | All required negative tests executed and passing. |
| V9 | Secrets safe | No credential committed. |

---

## 7. Acceptance criteria

- [ ] All documented endpoints implemented with correct schemas and statuses.
- [ ] Comparison/recommendation derived from deterministic results with disclosed coverage.
- [ ] Facilities presented separately; score unaffected.
- [ ] MySQL schema/migrations exist and persist auditable records.
- [ ] Negative tests executed with recorded results.
- [ ] No secrets committed; logs secret-free.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. A status cannot be propagated honestly (e.g. failure hidden as success).
2. The design would require scoring outside the risk engine or facilities in the score.
3. Persisting requires storing more sensitive data than necessary (Rule 13).
4. A credential would need to be committed (Rule 13).
5. Required negative tests cannot be made to pass honestly.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation | §4.8 |
| Rule 7 Score ownership | §5 A5, V5 |
| Rule 9 Missing coverage honesty | §4.5, V3–V4 |
| Rule 10 Routing honesty | §4.5 |
| Rule 11 Facilities separate | §4.6, V5 |
| Rule 13 Security/secrets | §5 A4, V9 |
| Rule 14 Testing honesty | §4.10, V8 |
| Rule 17 Auditability | §4.9, V6 |
| TRD §11–§12, §15–§16 | Whole phase |
| ARCHITECTURE §10–§11 | Whole phase |

---

## 10. Honesty note

The API reports **only** verified pipeline results. Error and missing-data paths are first-class
outcomes (`unassessed`/`failed`) and are never masked as success.

---

## 11. Completion report template

```
PHASE_16 — Backend API & Persistence Report
===========================================
Date (actual):        <YYYY-MM-DD>

1. Endpoints implemented
   <method path -> status/test>

2. Schemas
   - request/response: <conform to TRD §11?>
   - error schema:     <conform?>
   - status values:    assessed/partially_assessed/unassessed/failed

3. Comparison & recommendation
   - derived from: <deterministic scores + coverage>
   - unassessed handled: <yes>

4. Facilities separation
   - exposed via: <field/path>
   - score unaffected: <evidence>

5. Persistence (MySQL)
   - schema/migrations: <path>
   - stored fields incl. model_version + config_hash: <yes>
   - personal data minimised: <yes>

6. Security
   - validation: <summary>
   - timeouts/retries/rate limits: <summary>
   - secrets in .env only: <yes>
   - logs secret-free: <yes>

7. Test results (actual)
   - command: <exact>; passed/failed: <n>/<n>
   - negative tests: <list + results>

8. Validation results
   V1 <pass/fail + evidence> ... V9 <pass/fail + evidence>

9. Limitations / honesty note
   <LLM explanation pending PHASE_17; other gaps>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
