# SafeRoute AI — Single Consolidated Presentation Report

> **Purpose:** one document that answers every question the presentation is likely to
> get about **backend libraries**, the **map stack**, **YOLO11 + OpenCV**, and the
> **end-to-end project workflow** — so nothing has to be improvised in the viva.
>
> **Workspace:** `D:\New folder (3)` · **Report date:** 2026-10-21
> **Status:** read-only analysis of the *actual* implementation.
> **Companion docs:** [`11-presentation-and-viva.md`](11-presentation-and-viva.md) (slide
> outline, demo script, viva Q&A) · [`03-technology-stack-and-libraries.md`](03-technology-stack-and-libraries.md)
> (full dependency audit) · [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md)
> (architecture) · [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) (model detail)
>
> Every version below was read from the file on disk or from the installed
> environment. Every number is labelled **Measured**, **Repo-reported** or
> **Config value** — nothing is estimated.

---

## 0. The 30-second version (read this before the presentation)

> **SafeRoute AI** is a road-safety route-comparison system. It takes the routes a
> routing provider *actually* returns, matches **permitted** street imagery to each
> road segment within **25 metres**, runs a **YOLO11 (Ultralytics)** hazard detector
> on images prepared by a versioned **OpenCV** preprocessing pipeline, converts the
> verified detections into a **deterministic** score `S = 100 · exp(−λ·H)`, compares
> the routes, refuses to recommend one when the evidence does not support it, and
> explains the result with a **grounded** local LLM (Ollama) that has a deterministic
> fallback. The map is rendered with **MapLibre GL JS** on **OpenFreeMap** tiles.

**The one differentiator to say out loud:** the system knows what it does *not* know.
Missing, stale or insufficient imagery is reported as **unassessed**, never as a
safe road.

---

## 1. Backend libraries — complete inventory

### 1.1 Direct runtime dependencies (`requirements.txt`) — 6 pins

| # | Library | Version | Where it is used in this project | Why it is there |
|---|---|---|---|---|
| 1 | **torch** | `2.13.0+cu130` | `src/detection/detector.py` (CUDA device check, `boxes.data.cpu().numpy()`), `scripts/train_baseline.py`, `scripts/evaluate_baseline.py` | Inference backbone under YOLO11. The `+cu130` local-version pin **only** resolves from the PyTorch CUDA index, so a CPU-only wheel can never be installed silently. |
| 2 | **torchvision** | `0.28.0+cu130` | Transitive for Ultralytics; available for dataset/image transforms | Paired with torch; Ultralytics imports it. |
| 3 | **ultralytics** | `8.4.163` | `src/detection/detector.py:163` → `from ultralytics import YOLO`; `scripts/train_baseline.py`, `scripts/evaluate_baseline.py` | The **YOLO11** model API + training wrapper. This is the library that satisfies master_rules **Rule 4**. |
| 4 | **opencv-python** | `4.14.0.94` | `src/preprocessing/pipeline.py` (validation, letterbox, CLAHE, drawing), `src/detection/detector.py` (decode, channel coercion, drawing), `scripts/prepare_datayolo_2class.py`, `scripts/audit/phase20_duplicate_scan.py` | The **entire image pipeline** — decode/validate → letterbox → inference tensor → visualisation. Satisfies **Rule 6**. |
| 5 | **numpy** | `2.5.3` | `src/preprocessing/pipeline.py`, `src/detection/detector.py` (HWC→CHW, `/255.0` normalisation, `np.frombuffer`) | Array math for images, boxes and severity aggregation. |
| 6 | **PyYAML** | `6.0.3` | 11 modules (`src/config/settings.py`, `src/risk/engine.py`, `src/risk/severity.py`, `src/risk/comparison.py`, `src/config/thresholds.py`, `src/imagery/adapter.py`, `src/facilities/service.py`, `src/routing/adapter.py`, `src/geocoding/factory.py`, `src/preprocessing/pipeline.py`, `src/detection/detector.py`) | Every `config/*.yaml` file is parsed through it — the project is **config-driven**, not hard-coded. |

> **Heads-up on a doc drift:** the audit file
> [`03-technology-stack-and-libraries.md`](03-technology-stack-and-libraries.md) §3.1
> lists 9 direct dependencies (it also counts `requests` and `psutil`). The **file on
> disk today has 6 pins** — `requests` and `psutil` are still in the lock file and are
> still used by `scripts/`, they are just not declared in `requirements.txt` any more.
> If an examiner asks "how many direct dependencies?", say **six**, and quote this table.

### 1.2 Full lock file — `requirements-lock.txt`, 41 packages, 0 drift

All 41 were verified against the installed environment: **40 of 40 match exactly**
(`polars-runtime-32` is the platform-specific runtime of `polars` and is counted with it).
**Measured.**

