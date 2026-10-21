# 00 — Executive Summary

> **Subject:** SafeRoute AI — Intelligent Road Safety Navigation System
> **Workspace:** `D:\New folder (3)`
> **Audit date:** 2026-10-21
> **Audit type:** Read-only technical audit (documentation only)
> **Governing document:** [`../../master_rules.md`](../../master_rules.md) (authoritative)
> **Status of this document:** Evidence-based audit record. It describes what exists in the
> repository as of the audit date; it does not approve, change or extend any requirement.

---

## 1. What was audited

The complete SafeRoute AI workspace was inspected read-only: the backend package `src/`
(50 Python modules, 8 590 lines), the frontend source (89 files, separate nested Git
repository), the configuration set (`config/*.yaml`, 14 files), the test suite
(27 files, 299 test methods), the datasets (`data/`, `DATA-YOLO/`), the trained model
artifacts (`models/`, `weights/`, `yolo11n.pt`), the operational scripts (`scripts/`,
`scripts/audit/`), the generated logs (`logs/`), and the specification set
(`master_rules.md`, `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`,
`docs/TRAINING_RULES.md`, plus 63 files under `docs/`).

No application file was modified, moved or deleted. No package was installed or upgraded.
No dataset was altered. No model artifact was regenerated. No destructive command was run.

## 2. What the system is

SafeRoute AI answers one question honestly: **of the routes a routing provider actually
returns, which one has the best road-condition evidence, and what is the strength of that
evidence?** It does this by:

1. Fetching real route alternatives from OSRM (keyless OpenStreetMap).
2. Acquiring street-level imagery for each route segment from Mapillary (CC-BY-SA 4.0),
   matched spatially to the segment geometry within a 25 m buffer.
3. Running YOLO11n inference on that imagery through a versioned OpenCV pipeline.
4. Aggregating detections through a deterministic severity policy.
5. Scoring each route with a deterministic risk engine, `S_i = 100 × exp(-λ × H_i)`.
6. Comparing routes and issuing a recommendation **only** when the evidence supports one.
7. Explaining the result through a grounded local LLM (Ollama) with a deterministic
   fallback.
8. Presenting nearby medical/emergency facilities **as context only, never as a score
   input**.

The defining engineering property — stated identically in `master_rules.md` Rule 9,
`README.md`, and enforced in code — is **evidence honesty**: absent, stale, insufficient or
unavailable evidence is reported as *unassessed*, never as a safe road.

## 3. Headline verdict

**The system is a genuinely working, end-to-end, honest implementation — not a mock-up.**

| Dimension | Assessment | Basis |
|---|---|---|
| Core pipeline implemented | **Yes** | `src/api/pipeline.py` orchestrates routing → imagery → preprocessing → detection → aggregation → risk → comparison → explanation. |
| Risk scoring is deterministic & backend-owned | **Yes** | `src/risk/engine.py` `DeterministicRiskEngine`; LLM is strictly downstream in `src/llm/explainer.py`. |
| Facilities separated from the score | **Yes** | `config/facilities.yaml` `guardrails.facilities_in_hazard_score: false`; `src/facilities/schemas.py` contains no score field. |
| Provider honesty (no synthetic routes presented as real) | **Yes** | `config/routing.yaml` `guardrails.enforce_rule_10: true`; mock routes carry `is_demo`/limitations. |
| Automated test coverage | **Substantial** | 299 test methods; `unittest discover -s tests` → **Ran 299 tests … OK** (measured during Phase 2). |
| Deployment maturity | **Low** | No CI/CD, no container for the core repo, no migrations, no auth on the API. |
| Model accuracy | **Weak** | Repo-reported mAP50 ≈ 0.26–0.27 for the v1 baseline (not independently reproduced — see §6). |
| Documentation currency | **Poor** | `docs/TRD.md` and `docs/ARCHITECTURE.md` still state that no code, model, dataset or environment exists. |
| Frontend production readiness | **Partial** | Builds and passes 58 checks, but TS `strict` is off, no test framework, and the shipped `frontend/assets/` bundle is stale. |

The engineering is materially ahead of the specification. The specification is materially
behind the engineering. That divergence is the single largest documentation risk in the
project (Finding **F-01**).

## 4. Architecture in one paragraph

