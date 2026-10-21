# 14 — Findings and Recommendations

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Audit type:** read-only. **No finding in this document has been fixed.** Each entry is a
> report; applying any of them requires approval (Rule 19).
> **Related:** [`00-executive-summary.md`](00-executive-summary.md) ·
> [`15-traceability-matrix.md`](15-traceability-matrix.md)

---

## 1. Severity scale

| Level | Meaning |
|---|---|
| **Critical** | Blocks or invalidates the project's central claims; must be resolved before any external submission or deployment. |
| **High** | Materially misleads a reader, a reviewer or a user; or removes a safety/reliability guarantee. |
| **Medium** | A real gap that degrades quality, maintainability or reproducibility. |
| **Low** | Housekeeping; worth fixing when convenient. |
| **Info** | An observation with no defect, recorded for completeness. |

**Effort scale:** S = under an hour · M = under a day · L = multi-day.

---

## 2. Confirmed defects

### F-01 — The specification documents state that the project does not exist

| | |
|---|---|
| **Severity** | **High** |
| **Effort** | S–M |
| **Rules** | 2, 17 |
| **Evidence** | `docs/TRD.md` L27–28: *"the workspace contains only `master_rules.md` and `docs\PRD.md`. There is **no** dataset, model weights, virtual environment, source code, backend, frontend, database or integration of any kind."* `docs/ARCHITECTURE.md` L21–24: *"**no** source code, environment, dataset, model weights, backend, frontend, database, imagery or integration. **Every component described below is proposed architecture, not an implemented system.**"* |
| **Reality** | 50 backend modules (8 590 lines), 89 frontend files, 299 test methods, a complete trained checkpoint, 1 789 + 1 792 labelled images, 14 config files, a populated SQLite database and six live provider integrations. |
| **Impact** | Anyone reading the TRD or ARCHITECTURE document — a reviewer, a new contributor, an examiner — is told the project is unimplemented. The documents also still describe several components as *proposed* that are in fact implemented and working. This is the single largest source of misunderstanding in the project. |
| **Recommendation** | Rewrite the "current verified state" paragraphs in both documents to describe the implemented system. Add a status marker to each section: `implemented` / `proposed` / `superseded`. Keep the original proposals visible as history rather than deleting them. |
| **Do not** | Do not silently edit the documents to hide what was planned. The divergence between plan and implementation is itself a useful record (Rule 17). |

### F-02 — The architecture specification describes a different backend and database

| | |
|---|---|
| **Severity** | **High** |
| **Effort** | M |
| **Rules** | 2, 17 |
| **Evidence** | `docs/TRD.md` §2 specifies **FastAPI** and **MySQL**. `docs/ARCHITECTURE.md` §3 and §10 specify FastAPI and MySQL, with a full MySQL entity diagram in §10 including `users`, `routes`, `route_segments`, `imagery_refs` and `analysis_history`. |
| **Reality** | `src/api/app.py` implements the API with the standard library `http.server` + `ThreadingHTTPServer` (its own docstring explains: *"Implements the TRD §11 endpoints without third-party web frameworks (FastAPI is not installed and installing it is gated by Rule 19)"*). `src/api/store.py` implements persistence with stdlib `sqlite3` — 5 tables, no `users` table, route/segment/imagery detail stored inside `analyses.result_json`. |
| **Impact** | The specified architecture was a legitimate choice under Rule 19, but it was never updated after the decision. A reader planning to deploy or extend the system would plan against MySQL and FastAPI and find neither. |
| **Recommendation** | Rewrite `docs/ARCHITECTURE.md` §3, §10 and §12 to describe the actual implementation, and add a short "design decisions that changed" section recording why FastAPI/MySQL were not used. |

### F-03 — The evaluation record contradicts itself

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | S |
| **Rules** | 14, 17 |
| **Evidence** | `logs/evaluation/evaluation_record.json`: the structured fields record mAP50 **0.2731** (val) and **0.2615** (test). The `rationale` prose in the same file quotes mAP **0.278** and **0.231**. |
| **Impact** | The two sets of numbers are for the same quantities and they disagree. Any citation of this file is ambiguous, and the file is the project's primary metric record. |
| **Recommendation** | Determine which set is correct by re-deriving it from `results.csv` and the evaluation script, then correct the other. Until then, quote only the structured fields and disclose the discrepancy. |

