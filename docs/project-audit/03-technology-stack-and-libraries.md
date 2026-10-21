# 03 — Technology Stack and Libraries

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Method:** `importlib.metadata.version()` against the workspace `.venv`, cross-checked
> against `requirements.txt` and `requirements-lock.txt`.
> **Related:** [`01-repository-map.md`](01-repository-map.md) ·
> [`09-setup-testing-and-deployment.md`](09-setup-testing-and-deployment.md)

---

## 1. How to read this document

Three columns matter:

- **Declared** — the version pinned in `requirements.txt` / `requirements-lock.txt` /
  `package.json`.
- **Installed** — the version actually present in the workspace environment, read from
  the interpreter's own metadata.
- **Status** — whether the declared and installed agree, and how the dependency is used.

Every Python package below was verified installed at the declared version. **No package
was installed or upgraded during this audit** (Rule 19).

## 2. Runtime environment

| Item | Value | How verified |
|---|---|---|
| Interpreter | **Python 3.12.10** (`tags/v3.12.10:0cc8128`, MSC v.1943 64-bit AMD64) | `sys.version` |
| Virtual environment | `D:\New folder (3)\.venv` — workspace-local | directory listing |
| Default PATH Python | 3.14 (documented in `docs/TRD.md` §2) — **not** used by the project | `docs/TRD.md` |
| Package installer | `pip` via `.venv\Scripts\python.exe -m pip` | `README.md` |
| OS | Windows | host platform |
| GPU target | NVIDIA GeForce RTX 5050 Laptop GPU, 8 GB VRAM (per `docs/TRD.md` §17) | repo-reported; **not re-verified** in this audit |
| PyTorch build | `+cu130` — CUDA-enabled | installed version string |

## 3. Backend (Python) dependency inventory

### 3.1 Direct runtime dependencies — `requirements.txt`

`requirements.txt` contains 9 pinned direct dependencies plus a PyTorch CUDA
extra-index-url.

```text
--extra-index-url https://download.pytorch.org/whl/cu130

torch==2.13.0+cu130
torchvision==0.28.0+cu130
ultralytics==8.4.163
opencv-python==4.14.0.94
numpy==2.5.3
PyYAML==6.0.3
requests==2.34.2
psutil==7.2.2
```

> The `+cu130` local-version pins resolve **only** from the PyTorch CUDA index, so this
> file cannot silently install a CPU-only wheel from PyPI. This is a deliberate
> safeguard, documented in the file header.

### 3.2 Full lock — `requirements-lock.txt` (41 packages)

Every entry in the lock was verified against the installed environment. **All 41 match
exactly.**