A stdlib `http.server` API (`src/api/app.py`, `ThreadingHTTPServer`) exposes 10 endpoints
and statically serves the React SPA from the same origin. `src/api/bootstrap.py` is the
**only** place live providers are wired: OSRM routing, Mapillary imagery, Overpass
facilities, Nominatim geocoding and Ollama explanations, each selected by
`config/app.yaml` and `src/config/settings.py`, each degrading to an explicit
offline/mock path. `src/api/pipeline.py` orchestrates the analysis; `src/api/store.py`
persists analyses, scores, detections and model versions into SQLite
(`data/saferoute.db`) with `model_version` and `config_hash` recorded for auditability.
The frontend is a Vite + React 19 + MapLibre SPA that calls the backend through a single
module, `src/lib/api.ts`. There is **no** second scoring implementation: the backend is
the only authority for safety numbers.

## 5. Top findings

Full detail is in [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md).
The highest-impact items:

### Confirmed defects (verified in code or by measurement)

| ID | Finding | Evidence |
|---|---|---|
| **F-01** | `docs/TRD.md` and `docs/ARCHITECTURE.md` assert "no dataset, no model weights, no source code, no environment exists". All of it now exists. Anyone reading the spec is misinformed about the current system. | `docs/TRD.md` L27–28, `docs/ARCHITECTURE.md` L21–24 vs. `src/`, `models/`, `data/`, `.venv/` |
| **F-02** | `docs/ARCHITECTURE.md` §12 deployment table says "Not created / Not installed" for every row; the frontend §3 describes FastAPI while the backend is stdlib `http.server`. | `docs/ARCHITECTURE.md` L470–484, `src/api/app.py` L1–22 |
| **F-03** | `logs/evaluation/evaluation_record.json` is internally inconsistent: the rationale prose quotes mAP 0.278 / 0.231 while the machine-readable fields say mAP50 0.2731 / 0.2615. | `logs/evaluation/evaluation_record.json` |
| **F-04** | `logs/training/saferoute-yolo11-datayolo-exp/run_record.json` records `status: "ERROR"` (DataLoader worker crash) while `train.log` and `results.csv` in the same folder show a later, successful 68-epoch run with a `best.pt`. The provenance record under-reports the outcome. | `logs/training/saferoute-yolo11-datayolo-exp/` |
| **F-05** | `scripts/prepare_rdd2022_yolo.py` has a docstring and an `argparse` import describing a CLI, but no argument parsing or entry point is implemented. | `scripts/prepare_rdd2022_yolo.py` (123 lines) |
| **F-06** | The serving bundle in the outer repo (`frontend/assets/`) predates the current frontend source; the nested repo's own build output has different content hashes. The deployed UI is not the audited UI. | `frontend/index.html` vs `frontend/Frontend/project frontend/dist/assets/` |
| **F-07** | `frontend/.../src/utils/safety.ts` (317 lines, `analyzeRoutes`) is not imported anywhere and contains an independent route-scoring implementation, contradicting the "backend is the only score authority" rule. Dead code that could be mistaken for an active path. | import scan of `frontend/.../src/` |
| **F-08** | `logs/training/.../saferoute-yolo11-datayolo-exp` and the DATA-YOLO preparation pipeline are blocked by an unresolved licence question: no LICENSE / COPYING / NOTICE / TERMS file exists anywhere for `DATA-YOLO/`. `DATA-YOLO/Pushkar Singh Baghel.pdf` is a personal résumé, not a licence. | `DATA-YOLO/` tree |
| **F-09** | The DATA-YOLO licence gap is already recorded as an open item in the project's own report and remains unresolved after the phase that raised it. | `docs/reports/DATA_YOLO_TRAINING_PREP.md` L139 |
| **F-10** | `config/facilities.yaml` `default_provider` is `"mock"` while `config/app.yaml` selects `"overpass"`. The two files disagree about the default; the YAML default only applies when no override is supplied. | both config files |

### Risks (real but not currently breaking)

