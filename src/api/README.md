# SafeRoute AI — Backend API & Persistence (`src.api`)

> **Module Version:** `api-v1`
> **Phase ID:** PHASE_16
> **Governing rules:** master_rules.md Rules 1, 7, 9, 10, 11, 13, 14, 17; TRD §11–§12, §15.

---

## 1. Overview

`src.api` orchestrates the full assessment pipeline and exposes the TRD §11
endpoints. All structured calculations happen in the backend; the risk engine owns
scores (Rule 7) and facilities never enter the score (Rule 11).

**Implementation note (deviation):** the reference design names FastAPI. FastAPI is
not installed and installing packages is gated by Rule 19, so this API is implemented
with the Python **standard library** (`http.server`) and **SQLite** (`sqlite3`). It
runs with zero new dependencies and the schema mirrors TRD §12.

## 2. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service health + model version + config hash |
| POST | `/api/routes` | Resolve available routes (Rule 10) |
| POST | `/api/analyze` | Run the full safety analysis |
| GET | `/api/analyze/{id}` | Full analysis record |
| GET | `/api/analysis/{id}/hazards` | Hazard detections |
| GET | `/api/analysis/{id}/comparison` | Route comparison + recommendation |
| GET | `/api/analysis/{id}/explanation` | Grounded explanation |

### Request bodies

Coordinates must be supplied (no geocoding provider is configured):

```json
{ "origin": {"latitude": 12.9716, "longitude": 77.5946},
  "destination": {"latitude": 12.9352, "longitude": 77.6245} }
```

Error schema (TRD §11.3):

```json
{ "status": "failed", "error": { "code": "...", "message": "...", "detail": "..." } }
```

Status values: `assessed | partially_assessed | unassessed | failed`.

## 3. Pipeline

`routing → imagery → preprocessing → detection → aggregation → risk → comparison → explanation`

- Missing/insufficient imagery → segment `unassessed`, never scored as safe (Rule 9).
- Unassessed routes are **never** ranked or recommended (Rule 9).
- Routes over 100 km use a bounded, evenly-spaced evidence sample and at most one
  frame per assessed segment (config: `app.imagery.long_route`). Skipped segments
  remain explicitly `unassessed` in the coverage denominator and are disclosed in
  the route's `limitations` / `long_route` record; they are never treated as safe.
- Fewer than four routes are returned as-is (Rule 10).

## 4. Persistence

SQLite at `data/saferoute.db` (configurable). Tables mirror TRD §12: `model_versions`,
`searches`, `analyses`, `scores`, `hazard_detections`. Every score row stores
`model_version` + `config_hash` for reproducibility (Rule 17). No personal data stored
(Rule 13).

## 5. Running

```powershell
.\.venv\Scripts\python.exe -m src.api.app
# then: http://127.0.0.1:8000/api/health
```

## 6. Tests

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_api -v
```

## 7. Limitations

- stdlib HTTP server is single-purpose/demo-grade (no async, no auth).
- Geocoding (string destination → coordinates) is not implemented; coordinates required.
- SQLite chosen over MySQL for zero-install operation; schema is portable to MySQL.
