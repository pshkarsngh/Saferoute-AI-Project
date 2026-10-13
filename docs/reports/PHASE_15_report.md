# PHASE_15 — Facilities Lookup Service Report

> **Phase ID:** PHASE_15
> **Status:** COMPLETE
> **Date (actual):** 2026-10-13
> **Workspace:** `D:\New folder (3)`
> **Module Version:** `facilities-v1`
> **Predecessor:** PHASE_14 — Permitted Imagery Acquisition Adapter
> **Successor:** PHASE_16 — Backend API & Persistence
> **Governing documents:** master_rules.md (Rules 11, 13, 14, 17, 19, 20), PRD §4.7, TRD §4.7, ARCHITECTURE §8

---

## 1. Provider

| Provider | Terms | Cost | Rate limits | Use |
|---|---|---|---|---|
| **OpenStreetMap Overpass API** | ODbL (open) | $0, no key | Public instance limits | Live (on demand) |
| **`mock_facilities`** | Internal fixtures | $0 | Unlimited/offline | Tests & local demo |

No credentials are required; any future key would load only from `.env` (Rule 13).

## 2. Interface

`get_nearby_facilities(latitude, longitude, radius_m=None, categories=None) -> FacilityResult`

## 3. Records

Facility: `facility_id, category, name, latitude, longitude, distance_m, source, status`.
Result provenance: `provider, categories_requested, radius_m, origin, retrieved_at, limitations, error_message`.

## 4. Separation evidence (Rule 11)

- Score with facilities = Score without facilities (byte-identical `RouteSafetyResult`).
- Test: `TestFacilitiesSeparationGuardrail::test_rule_11_score_unchanged_with_and_without_facilities`.
- Payload-invariant test: facility JSON contains no score/severity/density keys.

## 5. Unavailability handling

Missing/no data → `unavailable` with `no_facilities_found_within_radius`; failures →
`provider_error` / `provider_timeout` / `rate_limited`; bad input → `invalid_request`.

## 6. Test results (actual)

Command: `.\.venv\Scripts\python.exe -m unittest tests.unit.test_facilities_service -v`

- **Passed / Total:** **9 / 9** (`Ran 9 tests ... OK`).

## 7. Validation results

| # | Check | Status | Evidence |
|---|---|:---:|---|
| V1 | Provider permitted | PASS | ODbL / internal mock documented |
| V2 | Interface implemented | PASS | `FacilitiesProvider.get_nearby_facilities` |
| V3 | Separation proven | PASS | Guardrail test (score unchanged) |
| V4 | No fabrication | PASS | `unavailable` returned explicitly |
| V5 | Provenance recorded | PASS | `FacilityResult` fields + test |
| V6 | Error handling | PASS | timeout/error/rate-limit tests |
| V7 | Secrets safe | PASS | no credentials; `.env` only |
| V8 | Tests pass | PASS | 9/9 |

## 8. Limitations / honesty note

Facility data is **context only** and is never mixed into the hazard score or ranking.
Overpass completeness/recency depends on OSM contributors; distances are straight-line.

## 9. Result & next phase

- **Result:** **COMPLETE**
- **Next Phase:** PHASE_16 — Backend API & Persistence.
