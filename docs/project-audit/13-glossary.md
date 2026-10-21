# 13 — Glossary

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Purpose:** project terminology in one place, with the exact identifier or config key
> used in the codebase so that a term and its implementation can be found together.

---

## A. Project and governance

**SafeRoute AI** — the project: an intelligent road-safety navigation system that
compares the routes a routing provider actually returns, using road-hazard evidence.

**Master rules** — `master_rules.md`, the authoritative root-level engineering document
containing 20 numbered rules. Every implementation decision in the project answers to one
of them. Where a rule and another approved document conflict, the rule prevails and the
conflict must be raised explicitly (Rule 2).

**PRD** — Product Requirements Document, `docs/PRD.md`. Describes intended product
behaviour; claims nothing is implemented.

**TRD** — Technical Requirements Document, `docs/TRD.md`. Elaborates the technical
design. **Currently stale** — it states that no dataset, model, environment or source
code exists (finding F-01).

**ARCHITECTURE** — `docs/ARCHITECTURE.md`. Proposed component architecture and data
flows. **Also stale** — it proposes FastAPI and MySQL, while the implementation uses
stdlib `http.server` and SQLite (finding F-02).

**TRAINING_RULES** — `docs/TRAINING_RULES.md`. Rules specific to dataset preparation
and model training.

**Phase** — an approved, incremental unit of work (Rule 3). Each phase produces a
report under `docs/reports/`.

**Evidence honesty** — the defining property of the project: missing, stale, insufficient
or unavailable evidence is disclosed as *unknown* or *unassessed*, and is never presented
as a safe road (Rule 9, `README.md`).

---

## B. Evidence and status vocabulary

**Assessed** — the segment was successfully evaluated against imagery that passed
validation and freshness checks. Status value: `assessed`.

**Partially assessed** — some imagery was available and some was not.
Status value: `partially_assessed`.

**Unassessed** — no usable imagery was available, or it could not be trusted.
Status value: `unassessed`. **Never** rendered as safe.

**Failed** — an error occurred (decode failure, inference error, provider rejection).
Status value: `failed`.

**Inaccessible** — the provider rejected the request (HTTP 401/403). Distinct from
"not found": the imagery exists but access was denied.

**Unmatched** — imagery was requested but nothing fell within the spatial buffer.

**Coverage** — the fraction of a route that actually carries a score.
`CoverageInfo(images_total, images_used, fraction)`.

**Assessed length fraction** — the fraction of a route's **length** that carries a score
(as opposed to the fraction of its segments). Computed by
`assessed_length_fraction()` in `src/risk/comparison.py`. This is the figure that
decides whether a recommendation is defensible.

**Coverage suppression** — when a segment's coverage is below
`min_coverage_threshold` (0.50), its score is withheld (`is_suppressed = True`,
`segment_score = None`) rather than being reported.

**Staleness** — imagery older than `max_age_days` (180). An **unknown** capture
timestamp is also treated as stale.

**Limitation** — an explicit, user-visible disclosure attached to a result.

**Demo imagery** — sample frames with no verified geographic location. Flagged
`is_demo: true`, never spatially matched, never presented as evidence for a real route.
Guarded by `config/imagery.yaml` → `demo.enabled: false`.

**Rule 10 / route fidelity** — show only the routes the routing provider actually
returned; show fewer than four when fewer are available. Never pad or synthesise.

---

## C. Machine learning

**YOLO11** — the mandated object-detection family (Rule 4). The project uses the
**YOLO11n** nano variant.

**Ultralytics** — the Python package (`ultralytics` 8.4.163) that provides the YOLO11
API, training loop and augmentation pipeline.

**Checkpoint** — a trained `.pt` weights file. `best.pt` is the epoch with the best
validation metric; `last.pt` is the final epoch.

**Serving checkpoint** — the checkpoint actually used in production inference. Currently
`models/training/saferoute-yolo11-v2/weights/best.pt`, selected by
`config/detection.yaml` → `model.checkpoint`.

**Model version** — the stable identifier for a trained model: `saferoute-yolo11-v1`,
`-v2`, `-datayolo-exp`. Model *size* is recorded separately, per TRD §5.6.

**Epoch** — one complete pass over the training set.

**Early stopping** — training halted when the monitored validation metric stopped
improving for a patience period. The v2 run stopped at epoch 104 of a 144-row log.

**Precision** — of the detections made, the fraction that are correct.

**Recall** — of the true hazards present, the fraction that were detected. **The weaker
axis for this project** (0.31 on validation for v1).

**F1** — the harmonic mean of precision and recall.

**mAP50** — mean Average Precision at an IoU threshold of 0.5. The primary headline
metric for this project; **repo-reported at 0.2731 (val) / 0.2615 (test)** for v1.

**mAP50–95** — mAP averaged over IoU thresholds from 0.5 to 0.95 in 0.05 steps. A
stricter measure of localisation quality: 0.1007 (val) / 0.0952 (test) for v1.

