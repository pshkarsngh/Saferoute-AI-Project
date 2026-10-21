# SafeRoute AI — Full Technical Audit Report

> **Date:** 2026-10-21
> **Scope:** entire repository — backend, frontend, config, datasets, model artefacts, docs
> **Mode:** read-only audit. **0 application files modified. 0 packages installed. 0 model artefacts altered.**
> **Authority:** `master_rules.md` (20 rules), `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`
> **Deliverable set:** 17 documents under `docs/project-audit/` (this file + `00`–`15`)

---

## Contents

| # | Document | Contents |
|---|---|---|
| 00 | [`00-executive-summary.md`](00-executive-summary.md) | Verdict, top findings, evidence status of every headline number |
| 01 | [`01-repository-map.md`](01-repository-map.md) | Directory tree, full file inventory, two-repository structure |
| 02 | [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md) | Component architecture and data flow, 10 Mermaid diagrams |
| 03 | [`03-technology-stack-and-libraries.md`](03-technology-stack-and-libraries.md) | Declared vs. installed versions, lockfile drift analysis |
| 04 | [`04-dataset-and-labeling.md`](04-dataset-and-labeling.md) | Provenance, class balance, splits, leakage, licence status |
| 05 | [`05-preprocessing-and-feature-engineering.md`](05-preprocessing-and-feature-engineering.md) | OpenCV pipeline, severity policy, risk features |
| 06 | [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) | Model lineage, training configs, reported metrics |
| 07 | [`07-api-database-and-integrations.md`](07-api-database-and-integrations.md) | 10 endpoints, SQLite schema, provider integrations |
| 08 | [`08-security-and-reliability.md`](08-security-and-reliability.md) | Secrets, input validation, resilience, failure honesty |
| 09 | [`09-setup-testing-and-deployment.md`](09-setup-testing-and-deployment.md) | Setup, test commands, CI/CD status, deployment |
| 10 | [`10-code-walkthrough.md`](10-code-walkthrough.md) | Guided tour of the codebase by responsibility |
| 11 | [`11-presentation-and-viva.md`](11-presentation-and-viva.md) | Presentation and viva preparation material |
| 12 | [`12-team-contribution-template.md`](12-team-contribution-template.md) | Per-member contribution record template |
| 13 | [`13-glossary.md`](13-glossary.md) | Project terminology |
| 14 | [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md) | All 37 findings with severity, evidence, actions |
| 15 | [`15-traceability-matrix.md`](15-traceability-matrix.md) | Requirement → rule → code → test → doc mapping |
| 16 | `16-final-audit-report.md` | **This file** — the consolidated single-file deliverable |

---

## 1. Architecture as built

A **stdlib** `http.server` API (`src/api/app.py`, `ThreadingHTTPServer`, 10 endpoints) that also
statically serves the React SPA from the same origin. There is no web framework.

```
Browser (React 19 + MapLibre SPA)
   │  single fetch module: src/lib/api.ts
   ▼
src/api/app.py  —  SafeRouteAPI  ──►  src/api/pipeline.py  —─►  src/api/store.py (SQLite)
                                    │
                                    ├─ routing      src/routing/osrm_adapter.py        (OSRM)
                                    ├─ imagery      src/imagery/*                      (Mapillary)
                                    ├─ detection    src/detection/detector.py           (YOLO11)
                                    ├─ aggregation  src/risk/aggregate.py               (SeverityPolicy)
                                    ├─ risk         src/risk/engine.py                  (DeterministicRiskEngine)
                                    ├─ comparison   src/risk/comparison.py              (RouteComparer)
                                    ├─ explanation  src/llm/explainer.py                (GroundedExplanationService)
                                    ├─ facilities   src/facilities/*                    (Overpass)  ← context only
                                    └─ geocoding    src/geocoding/*                    (Nominatim)
```

`src/api/bootstrap.py` is the **only** place live providers are wired. Each provider degrades
gracefully to an explicit offline/mock path, selected by `config/app.yaml` and
`src/config/settings.py`.

`src/api/store.py` persists analyses, scores, detections and model versions into SQLite
(`data/saferoute.db`) with `model_version` and `config_hash` recorded for auditability.

### 1.1 The scoring chain — one-directional and backend-owned