### F-04 — The datayolo-exp provenance record under-reports a successful run

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | S |
| **Rules** | 14, 17 |
| **Evidence** | `logs/training/saferoute-yolo11-datayolo-exp/run_record.json` records `status: "ERROR"` with a DataLoader worker crash at `workers=2`. In the same directory, `train.log` and `results.csv` show a later, successful **68-epoch** run, and `best.pt` exists (SHA-256 `730CE43974AF67BB228704C981D55D0FF8879FC42A4C75DF646ABE289FD590BB`). |
| **Impact** | The audit trail says the run failed when it in fact completed. Anyone reading the record concludes a checkpoint does not exist that does exist. |
| **Recommendation** | Regenerate `run_record.json` from `results.csv` and `train.log`, preserving the original error entry as a separate `prior_attempts` record rather than overwriting it. |

### F-05 — `scripts/prepare_rdd2022_yolo.py` has no CLI

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | M |
| **Rules** | 14, 17 |
| **Evidence** | The 123-line script has a docstring describing command-line usage and imports `argparse`, but implements no argument parsing and no entry point. |
| **Impact** | Running it as documented does nothing useful. It reads as complete work that is not. |
| **Recommendation** | Implement the CLI, or remove the `argparse` import and rewrite the docstring to state that the module must be called programmatically. |

### F-06 — The shipped frontend bundle is not the audited frontend

| | |
|---|---|
| **Severity** | **High** |
| **Effort** | S |
| **Rules** | 17, 20 |
| **Evidence** | The outer bundle is `frontend/assets/index-ChLfkaQi.js` + `index-sD57dfm8.css`. The frontend repository's own build output is `dist/assets/index-BCNmOTIq.js` + `index-Bl68t2ww.css`. Different content hashes ⇒ different builds. |
| **Impact** | The UI that the backend serves at `http://127.0.0.1:8000/` is older than the source that was audited and tested. A demonstration run against the backend serves the stale bundle; a demonstration against `vite preview` serves the current one. Presenting the former while claiming the latter's behaviour would be inaccurate. |
| **Recommendation** | Rebuild and commit the outer bundle as a dedicated change, or retire the outer copy and document that the API serves the frontend repository's `dist/` directly. Whichever is chosen, state in the README which bundle is authoritative. |

### F-07 — Dead frontend code contains a second, contradicting scoring implementation

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | S |
| **Rules** | 7, 17, 18 |
| **Evidence** | `frontend/.../src/utils/safety.ts` (317 lines) exports `analyzeRoutes`, which computes route safety scores in the browser. An import scan of all of `src/` shows **no importer**. |
| **Impact** | It contradicts the project's central architectural claim — that the backend is the only score authority — in a file that still contains a plausible implementation. A reviewer who opens it may reasonably conclude the project has two scoring systems. It also contradicts the audit's own note that "frontend contains no score computation on any live path". |
| **Recommendation** | Delete it. The Phase 2 decision was already made for `src/services/routing.ts` and for the browser-side Overpass client; this is the same class of cleanup. If it is kept deliberately for reference, move it out of `src/` into `docs/` or a `reference/` directory and add a header stating it is not used. |

### F-08 — The training dataset has no licence

| | |
|---|---|
| **Severity** | **Critical** |
| **Effort** | M + external dependency |
| **Rules** | 1, 15, 17 |
| **Evidence** | A search of the whole workspace found **no** LICENSE, COPYING, NOTICE or TERMS file for `DATA-YOLO/`. `DATA-YOLO/Road_crack/README.md` is **0 bytes**. `DATA-YOLO/Pushkar Singh Baghel.pdf` is a personal résumé, not a licence grant. |
| **Impact** | Three concrete consequences. (1) The trained weights may not be distributable. (2) Any claim that the model is legally usable is unsupported. (3) Any submission containing the dataset or derived artefacts inherits the risk. |
| **Recommendation** | Pursue, in order: (a) obtain a written licence statement from the publisher and record it in `DATA-YOLO/LICENSE` with a citation; (b) if unobtainable, exclude the dataset and every weight trained on it from all distributable artefacts and document the exclusion; (c) retrain on a corpus with a clear licence — `data/pothole_crack_manhole/data/` already carries Zenodo DOI `10.5281/zenodo.17834373` and is the natural candidate. Option (c) also addresses F-13. |