| Package | Version | Role |
|---|---|---|
| `torch` | 2.13.0+cu130 | YOLO11 inference backbone |
| `torchvision` | 0.28.0+cu130 | Ultralytics dependency |
| `ultralytics` | 8.4.163 | **YOLO11 model API + training** |
| `ultralytics-platform` | 0.1.83 | Ultralytics transitive |
| `ultralytics-thop` | 2.2.2 | Ultralytics FLOPs counter |
| `opencv-python` | 4.14.0.94 | **Image validation, letterbox, visualisation** |
| `numpy` | 2.5.3 | Array math |
| `PyYAML` | 6.0.3 | All config parsing |
| `requests` | 2.34.2 | HTTP (transitive via Ultralytics) |
| `httpx` | 0.28.1 | HTTP/2 client (Ultralytics) |
| `psutil` | 7.2.2 | Process/resource measurement (`scripts/measure_flow.py`) |
| `polars` / `polars-runtime-32` | 2.0.0 | Ultralytics results parsing |
| `networkx` | 3.6.1 | Ultralytics graph ops |
| `matplotlib` | 3.11.2 | Ultralytics training plots |
| `pillow` | 12.3.0 | Image I/O |
| `certifi` | 2026.7.22 | TLS CA bundle |
| `urllib3` | 2.8.0 | HTTP pool |
| `idna` | 3.20 | IDNA hostname encoding |
| `charset-normalizer` | 3.5.2 | Encoding detection |
| `filelock` | 3.32.3 | File locking (Ultralytics) |
| `fsspec` | 2026.7.0 | Filesystem abstraction |
| `Jinja2` / `MarkupSafe` | 3.1.6 / 3.0.3 | Template rendering (Ultralytics) |
| `mpmath` / `sympy` | 1.3.0 / 1.14.0 | Ultralytics math |
| `packaging` | 26.3 | Version parsing |
| `pyparsing` | 3.3.3 | Matplotlib dependency |
| `python-dateutil` | 2.9.0.post0 | Date parsing |
| `six` | 1.17.0 | Legacy compatibility shim |
| `setuptools` | 78.1.0 | Packaging |
| `typing_extensions` | 4.16.0 | Typing backport |
| `contourpy` | 1.4.0 | Matplotlib dependency |
| `cycler` | 0.12.1 | Matplotlib dependency |
| `fonttools` | 4.66.1 | Matplotlib dependency |
| `kiwisolver` | 1.5.1 | Matplotlib dependency |
| `anyio` / `h11` / `httpcore` | 4.15.1 / 0.16.0 / 1.0.9 | httpx dependencies |
| `cloudpickle` | 3.1.2 | Model (de)serialisation |
| `nvidia-ml-py` | 13.615.71 | GPU telemetry via psutil |

### 1.3 Standard-library modules doing the "framework" work

This is the part that surprises examiners: **the backend framework is the Python
standard library.** There is no FastAPI, no Flask, no SQLAlchemy, no Pydantic.

| Stdlib module | Used for | Concrete location |
|---|---|---|
| `http.server` | The whole REST API (`ThreadingHTTPServer` + `BaseHTTPRequestHandler`) | `src/api/app.py:29`, `create_server()` at `:376` |
| `sqlite3` | All persistence — schema created idempotently with `CREATE TABLE IF NOT EXISTS` | `src/api/store.py:12`; tables: `model_versions`, `searches`, `analyses`, `scores`, `hazard_detections` |
| `urllib.request` | **Every** outbound HTTP call — OSRM, Mapillary, Overpass, Nominatim, Ollama | `src/routing/osrm_adapter.py:15`, `src/facilities/overpass_provider.py:21`, `src/llm/explainer.py:35` |
| `hashlib` | SHA-256 config hash stamped on every score | `src/risk/engine.py:29` `compute_config_hash()` |
| `math` | The risk formula `exp(−λ·H)`, haversine distance | `src/risk/engine.py:105`, `src/routing/segmentation.py` |
| `dataclasses` | **All** API/domain contracts (no Pydantic) | every `src/*/schemas.py` |
| `abc` | Provider interfaces (`RoutingProvider`, `FacilitiesProvider`, `GeocodingProvider`) | `src/routing/interfaces.py:7`, `src/facilities/interfaces.py:8` |
| `concurrent.futures` | Bounded thread pool for imagery prefetch (default 16 workers) | `src/api/pipeline.py:14`, `:224` |
| `json`, `logging`, `threading`, `uuid`, `pathlib`, `datetime`, `os`, `time`, `socket`, `csv`, `subprocess` | General plumbing, request logging, retries with backoff | across `src/`, `scripts/` |

**Deliberately absent** (Rule 18 — minimal dependencies): `pytest`, `coverage`,
`ruff`/`flake8`/`black`/`mypy`, `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`,
`alembic`, `requests-cache`, `redis`, `geopy`, `shapely`. `requirements-dev.txt` is
**header-only** on purpose.

### 1.4 The "one-line" answer for a viva

> "The backend adds **zero framework dependencies** beyond the ML stack and PyYAML.
> `http.server` + `sqlite3` + `urllib.request` come from the standard library, so
> there is no FastAPI, no ORM and no requests-cache. The cost is hand-written request
> validation, which is uneven — that is recorded as an open finding."

---

## 2. The map stack — what was used for the map

### 2.1 Frontend map rendering