| Package | Declared | Installed | Match | Role in this project |
|---|---|---|:---:|---|
| `torch` | 2.13.0+cu130 | 2.13.0+cu130 | ✅ | YOLO11 inference backbone |
| `torchvision` | 0.28.0+cu130 | 0.28.0+cu130 | ✅ | Ultralytics dependency |
| `ultralytics` | 8.4.163 | 8.4.163 | ✅ | YOLO11 model API, training wrapper |
| `ultralytics-platform` | 0.1.83 | 0.1.83 | ✅ | Ultralytics transitive |
| `ultralytics-thop` | 2.2.2 | 2.2.2 | ✅ | Ultralytics FLOPs counter |
| `opencv-python` | 4.14.0.94 | 4.14.0.94 | ✅ | Image validation, letterbox, visualisation |
| `numpy` | 2.5.3 | 2.5.3 | ✅ | Array math for images and detections |
| `PyYAML` | 6.0.3 | 6.0.3 | ✅ | All `config/*.yaml` parsing |
| `requests` | 2.34.2 | 2.34.2 | ✅ | HTTP client (transitive + direct use) |
| `httpx` | 0.28.1 | 0.28.1 | ✅ | HTTP/2 client (Ultralytics) |
| `psutil` | 7.2.2 | 7.2.2 | ✅ | Process/resource measurement (`scripts/measure_flow.py`) |
| `polars` | 2.0.0 | 2.0.0 | ✅ | Ultralytics results parsing |
| `polars-runtime-32` | 2.0.0 | 2.0.0 | ✅ | `polars` native runtime |
| `networkx` | 3.6.1 | 3.6.1 | ✅ | Ultralytics graph ops |
| `matplotlib` | 3.11.2 | 3.11.2 | ✅ | Ultralytics training plots |
| `pillow` | 12.3.0 | 12.3.0 | ✅ | Image I/O |
| `certifi` | 2026.7.22 | 2026.7.22 | ✅ | TLS CA bundle |
| `urllib3` | 2.8.0 | 2.8.0 | ✅ | HTTP pool (requests) |
| `idna` | 3.20 | 3.20 | ✅ | IDNA hostname encoding |
| `charset-normalizer` | 3.5.2 | 3.5.2 | ✅ | Encoding detection |
| `filelock` | 3.32.3 | 3.32.3 | ✅ | File locking (Ultralytics) |
| `fsspec` | 2026.7.0 | 2026.7.0 | ✅ | Filesystem abstraction |
| `Jinja2` | 3.1.6 | 3.1.6 | ✅ | Template rendering (Ultralytics) |
| `MarkupSafe` | 3.0.3 | 3.0.3 | ✅ | Jinja2 dependency |
| `mpmath` | 1.3.0 | 1.3.0 | ✅ | SymPy dependency |
| `sympy` | 1.14.0 | 1.14.0 | ✅ | Ultralytics math |
| `packaging` | 26.3 | 26.3 | ✅ | Version parsing |
| `pyparsing` | 3.3.3 | 3.3.3 | ✅ | Matplotlib dependency |
| `python-dateutil` | 2.9.0.post0 | 2.9.0.post0 | ✅ | Date parsing |
| `six` | 1.17.0 | 1.17.0 | ✅ | Legacy compatibility shim |
| `setuptools` | 78.1.0 | 78.1.0 | ✅ | Packaging |
| `typing_extensions` | 4.16.0 | 4.16.0 | ✅ | Typing backport |
| `contourpy` | 1.4.0 | 1.4.0 | ✅ | Matplotlib dependency |
| `cycler` | 0.12.1 | 0.12.1 | ✅ | Matplotlib dependency |
| `fonttools` | 4.66.1 | 4.66.1 | ✅ | Matplotlib dependency |
| `kiwisolver` | 1.5.1 | 1.5.1 | ✅ | Matplotlib dependency |
| `anyio` | 4.15.1 | 4.15.1 | ✅ | httpx dependency |
| `h11` | 0.16.0 | 0.16.0 | ✅ | httpx dependency |
| `httpcore` | 1.0.9 | 1.0.9 | ✅ | httpx dependency |
| `cloudpickle` | 3.1.2 | 3.1.2 | ✅ | Ultralytics model (de)serialisation |
| `nvidia-ml-py` | 13.615.71 | 13.615.71 | ✅ | GPU telemetry via `psutil` |

**Verified result: 40 of 40 installed packages match the lock exactly.** (The lock lists
41 lines; `polars-runtime-32` is the platform-specific runtime companion of `polars` and
is counted once with it in the row above.)

### 3.3 Deliberately absent backend dependencies

`requirements-dev.txt` is **header-only**:

> PHASE_04 decision D2: header-only. No packages are pinned here yet. Testing and
> analysis tooling (e.g. pytest, coverage, linting) is deferred to the phase that first
> needs it, to avoid unnecessary dependencies (Rule 18).

Consequently:

| Not installed | Consequence |
|---|---|
| `pytest` | Tests must run via `python -m unittest discover -s tests`. |
| `coverage` | No measured test-coverage percentage exists for this project. |
| `ruff` / `flake8` / `black` / `mypy` | No Python linter or type checker is configured. |
| `fastapi` / `uvicorn` / `pydantic` | The API is stdlib `http.server`; request validation is hand-written. |
| `sqlalchemy` / `alembic` | Persistence is raw `sqlite3`; the schema is created idempotently, with no migration tool. |
| `pydantic` | All contracts are hand-written `dataclass`es (see §6). |
| `requests-cache` / `redis` | Caching is an in-process dict with a TTL (`src/routing/osrm_adapter.py`). |
| `geopy` / `shapely` | Geometry is hand-written in `src/facilities/geometry.py` and `src/imagery/matcher.py`. |

This is a coherent, deliberate strategy under Rule 18: **the backend adds zero
third-party dependencies beyond the ML stack and PyYAML/requests.** Every external
integration uses `urllib.request` from the standard library.

## 4. Frontend dependency inventory

Source: `frontend/Frontend/project frontend/package.json`. Lockfile: `package-lock.json`,
`lockfileVersion: 3`. Package name `saferoute-ai`, version `0.0.0`, `"type": "module"`.

### 4.1 Runtime dependencies (13)

