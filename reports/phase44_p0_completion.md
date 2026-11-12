# Phase 44 - P0 Completion Report

**Status:** COMPLETE (with explicitly listed `NOT_VERIFIED` / `NOT_ASSESSED` items)
**Generated (UTC):** 2026-11-11T17:14:40Z
**Git HEAD:** `b3ee84fc2f2de50eb1fdba6d48d8729179ed49f0` (`main`, uncommitted working tree)
**Python:** 3.12.10 (`.venv`)
**Environment:** Windows, repository `D:\COde\Major project\Saferoute-AI-Project`

This phase fixed the reported failures and completed the P0 runtime/frontend/documentation
work. No test was skipped, no assertion was deleted, and no safety logic was weakened.
No retraining, checkpoint/marker manipulation, risk-formula/threshold change, synthetic
data, dependency installation/download, commit, or push was performed. Phase 45 was not
started.

---

## 1. Reported failures: root cause and resolution

**Root cause.** The pre-existing default-origin fallback (Bengaluru coordinates) was
removed in the working tree, so requests without explicit coordinates correctly became
`400`. Test fixtures still relied on the removed fallback. The correct fix was to supply
real coordinates in fixtures, **not** to restore the fallback.

**Baseline before fixes** (`tests` discovery, `unittest`):

```
Ran 459 tests in 50.933s
FAILED (failures=11, errors=8)
```

That is **19** failing tests (11 failures + 8 errors). The task described 22; the
additional 3 were **not reproducible** against this working tree and are recorded as
`NOT_VERIFIED` (see section 10). No failure was suppressed.

**Files updated with explicit, valid coordinates:**

| File | Change |
|---|---|
| `tests/unit/test_api.py` | Explicit origin/destination fixtures; no default-origin reliance |
| `tests/integration/test_end_to_end_api.py` | Explicit origin fixture for every analyze/routes call |
| `tests/unit/test_stale_fresh_regression.py` | Explicit origin fixture |
| `tests/integration/test_end_to_end_pipeline.py` | Truthful `SMOKE_SUBSTITUTE` identity assertions |
| `tests/unit/test_detection.py` | Truthful `SMOKE_SUBSTITUTE` identity assertions |

**New regression coverage (7 tests, no deletions):**

- `tests/unit/test_api.py`
  - `test_missing_origin_rejected` - missing origin is `400 missing_location`
  - `test_missing_destination_rejected` - missing destination is `400 missing_location`
  - `test_malformed_coordinates_rejected` - string/missing/1-element/empty pair is `400 invalid_coordinates`
  - `test_out_of_range_coordinates_rejected` - lat +/-91, lon +/-181, NaN, Infinity are `400 invalid_coordinates`
- `tests/unit/test_detection_validation_gate.py` (new)
  - unvalidated production detector suppresses an existing recommendation
  - validated production detector preserves the recommendation
  - injected test detector is exempt but disclosed (`required_for_recommendation=false`)

The API contains **no** default-origin fallback. A search for `Bengaluru`/`12.9716` in
`src/` finds only the mock geocoder's place-name table and imagery documentation, never
an implicit route origin.

---

## 2. Final test suite (exact counts)

Command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Result (`reports/phase44_evidence/final_unittest.txt`):

```
Ran 466 tests in 26.885s
OK
```

| Metric | Count |
|---|---|
| Tests run | **466** |
| Passed | **466** |
| Failed | **0** |
| Errored | **0** |
| Skipped | **0** |

The only stderr noise is expected fake-provider retry logging
(`[facilities] overpass failed ... primary.example ...`) from negative-path tests; it
does not indicate a test failure.

---

## 3. Coordinate validation (live HTTP)

Nine invalid-input cases were sent to **both** `/api/routes` and `/api/analyze` on
port 8000. Every case returned HTTP `400`:

| Case | Error code |
|---|---|
| missing origin | `missing_location` |
| missing destination | `missing_location` |
| `null` origin | `missing_location` |
| malformed object (`latitude: "abc"`) | `invalid_coordinates` |
| malformed pair (`[18.9]`) | `invalid_coordinates` |
| out-of-range latitude (`999`) | `invalid_coordinates` |
| out-of-range longitude (`-400`) | `invalid_coordinates` |
| `NaN` latitude | `invalid_coordinates` |
| `Infinity` latitude | `invalid_coordinates` |

A spot check on port 8765 (missing origin, malformed, out-of-range) also returned
`400` with the same codes. Evidence: `reports/phase44_evidence/live_evidence.json`.

---

## 4. Truthful model identity

Serving checkpoint: `models/training/saferoute-yolo11-v2/weights/best.pt`
`sha256 = 19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0`
(5,443,482 bytes). `P0_SMOKE_SUBSTITUTE.json` is present; it is **not** genuine v1/v2.

Health, config, and analysis agree exactly on both ports:

| Field | Value |
|---|---|
| `model_version` | `p0-smoke-substitute` |
| `model_status` | `SMOKE_SUBSTITUTE` |
| `detection_validated` | `false` |
| `model_identity.checkpoint_sha256` | `19619F99...B916D0` |
| `declared_model_version` | `saferoute-yolo11-v2` (declared config only) |