### F-09 — The licence gap was raised once and never closed

| | |
|---|---|
| **Severity** | **Medium** (process) |
| **Effort** | S |
| **Rules** | 3, 17, 19 |
| **Evidence** | `docs/reports/DATA_YOLO_TRAINING_PREP.md` L139 records the same open item. It is still open after that phase. |
| **Impact** | A known blocker was logged and then not tracked. The same pattern is why F-03 and F-04 survived: issues were recorded but never re-checked. |
| **Recommendation** | Establish a single live "open items" register with an owner and a review date, and re-check it at the start of every phase. |

### F-10 — Two configuration files disagree about the default facilities provider

| | |
|---|---|
| **Severity** | **Low** |
| **Effort** | S |
| **Rules** | 17 |
| **Evidence** | `config/facilities.yaml` → `metadata.default_provider: "mock"`. `config/app.yaml` → `app.facilities_provider: "overpass"`. |
| **Impact** | The `app.yaml` value wins at runtime, so there is no live defect — but the YAML default contradicts it. A reader consulting `config/facilities.yaml` alone would conclude facilities are served from offline fixtures. |
| **Recommendation** | Make the two agree explicitly, and add a comment in `facilities.yaml` explaining that `default_provider` applies only when `app.yaml` supplies no override. |

---

## 3. Risks

### F-11 — No CI/CD in the core repository

| | |
|---|---|
| **Severity** | **High** |
| **Effort** | S |
| **Rules** | 14, 17 |
| **Evidence** | No `.github/`, `.gitlab-ci.yml`, `Dockerfile` (core repo), `docker-compose.yml` (core repo), `Makefile`, `tox.ini`, `noxfile.py`, `pyproject.toml`, `setup.py`, `.pre-commit-config.yaml` or `CODEOWNERS`. A `docker-compose.yml` and `backend/Dockerfile` exist only in the unrelated sub-project `frontend/Frontend/project frontend/SafeRouteAI/`. |
| **Impact** | Every check in §4 of [`09-setup-testing-and-deployment.md`](09-setup-testing-and-deployment.md) is manual. Nothing prevents a regression from being committed, and the audit trail of "the tests passed" depends on someone remembering to run them. |
| **Recommendation** | Add one workflow: install from `requirements-lock.txt`, run `python -m unittest discover -s tests`; and one for the frontend: `npm ci`, `npm run lint`, `npm run build`, `npm run test:frontend`. A proposed configuration is given in [`09-setup-testing-and-deployment.md`](09-setup-testing-and-deployment.md) §5.1 — **not created by this audit**. Resolve F-29 first, since the frontend lives in a separate repository. |

### F-12 — No authentication, rate limiting or request-size limit; permissive CORS

| | |
|---|---|
| **Severity** | **High for any non-local deployment** |
| **Effort** | M |
| **Rules** | 13; TRD §15 |
| **Evidence** | `src/api/app.py` sends `Access-Control-Allow-Origin: *` on every response. There is no authentication anywhere in the codebase, no per-client rate limit, no `Content-Length` ceiling (the body is read in full), no coordinate-range check and no string-length bound. The one existing body-size protection is the `isinstance(include_road_access, bool)` check. |
| **Impact** | The system is **loopback-only** today, so nothing is currently exposed. Changing the bind address to `0.0.0.0` — the obvious first step of any deployment — would expose an unauthenticated endpoint that can trigger OSRM, Mapillary, Overpass, Nominatim and a local LLM on demand. That is an abuse and cost vector, and it would breach the public providers' usage policies. |
| **Recommendation** | Before any non-local deployment: add a shared-secret or token header check, a per-client request budget, a `Content-Length` ceiling, coordinate-range validation, string-length bounds, and replace `Access-Control-Allow-Origin: *` with an explicit origin list. Also stop echoing the raw exception message in the 500 envelope (F-23). |