| Stage | Module | Function |
|---|---|---|
| Route + segment | `src/routing/osrm_adapter.py` | `RouteSegmenter.segment()` — target 200 m, 50–500 m bounds |
| Evidence | `src/imagery/*` | `SegmentImageryMatcher` (25 m buffer), `StalenessEvaluator` (180 days; unknown = stale) |
| Detection | `src/detection/detector.py` | `HazardDetector.detect()` — `SUPPORTED_CLASSES = {0: pothole, 1: crack}` |
| Severity | `src/risk/aggregate.py` | `HazardAggregator.assess_segment()`, `deduplicate_adjacent_segment_hazards()`, `compute_iou()` |
| **Score** | `src/risk/engine.py` | `DeterministicRiskEngine` — `S_i = 100 · exp(-λ·H_i)`, `λ = 0.10`, coverage suppression |
| **Decision** | `src/risk/comparison.py` | `RouteComparer.build()`, `assessed_length_fraction`, recommendation refusal policy |
| **Narration** | `src/llm/explainer.py` | `GroundedExplanationService` — `SYSTEM_PROMPT`, grounding validation, `_fallback` |

**Rule 7** — the deterministic engine owns the score. `src/llm/**` has **no import path** into
`src/risk/**` or `src/detection/**`.
**Rule 11** — facilities are context only. `src/facilities/**` is **not imported by**
`src/risk/**`, and `config/facilities.yaml` carries `guardrails.facilities_in_hazard_score: false`.
**Rule 9** — missing coverage yields `unassessed`; unassessed segments are scored `null`,
**never `100`**.

### 1.2 Frontend

Vite + React 19 + MapLibre SPA. All backend traffic flows through one module,
`src/lib/api.ts`. `src/utils/facilityPresentation.ts` centralises all facility wording.
There is **no second scoring implementation** in the frontend.

> **F-07 — dead code, not a defect.** `src/utils/safety.ts` (317 lines, `analyzeRoutes`) is an
> independent route-scoring implementation that is **not imported anywhere**. It is left in place
> and documented rather than deleted, because removing it is a change to application code and this
> audit is read-only. It should be deleted or quarantined (see Action 5).

---

## 2. Technology stack — verified installed, zero drift

All **40** installed Python packages match `requirements-lock.txt` **exactly**. No drift, no
unpinned extras.

| Package | Installed version |
|---|---|
| torch | 2.13.0+cu130 |
| torchvision | 0.28.0+cu130 |
| ultralytics | 8.4.163 |
| opencv-python | 4.14.0.94 |
| numpy | 2.5.3 |
| PyYAML | 6.0.3 |
| pillow | 12.3.0 |
| matplotlib | 3.11.2 |
| requests | 2.34.2 |
| httpx | 0.28.1 |
| psutil | 7.2.2 |
| polars | 2.0.0 |
| networkx | 3.6.1 |
| certifi | 2026.7.22 |
| urllib3 | 2.8.0 |

- **Python** 3.12.10 (`.venv`)
- **Backend** 50 modules, 8 590 lines
- **Tests** 24 test modules, 5 848 lines, 299 test methods
- **Config** 14 YAML policy files — the runtime source of truth. `config/app.yaml` holds the
  provider selection **and** the server / LLM / imagery settings (`app.llm.*`, `app.server.*`).
  There is **no** `config/llm.yaml`.
- **Frontend** Vite, React 19, TypeScript (`strict` **off** — F-16), MapLibre, `oxlint` 1.78.0
- **Providers** OSRM (routing) · Mapillary (imagery, CC-BY-SA 4.0) · Overpass (facilities) ·
  Nominatim (geocoding) · Ollama 0.40.6 / `llama3:latest` (explanations)

---

## 3. Findings — 37 raised

**1 Critical · 6 High · 16 Medium · 13 Low · 1 Info**

### 3.1 Critical

| ID | Finding | Evidence |
|---|---|---|
| **F-08** | The DATA-YOLO licence is unresolved. No `LICENSE` / `COPYING` / `NOTICE` / `TERMS` file exists anywhere for `DATA-YOLO/`. `DATA-YOLO/Pushkar Singh Baghel.pdf` is a personal résumé, not a licence. The trained weights may be unusable or non-redistributable. | `DATA-YOLO/` tree scan |