| Item | Value | Detail |
|---|---|---|
| **Map library** | **`maplibre-gl` 6.3.0** | The one and only map renderer. A fork of Mapbox GL JS with no vendor lock-in and no API-key requirement. |
| **Style / tiles** | **OpenFreeMap** — `https://tiles.openfreemap.org/styles/liberty` | `src/components/map/Map/Map.tsx:8` (`MAP_STYLE_URL`). Free tier, no key, no billing. |
| **Map source URL** | `https://tiles.openfreemap.org/planet` (planet), sprites from `https://tiles.openfreemap.org/sprites/ofm_f384/ofm` | `src/config/poiIcons.ts:18` |
| **Default view** | centre `[77.1025, 28.7041]` (Delhi), zoom 12, minZoom 3, maxZoom 18 | `Map.tsx:9-27` |
| **Map interaction** | `dragRotate: false`, `pitchWithRotate: false`, `touchPitch: false` | Map is a flat 2-D safety map by design (`Map.tsx:48-51`) |
| **Attribution** | `AttributionControl({ compact: true })`, bottom-right | `Map.tsx:55` — mandatory for ODbL/CC-BY-SA attribution |
| **Map state** | React `MapContext` + `useMap()` hook, `MapLibreMap` instance in state | `src/hooks/useMap.ts`, `Map.tsx:67` |

**Map components built on MapLibre**

| Component | File | MapLibre APIs used |
|---|---|---|
| `Map` | `src/components/map/Map/Map.tsx` | `new MapLibreMap(...)`, `AttributionControl`, `LngLatLike` |
| `RouteLayer` | `src/components/map/RouteLayer/RouteLayer.tsx` | `GeoJSONSource`, `LngLatBounds`, `MapLayerMouseEvent` — one GeoJSON `LineString` per route, with **casing + line** layers, colour/width/opacity driven by `recommendedIndex` and `activeIndex`, click-to-select sync |
| `FacilityLayer` | `src/components/map/FacilityLayer/FacilityLayer.tsx` | `GeoJSONSource` — POI points for nearby facilities (context only, Rule 11) |
| `MapMarker` | `src/components/map/MapMarker/MapMarker.tsx` | `Marker`, `Map` — origin/destination markers |
| `layers` util | `src/utils/layers.ts` | `Map` type for layer/filter helpers |

**Frontend supporting libraries for the map/UI**

| Package | Version | Role |
|---|---|---|
| `react` / `react-dom` | 19.2.8 | UI framework |
| `react-router-dom` | 7.18.2 | Client-side routing (`BrowserRouter`) |
| `three` | 0.185.1 | 3D/animation support |
| `framer-motion` | 13.1.0 | Component animation |
| `gsap` + `@gsap/react` | 3.15.0 / 2.1.2 | Timeline animation |
| `@dotlottie/player-component` | 2.7.12 | Lottie loader animation |
| `tailwindcss` + `@tailwindcss/vite` | 4.3.3 | Utility CSS |
| `clsx` | 2.1.1 | Conditional class names (one consumer) |
| `sass` | 1.102.0 | `*.module.scss` |
| **dev**: `vite` 8.2.1, `@vitejs/plugin-react` 6.0.5, `typescript` 6.0.3, `oxlint` 1.78.0, `@types/*` | | Build, type-check, lint |

> Note: `vite.config.ts` sets `optimizeDeps.exclude: ['maplibre-gl']` and there is
> **no dev proxy** — the browser calls the backend directly via `VITE_API_URL`.
ment spatial match (25 m radius, max 3 frames/segment) | `ImageryMatcher` | `src/imagery/matcher.py:85`; config `config/imagery.yaml` |
| Facility distance (straight-line vs road-network basis) | `src/facilities/geometry.py` | `src/facilities/geometry.py` |

### 2.3 All map-related external services

| Service | Endpoint | Key? | Licence | Used for | Config |
|---|---|:---:|---|---|---|
| **OpenFreeMap** | `tiles.openfreemap.org/styles/liberty` | No | Free tier | Frontend basemap + sprites | `Map.tsx`, `poiIcons.ts` |
| **OSRM** | `router.project-osrm.org` | No | OSM data, ODbL | Route alternatives | `config/routing.yaml` |
| **Mapillary** | `graph.mapillary.com` | **Yes** — `MAPILLARY_ACCESS_TOKEN` | CC-BY-SA 4.0 | Street-level imagery for detection | `config/imagery.yaml` |
| **Overpass** | `overpass-api.de/api/interpreter` + 2 mirrors | No | ODbL | Nearby facilities (context only) | `config/facilities.yaml` |
| **Nominatim** | `nominatim.openstreetmap.org` | No | ODbL, ≤1 req/s | Place name → coordinates | `config/app.yaml` |
| **Ollama** | `127.0.0.1:11434` | No | Local | Grounded explanation | `config/app.yaml` |
| **Google Street View** | — | — | — | **Explicitly disabled**: ToS §3.2.3 forbids automated download / caching / model ingestion | `config/imagery.yaml` → `enabled: false` |

### 2.2 Backend map/geospatial — hand-written, zero geo-libraries

**There is no `geopy`, no `shapely`, no `geojson`, no `scipy` in this project.** All
geometry is hand-written in plain Python + `math`:

