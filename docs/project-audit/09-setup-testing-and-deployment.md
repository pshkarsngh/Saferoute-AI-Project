# 09 — Setup, Testing and Deployment

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Related:** [`03-technology-stack-and-libraries.md`](03-technology-stack-and-libraries.md) ·
> [`08-security-and-reliability.md`](08-security-and-reliability.md)

---

## 1. Prerequisites

| Requirement | Detail | How to check |
|---|---|---|
| Python 3.12 | 3.12.10 installed in `.venv` | `.\.venv\Scripts\python.exe --version` |
| Node.js + npm | Required only for the frontend build | `node --version` |
| GPU | NVIDIA RTX 5050 Laptop (8 GB VRAM) — used for training; inference falls back to CPU | `nvidia-smi` |
| Disk | The workspace holds several GB of datasets, checkpoints and a 105 MB video | — |
| Mapillary token | Optional; without it, imagery is unavailable and segments are honestly unassessed | — |
| Ollama | Optional; without it, explanations fall back to the deterministic template | — |

**Note on `pytest`.** `pytest` is **not installed** and `requirements-dev.txt` is
header-only by design (Rule 18). Every test command below uses `unittest`.

## 2. Backend setup

```powershell
# 1. Create the workspace-local virtual environment (if it does not exist)
py -3.12 -m venv .venv

# 2. Install the pinned runtime dependencies
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt

# 3. (optional) verify the install matches the lock exactly
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-lock.txt

# 4. Create the local secrets file from the template
Copy-Item .env.example .env
#    then edit .env and set MAPILLARY_ACCESS_TOKEN and the OLLAMA_* values
```

`.env` is gitignored. `.env.example` is tracked and contains **variable names only**.

### 2.1 Verification

```powershell
.\.venv\Scripts\python.exe -c "import torch, ultralytics, cv2, numpy, yaml; print(torch.__version__, torch.cuda.is_available())"
```

**Expected:** `2.13.0+cu130 True` on the CUDA build.

## 3. Running the system

### 3.1 Single-command start (API + UI)

```powershell
.\.venv\Scripts\python.exe scripts\run_app.py
```

`scripts/run_app.py` accepts `--host`, `--port` and `--no-browser`. The API process also
serves the prebuilt `frontend/` directory, so a single process covers API and UI on
`http://127.0.0.1:8000`.

PowerShell equivalent:

```powershell
.\scripts\run_app.ps1
```

### 3.2 Separate frontend dev server

```powershell
cd "frontend\Frontend\project frontend"
npm install
npm run dev
```

The frontend reads `VITE_API_URL` from its own `.env`. **There is no Vite dev proxy** —
the browser calls the backend directly, so `VITE_API_URL` must point at the running API.

### 3.3 Production-style preview of the built frontend

```powershell
cd "frontend\Frontend\project frontend"
npm run build
npm run preview      # serves dist/ on 127.0.0.1:8123
```

This is the configuration used for the Phase 2 browser verification.

### 3.4 Ollama

```powershell
ollama serve
ollama pull llama3:latest
```

The model name must match `config/app.yaml` → `app.llm.model` (currently `llama3:latest`).
If Ollama is absent the explanation layer
returns the deterministic fallback and the rest of the analysis is unaffected.

## 4. Testing

### 4.1 Backend

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

**Last measured result: `Ran 299 tests … OK`.**

> **PowerShell note.** `unittest` writes its summary to **stderr**. PowerShell may report
> "Exited with code 1" even on a fully successful run. Read the
> `Ran 299 tests … OK` line — that is the authoritative signal, not the exit code.

Run from the workspace root. When running scripts from another directory, set
`PYTHONPATH` to the workspace root.