The UI badge rendered in a real browser:

> Detection model: P0 smoke substitute (NOT validated) - no safety claims [p0-smoke-substitute]

No smoke checkpoint is labelled genuine v1 or v2 anywhere in API responses, docs, or UI.

---

## 5. Production recommendation gate

**Live behavior** (port 8000 Mumbai analysis `an-b776c066173f`, port 8765 Delhi analysis
`an-1fc07ea4f4d4`):

- `recommendation = null`
- `comparison.recommended_route_id = null`
- `detection_validation = {required_for_recommendation: true, validated: false,
  model_status: "SMOKE_SUBSTITUTE", model_version: "p0-smoke-substitute",
  recommendation_suppressed: false}`
- Limitation appended: "Detection model status is SMOKE_SUBSTITUTE
  (p0-smoke-substitute); detection is not validated and no real-world safety
  recommendation is made."

`recommendation_suppressed` is `false` live because the deterministic comparer had
**already** withheld a recommendation for an independent reason (all available imagery
was stale, `comparability=no_sufficiently_assessed_route`); there was no existing
recommendation to suppress. The gate still ran (`required_for_recommendation=true`) and
kept `recommendation` null.

**Proof the gate suppresses an existing recommendation** is pinned by
`tests/unit/test_detection_validation_gate.py`: when a comparison does contain
`recommended_route_id`, an unvalidated production detector clears it, sets
`recommendation_status=cannot_determine`, `comparability=detection_not_validated`, and
`recommendation_suppressed=true`. A validated detector preserves it; injected test
detectors remain exempt. The deterministic scores, formula, and thresholds are untouched.

---

## 6. Route integrity (no fabrication / padding)

Back-to-back `/api/routes` preview and `/api/analyze` on port 8000 with identical
coordinates returned the same 3 routes from the same providers:

| Provider | Distance (m) | Duration (s) |
|---|---|---|
| osrm | 13,009.5 | 1,002.4 |
| osrm | 13,386.8 | 907.7 |
| valhalla | 33,559.0 | 4,364.7 |

Preview and analysis signatures were **identical**; both listed providers
`["osrm", "valhalla"]`; neither added nor removed a route. Route IDs differ between
calls because the routing adapters suffix them with a per-request `uuid4` value
(`src/routing/osrm_adapter.py`, `src/routing/valhalla_adapter.py`); that is identifier
generation, not fabricated route content.

---

## 7. Frontend runtime configuration and live autocomplete

**Runtime API base.** `/runtime-config.js` is served by the backend with
`apiBaseUrl: ""` by default (same origin), so the UI follows whatever host/port serves
it. The built bundle was patched in place
(`scripts/phase44/patch_frontend_bundle.py`); the byte-identical pre-edit backup is at
`frontend/backup/phase44_pre_edit/`.

Bundle checks:

- `node --check` on the patched bundle: **OK**
- `http://localhost:8000` occurrences: **1** (the intentional final `location.origin` fallback)
- `SAFEROUTE_API_BASE_URL` occurrences: **6**
- `__srLive` occurrences: **5**
- `/api/geocode` occurrences: **1**

**Live Nominatim autocomplete in a real browser.** Chrome 157 headless was driven via
the DevTools Protocol with genuine mouse clicks and text insertion (not just backend
calls):

| Port | Result |
|---|---|
| 8765 | Typing "Gateway of India" produced `aria-expanded=true`, a `role=listbox` with 2 live options, labels "(live geocoding - OpenStreetMap)", `POST /api/geocode -> 200`, **0 console errors** |
| 8000 | Typing "India Gate" produced 1 live option from Nominatim, `POST /api/geocode -> 200`; selecting it set the field to "India Gate" and closed the dropdown; **0 console errors** |

The 8765 test proves the UI is **not** hardcoded to port 8000: both the page and the
geocode request used `http://127.0.0.1:8765`.

Screenshots (captured from the real browser):

- `reports/phase44_evidence/ui_8000_autocomplete.png` (1348x804 PNG)
- `reports/phase44_evidence/ui_8765_autocomplete.png` (1348x804 PNG)

Automated DOM/behavior verification passed. Human visual/aesthetic review of the
screenshots is `NOT_VERIFIED` because the agent cannot view image content.

---

## 8. Ports and live endpoints

Both servers were started with `scripts/run_app.py --no-browser --port <port>` and
verified independently:

| Check | 8000 | 8765 |
|---|---|---|
| `/api/health` | 200, truthful identity | 200, truthful identity |
| `/api/config` | 200, truthful identity | 200, truthful identity |
| `/runtime-config.js` | 200, `apiBaseUrl: ""` | 200, `apiBaseUrl: ""` |
| `/` (SPA index) | 200, references runtime/model-status scripts | 200 |
| `/assets/index-CXsvefbt.js` | 200, 1,587,479 bytes | 200, same bytes |
| `/model-status.js` | 200 | 200 |
| `POST /api/geocode` (live Nominatim) | 200 with real candidates | 200 with real candidates |
| `POST /api/analyze` (valid coordinates) | 200, recommendation null | 200, recommendation null |