| Capability | Implementation | File |
|---|---|---|
| Haversine distance (Earth radius constant) | `haversine_distance_m()`, `EARTH_RADIUS_METERS` | `src/routing/segmentation.py` |
| Route → segment splitting (200 m target, 50–500 m bounds) | `RouteSegmenter` | `src/routing/segmentation.py`; config `config/routing.yaml` |
| Point → polyline **perpendicular** distance (point-to-*edge*, not point-to-vertex) | `point_to_segment_distance_m()` | `src/imagery/matcher.py:53` |
| Image ↔ seg
**Resilience:** Overpass has 3 base URLs (`max_endpoints: 3`, 10 s timeout, 2 retries,
0.5 s backoff, 0.7 s gap between category queries, 45 s overall deadline). OSRM has
3 retries, 5 s timeout and a 120-second in-process response cache. Nominatim enforces
a process-wide 1-second minimum interval.

> **Viva line:** "We chose MapLibre over Mapbox GL because MapLibre is BSD-licensed,
> needs no API key and no billing account, and it renders OpenFreeMap's free vector
> tiles — the same code path a city or a rescue organisation could actually deploy."

---

## 3. YOLO11 (Ultralytics) — exactly what is used

### 3.1 Model identity

| Item | Value | Source |
|---|---|---|
| Architecture | **YOLO11n** (nano variant) | master_rules **Rule 4** mandates YOLO11 |
| Library | `ultralytics==8.4.163` → `from ultralytics import YOLO` | `src/detection/detector.py:163` |
| Serving checkpoint | `models/training/saferoute-yolo11-v2/weights/best.pt` | `config/detection.yaml` → `model.checkpoint` |
| `model_version` reported to the client | `saferoute-yolo11-v2` | `src/detection/detector.py:30` |
| Module version | `detect-v2` | `src/detection/detector.py:29` |
| Trained classes | **`0: pothole`, `1: crack`** | `SUPPORTED_CLASSES`, `config/detection.yaml` |
| Explicitly **unsupported** (reported, never fabricated) | `manhole`, `damaged_patch`, `waterlogging`, `uneven_surface`, `speed_bump` | `config/detection.yaml` |
| Device | auto → `0` (CUDA) if `torch.cuda.is_available()` else `"cpu"` | `src/detection/detector.py:119-122` |
| Runtime | `torch 2.13.0+cu130` on an RTX 5050 Laptop GPU (8 GB VRAM) | `requirements.txt`, `docs/TRD.md` §17 |

### 3.2 Inference configuration (`config/detection.yaml`)

| Parameter | Value | Note |
|---|---|---|
| `imgsz` | **640** | Standard YOLO11 inference resolution; higher can help small cracks |
| `conf` | **0.25** | Single confidence policy — **must equal** `config/hazard_severity.yaml → thresholds.confidence_threshold`. It was 0.15, which made the aggregator (0.25) silently drop detections in [0.15, 0.25). Both are 0.25 now, so **no detection is silently discarded** |
| `iou` | **0.45** | NMS IoU |
| `max_det` | 300 | |
| `augment` | `false` | TTA off by default — slower, higher recall |
| `batch` | 1 | |
| `device` | `null` | auto |

### 3.3 The exact inference path (`HazardDetector.detect()`)

1. **Input normalisation** — accepts `str`/`Path`, `bytes`, or a BGR `np.ndarray`.
2. **Validation** — delegates to the OpenCV pipeline (`PreprocessingPipeline.validate_image`). Failure → `DetectionStatus.INVALID_IMAGE`, the image is **excluded from evidence** (Rule 9), never treated as "no hazard".
3. **Decode** — `cv2.imread` / `cv2.imdecode` → BGR array; single-channel → `COLOR_GRAY2BGR`, 4-channel → `COLOR_BGRA2BGR`.
4. **Preprocess** — `PreprocessingPipeline.preprocess()` → letterboxed 640×640 (see §4).
5. **Inference** — `self.model.predict(source=prepared.image, conf=…, iou=…, imgsz=…, max_det=…, augment=…, device=…, verbose=False)`.
6. **Box rescaling** — predictions come back in letterboxed space; they are mapped back to the original image using the stored `(pad_left, pad_top)` and `(scale_w, scale_h)`, clamped to the original bounds, and **also** normalised to `[0,1]` (`bbox_norm`).
7. **Class mapping** — a supported class id becomes `pothole`/`crack`; anything else becomes `unsupported_class_<id>` with an explicit error string (Rule 5).
8. **Status** — `SUCCESS` if any detection, `NO_DETECTIONS` if the image was clean, `FAILED` on exception, `INVALID_IMAGE` on a bad image. These are **different statuses on purpose** (Rule 9).
9. **Timing** — per-stage `timing_ms`: `validate`, `preprocess`, `inference`, `postprocess`, `total`.

### 3.4 Hard constraints the detector enforces

- **Never computes a score** (Rule 7) — the detector has no scoring code path.
- **Never falls back silently** — if the checkpoint is missing it raises `FileNotFoundError`; there is no "use another model" or "use random weights" path.
- **Never mutates source images** (Rule 1) — `visualise()` refuses to write to the source path and draws on a copy.
- **Workspace isolation** — `_verify_workspace_path()` rejects any checkpoint or output path outside `D:\New folder (3)`.
- **Model version reflects reality** — `model_version` is derived from the *loaded* checkpoint's directory name, not from a hard-coded label.

