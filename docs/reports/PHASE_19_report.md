# PHASE_19 — Real-Life Enablement Report

> **Status:** COMPLETE · **Date:** 2026-10-14
> **Governing:** master_rules.md Rules 1, 8, 9, 10, 11, 12, 13, 17, 19, 20

## 1. Objective

Make the already-built stack usable in real life with **no new package
installs**: real place-name geocoding, live keyless OpenStreetMap routing and
facilities, real street imagery via Mapillary (token), a local Ollama path, a
map UI, and one-command startup.

## 2. What was added

- `src/config/` — stdlib `.env` loader + typed settings (`config/app.yaml`).
- `src/geocoding/` — Nominatim (keyless) + mock geocoder + factory.
- `src/imagery/mapillary_provider.py` — Mapillary imagery with local fallback.
- `src/api/bootstrap.py` — live provider wiring; `app.py` now serves the UI and
  exposes `/api/geocode` and `/api/config`.
- `frontend/` — Leaflet map, place-name search, device location, route overlays.
- `scripts/run_app.py`, `scripts/run_app.ps1` — one-command launch.
- Aggregate tests for geocoding, Mapillary, and settings.

## 3. Observed live verification (Rule 14)

| Check | Result |
|---|---|
| Nominatim geocode "MG Road, Bengaluru" | OK (2 candidates) |
| OSRM route Bengaluru origin→destination | OK (2 routes, 38 segments) |
| Test suite (`tests/`) | 115 tests, OK |