Verification servers were temporary and were stopped after evidence capture.

---

## 9. Protected state and secrets

### 9.1 Protected hashes (unchanged)

| Artifact | Current SHA-256 | Phase 42 baseline |
|---|---|---|
| `config/detection.yaml` | `22371AE8C1DA3CBA77E40EE096337915D16C0CFDDB9E7E2AF9213F4BE1B18344` | MATCH |
| `config/hazard_severity.yaml` | `D11AA0F73511E4EEF4B49869D2D009F5F06048801A1B03A64ED5CDB407CDF473` | MATCH |
| `src/risk/engine.py` | `16319D56B457D039E7E92458BE8F3BCF2443039382EA2D4597E0E5AF3AC834EE` | MATCH |
| `src/risk/aggregate.py` | `3144F027F80D0517D3A4F85A0CB4B64F887800684E5F6EC1AFDF24B79942A10C` | MATCH |
| `config/risk_engine.yaml` | `61B8143B42DF7FA76D2FF53902D4509D864D75B2705898FB32466E1559621D01` | `NOT_RECORDED` in Phase 42 manifest; `git diff` clean |

Checkpoint and marker were not modified:

| Artifact | SHA-256 |
|---|---|
| serving checkpoint | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` |
| `P0_SMOKE_SUBSTITUTE.json` | `8B69C24E7B86976B3038BBA4B5BBFB639094EDC852FBAA4DC49EB933AF795D05` |

Full machine-readable record: `reports/phase44_evidence/final_hashes.json`.

### 9.2 Secrets

- `.env` is present and **not tracked** by git.
- Only `MAPILLARY_ACCESS_TOKEN` is secret-like in `.env`.
- Its value does **not** appear in `/api/health`, `/api/config`,
  `/runtime-config.js`, `/`, `/model-status.js`, or the JS bundle.
- `health`/`config` do not even mention the secret key names.
- Token-shaped string scan across those responses: **0**.
- `.env.example` documents `SAFEROUTE_API_BASE_URL` only; no secret values.

---

## 10. Documentation corrections

- `README.md`
  - Added an explicit "Detector status is not production-validated" limitation with the
    smoke marker, hash, `SMOKE_SUBSTITUTE` status, and recommendation suppression.
  - Replaced the unqualified `mAP@0.5 ~= 0.26` claim with "reported, not independently
    verified", noted its conflict with Phase 40's reported `mAP50 0.0423`, and stated
    that no current accuracy claim is made.
  - Clarified the intro so the YOLO11 detector is not presented as validated.
- `docs/reports/PHASE_42_INDEPENDENT_EVALUATION.md` - rewritten to the honest
  `NOT_ASSESSED` position (genuine v2 absent; smoke substitute refused; no metrics).
- `docs/reports/PHASE_43_P2_P3.md` and `docs/datasets/*` - already describe evaluation
  as BLOCKED and forbid presenting smoke/pretrained weights as genuine v2.

---

## 11. Not verified / not assessed

| Item | Status | Reason |
|---|---|---|
| The 3 extra reported failures beyond the 19 reproduced (22 total) | `NOT_VERIFIED` | Baseline in this tree produced exactly 11 failures + 8 errors; no additional failing test could be reproduced or identified |
| Genuine `saferoute-yolo11-v2` accuracy / deployment readiness | `NOT_ASSESSED` | Genuine checkpoint absent; canonical path holds the P0 smoke substitute; independent dataset missing |
| Frontend source-project npm install/build/lint/test | `NOT_VERIFIED` | `frontend/Frontend/project frontend` and its `package.json` are not present in this repository; only built assets exist |
| Human visual review of UI screenshots | `NOT_VERIFIED` | Screenshots were captured from a real browser, but the agent cannot view image content; DOM/behavior was verified programmatically |
| Live demonstration of `recommendation_suppressed=true` | `NOT_VERIFIED` live, verified by unit test | Live imagery was stale, so the comparer withheld a recommendation before the gate; the gate's suppression of an existing recommendation is proven by the new regression test |

---

## 12. Evidence index

| Artifact | Purpose |
|---|---|
| `reports/phase44_evidence/final_unittest.txt` | Full final suite output (`Ran 466 tests ... OK`) |
| `reports/phase44_evidence/live_evidence.json` | Identity consistency, route parity, 400 matrix, gate fields |
| `reports/phase44_evidence/final_hashes.json` | Protected/checkpoint/bundle hashes and baseline comparisons |
| `reports/phase44_evidence/ui_8000_autocomplete.png` | Real-browser live autocomplete on port 8000 |
| `reports/phase44_evidence/ui_8765_autocomplete.png` | Real-browser live autocomplete on port 8765 |
| `reports/phase44_bundle_manifest.json` | Pre/post bundle hashes and backup path (matches current files) |
| `tests/unit/test_detection_validation_gate.py` | Recommendation-gate regression tests |
