# SafeRoute AI — Phase 15: Facilities Lookup Service

> **Phase ID:** PHASE_15
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_14`](./PHASE_14.md) — Permitted Imagery Acquisition Adapter
> **Successor:** [`PHASE_16`](./PHASE_16.md) — Backend API & Persistence
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## 1. Objective

Implement a **facilities lookup service** that returns nearby facilities (e.g. hospitals,
pharmacies, restaurants, hotels, petrol pumps, police stations) from a **permitted provider**,
while keeping facilities **strictly separate from the hazard score** (Rule 11; TRD §4.7,
ARCHITECTURE §8).

Facilities are a presentation/context concern only. They must never enter the risk engine or
change route safety ranking unless an explicit, documented and approved requirements change
establishes a facility-aware policy (Rule 11).

---

## 2. Scope

### In scope
- Choose/document a permitted facilities provider and its terms.
- Implement `get_nearby_facilities(location, radius, categories)`.
- Return structured facility records (category, name, location, distance, source, status).
- Guarantee **no coupling** to the risk engine; facilities are never an input to `H_i`/`S_i`.
- Handle unavailability honestly (empty/unknown, not fabricated) (Rule 20).
- Tests: normal, empty, provider error, and a guardrail test asserting the score does not change
  when facilities are present.

### Out of scope
- Including facilities in the hazard score or ranking (Rule 11).
- Routing/imagery (PHASE_13/PHASE_14).
- Frontend rendering (PHASE_18).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_13 complete | Locations/geometry available |
| P2 | User approves a permitted facilities provider + terms | Rule 19 |
| P3 | Credentials approach approved (`.env` only) if required | Rule 13 |
| P4 | User approves any paid usage | Rule 19 |

---

## 4. Detailed procedure

1. **Select a permitted provider.** Document source, terms, cost, and rate limits.
2. **Define the interface** `get_nearby_facilities(location, radius, categories)`.
3. **Implement the adapter:** fetch, validate and structure results; record source and status.
4. **Enforce separation (Rule 11):**
   - the risk engine's inputs must not include facility data;
   - ranking must not use facilities;
   - add a test asserting the score is unchanged whether facilities are present or not.
5. **Unavailability honesty:** return an explicit `unavailable`/empty status; never fabricate
   facilities (Rule 20).
6. **Record provenance** (provider, timestamp, radius/categories, status).
7. **Tests:** normal, empty, provider error, rate limit, and the separation guardrail. Record
   actual results (Rule 14).
8. **Document** the service, its provider and the explicit separation policy.
9. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_15. |
| A2 | User approves the facilities provider, terms and any cost. |
| A3 | Any change that would mix facilities into the hazard score requires an **explicit approved requirements change** (Rule 11). |
| A4 | Secrets remain in `.env` only (Rule 13). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Provider permitted | Terms documented and permit use. |
| V2 | Interface implemented | `get_nearby_facilities` exposed. |
| V3 | Separation proven | Test shows score unchanged with/without facilities. |
| V4 | No fabrication | Empty/unknown returned honestly. |
| V5 | Provenance recorded | Source/timestamp/params captured. |
| V6 | Error handling | Provider error/rate limit surfaced explicitly. |
| V7 | Secrets safe | No credential in source. |
| V8 | Tests pass | Tests executed and actually passing. |

---

## 7. Acceptance criteria

- [ ] A permitted facilities provider is approved and documented.
- [ ] The service is implemented and returns structured facility records.
- [ ] A test proves facilities do not change the hazard score or ranking.
- [ ] Unavailability is reported honestly.
- [ ] No credential committed; no unauthorized paid call.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The provider's terms do not permit the intended use.
2. Facilities would be required inside the hazard score to satisfy a request (Rule 11) — this
   needs an approved requirements change.
3. Results would have to be fabricated to fill a category.
4. Credentials or payment would be required without approval (Rule 19).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 11 Facilities separate | Whole phase |
| Rule 13 Secret handling | §5 A4, V7 |
| Rule 14 Testing honesty | §4.7, V8 |
| Rule 20 Honest demonstration | §4.5 |
| Rule 19 No unauthorized actions | §5 A2, §8.4 |
| PRD FR-F1, FR-F2 | Whole phase |
| TRD §4.7 | Whole phase |
| ARCHITECTURE §8 | §4.2–§4.4 |

---

## 10. Honesty note

Facilities are **context**, not safety evidence. They must be displayed separately and must
never imply that a road is safer or riskier. Unavailable facility data is disclosed, not
invented.

---

## 11. Completion report template

```
PHASE_15 — Facilities Service Report
====================================
Date (actual):        <YYYY-MM-DD>

1. Provider
   - name:       <name>
   - terms:      <...>
   - cost:       <...>
   - rate limits:<...>

2. Interface
   - get_nearby_facilities(location, radius, categories) -> <result type>

3. Facility record
   - fields: <category, name, location, distance, source, status>

4. Separation evidence (Rule 11)
   - score with facilities:    <value/unchanged>
   - score without facilities: <value/unchanged>
   - test name:                <...>

5. Unavailability handling
   - behaviour: <explicit unavailable/empty>

6. Test results (actual)
   - command: <exact>; passed/failed: <n>/<n>

7. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

8. Limitations / honesty note
   <facilities are context only; never affect safety score>

9. Result: COMPLETE / BLOCKED / STOPPED
   Next phase authorised? YES / NO (awaiting approval)
```