### 3.5 Training / evaluation tooling (`scripts/`)

| Script | Purpose | Key imports |
|---|---|---|
| `scripts/train_baseline.py` | Ultralytics training entry point with env/VRAM checks and provenance capture | `torch`, `ultralytics`, `cv2`, `psutil` |
| `scripts/evaluate_baseline.py` | Evaluation with hash + environment recording | `torch`, `ultralytics`, `numpy` |
| `scripts/prepare_datayolo_2class.py` | Dataset prep (2-class, XML/CSV → YOLO labels) | `cv2` |
| `scripts/prepare_rdd2022_yolo.py` | RDD2022 → YOLO conversion | stdlib `xml.etree` |
| `scripts/build_derived_dataset_v2.py` | Date-atomic split builder (leakage-free by construction) | stdlib `hashlib`, `csv` |
| `scripts/verify_yolo_opencv.py` | End-to-end YOLO+OpenCV smoke verification | `cv2`, `numpy`, `HazardDetector`, `HazardAggregator`, `SeverityPolicy`, `DeterministicRiskEngine` |
| `scripts/measure_flow.py` | Flow measurement over the live API | `urllib.request`, `psutil` |

### 3.6 Measured model numbers (use the labels)

| Metric | Value | Status |
|---|---|---|
| mAP50, v1 checkpoint | **0.2731** validation / **0.2615** test | **Repo-reported** — say "repo-reported", do not claim it as independently reproduced |
| Recall, v1 | 0.3110 val / 0.3009 test | **Repo-reported** |
| Inference latency | 4.02 ms/image | **Repo-reported**, tied to that checkpoint |
| v2 promotion | micro-F1 0.297 → 0.327 on a 601-image unseen set | **Repo-reported**, and **not comparable to mAP50** — say so if asked |
| Cross-split image leakage | **0** (SHA-256 comparison across splits) | **Measured** |
| Intra-split duplicate groups (older corpus) | 49 | **Measured** — a known issue |

> **Never say "97% accurate" or "the model is accurate."** The honest framing is:
> "mAP50 is about 0.27 — that is the model's main limitation, and it is precisely why
> the system's real value is the honest coverage and refusal behaviour rather than
> the detection itself."

---

## 4. OpenCV — exactly what is used

### 4.1 The versioned pipeline

`src/preprocessing/pipeline.py` — `pipeline_version: "preprocess-v1"`, config-driven from
`config/preprocessing.yaml`. One pipeline serves **both** training and inference
(Rule 6), so there is no train/serve skew.

| Stage | OpenCV call | Config value | Purpose |
|---|---|---|---|
| **Decode & validate** | `cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)` | min 32×32, 3 channels, ext `.jpg .jpeg .png .bmp .webp` | Never raises — returns a typed `ImageStatus` (`OK` / `EMPTY` / `UNREADABLE` / `CORRUPT` / `UNSUPPORTED` / `TOO_SMALL` / `LOW_QUALITY`) |
| **Letterbox** | `cv2.resize(..., interpolation=cv2.INTER_LINEAR)` + `cv2.copyMakeBorder(..., cv2.BORDER_CONSTANT, value=(114,114,114))` | target `[640, 640]`, `stride: 32`, `auto: false`, `scale_fill: false`, `scale_up: true` | Aspect-ratio-preserving resize + grey pad — **Ultralytics-compatible**, so the model sees exactly what it was trained on. Returns `(image, ratio, (pad_left, pad_top))` so boxes can be un-padded later |
| **Optional CLAHE** | `cv2.cvtColor(BGR2LAB)` → `cv2.split` → `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` → `cv2.merge` → `cvtColor(LAB2BGR)` | **`enable_clahe: false`** | Implemented and config-switchable, but **disabled by default** because it was not empirically justified (Rule 6: only apply preprocessing that is justified and tested) |
| **Channel coercion** | `cv2.cvtColor(..., COLOR_GRAY2BGR)` / `COLOR_BGRA2BGR` | — | Robustness for grayscale and 4-channel inputs |
| **Tensor prep** | `cv2.cvtColor(BGR2RGB)` + `np.transpose((2,0,1))` + `np.ascontiguousarray(float32)` + `/255.0` | — | HWC→CHW, BGR→RGB, [0,255]→[0,1] |
| **Visualisation** | `cv2.rectangle`, `cv2.getTextSize`, `cv2.putText` (HERSHEY_SIMPLEX), `cv2.imwrite` | pothole `[0,0,255]` red, crack `[0,165,255]` orange, default green | Bounding boxes + labels; always on a **copy**, source image never overwritten (Rule 1) |

### 4.2 Why OpenCV is in the project at all (Rule 6)

> "OpenCV is not decoration here — it is the contract between the image on disk and
> the tensor the model consumes. A single versioned pipeline does validation,
> letterboxing and normalisation, so the image the detector sees at inference is
> byte-for-byte the same shape it saw during training. CLAHE is implemented but
> switched off, because Rule 6 says apply only preprocessing that is justified and
> tested, and we had not measured a benefit."