**IoU (Intersection over Union)** — the overlap ratio of two bounding boxes. Used for
within-frame de-duplication (threshold 0.45) and adjacent-segment de-duplication
(threshold 0.50).

**NMS (Non-Maximum Suppression)** — the standard detector post-process that removes
overlapping boxes for the same object. The detector's own NMS runs at IoU 0.45.

**Supported class** — a class the loaded checkpoint was actually trained to detect:
`0: pothole`, `1: crack`. Anything else is reported as `unsupported_class` (Rule 5).

**Unsupported class** — a class in the project's target hazard taxonomy that the current
checkpoint cannot detect: `manhole`, `damaged_patch`, `waterlogging`,
`uneven_surface`, `speed_bump`.

**Transfer learning** — initialising training from pretrained weights (`yolo11n.pt`)
rather than from scratch.

**Mixed precision (AMP)** — reduced-precision arithmetic during training, for speed and
VRAM headroom.

**Letterbox** — aspect-ratio-preserving image resizing with padding, so the detector
receives a fixed-size input without distorting the geometry.

**Confidence threshold** — the minimum detection confidence that is retained. **0.25**,
and it must be identical in `config/detection.yaml` and
`config/hazard_severity.yaml` — enforced by `assert_threshold_consistency()`.

**Leakage (train/test)** — the same or near-identical images appearing in more than one
split. Measured: **0 cross-split duplicates** in both corpora.

**Hard link** — an NTFS file reference, so `data/datayolo_prep/` images and the
`DATA-YOLO/` originals share the same bytes on disk.

---

## D. Risk scoring

**Hazard detection** — a raw output from the YOLO11 model: class, confidence, bounding
box.

**Hazard record** — a detection after severity assignment, thresholding and
de-duplication. `HazardRecord` in `src/risk/schemas.py`.

**Severity** — a 1.0 (minor) to 5.0 (critical) score assigned by
`SeverityPolicy` from a class base table, modulated by bbox area and confidence, and
clamped. Deterministic; never decided by an LLM (Rules 5, 7, 12).

**Base severity** — the class-level starting value: `pothole` 3.0, `crack` 1.5,
`unsupported` 1.0.

**H (hazard density)** — total severity per kilometre of road:
`H = sum(severity) / max(length_m / 1000, min_segment_length_km)`.

**λ (lambda_decay)** — the exponential decay constant in the scoring formula. **0.10**,
documented in the config as a *provisional baseline*.

**S (safety score)** — `S = 100 × exp(−λ × H)`. Range 0–100, higher = safer. A
**deterministic, ordinal** value — comparable between routes under a fixed policy, but
not a calibrated probability of harm.

**Config hash** — a SHA-256 digest of the risk-engine configuration file, recorded on
every score, analysis and database row. Makes any score traceable to the exact policy
that produced it (Rule 17).

**Recommendation** — the route the comparison layer names as safest. Issued **only**
when the evidence supports it; `null` otherwise.

**`cannot_determine`** — the status used when a recommendation is withheld because the
evidence is insufficient.

**Tie** — two or more routes sharing the top score. A tie produces **no
recommendation** (Rule 14: never fabricate a preference).

---

## E. Routing and geography

**Route** — a path returned by the routing provider, with geometry, distance, duration
and segments.

**Route segment** — a bounded portion of a route, produced by `RouteSegmenter`.
Target 200 m, floor 50 m, ceiling 500 m.

**OSRM** — Open Source Routing Machine, the keyless OpenStreetMap routing engine used
here. Public demo server at `router.project-osrm.org`.

**Geocoding** — converting a place name into coordinates. Done by Nominatim (keyless).

**Nominatim** — the OpenStreetMap geocoding service, used under its usage policy: a
descriptive User-Agent and at most one request per second.

**Haversine distance** — the great-circle distance between two lat/lon points, used for
route length and matcher geometry.

**LineString** — the GeoJSON geometry type used for route and segment geometry.

**Bounding box (bbox)** — the `(south, west, north, east)` rectangle around one or more
route polylines. Used to scope the Overpass query.

**Corridor** — the set of points within a radius of the route polyline, rather than a
circle around a single point.

**Straight-line distance** — great-circle distance. Distinct from road-network distance;
always labelled by `distance_kind`.

**Road-network distance / travel time** — a road distance obtained from a **real**
routing provider. Present only when a real road route was actually returned; never
estimated locally.

**Subtype** — the granular OSM value behind a facility category. E.g. category `medical`
with `subtype: "pharmacy"`.

---

## F. Imagery and facilities

**Permitted imagery** — imagery from a source whose access and reuse terms allow
automated retrieval and model inference (Rule 8). Here: Mapillary (CC-BY-SA 4.0) and the
local `workspace_dashcam_v1` archive (CC-BY 4.0).