### 3.2 High

| ID | Finding | Evidence |
|---|---|---|
| **F-01** | `docs/TRD.md` and `docs/ARCHITECTURE.md` assert "no dataset, no model weights, no source code, no environment exists". All of it now exists. Anyone reading the spec is misinformed about the current system. | `docs/TRD.md` L27–28, `docs/ARCHITECTURE.md` L21–24 vs. `src/`, `models/`, `data/`, `.venv/` |
| **F-02** | `docs/ARCHITECTURE.md` §12 deployment table says "Not created / Not installed" for every row; the frontend §3 describes FastAPI while the backend is stdlib `http.server`. | `docs/ARCHITECTURE.md` L470–484, `src/api/app.py` L1–22 |
| **F-06** | The serving bundle in the outer repo (`frontend/assets/`) predates the current frontend source; the nested repo's own build output has different content hashes. The deployed UI is not the audited UI. | `frontend/index.html` vs `frontend/Frontend/project frontend/dist/assets/` |
| **F-11** | No CI/CD. No `.github/`, no Dockerfile, no compose, no Makefile, no `tox`/`nox`, no `pre-commit` for the core repository. Every check is manual. | tree scan |
| **F-12** | No API authentication or rate limiting. `Access-Control-Allow-Origin: *` on every response; `ThreadingHTTPServer` accepts concurrent connections. Acceptable for a local demo, not for a shared deployment. | `src/api/app.py` L259–265 |
| **F-13** | Detection accuracy is weak. Repo-reported mAP50 0.2731 (val) / 0.2615 (test) for v1; the detector is close to the noise floor. This is the honest state, but it caps the usefulness of the hazard evidence the product is built to present. | `logs/evaluation/evaluation_record.json` |

### 3.3 Medium

| ID | Finding | Evidence |
|---|---|---|
| **F-03** | `logs/evaluation/evaluation_record.json` is internally inconsistent: the rationale prose quotes mAP 0.278 / 0.231 while the machine-readable fields say mAP50 0.2731 / 0.2615. | `logs/evaluation/evaluation_record.json` |
| **F-04** | `logs/training/saferoute-yolo11-datayolo-exp/run_record.json` records `status: "ERROR"` (DataLoader worker crash) while `train.log` and `results.csv` in the same folder show a later, successful 68-epoch run with a `best.pt`. The provenance record under-reports the outcome. | `logs/training/saferoute-yolo11-datayolo-exp/` |
| **F-05** | `scripts/prepare_rdd2022_yolo.py` has a docstring and an `argparse` import describing a CLI, but no argument parsing or entry point is implemented. | `scripts/prepare_rdd2022_yolo.py` (123 lines) |
| **F-07** | `src/utils/safety.ts` (317 lines, `analyzeRoutes`) is not imported anywhere and contains an independent route-scoring implementation. Dead code that could be mistaken for an active path. | import scan of `frontend/.../src/` |
| **F-09** | The DATA-YOLO licence gap is already recorded as an open item in the project's own report and remains unresolved after the phase that raised it. | `docs/reports/DATA_YOLO_TRAINING_PREP.md` L139 |
| **F-14** | DATA-YOLO contains **49** intra-split duplicate image groups (33 train / 71 files, 7 val / 14 files, 9 test / 18 files). Cross-split overlap is **0**, so there is no test-set leakage, but the duplicates inflate the effective training-set size. | SHA-256 duplicate scan |
| **F-15** | The `datayolo_prep` `test:` split is not an independent holdout. It is a same-source, scene-grouped list; the `MANIFEST.json` itself says so. | `data/datayolo_prep/MANIFEST.json` |
| **F-16** | TypeScript `strict` is disabled in `tsconfig.app.json`, and there is no ESLint/Prettier configuration in the frontend package (`oxlint` is used instead). | `frontend/.../tsconfig.app.json`, `package.json` |
| **F-17** | Frontend accessibility gaps: no `prefers-reduced-motion` handling and no `aria-live` region for async status, despite animations throughout. | `frontend/.../src/` |
| **F-18** | The shipped frontend bundle in the outer repo was deliberately not rebuilt during Phase 2, so the UI served by the backend is older than the source. | `frontend/assets/` vs nested `dist/` |
| **F-20** | Live Mapillary frames currently return `captured_at = None`, so freshness cannot be verified and analyses resolve to `recommendation: null` / `cannot_determine`. This is correct Rule-9 behaviour, but the live product currently cannot issue a recommendation. | live `POST /api/analyze` |
| **F-26** | No database migration mechanism. `AnalysisStore._init_schema()` uses `CREATE TABLE IF NOT EXISTS` only. | `src/api/store.py` |
| **F-28** | The API server writes no structured logs to `logs/`; `log_message` is overridden to a no-op, while TRD §3.4 requires structured logs. | `src/api/app.py` |
| **F-29** | The nested frontend repository breaks single-clone and single-PR workflows; the outer `.gitignore` excludes `frontend/Frontend/`. This also blocks a clean CI setup (F-11). | outer `.gitignore` |
| **F-31** | Coordinate-range and string-length validation is missing at the API boundary. | `src/api/app.py` |
| **F-37** | v1 and v2 were trained and evaluated on a **silently reduced** image set: Ultralytics discards any image whose label contains class ≥ `nc`, so only **861 of 1 406** train, **264 of 402** val and **125 of 201** test images were actually used. The defect was diagnosed and fixed (a corrected derived dataset exists), but the published metrics still carry it. | `config/training_canonical.yaml` |