### 4.3 OpenCV outside the inference path

| Location | Use |
|---|---|
| `scripts/prepare_datayolo_2class.py` | Image inspection during dataset preparation |
| `scripts/audit/phase20_duplicate_scan.py` | Duplicate-frame scanning in the dataset |
| `scripts/verify_yolo_opencv.py` | Smoke-test of the full YOLO+OpenCV chain |
| `src/detection/detector.py` | `cv2.imencode` to re-encode an ndarray for validation; `cv2.imread`/`imdecode`; drawing |

---

## 5. Project workflow — end to end

### 5.1 The pipeline (this is the slide-3 diagram)

```
USER (browser)
  → PLACE NAME
  → GEOCODING           Nominatim  (src/geocoding/nominatim.py)
  → ROUTING             OSRM       (src/routing/osrm_adapter.py)
       └─ routes shown EXACTLY as returned — never padded to four  (Rule 10)
  → SEGMENTATION        ~200 m segments, 50–500 m bounds (src/routing/segmentation.py)
  → IMAGERY             Mapillary  (src/imagery/mapillary_provider.py)
       └─ permitted sources only; Google Street View disabled  (Rule 8)
       └─ 25 m spatial match, ≤3 frames/segment, 180-day freshness  (Rule 9)
  → PREPROCESSING       OpenCV     (src/preprocessing/pipeline.py)  → 640×640 letterbox
  → DETECTION           YOLO11     (src/detection/detector.py)      → pothole / crack
  → AGGREGATION         HazardAggregator + cross-segment dedup     (src/risk/aggregate.py)
  → RISK SCORE          DeterministicRiskEngine  S = 100·exp(−λ·H) (src/risk/engine.py)
  → COMPARISON          RouteComparer — ties → no recommendation    (src/risk/comparison.py)
  → EXPLANATION         GroundedExplanationService (Ollama)        (src/llm/explainer.py)
  → FRONTEND            React 19 + MapLibre GL JS + OpenFreeMap
```

### 5.2 Step-by-step, with the code that does it

| # | Step | Module / function | What actually happens |
|---|---|---|---|
| 1 | **Bootstrap** | `src/api/bootstrap.py` → `build_pipeline()`, `build_geocoder()` | Reads `config/app.yaml` + `.env`, constructs the live providers (OSRM, Mapillary, Overpass, Nominatim, Ollama) and injects them into `SafetyAnalysisPipeline`. |
| 2 | **Serve** | `src/api/app.py` → `create_server()` → `ThreadingHTTPServer` | Stdlib HTTP server on `127.0.0.1:8000`, also serves the built SPA statically. `Settings.to_safe_dict()` is the only outward-facing config method — it never emits a secret. |
| 3 | **Geocode** | `POST /api/geocode` → `NominatimGeocoder` | Place name → coordinates. 1 req/s process-wide pacing, descriptive User-Agent. |
| 4 | **Route** | `POST /api/routes` → `OSRMRoutingAdapter.get_routes()` | OSRM `/route/v1/driving/...?alternatives=true&geometries=geojson&steps=true`. 3 retries, 5 s timeout, 120 s in-process cache. **Only the routes OSRM actually returned are displayed.** |
| 5 | **Segment** | `RouteSegmenter` | Splits each route polyline into ~200 m segments, clamped to 50–500 m, ids `seg-{route_id}-{seq:04d}`. |
| 6 | **Fetch imagery** | `PermittedImageryAdapter` → `MapillaryProvider` → `ImageryMatcher` | For each segment, query Mapillary, keep frames within **25 m** of the segment geometry (perpendicular point-to-edge distance), max **3** per segment, reject anything older than **180 days**. Images cached under `data/imagery/`. |
| 7 | **Staleness** | `StalenessEvaluator` (`src/imagery/staleness.py`) | An **unknown capture time is treated as stale**. Stale evidence is flagged, and it does not justify a recommendation. |
| 8 | **Prefetch (perf)** | `SafetyAnalysisPipeline._prefetch_segment_imagery()` | Imagery retrieval is network-bound and order-independent → one bounded `ThreadPoolExecutor` (default 16 workers, `SAFEROUTE_IMAGERY_WORKERS`) across **all** routes at once. Results are placed back at their original index, so the downstream sequence is unchanged. Measured: 20 km / ~100-segment trip went ~18 s → ~4 s with identical evidence. |
| 9 | **Detect** | `HazardDetector.detect()` (see §3.3) | OpenCV validation → letterbox → YOLO11 `predict()` → boxes un-padded and re-normalised → class mapping. |
| 10 | **Deduplicate detections** | `detection_cache` + `_restamp_detection_result()` | The same downloaded frame often matches several segments (adjacent segments, or two alternative routes sharing a road). Inference on identical pixels is deterministic, so the heavy YOLO pass runs **once per image per request** and the result is re-stamped per segment. Evidence and scores are unchanged. |
| 11 | **Aggregate** | `HazardAggregator.assess_segment()` + `deduplicate_adjacent_segment_hazards()` | Per-segment hazard list; cross-segment de-duplication by shared image identity with `adjacent_boundary_iou: 0.50` so a boundary hazard is not counted twice. |
| 12 | **Score** | `DeterministicRiskEngine.score_route()` | `H = Σ severity / max(length_km, 0.10)`; `S = 100 · exp(−0.10 · H)`; coverage suppression; **SHA-256 hash of `config/risk_engine.yaml` stamped on every result**. |
| 13 | **Coverage** | `config/risk_engine.yaml` | `min_coverage_threshold: 0.50`, `full_coverage_threshold: 0.90`, `suppress_insufficient_coverage: true`, **`unassessed_score_placeholder: null`** — an unassessed road is never given a score of 100. |
| 14 | **Compare** | `RouteComparer.build()` | Length-weighted assessed fraction; demo / stale / unassessed routes are excluded; **a tie produces no recommendation**; ordering is still returned. |
| 15 | **Explain** | `GroundedExplanationService.explain()` | Sends only verified backend records to Ollama `/api/generate` with a JSON schema; validates the reply against the schema; checks every route/hazard id and every quoted score against the input; on any failure → **deterministic fallback** with `source: "fallback"`. |
| 16 | **Persist** | `AnalysisStore` (`src/api/store.py`) | SQLite `data/saferoute.db`; tables `model_versions`, `searches`, `analyses`, `scores`, `hazard_detections`; schema created idempotently. |
| 17 | **Render** | React 19 + `maplibre-gl` 6.3.0 | Route lines (casing + line, colour by recommendation), facility markers, origin/destination markers, on OpenFreeMap Liberty tiles. |

