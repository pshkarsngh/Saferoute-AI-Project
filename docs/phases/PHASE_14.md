# SafeRoute AI — Phase 14: Permitted Imagery Acquisition Adapter

> **Phase ID:** PHASE_14
> **Status:** Complete
> **Predecessor:** [`PHASE_13`](./PHASE_13.md) — Routing Provider Selection & Adapter
> **Successor:** [`PHASE_15`](./PHASE_15.md) — Facilities Lookup Service
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## 1. Objective

Implement the **imagery adapter** that retrieves road imagery **only from permitted sources**,
records provenance/timeliness, and returns an explicit `Unavailable` result when imagery is
missing, stale, disallowed or unmatched (Rule 8, Rule 9; TRD §10, ARCHITECTURE §8).

This resolves open decision TRD §18.1 #3 (permitted imagery source). The core guardrail:
**never assume a routing API grants permission to download or reuse street-level imagery.**

---

## 2. Scope

### In scope
- Determine and document the **permitted imagery source** and its licence/terms.
- Implement `get_imagery(segment_id, permitted_source) -> ImageRef[] | Unavailable`.
- Record per-image provenance: source, licence, capture/retrieval timestamps, staleness,
  status.
- Segment-to-image matching method, with accuracy/limitations documented.
- Return `Unavailable` (→ segment `unassessed`) for missing/stale/inaccessible/disallowed
  imagery.
- Persist images to a workspace-local path; record references; never overwrite sources.
- Tests with recorded fixtures/mocks for available, missing, stale and unmatched cases.

### Out of scope
- Downloading imagery from non-permitted sources (forbidden, Rule 8).
- Preprocessing (PHASE_06) and inference (PHASE_10).
- Scoring (PHASE_12).
- Treating unavailable imagery as safe (forbidden, Rule 9).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_13 complete | Segment identifiers available |
| P2 | User approves a specific permitted imagery source, with its terms | Rule 8, Rule 19 |
| P3 | User approves any imagery download/usage | Rule 19 |
| P4 | Storage path inside the workspace approved | Rule 1 |

---

## 4. Detailed procedure

1. **Select a permitted source.** Document the source, its licence/terms, permitted uses, and
   any attribution. Explicitly confirm it allows the intended storage/processing/reuse.
2. **Record the guardrail:** the routing provider's terms do **not** grant imagery rights; only
   an explicitly reviewed source may be used (Rule 8).
3. **Define the interface** `get_imagery(segment_id, permitted_source)`.
4. **Implement retrieval:**
   - fetch only from the permitted source;
   - store images under an approved workspace path (e.g. `data\imagery\`);
   - return `ImageRef` records (id, path, source, licence, captured_at, retrieved_at, status).
5. **Timeliness/staleness:** define a documented staleness rule and flag stale images rather
   than presenting them as current (Rule 9).
6. **Segment matching:** document the matching method (coordinates/geometry overlap) and its
   accuracy limits; unmatched segments → `unassessed`.
7. **Unavailable handling:** missing, stale, inaccessible, disallowed or unmatched → `Unavailable`
   (never "clean") (Rule 9).
8. **Tests:** fixtures/mocks for available, missing, stale, inaccessible, unmatched. Confirm the
   adapter never fabricates an image reference. Record actual results (Rule 14).
9. **Document** the adapter, the source licence and the matching method.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_14. |
| A2 | User **approves the specific permitted imagery source and its terms** (Rule 8). |
| A3 | User approves any download and its storage location (Rule 19). |
| A4 | Using imagery not covered by the approved licence is forbidden. |
| A5 | No imagery may be fetched from a routing provider by default (Rule 8). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Source permitted | Licence/terms documented and permit the use. |
| V2 | No forbidden source | No imagery from unpermitted sources. |
| V3 | Provenance recorded | Source, licence, timestamps captured per image. |
| V4 | Staleness flagged | Stale imagery flagged, not shown as current. |
| V5 | Unavailable handled | Missing/stale/unmatched → `Unavailable`. |
| V6 | Matching documented | Method + accuracy limits recorded. |
| V7 | No fabrication | Adapter never invents image references. |
| V8 | Workspace-local storage | All stored imagery inside the workspace. |
| V9 | Tests pass | Tests executed and actually passing. |

---

## 7. Acceptance criteria

- [x] A permitted imagery source is approved and documented with terms.
- [x] Imagery adapter implemented behind the interface.
- [x] Provenance/timeliness recorded per image.
- [x] Unavailable/stale/unmatched handled as `unassessed` (never safe).
- [x] No imagery from unpermitted sources.
- [x] Tests execute with recorded results.
- [x] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. No permitted imagery source can be approved → assessment pipeline is blocked; report.
2. The only available source's terms forbid storage/processing/reuse.
3. A routing provider would be misused to fetch imagery (Rule 8).
4. Matching cannot be made defensible, leaving most segments unassessed.
5. Imagery would be stored outside the workspace (Rule 1).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Workspace isolation | §4.4, V8 |
| Rule 8 Permitted imagery only | Whole phase |
| Rule 9 Missing/stale imagery handling | §4.5–§4.7, V4–V5 |
| Rule 14 Testing honesty | §4.8, V9 |
| Rule 19 No unauthorized actions | §5 A3 |
| PRD FR-I1–FR-I3 | Whole phase |
| TRD §10 imagery interfaces | §4.3–§4.7 |
| ARCHITECTURE §8 | Whole phase |

---

## 10. Honesty note

If no permitted imagery source is available, the system must honestly report segments as
**unassessed**. Unavailable imagery is **never** evidence of a safe road (Rule 9).

---

## 11. Completion report template

```
PHASE_14 — Imagery Adapter Report
=================================
Date (actual):        <YYYY-MM-DD>

1. Permitted source
   - source:     <name>
   - licence:    <type + terms>
   - permitted uses: <stated>
   - attribution: <required?>
   - guardrail noted (routing API != imagery rights): <yes>

2. Interface
   - get_imagery(segment_id, permitted_source) -> <result type>

3. Provenance record
   - fields: <id, path, source, licence, captured_at, retrieved_at, status>

4. Staleness rule
   - definition: <...>
   - flagged behaviour: <...>

5. Segment matching
   - method:     <...>
   - accuracy/limits: <...>
   - unmatched -> <Unavailable/unassessed>

6. Storage
   - path:       <workspace path>
   - inside workspace: <yes>

7. Test results (actual)
   - available / missing / stale / inaccessible / unmatched: <behaviour>
   - command: <exact>; passed/failed: <n>/<n>

8. Validation results
   V1 <pass/fail + evidence> ... V9 <pass/fail + evidence>

9. Limitations / honesty note
   <unassessed segments disclosed; no safety inference from absence>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