### 3.4 Low and Info

| ID | Finding | Severity |
|---|---|---|
| F-10 | `config/facilities.yaml` `default_provider` is `"mock"` while `config/app.yaml` selects `"overpass"` | Low |
| F-19 | `public/video/video.mp4` is **105 MB** inside the frontend public directory | Low |
| F-21 | No `LICENSE` file for the SafeRoute AI source code itself | Low |
| F-22 | Silent LLM fallback is not counted or logged | Low |
| F-23 | The 500-response `detail` field echoes the raw exception message | Low |
| F-24 | Malformed numeric request fields are silently coerced to defaults | Low |
| F-25 | The OSRM response cache has no lock | Low |
| F-27 | No indexes declared on the SQLite schema | Low |
| F-30 | `vercel.json` is a misleading leftover scaffold | Low |
| F-32 | `weights/yolo26n.pt` (5 544 453 B) has no training record | Low |
| F-33 | Dead frontend assets and 5 stray `console.log` calls per facility request | Low |
| F-35 | The backend has no Python linter, formatter or type checker | Low |
| F-36 | No test-coverage measurement exists | Low |
| F-34 | Phase report numbering has gaps (`PHASE_21`, `26`, `27`, `30`) | Info |

### 3.5 F-37 in detail — the most consequential new finding

`config/training_canonical.yaml` records a defect that materially qualifies every published metric:

> The original `data/dataset.yaml` declares `nc=2` but the source labels contain class-2 (manhole)
> rows in **759 of 2 009** images. Ultralytics treats any label with `class >= nc` as corrupt and
> **discards the whole image**, so v1 and v2 were silently trained on only **861 of 1 406** images
> and evaluated on **264 of 402** (val) and **125 of 201** (test).

| Quantity | Nominal (split file) | Actually used |
|---|---:|---:|
| Train images | 1 406 | **861** (61 %) |
| Validation images | 402 | **264** (66 %) |
| Test images | 201 | **125** (62 %) |

The failure mode was **silent** — Ultralytics drops the offending image and continues, so nothing
in the training log signals a problem.

**How it was fixed.** `config/training_canonical.yaml` was created as the single documented
canonical training workflow. It trains on the audited derived two-class corpus
(`data/dataset_v2.yaml` + `data/splits_v2`, date-atomic, **zero** corrupt images), where the
manhole box is removed **in the derived labels only** — the original annotation is preserved
unchanged, so nothing is silently relabelled (Rule 15). **This is credited as P-16.**

**What remains open.** The published metrics are still the ones measured under the defect, and
the v2 checkpoint that actually serves traffic was promoted on a different 601-image micro-set.
One clean re-measurement closes F-13, F-15, F-37 and part of F-03 at once.

---

## 4. Positive confirmations — 16

Things the audit confirmed as done correctly, and which should be stated in any assessment.