### 5.3 API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service + provider status, `model_version`, `mapillary_token=yes\|no` |
| GET | `/api/config` | Non-secret effective settings |
| POST | `/api/geocode` | Place name → coordinates |
| POST | `/api/routes` | Routes (coords or `destination_query`) |
| POST | `/api/analyze` | Full safety analysis |
| GET | `/api/analyze/{id}` | Analysis record |
| GET | `/api/analysis/{id}/hazards` | Hazard detections |
| GET | `/api/analysis/{id}/comparison` | Route comparison |
| GET | `/api/analysis/{id}/explanation` | Grounded explanation |
| POST | `/api/facilities` | Nearby facilities — **separate endpoint, context only (Rule 11)** |

### 5.4 The scoring model in one box

```
H_i  =  ( Σ severity of hazards on segment i ) / max( length_i_metres / 1000 , 0.10 )
S_i  =  100 · exp( −λ · H_i )          λ = 0.10   (config/risk_engine.yaml)
```

* `λ` is an explicitly **provisional baseline** — the score is **ordinal** (it reliably
  orders routes under a fixed policy), **not** a calibrated probability of meeting a hazard.
* Severity comes from a config-driven policy (`config/hazard_severity.yaml`):

  | Hazard class | Base severity (1.0 minor → 5.0 critical) | Why |
  |---|---|---|
  | `pothole` | **3.0** | Direct mechanical shock, puncture risk, loss of vehicle stability |
  | `crack` | **1.5** | Surface defect degrading traction; precursor to road decay |
  | `unsupported` | 1.0 | Neutral floor for a class the checkpoint did not learn |

  Modulation is enabled: `severity = clamp(base × area_factor × conf_factor, 1.0, 5.0)`
  with `alpha_confidence: 0.25`, `beta_area: 0.50`, area clamped to `0.30` normalised area.
* Every stored score carries the **SHA-256 of the config file** that produced it, so any
  score can be traced back to the exact policy that made it.

### 5.5 How to run it (the demo commands)

```powershell
# 1. dependencies (already installed in the workspace .venv)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. optional live services
Copy-Item .env.example .env     # fill MAPILLARY_ACCESS_TOKEN / OLLAMA_*

# 3. API + UI in one command
.\.venv\Scripts\python.exe scripts\run_app.py
#   → http://127.0.0.1:8000/

# 4. tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
#   → 299 backend test methods, all passing   (Measured)

# 5. frontend
cd "frontend\Frontend\project frontend"
npm run lint            # oxlint → 0 errors   (Measured)
npm run test:frontend   # 58 runtime checks   (Measured)
npm run build && npm run preview   # serve on 127.0.0.1:8123
```

---

## 6. The four rules that shaped the architecture

| Rule | Statement | Where it lives in code |
|---|---|---|
| **7** | Deterministic risk engine — the LLM must never calculate or invent a score | `src/risk/engine.py`; `src/risk/*` never imports `src/llm/*` |
| **9** | Missing coverage is disclosed as unknown/unassessed — never treated as proof of a safe road | `unassessed_score_placeholder: null`; `StalenessEvaluator` treats unknown capture time as stale |
| **11** | Facilities stay separate from the hazard score | `src/facilities/schemas.py` has no score field; `src/risk/*` never imports `src/facilities/*` |
| **12** | The LLM may parse preferences and explain verified results — nothing more | `GroundedExplanationService._parse_and_ground()` + deterministic fallback |

---

## 7. Numbers you may quote

