# SafeRoute AI — Frontend (`frontend/`)

> **Phase ID:** PHASE_18
> **Governing rules:** master_rules.md Rules 9, 10, 11, 12, 14, 18, 20; TRD §14, §16.

## Overview

A dependency-free static web UI (HTML/CSS/JS) that displays verified backend results.
It contains **no scoring logic** (Rule 7). It calls the Phase 16 API.

**Implementation note (deviation):** the reference design names React. Installing a
Node/React toolchain is gated by Rule 19, so the UI is implemented with plain
HTML/CSS/JS — no build step, no `npm install`. It can be opened directly in a browser
or served statically.

## Sections

1. Destination input (coordinates; validation/errors).
2. Routes returned — only those actually returned (Rule 10).
3. Comparison & recommendation — from deterministic scores; unassessed routes never
   ranked as safe (Rule 9).
4. Hazard evidence — classes, confidences, severities.
5. **Facilities — separate section, never part of the score** (Rule 11).
6. Explanation — labeled with its `source` (`ollama` / `fallback`), "generated from
   verified data only" (Rule 12).
7. Coverage / limitations / honesty disclosures.

Unassessed routes are visually distinct (grey/italic badge `unassessed`).

## Running (local)

1. Start the API:
   ```powershell
   .\.venv\Scripts\python.exe -m src.api.app
   ```
2. Open `frontend/index.html` in a browser (or serve the folder). The API base
   defaults to `http://127.0.0.1:8000`; override with `window.SAFEROUTE_API`.

## Tests

Backend end-to-end + negative tests:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.integration.test_end_to_end_api -v
```

## Limitations

- No geocoding: coordinates are required (disclosed in the UI).
- Every score must be read together with its coverage and status.
- Detector metrics come only from PHASE_09 and are unaffected by this UI.