| # | Confirmation | Rule |
|---:|---|:---:|
| P-01 | The backend is the sole owner of safety scores; no path from facilities or the LLM into the risk engine | 7, 11, 12 |
| P-02 | Missing evidence yields `unassessed`, never a safety claim; unassessed segments are scored `null`, not `100` | 9 |
| P-03 | Only provider-returned routes are shown; no padding, no synthesis | 10 |
| P-04 | Cross-split image leakage is **zero** in both corpora | 15 |
| P-05 | The date-atomic split removes leakage by construction | 15 |
| P-06 | The single-confidence-threshold policy is enforced by a loud failure, not by convention | 6, 9 |
| P-07 | Zero dependency drift — all 40 installed packages match the lock exactly | 18 |
| P-08 | The LLM boundary is enforced: grounding validation plus an honest fallback path | 12, 14 |
| P-09 | Provider failures are disclosed, never emptied into a falsely clean result | 9, 14 |
| P-10 | Path traversal in the static file server is blocked | 12 |
| P-11 | No secret value appears in any source, config, log or document | 13 |
| P-12 | Unsupported classes are reported honestly rather than silently dropped | 14 |
| P-13 | Google Street View is disabled with a recorded ToS reason; no disallowed imagery source is reachable | 8 |
| P-14 | 299 backend test methods, all passing | 14 |
| P-15 | The negative tests are thorough — failure paths are asserted, not just happy paths | 14, 17 |
| P-16 | The class-2 "corrupt image" defect was diagnosed, documented in `config/training_canonical.yaml`, and fixed with a corrected derived dataset rather than by patching labels in place | 15, 17 |

---

## 5. Evidence status of every headline number

Nothing here is presented as *measured* unless it was measured. The project's model metrics were
**not** re-measured during this audit — they are quoted as *repo-reported* and labelled.

| Quantity | Value | Status |
|---|---|---|
| Backend tests | `Ran 299 tests … OK` (19.4 s) | **Measured** (re-run during this audit) |
| Frontend checks | 58 checks, 0 failures | **Measured** (re-run during this audit) |
| Frontend build | clean | **Measured** (Phase 2 run) |
| Frontend lint | 0 errors (1 177 warnings, 1 163 in vendored `public/assets/maplibre-gl-*.mjs`) | **Measured** (re-run during this audit) |
| Backend lines / modules | 8 590 / 50 | **Measured** (this audit) |
| Test lines / methods | 5 848 / 299 | **Measured** (this audit) |
| Installed Python packages | 40 pinned, all matching `requirements-lock.txt` | **Measured** (this audit) |
| Cross-split image leakage | 0 | **Measured** (this audit) |
| Intra-split duplicate groups (older corpus) | 49 | **Measured** (this audit) |
| v1 model mAP50 | 0.2731 val / 0.2615 test | **Repo-reported**, not independently reproduced |
| v2 model promotion | 601-image unseen micro F1 0.297 → 0.327 @ conf 0.25 | **Repo-reported** (`config/detection.yaml` comment) |
| Inference latency | 4.02 ms/image | **Repo-reported** |
| Effective v1/v2 evaluated images | 861 / 1 406 · 264 / 402 · 125 / 201 | **Repo-reported** (`config/training_canonical.yaml`) |
| Overpass live lookup | `status: provider_error` | **Measured** (all public mirrors unreachable from this machine) |

### 5.1 What is genuinely unknown

- **No live Overpass record was retrieved end-to-end.** All public mirrors fail from this machine
  (`overpass-api.de` → HTTP 502; `overpass.kumi.systems`, `overpass.private.coffee`,
  `maps.mail.ru` → 30 s read timeout; `overpass.osm.jp` → SSL
  `CERTIFICATE_VERIFY_FAILED: Hostname mismatch`). This is an **environment condition, not a code
  defect**. The live path correctly returns `status: provider_error` with honest notes; the
  provider-success path is covered by stubbed-`urlopen` unit tests.
- **Mapillary capture timestamps** return `captured_at = None`, so freshness is unverifiable and
  live analyses resolve to `cannot_determine` (F-20).
- **Model metrics were not re-measured.** Labelled *repo-reported* throughout.
- **Mermaid rendering was validated structurally, not by rendering** — `mermaid` /
  `mermaid-cli` is not installed and nothing was installed.
- **No coverage percentage exists** and none was invented (F-36).