### F-13 — Detection accuracy is weak

| | |
|---|---|
| **Severity** | **High** (functional), mitigated in design |
| **Effort** | L |
| **Rules** | 14, 20 |
| **Evidence** | Repo-reported, from `logs/evaluation/evaluation_record.json` for the v1 checkpoint: mAP50 0.2731 (val) / 0.2615 (test); recall 0.3110 (val) / 0.3009 (test); mAP50–95 0.1007 / 0.0952. Not independently reproduced. |
| **Impact** | Recall near 0.31 means most true hazards are missed. A low hazard count on a segment is therefore weak evidence, not strong evidence. The project's design already compensates — coverage is published with every score and the comparison layer refuses to recommend on insufficient evidence — but the underlying evidence remains thin. |
| **Recommendation** | (1) Re-evaluate the **serving** v2 checkpoint on the **date-atomic** `data/splits_v2` test split (216 images, capture date 2025-02-26) and publish one unambiguous figure. (2) Retrain on the licensed corpus (see F-08 option c), de-duplicated (F-14). (3) Present the number honestly in every demonstration — it is a real limitation and Rule 20 requires it to be disclosed. |

### F-14 — Intra-split duplicate images inflate the effective training set

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | M |
| **Rules** | 15 |
| **Evidence** | SHA-256 scan of `data/datayolo_prep`: 33 duplicate groups in `train` (71 files), 7 in `val` (14 files), 9 in `test` (18 files) - **49 groups** overall. Cross-split overlap is **0**. `data/derived_2class`: 5 duplicate groups overall, 0 within a split, 0 across splits. |
| **Impact** | The nominal training set overstates the information it contains. It also means the validation metric is computed over partly repeated data. There is no test-set leakage, which is the more serious failure mode, and it is absent. |
| **Recommendation** | De-duplicate before the next training run and record the before/after counts in the run record. The `scripts/audit/` tooling already computes these numbers, so this is a configuration change to the preparation pipeline rather than new tooling. |

### F-15 — The published evaluation used a non-independent holdout

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | M |
| **Rules** | 14, 15 |
| **Evidence** | `data/datayolo_prep/dataset.yaml` declares a `test:` key, but the dataset YAML and `MANIFEST.json` both describe it as a same-source, scene-grouped list — not an independent benchmark. The `MANIFEST.json` also records an original-split leakage diagnostic (148 of 332 validation images leaking into train), which is why the pipeline re-groups by scene. |
| **Impact** | Accuracy conclusions drawn from that split are weaker than the wording "test set" implies. The newer `data/splits_v2` corpus is split by capture date, which is structurally sound and should be preferred. |
| **Recommendation** | Make `data/splits_v2` the evaluation basis for all published numbers, and state the split basis explicitly wherever a metric is quoted. |

### F-16 — TypeScript `strict` mode is disabled

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | M |
| **Rules** | 6, 17 |
| **Evidence** | `tsconfig.app.json` does not set `strict`. The frontend also has no ESLint and no Prettier configuration — `oxlint` is used instead. |
| **Impact** | A class of type errors that `strict` would reject (implicit `any`, possibly-undefined access, nullable misuse) is not reported. The API payload types live in `src/lib/analyzeTypes.ts`; `null`-ability in those payloads is exactly the kind of thing this system must get right. |
| **Recommendation** | Enable `strict` incrementally — one module at a time, starting with `src/lib/` and `src/hooks/` — and fix the errors as they surface. Do not enable it globally in one step. |

### F-17 — Accessibility gaps

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | M |
| **Rules** | 14 (TRD §14: explicit error and loading states) |
| **Evidence** | ARIA attributes are present throughout the frontend, but there is **no** `prefers-reduced-motion` handling despite GSAP, Framer Motion, Three.js and Lottie animations, and **no** `aria-live` region for the asynchronous analysis status. There is no skip-to-content link. |
| **Impact** | Users with vestibular disorders get unrequested motion, and screen-reader users are not notified when a long analysis completes or fails. For a safety product, an unreadable failure state is a real problem. |
| **Recommendation** | Add a global `@media (prefers-reduced-motion: reduce)` rule that disables the animation layers; add an `aria-live="polite"` status region for the analysis state; add a skip link. |