**Mapillary** — the street-level imagery platform used here. Requires an access token
from `.env`.

**ImageRef** — a retrieved image with its provenance: source, licence, capture time,
coordinates, distance to the segment, staleness and demo flags.

**Spatial match / buffer** — the 25 m radius around a segment's geometry within which an
image is accepted as evidence for that segment.

**Overpass** — the OpenStreetMap API for querying map features; used here for nearby
facilities. Keyless. The provider queries one category at a time across 3 mirrors with a
0.7 s gap and a 45 s overall deadline.

**Facility** — a nearby hospital, medical facility, police station, fuel station, hotel
or restaurant. **Context only** — never an input to the hazard score (Rule 11).

**Attributes verified** — whether the facility's underlying attributes were
independently confirmed. For OpenStreetMap data this is always `false`; the tags are
echoed exactly as tagged.

**ODbL** — the Open Database License, covering OpenStreetMap data.

**CC-BY / CC-BY-SA** — Creative Commons attribution and attribution-share-alike licences,
covering Mapillary imagery (CC-BY-SA 4.0) and the local dashcam archive (CC-BY 4.0).

**Zenodo DOI** — a persistent identifier for a dataset. `10.5281/zenodo.17834373` is
carried by `data/pothole_crack_manhole/data/README.md`.

---

## G. Platform and infrastructure

**Provider** — an external service the application depends on: OSRM, Mapillary,
Overpass, Nominatim, Ollama.

**Provider adapter** — the module that implements a provider behind an interface, so the
provider can be swapped without touching higher layers.

**Mock provider / offline fixture** — a deterministic, network-free stand-in used in
tests or offline operation. Synthetic routes from a mock are **flagged as demo** and
excluded from real-world recommendations.

**Mirror failover** — trying a second and third endpoint when the first fails.
Configured for Overpass (3 endpoints).

**Query deadline** — an overall time budget for one logical operation (Overpass: 45 s),
after which remaining sub-queries are skipped and the partial result disclosed.

**Backoff** — the wait between retry attempts (0.5 s for OSRM and Overpass).

**ThreadingHTTPServer** — the stdlib HTTP server that handles each request on its own
thread.

**SPA fallback** — serving `index.html` for a client-side route so a direct navigation
or refresh works.

**Path traversal** — an attempt to escape the served directory using `../`. Blocked by
resolving the path and verifying containment.

**SQLite** — the file-based relational database used for persistence, via the stdlib
`sqlite3` module. The database file is `data/saferoute.db`.

**Analysis store** — `AnalysisStore`, the class that owns the schema and all reads and
writes.

**Idempotent write** — a write that produces the same result whether applied once or
many times. `INSERT OR REPLACE` plus an explicit delete-then-insert for detections.

**Ollama** — the local LLM runtime. Serves `llama3:latest` on `127.0.0.1:11434`.

**Grounded explanation** — an LLM explanation that contains only facts present in the
verified backend input, validated by schema and entity-grounding checks.

**Fallback explanation** — the deterministic template explanation used when the LLM is
unavailable or its output fails validation. Always carries `source: "fallback"`.

**Entity grounding check** — the validation that rejects any LLM reply referencing a
route or hazard identifier absent from the input.

**Prompt injection** — an attempt to make the LLM follow instructions embedded in user
text or imagery content. Mitigated by treating all such content as data and granting
the LLM no tool access.

**MapLibre GL** — the open-source map renderer used by the frontend, with the
OpenFreeMap Liberty style.

**Vite** — the frontend build tool and dev server.

**oxlint** — the Rust-based linter used in place of ESLint.

**Lock file** — `requirements-lock.txt` (41 pinned Python packages) and
`package-lock.json` (`lockfileVersion: 3`).

**`unittest`** — the standard-library test runner used by the project. `pytest` is
deliberately **not** installed.

**Prebuilt bundle** — a compiled static frontend under `frontend/assets/`, distinct from
the frontend source repository and from that repository's own `dist/` output. Currently
**stale** relative to source (finding F-06).

**Nested repository** — a Git repository inside another Git repository. The frontend is
one; the outer `.gitignore` excludes it, so its commits do not appear in the outer
history.

---

## H. Status and vocabulary used in these audit documents

| Term | Meaning |
|---|---|
| **Measured** | Verified during this audit or during the recorded Phase 2 verification, with the method stated. |
| **Repo-reported** | Quoted from a file in the repository. Not independently reproduced. Always labelled. |
| **Unverified** | Stated in the repository but not checked. |
| **Not found** | Searched for and absent. |
| **Unknown** | Could not be determined from the available material. |
| **Finding (F-nn)** | A confirmed defect or risk, listed in `14-findings-and-recommendations.md`. |
| **Rule n** | A numbered rule in `master_rules.md`. |

---

*Terminology in this glossary was taken from the source files, config keys and
documentation in the workspace. Where a term has both a project meaning and a general
one, the project meaning is given.*