| ID | Risk | Note |
|---|---|---|
| **F-11** | **No CI/CD.** No `.github/`, no Dockerfile, no compose, no Makefile, no `tox`/`nox`, no `pre-commit` for the core repository. Every check is manual. | tree scan |
| **F-12** | **No API authentication or rate limiting.** `Access-Control-Allow-Origin: *` on every response; `ThreadingHTTPServer` accepts concurrent connections. Acceptable for a local demo, not for a shared deployment. | `src/api/app.py` L259–265 |
| **F-13** | **Detection accuracy is weak.** Repo-reported mAP50 0.2731 (val) / 0.2615 (test) for v1; the detector is close to the noise floor. This is the honest state, but it caps the usefulness of the hazard evidence the product is built to present. | `logs/evaluation/evaluation_record.json` |
| **F-14** | **DATA-YOLO contains 49 intra-split duplicate image groups** (33 in train / 71 files, 7 in val / 14 files, 9 in test / 18 files). Cross-split overlap is **0**, so there is no test-set leakage, but the duplicates inflate the effective training-set size. | SHA-256 duplicate scan |
| **F-15** | **The `datayolo_prep` `test:` split is not an independent holdout.** It is a same-source, scene-grouped list. The `MANIFEST.json` itself says so. Conclusions drawn from it are weaker than an independent holdout would give. | `data/datayolo_prep/MANIFEST.json` |
| **F-16** | **TypeScript `strict` is disabled** in `tsconfig.app.json`, and there is no ESLint/Prettier configuration in the frontend package. | `frontend/.../tsconfig.app.json`, `package.json` |
| **F-17** | **Frontend accessibility gaps**: no `prefers-reduced-motion` handling and no `aria-live` region for async status, despite animations throughout. | `frontend/.../src/` |
| **F-18** | **The shipped frontend bundle in the outer repo was deliberately not rebuilt** during Phase 2, so the UI served by the backend is older than the source. | `frontend/assets/` vs nested `dist/` |
| **F-19** | `public/video/video.mp4` is **105 MB** inside the frontend public directory. | `frontend/.../public/video/video.mp4` |
| **F-20** | Live Mapillary frames currently return `captured_at = None`, so freshness cannot be verified and analyses resolve to `recommendation: null` / `cannot_determine`. This is correct Rule-9 behaviour, but it means the live product currently cannot issue a recommendation. | live `POST /api/analyze` |
| **F-37** | v1 and v2 were trained and evaluated on a **silently reduced** image set: Ultralytics discards any image whose label contains class ≥ `nc`, so only 861 of 1 406 train, 264 of 402 val and 125 of 201 test images were actually used. The defect was diagnosed and fixed (a corrected derived dataset exists), but the published metrics still carry it. | `config/training_canonical.yaml` |

### Documentation-only, deliberate, non-blocking

- `src/services/routing.ts` (`fetchRoadRoutes`, 171 lines) — dead after the backend became
  the single source of truth.
- `src/components/Header/**` (8 files), `src/components/common/Stairs.tsx`,
  `src/components/ui/animated-search-1.tsx` (416 lines, the only `clsx` consumer) —
  unreferenced UI.
- `src/assets/indroute-logo.svg` — unreferenced asset.
- `public/assets/maplibre-gl-*.mjs` — dead worker copies.
- 5 `console.log` calls per facility request in `FacilityLayer.tsx`.

## 6. Evidence status of every headline number

Nothing in this audit set is presented as measured unless it was measured. The project's
model metrics were **not** re-measured during this audit — they are quoted as
*repo-reported* and clearly labelled.

| Quantity | Value | Status |
|---|---|---|
| Backend tests | `Ran 299 tests … OK` | **Measured** (re-run during this audit, 19.4 s) |
| Frontend checks | 58 checks, 0 failures | **Measured** (re-run during this audit) |
| Frontend build | clean | **Measured** (Phase 2 run) |
| Frontend lint | 0 errors (1 177 warnings, 1 163 of them in vendored `public/assets/maplibre-gl-*.mjs`) | **Measured** (re-run during this audit) |
| Backend lines / modules | 8 590 / 50 | **Measured** (this audit) |
| Test lines / methods | 5 848 / 299 | **Measured** (this audit) |
| Installed Python packages | 40 pinned, all matching `requirements-lock.txt` | **Measured** (this audit) |
| v1 model mAP50 | 0.2731 val / 0.2615 test | **Repo-reported**, not independently reproduced |
| v2 model promotion | 601-image unseen micro F1 0.297 → 0.327 @ conf 0.25 | **Repo-reported** (`config/detection.yaml` comment) |
| Inference latency | 4.02 ms/image | **Repo-reported** |
| Overpass live lookup | `status: provider_error` | **Measured** (this machine: all public mirrors unreachable) |

## 7. What this audit did **not** do

- It did not re-train, re-evaluate, or re-benchmark any model.
- It did not run the live Overpass facility lookup successfully — see
  [`07-api-database-and-integrations.md`](07-api-database-and-integrations.md) §7.
- It did not modify, reformat or "fix" any of the findings above. Every finding is a
  report, not a patch.
- It did not delete dead code, rebuild the frontend bundle, or close the DATA-YOLO
  licence question. Those are decisions requiring approval (Rule 19).

## 8. Recommended next actions