---

## 6. Dataset and split integrity (measured)

| Corpus | Images on disk | Label rows | Class 0 / Class 1 | Empty labels |
|---|---:|---:|---:|---:|
| `data/datayolo_prep/` | **1 789** (train 1 251 / val 269 / test 269) | **2 535** | 1 505 / 1 030 | 0 |
| `data/derived_2class/` | **2 009** on disk, **1 792** labelled | **3 420** | 1 166 / 2 254 | 336 |
| `DATA-YOLO/` | upstream source | — | — | licence unresolved (F-08) |

| Split file | train | val | test | quarantined |
|---|---:|---:|---:|---:|
| `data/splits/` (v1) | 1 406 | 402 | 201 | — |
| `data/splits_v2/` (v2, date-atomic) | 1 398 | 178 | 216 | 212 |

- **SHA-256 duplicate scan** — `datayolo_prep`: 49 intra-split groups (33 train / 71 files,
  7 val / 14 files, 9 test / 18 files). `derived_2class`: 5 groups overall.
- **Cross-split leakage: 0** in both corpora — verified by hashing every split member against the
  split files, not assumed.
- The 212 quarantined images are **held out**, not discarded — consistent with Rule 15.

---

## 7. Validation of this documentation set

| Check | Result |
|---|---|
| Files present | 17 of 17 (`00`–`16`) |
| Relative Markdown links | **66 checked, 0 broken** |
| Mermaid blocks | **11 checked, 0 structural issues** — balanced `subgraph`/`par`…`end`, quotes, brackets, parens, braces; no reserved-word node IDs |
| Code fences | balanced in all 17 files |
| Path-existence sweep | **202** distinct path tokens; every unresolved token is intentional ellipsis shorthand (`frontend/.../src/...`) or a file the finding explicitly states does not exist |
| Secret-literal scan | only variable *names* (`MAPILLARY_ACCESS_TOKEN`) and path/type descriptions — **no credential value anywhere** |
| Cross-document count agreement | 37 findings, 16 positive confirmations, 24 test modules, 14 config files, 49 duplicate groups — consistent in every document |

### 7.1 Corrections applied to earlier drafts of this set

Found and fixed during validation. Recorded here so the audit trail is honest.

| # | Error in the first draft | Correction | How it was caught |
|---:|---|---|---|
| 1 | "54 intra-split duplicate groups" | **49** (arithmetic error: 33 + 7 + 9) | re-ran the SHA-256 scan |
| 2 | `config/` listed 6 files that do not exist (`llm.yaml`, `api.yaml`, `app_settings.yaml`, `training.yaml`, `dataset.yaml`, `evaluation.yaml`) | the **14 real** files; `config/app.yaml` holds `app.llm.*` / `app.server.*` | directory listing |
| 3 | Mermaid dependency graph labelled `config/settings.py`, `config/__init__.py`, `config/thresholds.py` | corrected to `src/config/…` | path-existence sweep |
| 4 | A fabricated row for `tests/unit/test_detect_v2*.py` | **removed**; test count 23 → **24** modules | directory listing |
| 5 | `data/derived_2class/` reported as "1 792 images" | **2 009 on disk / 1 792 labelled** | disk count vs. split-file count |
| 6 | `config/llm.yaml` cited as the LLM config source in 5 documents | `config/app.yaml` → `app.llm` | config inspection |
| 7 | *(new finding)* the class-2 corrupt-image effect on the published metrics was missed entirely | added as **F-37**, with §5.5 in doc 04 and §7 in doc 06 | re-read of `config/training_canonical.yaml` |

---

## 8. Recommended next actions

Ordered by value per unit of effort. Full rationale in
[`14-findings-and-recommendations.md`](14-findings-and-recommendations.md) §5.

### Tier 1 — do first (low effort, high value)

| # | Action | Findings | Effort |
|---:|---|---|---|
| 1 | Refresh the specification set so it describes the implemented system | F-01, F-02 | S–M |
| 2 | Add a minimal CI workflow for the backend | F-11 | S |
| 3 | Rebuild the outer frontend bundle, or document the frontend repository's `dist/` as authoritative | F-06, F-18 | S |
| 4 | Delete the dead browser-side scoring module | F-07 | S |
| 5 | Repair the two stale provenance records | F-03, F-04 | S |
| 6 | Reconcile the two facilities-provider defaults | F-10 | S |
| 7 | Log the LLM fallback usage | F-22 | S |