### F-18 — The frontend bundle was deliberately not rebuilt during Phase 2

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | S |
| **Rules** | 18 |
| **Evidence** | The Phase 2 report (`docs/reports/PHASE_29_HOSPITAL_ACCESSIBILITY.md`) records the decision to leave the outer `frontend/assets/` bundle unbuilt so the diff stayed reviewable. |
| **Impact** | This is a *deliberate, documented* decision with a real cost: the served UI predates the Phase 2 frontend changes, so the facilities consolidation is not visible in the served bundle. It is recorded here so that the gap is not mistaken for an oversight. |
| **Recommendation** | Keep the decision, but treat the bundle rebuild as the next approved change (see F-06), and state clearly in the Phase 2 report that the deployed bundle lags the source. |

### F-19 — A 105 MB video inside the frontend public directory

| | |
|---|---|
| **Severity** | **Low** |
| **Effort** | S |
| **Rules** | 18 |
| **Evidence** | `frontend/Frontend/project frontend/public/video/video.mp4` is **105 MB**. |
| **Impact** | It is copied verbatim into every build output and is served to any browser that requests it. It dominates the bundle size and slows any deployment of the frontend. |
| **Recommendation** | Move it out of `public/` and serve it from a CDN or a compressed derivative, or remove it if it is unused. |

### F-20 — Live analyses cannot currently reach a recommendation