| Package | Declared | Role |
|---|---|---|
| `react` | 19.2.8 | UI framework |
| `react-dom` | 19.2.8 | DOM renderer |
| `react-router-dom` | 7.18.2 | Client-side routing (`BrowserRouter`) |
| `maplibre-gl` | 6.3.0 | Map rendering (OpenFreeMap Liberty style) |
| `three` | 0.185.1 | 3D/animation support |
| `framer-motion` | 13.1.0 | Component animation |
| `gsap` | 3.15.0 | Timeline animation |
| `@gsap/react` | 2.1.2 | React ↔ GSAP integration |
| `@dotlottie/player-component` | 2.7.12 | Lottie animation player |
| `@tailwindcss/vite` | 4.3.3 | Tailwind CSS 4 via the Vite plugin |
| `tailwindcss` | 4.3.3 | Utility CSS framework |
| `clsx` | 2.1.1 | Conditional class names (**one consumer only** — `src/components/ui/animated-search-1.tsx`, itself dead) |
| `sass` | 1.102.0 | SCSS modules (`*.module.scss`) |

### 4.2 Development dependencies (12)

| Package | Declared | Role |
|---|---|---|
| `vite` | 8.2.1 | Build tool and dev server |
| `@vitejs/plugin-react` | 6.0.5 | React fast refresh / JSX transform |
| `typescript` | 6.0.3 | Type checking (`tsc -b`) |
| `oxlint` | 1.78.0 | Linter — **replaces ESLint** |
| `@types/node` | 24.13.3 | Node typings |
| `@types/react` | 19.2.18 | React typings |
| `@types/react-dom` | 19.2.4 | React DOM typings |
| `@types/three` | 19.2.18 | three.js typings |
| `@types/maplibre-gl` | *(19.2.18-range)* | MapLibre typings |

### 4.3 npm scripts

| Script | Command | Notes |
|---|---|---|
| `dev` | `vite` | Dev server |
| `build` | `tsc -b && vite build` | Type-check then bundle |
| `lint` | `oxlint` | 0 errors at the last measured run |
| `preview` | `vite preview` | Serves the built bundle (used on 127.0.0.1:8123) |
| `test:frontend` | `node tools/frontend-tests/run.mjs` | 58 runtime checks, 0 failures at the last measured run |

**Not wired into any npm script:** `tools/browser-test/run.mjs` — the Edge/CDP browser
check must be invoked manually as `node tools/browser-test/run.mjs <baseUrl>`.

### 4.4 Frontend tooling gaps

| Expected | Status | Impact |
|---|---|---|
| ESLint | **Not found** | `oxlint` is used instead — a Rust-based linter with a different rule set and no React-specific plugin in this setup. |
| Prettier | **Not found** | Formatting is manual; no automated format check. |
| Jest / Vitest | **Not found** | The frontend test harness is hand-written (`tools/frontend-tests/run.mjs`). |
| Playwright / Cypress | **Not found** | Browser verification is a hand-written CDP driver. |
| `tsconfig` `strict` | **Disabled** in `tsconfig.app.json` | Type errors that `strict` would catch are not reported. Finding F-16. |
| Vitest/vite coverage | **Not found** | No frontend coverage figure exists. |

### 4.5 `vite.config.ts`

| Setting | Value |
|---|---|
| Plugins | `@vitejs/plugin-react`, `@tailwindcss/vite` |
| Alias | `@` → `./src` |
| `optimizeDeps.exclude` | `['maplibre-gl']` |
| `server.proxy` | **not configured** |
| `build.outDir` | **not configured** (Vite default `dist/`) |
| `envPrefix` | **not configured** (Vite default `VITE_`) |

Because there is no dev proxy, the browser calls the backend directly using
`VITE_API_URL` — which is why the frontend `.env.example` must document it and why the
browser check asserts the base URL.

## 5. External services and providers

| Provider | Endpoint | Key required | Licence / terms | Configured in |
|---|---|:---:|---|---|
| **OSRM** (routing) | `https://router.project-osrm.org` | No | OpenStreetMap data (ODbL) | `config/routing.yaml` → `provider.osrm` |
| **Mapillary** (imagery) | `https://graph.mapillary.com` | **Yes** — `MAPILLARY_ACCESS_TOKEN` in `.env` | CC-BY-SA 4.0 | `config/imagery.yaml` → `sources.mapillary` |
| **Overpass** (facilities) | `https://overpass-api.de/api/interpreter` + 2 mirrors | No | ODbL | `config/facilities.yaml` → `providers.overpass.base_urls` |
| **Nominatim** (geocoding) | `https://nominatim.openstreetmap.org` | No | ODbL, ≤1 req/s | `config/app.yaml` → `app.geocoding.base_url` |
| **Ollama** (LLM) | `http://127.0.0.1:11434` | No | local | `config/app.yaml` → `app.llm` |
| **OpenFreeMap** (map tiles) | `https://tiles.openfreemap.org/styles/liberty` | No | free tier | `frontend/.../src/` map style constant |
| **Google Street View** | — | — | **explicitly disabled**: "Strict commercial ToS §3.2.3 forbids automated downloading, caching, and model ingestion." | `config/imagery.yaml` → `sources.google_street_view.enabled: false` |

