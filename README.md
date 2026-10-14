# SafeRoute AI

Intelligent road-safety navigation: it compares the routes a routing provider
actually returns, detects road hazards on **permitted** imagery with a YOLO11
detector, converts verified evidence into a **deterministic hazard-risk score**,
and explains the result through a **grounded LLM** (with a deterministic
fallback).

The defining principle is **evidence honesty**: missing, stale or insufficient
evidence is always disclosed as *unassessed* — never presented as a safe road.

> Governed by [`master_rules.md`](master_rules.md) (authoritative). See
> [`docs/`](docs) for PRD, TRD, architecture, training rules and per-phase
> reports.

## Quick start

```powershell
# 1. Activate / use the workspace virtual environment
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # already installed

# 2. (optional) configure live services
Copy-Item .env.example .env    # then fill in MAPILLARY_ACCESS_TOKEN / OLLAMA_*

# 3. Run API + web UI in one command
.\.venv\Scripts\python.exe scripts\run_app.py
#   or:  .\scripts\run_app.ps1
```

Then open <http://127.0.0.1:8000/>. Type a place name, click **Analyze safety**.

## What runs live (real-life defaults)

| Concern | Default | Key needed |
|---|---|---|
| Geocoding | Nominatim (OpenStreetMap) | no |
| Routing | OSRM (OpenStreetMap) | no |
| Facilities | Overpass (OpenStreetMap) | no |
| Street imagery | Mapillary (CC-BY-SA 4.0) | **`MAPILLARY_ACCESS_TOKEN`** |
| Explanation | local Ollama | Ollama installed |

Every live provider degrades gracefully: with no Mapillary token the permitted
local archive is used (disclosed as a limitation); if Ollama is unreachable the
deterministic fallback explanation is returned. Routing failure is surfaced as
`failed` — synthetic routes are **never** substituted (Rule 10).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service + provider status |
| GET | `/api/config` | Non-secret effective settings |
| POST | `/api/geocode` | Place name → coordinates |
| POST | `/api/routes` | Routes (accepts coords or `destination_query`) |
| POST | `/api/analyze` | Full safety analysis |
| GET | `/api/analyze/{id}` | Analysis record |
| GET | `/api/analysis/{id}/hazards` | Hazard detections |
| GET | `/api/analysis/{id}/comparison` | Route comparison |
| GET | `/api/analysis/{id}/explanation` | Grounded explanation |
| POST | `/api/facilities` | Nearby facilities (separate, Rule 11) |

## Tests

```powershell
# Hermetic unit + end-to-end API tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Known limitations (honest)

- Detector covers **`pothole`** and **`crack`** only (mAP@0.5 ≈ 0.26 on a single
  dashcam dataset); other target classes are reported **unsupported**.
- Metrics are not a global safety guarantee; the deterministic risk engine owns
  all scoring (Rule 7), and the LLM only explains (Rule 12).
- Imagery is limited to permitted sources; Google Street View is intentionally
  **not** wired (its terms forbid automated reuse).
- Manual coordinates remain available as an offline fallback.