| | |
|---|---|
| **Severity** | **Medium** (functional; the behaviour is correct) |
| **Effort** | M |
| **Rules** | 9, 20 |
| **Evidence** | Live Mapillary frames return `captured_at = None`, so `StalenessEvaluator` treats them as stale, the assessed-length fraction stays below the recommendation threshold, and the comparison layer returns `recommendation: null` with status `cannot_determine`. |
| **Impact** | The code is behaving **exactly as designed** — this is Rule 9 working. But the practical consequence is that the live product cannot currently name a safest route, which limits the demonstration. |
| **Recommendation** | Investigate why the Mapillary Graph API response yields no capture timestamp (field name, query parameters, or the provider's response schema). If the timestamps genuinely are unavailable from the provider, consider whether freshness can be established by another permitted means, or narrow the demo to routes where imagery metadata *is* present. Do **not** work around this by relaxing the staleness policy. |

### F-37 — v1 and v2 were trained and evaluated on a silently reduced image set

| | |
|---|---|
| **Severity** | **Medium** |
| **Effort** | M |
| **Rules** | 14, 15, 17 |
| **Evidence** | `config/training_canonical.yaml` records: the original `data/dataset.yaml` declares `nc=2`, but the source labels contain class-2 (manhole) rows in **759 of 2 009** images. Ultralytics treats any label with `class >= nc` as corrupt and **discards the whole image**, so v1 and v2 were silently trained on only **861 of 1 406** images and evaluated on **264 of 402** (val) and **125 of 201** (test). |
| **Impact** | The failure mode was silent — Ultralytics drops the offending image and continues, so nothing in the training log signals a problem. The effective evaluation set was roughly two thirds of the nominal one, and the v1 metrics in `logs/evaluation/evaluation_record.json` were measured on that reduced set. Quoting those metrics without this qualification overstates the evidence. |
| **Recommendation** | (1) Publish the v1 metrics with the actual evaluated image counts attached. (2) Re-evaluate the **serving** v2 checkpoint on the clean, date-atomic `data/splits_v2` test split (216 images, capture date 2025-02-26) — this closes F-13, F-15, F-37 and part of F-03 in one measurement. (3) Add a corpus check to the training scripts that fails loudly when the number of images actually loaded differs from the split size, so this class of silent reduction cannot recur. |
| **Credit where due** | The project diagnosed the mechanism, documented it in a config file, and built a corrected dataset (`data/derived_2class`) in which the manhole box is removed **in the derived labels only** — the original annotation is preserved, so nothing is silently relabelled (Rule 15). This is the right response, and it is recorded as a positive confirmation (P-16). |

---

## 4. Minor findings and observations

| ID | Finding | Severity | Evidence | Recommendation |
|---|---|---|---|---|
| F-21 | No `LICENSE` file for the SafeRoute AI source code itself | Low | Not found anywhere in the workspace | Add one; the licence of the project's own code is currently unspecified |
| F-22 | Silent LLM fallback is not counted or logged | Low | `src/llm/explainer.py` returns `source: "fallback"` but nothing counts it | Log fallback usage. The Phase 28 incident — every live request silently falling back — would have been caught immediately by one counter |
| F-23 | The 500-response `detail` field echoes the raw exception message | Low | `src/api/app.py`: `_error("internal_error", "Unhandled server error.", f"{type(e).__name__}: {e}")` | Log it server-side; omit it from the response body for non-local deployments |
| F-24 | Malformed numeric request fields are silently coerced to defaults | Low | `SafeRouteAPI._optional_float` returns `None` on a bad value, which becomes the default | Reject with a 400 instead of defaulting. A silently-defaulted radius or coordinate produces a plausible-but-wrong answer |
| F-25 | The OSRM response cache has no lock | Low | `src/routing/osrm_adapter.py` — plain dict mutated from multiple request threads | Add a lock, or move to a thread-safe structure. Low practical impact under CPython's GIL, but the expiry logic can race |
| F-26 | No database migration mechanism | Medium | `AnalysisStore._init_schema()` uses `CREATE TABLE IF NOT EXISTS` only; the schema is never altered | Add a `schema_version` table and a migration function. Currently, adding a column to an existing `data/saferoute.db` will not happen automatically |
| F-27 | No indexes declared on the SQLite schema | Low | `src/api/store.py::_SCHEMA` | Index `analyses(search_id)`, `scores(analysis_id)`, `hazard_detections(analysis_id)` — the read paths are all by `analysis_id` |
| F-28 | The API server writes no structured logs to `logs/` | Medium | `http.server`'s `log_message` is overridden to a no-op | Emit structured, secret-free JSON lines to `logs/`. TRD §3.4 requires structured logs with timestamps and component; the API does not currently produce any |
| F-29 | The nested frontend repository breaks single-clone and single-PR workflows | Medium | The outer `.gitignore` excludes `frontend/Frontend/` | Decide explicitly: vendor the frontend into the core repository, or maintain it as a published package with a documented sync procedure. This blocks a clean CI setup (F-11) |
| F-30 | `vercel.json` is a misleading leftover scaffold | Low | Present in the frontend package; declares framework `vite` and `outputDirectory: dist` | It does not deploy this system — the backend, SQLite, the local LLM and the Mapillary token have no place in a static-hosting deployment. Remove it or add a comment stating it is unused |
| F-31 | Coordinate-range and string-length validation is missing | Medium | No check on latitude beyond ±90 or longitude beyond ±180; no length bound on origin/destination | TRD §15 explicitly requires "types, ranges, string bounds". Add them at the API boundary |
| F-32 | `weights/yolo26n.pt` has no training record | Low | The file exists (5 544 453 B); no `args.yaml`, `results.csv` or run record anywhere | Either train from it and record the run, or remove it. An unexplained 5.5 MB weight file in the repository invites questions |
| F-33 | Dead frontend assets and stray logging | Low | `public/assets/maplibre-gl-*.mjs`; `src/assets/indroute-logo.svg`; 5 `console.log` calls per facility request in `FacilityLayer.tsx` | Delete the dead assets; replace `console.log` with a logger that honours the "no secrets in logs" rule |
| F-34 | Phase report numbering has gaps | Info | No `PHASE_21`, `PHASE_26`, `PHASE_27` or `PHASE_30` report exists, though those identifiers appear in commit messages and in-code comments | Either add short bridging notes or add an index mapping phase identifiers to reports. Not a defect — a navigation aid |
| F-35 | The backend has no Python linter, formatter or type checker | Low | No ruff/flake8/black/mypy configuration; `requirements-dev.txt` is header-only by design (Rule 18) | Add `ruff` to `requirements-dev.txt` when a phase genuinely needs it. Deliberate under Rule 18, but the backend is now 8 590 lines |
| F-36 | No test-coverage measurement exists | Low | `coverage` is not installed; no coverage percentage is recorded anywhere | If coverage matters for the submission, add `coverage` to `requirements-dev.txt` and run it once. Do not add it "just in case" (Rule 18) |

---

## 5. Prioritised action plan

### Tier 1 — do first (low effort, high value)

| # | Action | Findings | Effort |
|---:|---|---|---|
| 1 | Refresh `docs/TRD.md` and `docs/ARCHITECTURE.md` to describe the implemented system | F-01, F-02 | S–M |
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

### Tier 3 — quality and maintainability

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

## 6. What the audit recommends **not** doing

| Action | Why not |
|---|---|
| Relaxing the staleness policy so live analyses produce a recommendation | It would convert a correct Rule-9 refusal into a false claim. Fix the timestamp problem (F-20) instead |
| Removing the coverage-suppression behaviour to make scores look better | Same reason. The suppression is the product |
| Enabling the LLM to compute or adjust scores | Prohibited by Rule 7, and the reason the system is trustworthy |
| Mixing facility counts into the hazard score | Prohibited by Rule 11 |
| Padding the route list to four | Prohibited by Rule 10 |
| Silently editing `docs/TRD.md` / `docs/ARCHITECTURE.md` to remove the original proposals | Rule 17 asks for limitations and history to be recorded, not erased |
| Installing a web framework, a linter or a test framework without a phase that needs it | Rule 18. The current minimal dependency footprint is a deliberate, defensible choice |
| Deleting `DATA-YOLO/` or its derived corpora to "fix" F-08 | The problem is the missing licence, not the presence of data. Deleting evidence would make the audit trail worse |
| Rebuilding the frontend bundle as part of an unrelated change | Rule 18 — minimal changes. It deserves its own reviewed commit |

---

## 7. Summary counts

| Severity | Count |
|---|---:|
| Critical | 1 (F-08) |
| High | 6 (F-01, F-02, F-06, F-11, F-12, F-13) |
| Medium | 16 (F-03, F-04, F-05, F-07, F-09, F-14, F-15, F-16, F-17, F-18, F-20, F-26, F-28, F-29, F-31, F-37) |
| Low | 13 (F-10, F-19, F-21 … F-25, F-27, F-30, F-32, F-33, F-35, F-36) |
| Info | 1 (F-34) |
| **Total** | **37** |

**Positive findings** — things the audit confirmed as done correctly, and which should be
stated in any assessment:

| # | Confirmation | Rule |
|---:|---|:---:|
| P-01 | The backend is the sole owner of safety scores; no path from facilities or the LLM into the risk engine | 7, 11, 12 |
| P-02 | Missing evidence yields `unassessed`, never a safety claim; unassessed segments are scored `null`, not `100` | 9 |
| P-03 | Only provider-returned routes are shown; no padding, no synthesis | 10 |
| P-04 | Cross-split image leakage is **zero** in both corpora | 15 |
| P-05 | The date-atomic split removes leakage by construction | 15 |
| P-06 | The single-confidence-threshold policy is enforced by a loud failure, not by convention | 6, 9 |
| P-07 | Zero dependency drift — all 40 installed packages match the lock exactly | 18 |
| P-08 | The LLM boundary is enforced by schema validation **and** entity grounding, with a deterministic fallback | 12 |
| P-09 | Provider failures are disclosed honestly; a failed lookup is never rendered as "none found" | 20 |
| P-10 | Path traversal is blocked at the HTTP boundary | 1, 13 |
| P-11 | No secret value appears in any source, config, log or document | 13 |
| P-12 | The unsupported hazard classes are reported honestly rather than guessed | 5 |
| P-13 | The manhole class was excluded from the 2-class corpus rather than relabelled | 15 |
| P-14 | Google Street View is explicitly disabled with a recorded ToS reason | 8 |
| P-15 | 299 backend test methods, all passing, including thorough negative tests | 14 |
| P-16 | The class-2 "corrupt image" defect was diagnosed, documented in `config/training_canonical.yaml`, and fixed with a corrected derived dataset rather than by patching labels in place | 15, 17 |

---

*All findings were derived from direct inspection of the repository on 2026-10-21. No
finding was fixed, no file was modified, and no destructive action was taken in
producing this register.*