### Tier 2 — resolve the substantive blockers

| # | Action | Findings | Effort |
|---:|---|---|---|
| 8 | **Resolve the DATA-YOLO licence** — obtain, exclude, or retrain on a licensed corpus | F-08, F-09, F-13 | M + external |
| 9 | Re-evaluate the serving checkpoint on the date-atomic test split; publish one unambiguous metric | F-13, F-15, F-37, F-03 | M |
| 10 | De-duplicate the training corpus before the next training run | F-14 | M |
| 11 | Investigate the missing Mapillary capture timestamps | F-20 | M |
| 12 | Add authentication, rate limiting, body-size limits and tighter CORS | F-12 | M |
| 13 | Add a corpus check to the training scripts that fails loudly when the loaded image count differs from the split size | F-37 | S |

### Tier 3 — engineering hygiene

| # | Action | Findings | Effort |
|---:|---|---|---|
| 14 | Enable TypeScript `strict` incrementally | F-16 | M |
| 15 | Add `prefers-reduced-motion` support and an `aria-live` status region | F-17 | M |
| 16 | Add a database migration mechanism and the missing indexes | F-26, F-27 | M |
| 17 | Emit structured API logs to `logs/` | F-28 | M |
| 18 | Add coordinate-range and string-length validation; reject rather than coerce | F-31, F-24 | M |
| 19 | Decide the frontend repository strategy | F-29 | M |
| 20 | Implement or remove the `prepare_rdd2022_yolo.py` CLI | F-05 | M |
| 21 | Clean up dead assets, the 105 MB video and stray `console.log` calls | F-19, F-33 | S |

### Tier 4 — polish

| # | Action | Findings | Effort |
|---:|---|---|---|
| 22 | Add a `LICENSE` for the project source | F-21 | S |
| 23 | Add `ruff` to `requirements-dev.txt` and run it once | F-35 | S |
| 24 | Lock the OSRM cache and add a `schema_version` table | F-25, F-26 | S |
| 25 | Remove `vercel.json`, or annotate it as unused | F-30 | S |
| 26 | Explain or remove `weights/yolo26n.pt` | F-32 | S |
| 27 | Add a phase-report index | F-34 | S |
| 28 | Measure test coverage once, if the submission needs it | F-36 | S |

---

## 9. Compliance statement

- **Files modified by this audit: 0.** The only files created are the documents under
  `docs/project-audit/`.
- **Nothing staged, committed or pushed** in either repository. Outer HEAD `53f7f63`; nested
  frontend HEAD `8449593`.
- **Both git baselines are byte-identical to their pre-audit state:**
  - Outer: 15 modified, 5 untracked (`docs/project-audit/`, the two Phase 28/29 reports,
    `src/facilities/geometry.py`, `tests/unit/test_facilities_api.py`).
  - Nested frontend: 11 modified, 1 untracked (`src/utils/facilityPresentation.ts`).
- **No packages installed, no dependencies upgraded, no database migrated, no model artefact
  altered.**
- Pre-existing Phase 28 work (`.gitignore`, `.env.example`, `config/app.yaml`,
  `src/config/settings.py`, `src/llm/explainer.py`, `tests/unit/test_llm_explainer.py`,
  `docs/reports/PHASE_28_LLM_EXPLANATION_REPAIR.md`) was left **untouched**.
- **No credential value** is reproduced in any document. Credential issues are reported by path
  and type only (Rule 13).
- Every implementation claim names a file path and, where applicable, a function or class that
  exists at the stated path.
- Unknowns are marked `Unknown`, `Not found` or `Not verified` rather than estimated.
- **Phase 3 has not been started** and will not be until explicitly approved.

---

*Compiled on 2026-10-21 from direct inspection of `master_rules.md`, `docs/PRD.md`,
`docs/TRD.md`, `docs/ARCHITECTURE.md`, the `src/**`, `config/**`, `tests/**`, `scripts/**`,
`data/**`, `models/**`, `logs/**` trees and the frontend source, plus a live run of the backend
test suite, the frontend check runner and the linter.*