| Claim | Value | Status | Safe? |
|---|---|---|---|
| Backend tests passing | **299** methods, 27 `.py` files, 5 852 lines | **Measured** | ✅ |
| Frontend runtime checks passing | **58** | **Measured** | ✅ |
| Frontend lint errors | **0** | **Measured** | ✅ |
| Backend source size | 50 modules, 8 590 lines | **Measured** | ✅ |
| Pinned dependency drift | **0 of 40** | **Measured** | ✅ |
| Direct backend dependencies | **6** | **Measured** (file on disk) | ✅ |
| Locked backend packages | **41** | **Measured** | ✅ |
| Cross-split image leakage | **0** | **Measured** | ✅ |
| mAP50 (v1) | 0.2731 val / 0.2615 test | Repo-reported | ✅ with the label |
| Recall (v1) | 0.3110 val / 0.3009 test | Repo-reported | ✅ with the label |
| Inference latency | 4.02 ms/image | Repo-reported | ⚠️ with checkpoint label |
| v2 promotion | micro-F1 0.297 → 0.327 (601 unseen images) | Repo-reported | ⚠️ **not comparable to mAP50** |
| Live recommendation right now | `cannot_determine` | **Measured** | ✅ — lead with it |
| Overpass live lookup from the audit host | `provider_error` | **Measured** | ✅ as an environment note |

---

## 8. Honest limitations — say these before the examiner asks

1. **The detector is weak.** mAP50 ≈ 0.27, recall ≈ 0.31. Two classes only (`pothole`, `crack`); the other five target classes are reported as **unsupported**, not faked.
2. **The DATA-YOLO training-data licence is unresolved** — no licence file anywhere in the tree. This is the most serious open item; every downstream claim is provisional until it is closed.
3. **No CI/CD.** No `.github/workflows`, no Dockerfile, no `tox`/`nox`. Every check is manual. (Finding F-11.)
4. **Live recommendation currently returns `cannot_determine`** because the imagery the provider returns has no capture timestamp → freshness unverifiable → segments count as unassessed → assessed-length fraction below threshold → the system declines. **That is the designed behaviour, not a bug** — and it is the best 30 seconds of the demo.
5. **The shipped `frontend/assets/` bundle is stale** relative to source (F-06). Use the Vite preview build.
6. **The TRD still says FastAPI + MySQL.** The implementation is stdlib `http.server` + SQLite (F-02). The spec is out of date, not the code.
7. **No measured code-coverage percentage** — `coverage` is deliberately not installed.
8. **Overpass was unreachable from the audit host** — show the honest error, or use the recorded unit-test path.

---

## 9. Phrases to avoid

| ❌ Do not say | ✅ Say instead |
|---|---|
| "AI-powered road safety" | "YOLO11 detection feeding a deterministic risk score" |
| "Accurate hazard detection" | "mAP50 0.2731 — the model's main limitation" |
| "Always recommends the safest route" | "Recommends only when the evidence supports it" |
| "Real-time" | "Typically under the configured client timeout; imagery acquisition dominates" |
| "Production-ready" | "Deployment-ready for a local, single-user evaluation" |
| "Verified hospital data" | "OpenStreetMap tags, echoed as tagged and marked unverified" |
| "The AI explains the route" | "A local LLM explains verified backend results, with a deterministic fallback" |
| "FastAPI backend" | "Standard-library `http.server` backend" |

---

## 10. The closing line (use this verbatim)

> "The defining property of this system is that it knows what it does **not** know.
> Missing imagery, stale imagery, insufficient coverage, tied scores, an unreachable
> provider, an unavailable LLM, an unverified OSM attribute — each has a defined,
> tested, user-visible outcome, and none of them is silently converted into a positive
> claim. `master_rules.md` has 20 rules, every one of them is enforced somewhere in the
> code, and a SHA-256 hash of the scoring configuration is recorded on every score."

---

## 11. Where the evidence for this report came from

| Section | Source |
|---|---|
| §1 Backend libraries | `requirements.txt`, `requirements-lock.txt`, `requirements-dev.txt`, `import` statements across `src/**` and `scripts/**`, `importlib.metadata.version()` against `D:\New folder (3)\.venv` (2026-10-21) |
| §2 Map stack | `frontend/Frontend/project frontend/package.json`, `src/components/map/**`, `src/hooks/useMap.ts`, `src/utils/layers.ts`, `src/config/poiIcons.ts`, `src/imagery/matcher.py`, `src/routing/segmentation.py`, `src/facilities/geometry.py`, `config/*.yaml` |
| §3 YOLO11 | `src/detection/detector.py`, `config/detection.yaml`, `config/hazard_severity.yaml`, `scripts/train_baseline.py`, `scripts/evaluate_baseline.py` |
| §4 OpenCV | `src/preprocessing/pipeline.py`, `src/detection/detector.py`, `config/preprocessing.yaml` |
| §5 Workflow | `src/api/pipeline.py`, `src/api/app.py`, `src/api/bootstrap.py`, `src/api/store.py`, `src/risk/*`, `src/llm/explainer.py`, `src/imagery/*`, `README.md`, `master_rules.md` |
| §6–§10 | [`11-presentation-and-viva.md`](11-presentation-and-viva.md), [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md), [`16-final-audit-report.md`](16-final-audit-report.md) |

*No package was installed, upgraded or removed. No file was modified to produce this
report. All versions were read from the repository or the installed environment on
2026-10-21.*