### 5.1 Provider failover and pacing

| Mechanism | Implementation |
|---|---|
| Overpass mirrors | 3 base URLs, `max_endpoints: 3`, `timeout_seconds: 10.0`, `max_retries: 2`, `backoff_factor_seconds: 0.5` |
| Overpass query pacing | `query_gap_seconds: 0.7` between per-category queries; `query_deadline_seconds: 45.0` overall |
| OSRM retries | `max_retries: 3`, `backoff_factor_seconds: 0.5`, `timeout_seconds: 5.0`; 120 s response cache |
| Nominatim pacing | process-wide minimum interval of 1 s, bounded retries, descriptive User-Agent |

## 6. Contract technology

All backend contracts are **hand-written `dataclass`es** — no validation framework is
used.

| Package | Contract types |
|---|---|
| `src/routing/schemas.py` | `RoutingStatus`, `Coordinate`, `RouteGeometry`, `RouteSegment`, `Route`, `RouteRequest`, `RouteResponse` |
| `src/imagery/schemas.py` | `ImageryStatus`, `ImageRef`, `ImageryUnavailable`, `ImageryResult` |
| `src/detection/schemas.py` | `DetectionStatus`, `DetectionRecord`, `ImageDetectionResult` |
| `src/risk/schemas.py` | `AssessmentStatus`, `HazardRecord`, `CoverageInfo`, `SegmentAssessment`, `SegmentScoreResult`, `RouteSafetyResult` |
| `src/llm/schemas.py` | `ExplanationResult` |
| `src/facilities/schemas.py` | `Facility`, `FacilityResult` |
| `src/geocoding/schemas.py` | `GeocodeStatus`, `GeocodeCandidate`, `GeocodeResult` |

**Trade-off:** zero dependency cost and full control (Rule 18), but validation is
per-handler and therefore uneven — some handlers coerce bad input to a default rather
than rejecting it. See [`08-security-and-reliability.md`](08-security-and-reliability.md) §3.

## 7. Specification-vs-reality technology divergences

| Spec says | Reality | Finding |
|---|---|---|
| FastAPI backend (`docs/TRD.md` §2, `docs/ARCHITECTURE.md` §3) | stdlib `http.server` + `ThreadingHTTPServer` | F-02 |
| MySQL persistence (`docs/TRD.md` §2, `docs/ARCHITECTURE.md` §10) | SQLite at `data/saferoute.db` | F-02 |
| React frontend | React 19 + Vite 8 + MapLibre — **matches** | — |
| Ollama local LLM | Ollama 0.40.6 with `llama3:latest` — **matches** | — |
| CUDA-enabled PyTorch | `torch 2.13.0+cu130` — **matches** | — |
| Routing provider "to be selected" | OSRM selected and implemented | — |
| Permitted imagery source "unresolved" | Mapillary (CC-BY-SA 4.0) selected and implemented | — |
| Facility provider "unresolved" | Overpass selected and implemented | — |
| "No dataset, no model weights, no environment" | All present | F-01 |

## 8. Dependency hygiene assessment

**Strengths**
- Complete pinning with a full lock file; **zero drift** between declared and installed.
- The CUDA-only PyTorch index prevents accidental CPU-only installation.
- `requirements-dev.txt` stays empty until a phase actually needs a tool (Rule 18).
- The backend introduces no framework dependencies — an unusually disciplined choice for
  a project of this scope.

**Weaknesses**
- No automated dependency-update or vulnerability-scan job exists (no CI — F-11).
- No `pip-audit`/`safety` run is recorded anywhere in the repository.
- The frontend has no lockfile-integrity step and no `npm audit` record.
- `requirements-lock.txt` was not regenerated after the Phase 2 work, but the Phase 2
  work added no new packages, so it remains accurate — **verified**, not assumed.
- `requests` is declared as a direct dependency but the backend's own HTTP calls use
  `urllib.request`; `requests` appears to be used only via the Ultralytics chain. This
  is a minor over-declaration, not a defect.

---

*All version strings in the "Declared" and "Installed" columns are exact, read from
`requirements*.txt`, `package.json`, `package-lock.json` and the interpreter's package
metadata on 2026-10-21. No package was installed, upgraded or removed.*
