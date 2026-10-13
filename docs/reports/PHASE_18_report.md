# PHASE_18 — Frontend Integration & End-to-End Validation Report

> **Phase ID:** PHASE_18 · **Status:** COMPLETE · **Date:** 2026-10-14
> **Workspace:** `D:\New folder (3)` · **Predecessor:** PHASE_17
> **Governing:** master_rules.md (1, 9, 10, 11, 12, 14, 18, 20), TRD §14, §16, ARCHITECTURE §14

---

## 1. Frontend implemented

- Destination input + validation/errors: yes (coordinates; no geocoding configured).
- Route alternatives (only returned): yes (Rule 10).
- Scores with basis + coverage: yes.
- Hazard evidence: yes.
- Facilities shown separately: yes (Rule 11).
- Explanation labeled with `source` (ollama/fallback): yes (Rule 12).
- Loading/error states: yes.
- No scoring logic in UI: confirmed (display only).

**Deviation:** implemented as dependency-free HTML/CSS/JS instead of React — no `npm install`
(Rule 19).

## 2. Honesty behaviours

- Unassessed routes visually distinct (grey/italic `unassessed` badge); never shown as safe.
- Fewer-than-four routes shown honestly; no padding.

## 3. E2E tests (actual)

Command: `.\.venv\Scripts\python.exe -m unittest tests.integration.test_end_to_end_api -v`
Flow: destination -> routes -> analysis -> comparison -> explanation (over HTTP).
Result: **7 / 7 passed**.

## 4. Negative tests (actual)

| Negative test | Result |
|---|---|
| Missing imagery -> `unassessed` (not safe) | PASS |
| Invalid destination/annotations -> audit/validation failure | PASS (`invalid_request`, dataset audit PHASE_03) |
| Empty detections != "no hazards exist" | PASS (`NO_DETECTIONS` distinct) |
| LLM unavailable -> fallback | PASS (`source="fallback"`) |
| Routing failure/timeout -> error, no fabricated routes | PASS (`failed`, 0 routes) |

## 5. Honesty table (Rule 20)

| Capability | Status | Evidence |
|---|---|---|
| Routing (OSRM live / mock) | working (mock proven; OSRM untested live) | PHASE_13 tests |
| Imagery adapter (permitted sources) | working (local archive); live Mapillary untested | PHASE_14 tests |
| Preprocessing | working | PHASE_06/10 tests |
| Detector (pothole, crack) | working (limited accuracy) | PHASE_09 metrics; harden detect-v2 |
| Aggregation + risk engine | working | PHASE_11/12 tests |
| Facilities | working (mock); Overpass live untested | PHASE_15 tests |
| Backend API + persistence | working (stdlib/SQLite) | PHASE_16 tests |
| LLM explanation | fallback working; Ollama not enabled | PHASE_17 tests |
| Frontend | working (static) | PHASE_18 E2E |
| Classes waterlogging/speed_bump/uneven/damaged_patch | **unsupported** (not in dataset) | PHASE_09 disclosure |

## 6. Metrics provenance

- All detector metrics trace to PHASE_09; this phase changes none.
- Test set remained isolated; no re-tuning.

## 7. Validation results

| # | Check | Status |
|---|---|:---:|
| V1 | Routes honest | PASS |
| V2 | Coverage honest | PASS |
| V3 | Facilities separate | PASS |
| V4 | Explanation marked | PASS |
| V5 | No unassessed-safe | PASS |
| V6 | E2E passes | PASS (7/7) |
| V7 | Negative tests pass | PASS |
| V8 | Honesty table | PASS |
| V9 | No fabricated claims | PASS |
| V10 | Isolation | PASS |

## 8. System limitations statement

- Detector covers only `pothole` and `crack`; other target classes require additional
  labelled data and are reported unsupported.
- Metrics are from a single CC-BY 4.0 dashcam dataset; not a global guarantee.
- The API is demo-grade (stdlib HTTP, SQLite); LLM uses the fallback unless Ollama is
  approved.
- Missing/insufficient imagery yields `unassessed` segments that are never ranked as safe.

## 9. Result

- **Result:** **COMPLETE**
- Final system acceptance requested: **YES** (pending user review).


