# SafeRoute AI — Phase 13: Routing Provider Selection & Adapter

> **Phase ID:** PHASE_13
> **Status:** Complete
> **Predecessor:** [`PHASE_12`](./PHASE_12.md) — Deterministic Risk Engine
> **Successor:** [`PHASE_14`](./PHASE_14.md) — Permitted Imagery Acquisition Adapter
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## 1. Objective

Select a routing provider (resolving open decision TRD §18.1 #4) and implement a
**provider-independent routing adapter** exposing `get_routes`, `get_route_geometry` and
`get_segment_metadata`, returning **only the routes actually returned** (Rule 10) and mapping
failures to explicit statuses (TRD §10, ARCHITECTURE §8).

The adapter isolates the provider so it can be swapped without touching higher layers.

---

## 2. Scope

### In scope
- Evaluate candidate routing providers against cost, coverage, terms and reliability; record the
  decision and rationale.
- Define abstract interfaces (protocols) as specified in TRD §10.1.
- Implement an adapter for the selected provider behind those interfaces.
- Return **exactly** the routes returned; never synthesise/pad to a fixed count (Rule 10).
- Handle edge cases: fewer than four routes, no routes, provider error, timeout (bounded
  retries with backoff), rate limits.
- Decompose routes into assessable segments with **stable identifiers** (FR-R4).
- Record provenance/response metadata for auditability.
- Unit tests with **recorded** provider responses or a documented mock; **never** invent live
  responses.

### Out of scope
- Imagery acquisition (PHASE_14).
- Risk scoring (PHASE_12).
- Facilities (PHASE_15).
- Frontend/API wiring (PHASE_16–PHASE_18).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_12 complete | Scoring available for later comparison |
| P2 | User selects/approves the routing provider and terms | Rule 10, Rule 19 |
| P3 | Credentials approach approved (stored in local `.env` only) | Rule 13 |
| P4 | User approves any paid API usage | Rule 19 |

---

## 4. Detailed procedure

1. **Evaluate providers.** Document candidates and compare on: coverage, cost, terms of
   use, rate limits, reliability, and geometry quality. Record the decision.
2. **Confirm the imagery guardrail.** Explicitly state that the routing provider's terms do
   **not** automatically grant rights to download or reuse street-level imagery (Rule 8).
3. **Define interfaces** exactly per TRD §10.1:
   `get_routes`, `get_route_geometry`, `get_segment_metadata`.
4. **Implement the adapter:**
   - call the provider using credentials from `.env` (never committed) (Rule 13);
   - parse only genuine responses; forbid padding or synthesis (Rule 10);
   - map provider errors to explicit failure statuses with error codes.
5. **Edge-case behaviour** per TRD §10.2:
   | Situation | Behaviour |
   |---|---|
   | Fewer than 4 routes | Return exactly those returned |
   | No routes | Explicit empty/failed status |
   | Request fails/timeouts | Bounded retry with backoff, then surface error |
   | Rate limited | Surface explicitly; back off |
6. **Segmentation:** decompose routes into segments with stable IDs
   (e.g. `seg-<route>-<seq>`) and record length/extent where available.
7. **Provenance:** record provider name/version, request metadata and retrieval timestamps.
8. **Tests:** use recorded fixtures or a mock provider. Test: zero routes, fewer than four,
   error, timeout, and segment-ID stability. Record actual results (Rule 14).
9. **Document** the adapter, configuration and credentials setup safely.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_13. |
| A2 | User **selects and approves** the routing provider and accepts its terms. |
| A3 | User approves any credentials creation and any paid API calls (Rule 19). |
| A4 | Secrets must be stored only in local, uncommitted `.env` (Rule 13). |
| A5 | Using the provider for imagery is **not** granted by this phase (Rule 8). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Provider decided | Selection + rationale recorded. |
| V2 | Interface-only coupling | Higher layers depend on interfaces, not the provider. |
| V3 | No fabrication | Only returned routes are emitted. |
| V4 | Edge cases handled | Fewer than four / none / error / timeout / rate limit. |
| V5 | Stable segment IDs | IDs deterministic per route. |
| V6 | Provenance recorded | Provider + timestamps captured. |
| V7 | Secrets safe | No credential in source; `.env` only. |
| V8 | Tests pass | Tests executed and actually passing (or `blocked` reported). |

---

## 7. Acceptance criteria

- [x] Routing provider selected and terms reviewed/recorded.
- [x] Provider-independent adapter implemented and documented.
- [x] Fewer-than-four and zero-route cases handled without padding.
- [x] Failure/timeout/rate-limit produce explicit errors.
- [x] Segment IDs stable and documented.
- [x] No credential committed; no unauthorized paid call.
- [x] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The provider's terms do not permit the intended use, or are unclear.
2. Credentials would be required but not approved (Rule 19).
3. The adapter would need to synthesise or pad routes (Rule 10).
4. Imagery acquisition would be implied without a permitted source (Rule 8).
5. No provider can be approved, leaving the core flow blocked.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 8 Imagery permission guardrail | §4.2, §5 A5 |
| Rule 10 Routing honesty | §4.4, V3 |
| Rule 13 Secret handling | §5 A4, V7 |
| Rule 14 Testing honesty | §4.8, V8 |
| Rule 17 Documentation | §4.9 |
| Rule 19 No unauthorized actions | §5 A3 |
| PRD FR-R1–FR-R4 | §4.3–§4.6 |
| TRD §10 routing interfaces | Whole phase |
| ARCHITECTURE §8 | Whole phase |

---

## 10. Honesty note

The provider record is **unresolved** until terms are reviewed and approved. This phase may not
invent endpoints, permissions or datasets. Only routes actually returned are used, and fewer
than four is a valid, honest result.

---

## 11. Completion report template

```
PHASE_13 — Routing Adapter Report
=================================
Date (actual):        <YYYY-MM-DD>

1. Provider selection
   - chosen provider: <name>
   - alternatives evaluated: <list>
   - rationale:       <...>
   - terms reviewed:  <yes + notes>
   - imagery guardrail noted: <yes>

2. Interfaces implemented
   - get_routes / get_route_geometry / get_segment_metadata

3. Edge-case behaviour (observed)
   - fewer than 4 routes: <behaviour>
   - no routes:           <behaviour>
   - error/timeout:       <behaviour>
   - rate limited:        <behaviour>

4. Segmentation
   - ID scheme:  <value>
   - stability:  <evidence>

5. Provenance
   - provider version / request metadata / timestamps: <...>

6. Secrets
   - stored in .env only: <yes>
   - nothing committed:   <confirmed>

7. Test results (actual)
   - command:       <exact>
   - passed/failed: <n>/<n>
   - fixtures/mock: <description>

8. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

9. Limitations / honesty note
   <provider unresolved aspects; no imagery rights implied>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