**Per-suite runs:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests\unit -t .
.\.venv\Scripts\python.exe -m unittest discover -s tests\integration -t .
.\.venv\Scripts\python.exe -m unittest tests.unit.test_facilities_service
```

### 4.2 Frontend

```powershell
cd "frontend\Frontend\project frontend"
npm run test:frontend     # node tools/frontend-tests/run.mjs
```

**Last measured result: 58 checks, 0 failures.**

The harness is hand-written: 49 static `check()` sites that expand to 58 runtime checks
at execution. It is not a Jest/Vitest suite and does not use a test framework.

### 4.3 Frontend build and lint

```powershell
npm run build             # tsc -b && vite build  -> clean
npm run lint              # oxlint               -> 0 errors
```

### 4.4 Browser check (not wired to an npm script)

```powershell
cd "frontend\Frontend\project frontend"
node tools/browser-test/run.mjs http://127.0.0.1:8123
```

A hand-written Chrome DevTools Protocol driver that launches **Microsoft Edge**
headless and exercises the real UI. 15 static checks expanding to 11–15 runtime checks
depending on branch coverage.

**Exit code 2** means "Microsoft Edge not found; skipping browser test" — this is a
*skip*, not a failure, and must not be reported as a pass.

Edge is located at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` or
`C:\Program Files\Microsoft\Edge\Application\msedge.exe`. Launch flags:
`--headless=new --disable-gpu --no-first-run --no-default-browser-check
--remote-debugging-port=9333 --user-data-dir=%TEMP%\saferoute-edge-profile`.

The fixture trip is Howrah Bridge, Kolkata → Salt Lake Sector V, Kolkata.

### 4.5 What is **not** tested

| Area | Status |
|---|---|
| Frontend unit/component tests | **Not found** — no Jest/Vitest |
| Frontend E2E (Playwright/Cypress) | **Not found** — hand-written CDP script |
| Python coverage measurement | **Not found** — `coverage` is not installed; no coverage percentage exists |
| Python linting / type checking | **Not found** — no ruff/flake8/mypy |
| Load / stress testing | **Not found** |
| Security scanning (`pip-audit`, `npm audit`) | **Not found** |
| Live-provider integration tests | **Not found** — every provider is stubbed in tests; live behaviour was verified manually |

## 5. CI/CD status

**There is no CI/CD in the core repository.** Verified by tree scan:

| Expected | Found |
|---|---|
| `.github/workflows/` | **Not found** |
| `.gitlab-ci.yml` / `azure-pipelines.yml` | **Not found** |
| `Dockerfile` (core repo) | **Not found** |
| `docker-compose.yml` (core repo) | **Not found** |
| `Makefile` | **Not found** |
| `tox.ini` / `noxfile.py` | **Not found** |
| `pyproject.toml` / `setup.py` | **Not found** |
| `.pre-commit-config.yaml` | **Not found** |
| `CODEOWNERS` | **Not found** |

**One exception, in a different sub-project.** `frontend/Frontend/project frontend/SafeRouteAI/`
contains a `docker-compose.yml` and a `backend/Dockerfile`. This belongs to a separate
sub-project and does **not** containerise the core SafeRoute AI backend.

**Consequence.** Every check described in §4 must be run manually, and nothing prevents
a regression from being committed. F-11.

### 5.1 The single highest-value CI addition

A minimal workflow would be:

```yaml
# .github/workflows/ci.yml  (proposed — not created by this audit)
name: ci
on: [push, pull_request]
jobs:
  backend:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements-lock.txt
      - run: python -m unittest discover -s tests
  frontend:
    runs-on: windows-latest
    defaults: { run: { working-directory: frontend/Frontend/project frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci
      - run: npm run lint
      - run: npm run build
      - run: npm run test:frontend
```

This is a **proposal**, not an implemented artefact. It has not been created, and
creating it requires approval (Rule 19) and a decision about the nested-repository
layout, which is itself a finding.

### 5.2 The nested-repository problem

The frontend lives in a **separate Git repository** inside the core repository, and the
outer `.gitignore` excludes it. Consequences:

- A single `git clone` of the core repository does **not** bring the frontend.
- A single PR cannot span both repositories.
- CI in the core repository cannot run the frontend checks without an extra clone step.
- Change review and contribution accounting must be done in two places.

This is a structural issue that deserves a decision — either vendor the frontend into
the core repository, or maintain it as a published package/submodule with an explicit
sync procedure.

## 6. Deployment

### 6.1 Current state — local, single-host

| Component | Deployment | Status |
|---|---|---|
| Backend | `scripts/run_app.py` on `127.0.0.1:8000` | Working |
| Frontend | Prebuilt `frontend/` served by the API, or `vite preview` on `127.0.0.1:8123` | Working |
| Database | SQLite file at `data/saferoute.db` | Working |
| LLM | Local Ollama at `127.0.0.1:11434` | Working |
| Imagery | Mapillary (external, token required) | Working; capture timestamps missing (F-20) |
| Routing | OSRM (external, keyless) | Working |
| Facilities | Overpass (external, keyless) | **All mirrors unreachable from this host** |
| Reverse proxy / TLS | — | **Not present** |
| Containerisation | — | **Not present** |
| Process supervision | — | **Not present** |
| Authentication | — | **Not present** |
| Migrations | — | **Not present** |
| Logging to file | — | **Not present** (`log_message` is a no-op) |
| Monitoring / health checks | `/api/health` only | Minimal |