Ordered by value per unit of effort. Full rationale in
[`14-findings-and-recommendations.md`](14-findings-and-recommendations.md).

1. **Refresh the specification set** (F-01, F-02). Rewrite the "current verified state"
   paragraphs of `docs/TRD.md` and `docs/ARCHITECTURE.md`, and reconcile the FastAPI/MySQL
   design with the stdlib-SQLite reality. *Effort: S. Unblocks: every reader of the spec.*
2. **Rebuild and ship the frontend bundle** (F-06, F-18) or formally retire the outer
   `frontend/assets/` copy. *Effort: S. Unblocks: the audited UI becomes the delivered UI.*
3. **Resolve the DATA-YOLO licence** (F-08, F-09) by obtaining a licence statement from
   the source, or by excluding the dataset from any distributable artefact and documenting
   that exclusion. *Effort: M, external dependency.*
4. **Repair the two stale provenance records** (F-03, F-04) so the audit trail matches the
   artefacts. *Effort: S. Unblocks: defensible metric claims.*
5. **Add a minimal CI gate** (F-11): one workflow that installs from
   `requirements-lock.txt` and runs `python -m unittest discover -s tests`. *Effort: S.
   Unblocks: every other fix staying fixed.*
6. **Measure the model honestly on an independent holdout** and record it (F-13, F-14,
   F-15, F-37). Re-evaluate the **serving** v2 checkpoint on the date-atomic
   `data/splits_v2` test split, and publish the *actual* number of images used — the
   v1/v2 runs silently used only 861/1 406 train, 264/402 val and 125/201 test images.
   *Effort: M. Unblocks: any performance claim.*
7. **Remove or clearly quarantine the dead scoring code** (F-07) so that no reader can
   mistake `src/utils/safety.ts` for the scoring authority. *Effort: S.*
8. **Enable TypeScript `strict`** and fix the resulting errors (F-16). *Effort: M.*
9. **Add API authentication and a request-size limit** before any non-local deployment
   (F-12). *Effort: M.*
10. **Delete the 105 MB video from `public/`** and evaluate replacing `console.log` calls
    with the logger (F-19). *Effort: S.*

## 9. Document index

| # | Document | Contents |
|---|---|---|
| 00 | `00-executive-summary.md` | This document. |
| 01 | [`01-repository-map.md`](01-repository-map.md) | Directory tree, file inventory, two-repository structure. |
| 02 | [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md) | Component architecture and data flow, with Mermaid diagrams. |
| 03 | [`03-technology-stack-and-libraries.md`](03-technology-stack-and-libraries.md) | Full library inventory: declared vs. installed versions. |
| 04 | [`04-dataset-and-labeling.md`](04-dataset-and-labeling.md) | Dataset provenance, class balance, splits, leakage, licence status. |
| 05 | [`05-preprocessing-and-feature-engineering.md`](05-preprocessing-and-feature-engineering.md) | OpenCV pipeline, severity policy, risk features. |
| 06 | [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) | Model lineage, training configuration, reported metrics. |
| 07 | [`07-api-database-and-integrations.md`](07-api-database-and-integrations.md) | Endpoints, SQLite schema, external provider integrations. |
| 08 | [`08-security-and-reliability.md`](08-security-and-reliability.md) | Secrets, input validation, resilience, failure honesty. |
| 09 | [`09-setup-testing-and-deployment.md`](09-setup-testing-and-deployment.md) | Setup, test commands, CI/CD status, deployment. |
| 10 | [`10-code-walkthrough.md`](10-code-walkthrough.md) | Guided tour of the codebase by responsibility. |
| 11 | [`11-presentation-and-viva.md`](11-presentation-and-viva.md) | Presentation and viva preparation material. |
| 12 | [`12-team-contribution-template.md`](12-team-contribution-template.md) | Per-member contribution record template. |
| 13 | [`13-glossary.md`](13-glossary.md) | Project terminology. |
| 14 | [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md) | All findings, severity, evidence, recommended actions. |
| 15 | [`15-traceability-matrix.md`](15-traceability-matrix.md) | Requirement → rule → code → test → doc mapping. |
| 16 | [`16-final-audit-report.md`](16-final-audit-report.md) | The consolidated single-file deliverable: architecture, stack, all 37 findings, 16 confirmations, evidence status, validation, action plan. |

---

*Audit performed read-only against `master_rules.md` Rules 1, 2, 3, 13, 14, 17, 18, 19 and
20. Unknowns are marked `Unknown`, `Not found` or `Not verified` rather than estimated.*