### 6.2 A note on `vercel.json`

The frontend package contains a `vercel.json` declaring framework `vite`, output
directory `dist` and rewrites. **This is not a working deployment of SafeRoute AI** —
the backend is not deployed by it, and SQLite persistence, the local LLM and the
Mapillary token have no place in a static-hosting deployment. The file is a leftover
scaffold. It is recorded here so that no one mistakes it for a deployment plan.

### 6.3 Deployment readiness checklist

Against TRD §15 and `docs/ARCHITECTURE.md` §11:

| Requirement | Status |
|---|---|
| Input validation on all endpoints | Partial |
| File upload restrictions | N/A — there is no upload endpoint |
| API timeouts and bounded retries | ✅ Implemented for every provider |
| Rate limits (per client and per provider) | **Provider only** — no per-client limit |
| Secret handling via `.env` | ✅ |
| Safe logging (no secrets or personal data) | ✅ |
| Pinned dependencies | ✅ Backend fully pinned |
| Recovery behaviour | ✅ Analyses are persisted and re-readable; failures are explicit |
| Database migrations | **Not present** |
| Authentication / authorisation | **Not present** |
| TLS termination | **Not present** |
| Structured log output to `logs/` | **Not present** for the API server |

**Conclusion.** The system is **deployment-ready for a local, single-user, evaluation
setting** and is **not** deployment-ready for a shared or public environment. The gap is
not in the ML or the API logic; it is entirely in the operational layer.

## 7. Reproducible command index (Rule 14)

Every command the project relies on, in one place. This is the checklist a reviewer
should run to reproduce the audit's claims.

| Purpose | Command | Expected (last measured) |
|---|---|---|
| Backend tests | `.\.venv\Scripts\python.exe -m unittest discover -s tests` | `Ran 299 tests … OK` |
| Backend unit tests only | `.\.venv\Scripts\python.exe -m unittest discover -s tests\unit -t .` | OK |
| Backend integration tests only | `.\.venv\Scripts\python.exe -m unittest discover -s tests\integration -t .` | OK |
| Installed versions | `.\.venv\Scripts\python.exe -c "import importlib.metadata as md; ..."` | 40 packages match the lock |
| Frontend checks | `npm run test:frontend` | 58 checks, 0 failures |
| Frontend lint | `npm run lint` | 0 errors |
| Frontend build | `npm run build` | clean |
| Browser check | `node tools/browser-test/run.mjs http://127.0.0.1:8123` | all passed (Edge present) |
| Start API + UI | `.\.venv\Scripts\python.exe scripts\run_app.py` | listening on 127.0.0.1:8000 |
| Health | `curl http://127.0.0.1:8000/api/health` | `saferoute-yolo11-v2` |
| Config summary | `curl http://127.0.0.1:8000/api/config` | no secrets |
| Facilities (live) | `POST /api/facilities` with a route polyline | `provider_error` from this host |
| Flow measurement | `python scripts/measure_flow.py <port> <routes_body.json> <analyze_body.json>` | latency report |
| Dataset audit | `scripts/audit/*.py` | read-only; writes only under `reports/` |

## 8. Setup and deployment findings

| ID | Finding | Severity |
|---|---|---|
| F-11 | No CI/CD in the core repository | **High** |
| — | Nested frontend repository breaks single-clone / single-PR workflows | Medium |
| — | No containerisation for the core repository | Medium (for any non-local deployment) |
| — | No database migration mechanism | Medium |
| — | No authentication, rate limiting or body-size limit | High for non-local deployment (F-12) |
| — | API server writes no structured logs to `logs/` | Medium |
| — | `vercel.json` is a misleading leftover scaffold | Low |
| — | `requirements-dev.txt` header-only → no linting/typing/coverage tooling | Low (deliberate) |
| — | Frontend `strict` mode off; no ESLint/Prettier | Medium (F-16) |
| — | Browser check exits with code 2 when Edge is absent, which can be misread | Low |
| — | 105 MB `public/video/video.mp4` in the frontend bundle | Low (F-19) |

---

*All commands and their last-measured results were recorded during the Phase 2
verification and the 2026-10-21 audit. No installation, upgrade, migration or
deployment was performed during this audit.*
