# 11 — Presentation and Viva Preparation

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Purpose:** a defensible presentation and viva pack built only from what is
> implemented and measured. Every number here is labelled *measured*, *repo-reported* or
> *Unknown*, so nothing in a viva can be overstated.
> **Related:** [`00-executive-summary.md`](00-executive-summary.md) ·
> [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) ·
> [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md)

---

## 1. The one-sentence answer

> SafeRoute AI compares the routes a routing provider actually returns, assesses road
> hazards on **permitted** street imagery with a YOLO11 detector, converts that evidence
> into a **deterministic** risk score, refuses to recommend a route when the evidence
> does not support one, and explains the result through a **grounded** local LLM with a
> deterministic fallback.

If an examiner remembers only one sentence, make it this one. It names the pipeline, the
determinism, and — critically — the refusal.

## 2. The three-sentence answer

> Most navigation apps optimise for time and distance and ignore road condition.
> SafeRoute AI adds a road-hazard evidence layer: it fetches real route alternatives from
> OSRM, matches permitted Mapillary imagery to each road segment within 25 metres, runs a
> YOLO11 detector, and turns verified detections into a score of the form
> `S = 100 · exp(−λ · H)`.
> The distinguishing feature is not the detection — it is that the system reports
> *unassessed* whenever the evidence is missing, stale or insufficient, and refuses to
> name a safest route in those cases.

## 3. Slide outline (12–14 slides, 15 minutes)

| # | Slide | Content | Rule |
|---:|---|---|---|
| 1 | **Problem** | Navigation optimises time/distance/traffic; road condition is invisible. Drivers make route choices with no hazard evidence. | — |
| 2 | **Solution** | Evidence-based route comparison with an explicit safety score and an honest coverage disclosure. | — |
| 3 | **The pipeline** | Route → imagery → OpenCV → YOLO11 → aggregation → risk → comparison → grounded LLM → UI. | 7 |
| 4 | **Architecture** | Stdlib `http.server` API; React + MapLibre SPA; provider adapters behind interfaces; SQLite persistence. | 17 |
| 5 | **Rule-driven design** | The 20 master rules, and the four that shape the architecture: 7 (deterministic risk), 9 (missing coverage), 11 (facilities separate), 12 (LLM boundary). | 2 |
| 6 | **Routing** | OSRM, keyless OSM. Routes shown **exactly as returned** — never padded to four. | 10 |
| 7 | **Imagery** | Mapillary, CC-BY-SA 4.0. 25 m spatial match, 180-day freshness, workspace-local cache, no demo substitution. | 8, 9 |
| 8 | **Detection** | YOLO11n, two classes (pothole, crack). 640 px, conf 0.25, IoU 0.45. Unsupported classes reported honestly. | 4, 5 |
| 9 | **Scoring** | `H` = severity per km; `S = 100·exp(−0.10·H)`; coverage suppression; SHA-256 config hash on every result. | 7, 17 |
| 10 | **Honest comparison** | Ties → no recommendation. Demo/stale/unassessed routes excluded. Length-weighted assessed fraction. | 9, 14 |
| 11 | **Facilities** | Overpass (ODbL), backend-only since Phase 2, context only — distance kind stated, OSM tags flagged unverified. | 11, 20 |
| 12 | **Grounded LLM** | Bounded grounded prompt, schema validation, entity-grounding check, deterministic fallback. | 12 |
| 13 | **Evidence** | 299 backend tests passing (measured); 58 frontend checks (measured); repo-reported mAP50 0.2731 val / 0.2615 test for v1. | 14 |
| 14 | **Honest limitations & next steps** | Weak detector accuracy; DATA-YOLO licence unresolved; no CI/CD; live recommendation blocked by missing imagery timestamps. | 20 |

**Slide 14 is not optional.** An examiner who sees a project that volunteers its own
weaknesses will trust the rest of the presentation. A project that claims perfection will
be tested on it.

## 4. Live demo script

### 4.1 Pre-flight

| Check | Command | Expected |
|---|---|---|
| API up | `curl http://127.0.0.1:8000/api/health` | `saferoute-yolo11-v2`, providers listed |
| Model loaded | same response | `model_version: saferoute-yolo11-v2` |
| Frontend up | open `http://127.0.0.1:8123` | SPA loads, map renders |
| Ollama up | `ollama list` | `llama3:latest` present |
| Network | try a route | OSRM responds |

### 4.2 The demo, in order

**Step 1 — Search (30 s).** Enter the fixture trip: Howrah Bridge, Kolkata → Salt Lake
Sector V. Show that the route list contains **only** the routes OSRM returned. Say the
count out loud.

> "The provider returned N routes and the system shows N routes. There is no code path
> that pads this list."

**Step 2 — Analysis (2–4 min).** Trigger the analysis. Show the loading state, then the
results: route cards, score, coverage, hazard evidence.

**Step 3 — The refusal (the most important 30 seconds).** Point at the coverage figure
and the recommendation field.

> "This analysis returns `recommendation: null` with status `cannot_determine`. The
> imagery the provider returned has no capture timestamp, so freshness cannot be
> verified, so the segments count as unassessed, so the assessed-length fraction is
> below the threshold, so the system declines to name a safest route. That is the
> designed behaviour, not a bug."

**This is the single best moment in the demo.** A system that refuses to answer when the
evidence is insufficient is far more impressive than one that always answers — and it is
the project's actual engineering position.

**Step 4 — Facilities (30 s).** Show the medical-access panel. Point at the distance
basis and the OSM attribution note.

> "Facilities come from the backend — the browser never queries OpenStreetMap itself.
> The distance is labelled as straight-line or road-network. The OSM tags are shown
> exactly as tagged and marked as not independently verified. And none of this touches
> the safety score."

**Step 5 — Explanation (30 s).** Show the explanation and its `source` badge. If the
badge says `fallback`, say so: "Ollama produced a reply that failed the grounding check,
so the deterministic template was used. The system will not show unverified model text."

### 4.3 Do not do these in a demo

| Avoid | Why |
|---|---|
| Claim the model is accurate | mAP50 ≈ 0.27. Claiming accuracy without the number violates Rule 14 and will fail a follow-up question. |
| Show the prebuilt `frontend/assets/` bundle as "our UI" | It is stale relative to source (F-06). Use the Vite preview build. |
| Present facilities as a scoring feature | Rule 11 — facilities are context only. |
| Hide the "unassessed" states | They are the product. |
| Run the live Overpass lookup as the centrepiece | All public mirrors were unreachable from the audit host. Show the honest error, or use the recorded unit-test path. |

## 5. Viva question bank

### 5.1 Architecture and design

**Q. Why did you not use FastAPI?**
> "Rule 19 gates every package installation, and `http.server` plus `sqlite3` are in the
> standard library, so the backend added zero framework dependencies. The cost is
> hand-written request validation, which is uneven — some malformed values are rejected
> with a 400, others are coerced to a default. For a local evaluation deployment that
> trade was right; for a public deployment I'd want a real validation layer and an
> authentication layer, both of which are recorded as open findings."

**Q. Why is the risk score deterministic? Why not train a regression model?**
> "Rule 7 says the backend risk engine computes scores using documented formulas and
> verified detector outputs, and that the LLM must never calculate or invent scores. A
> learned scorer would be harder to audit, harder to reproduce, and would need its own
> validation. The exponential form `S = 100·exp(−λ·H)` is simple, inspectable, and every
> input is traceable: `H` is severity per kilometre from a config-driven severity policy,
> and λ is a config value. The trade-off is that the score is **ordinal** — it reliably
> orders routes under a fixed policy, but it is not a calibrated probability of
> encountering a hazard. λ is explicitly documented as a provisional baseline."

**Q. How is this different from just showing a Google Maps traffic layer?**
> "Three things. First, the evidence base is road imagery with a detector, not traffic
> data. Second, the score comes with a coverage figure and discloses when it cannot be
> trusted. Third — and this is the real difference — the system is willing to decline to
> answer. A navigation app that always tells you which route is safest is making claims
> it cannot support; ours refuses to."

### 5.2 Rules, honesty and evidence

**Q. What happens if Mapillary returns no images for a segment?**
> "The segment becomes `unassessed`, not 'safe'. The `StalenessEvaluator` treats an
> unknown capture time as stale. The risk engine suppresses the segment score entirely —
> `unassessed_score_placeholder` is `null`, not 100 — so the route's coverage fraction
> drops. And the comparison layer will not recommend a route whose assessed length is
> below the threshold. That whole chain is covered by tests."

**Q. If two routes tie, what does the system do?**
> "It issues no recommendation. A tie means the evidence does not distinguish them, and
> naming one would be fabricating a preference — which Rule 14 forbids. The route
> ordering is still returned."

**Q. How do you know the coverage number is honest?**
> "The coverage fraction is length-weighted, not segment-count-weighted, so 'assessed'
> means the road was actually looked at, not merely that a few frames happened to exist.
> And the coverage thresholds live in `config/risk_engine.yaml` — a single place, with a
> SHA-256 hash of that file recorded on every stored score, so any score can be traced
> back to the exact policy that produced it."

**Q. Can the LLM make up a hazard?**
> "No. The explainer receives only verified backend results. The reply is checked
> against a schema, and then every route and hazard identifier it references is checked
> against the identifiers present in the input. If it references something that is not
> there, the reply is discarded and the deterministic fallback is used. There was a real
> incident where the local model was given a 140 KB prompt and answered by continuing
> the data as more JSON — the grounding check caught it, and the fix was to bound the
> prompt and state the exact totals separately."

### 5.3 Model, data and evaluation

**Q. What is your model's accuracy?**
> "The repo-recorded evaluation for the v1 checkpoint is mAP50 0.2731 on validation and
> 0.2615 on test, with recall at 0.31 — that is repo-reported and I have not
> independently reproduced it. The serving checkpoint is v2, promoted on a smaller
> unseen micro-set. And honestly, that accuracy is weak. It's the main limitation of the
> project. It is also why the system's real value is in the honest coverage and refusal
> behaviour rather than in the detection itself."

**Q. Why did you choose YOLO11n and not a larger model?**
> "Rule 4 mandates YOLO11, and the hardware is an 8 GB RTX 5050 laptop. Baseline-first
> was the deliberate strategy in TRD §5.1 — establish an honest baseline before spending
> hardware headroom. A larger variant is the obvious next step if VRAM allows."

**Q. How do you know there's no train/test leakage?**
> "We hashed every image with SHA-256 and compared across splits: zero cross-split
> overlaps. Independently, the `splits_v2` corpus is split by **capture date** rather
> than randomly, so leakage is prevented by construction rather than detected after the
> fact. There are 49 duplicate groups *within* splits in the older corpus - that inflates
> the effective training size without adding information, and it's recorded as a known
> issue."

**Q. What is the licence of your training data?**
> "**Unresolved — and this is the most serious open item in the project.** There's no
> licence file anywhere in the DATA-YOLO tree. The file `Pushkar Singh Baghel.pdf` is a
> CV, not a licence, and `Road_crack/README.md` is zero bytes. The gap was already
> raised in our own DATA-YOLO training-prep report and it is still open. The resolution
> paths are: obtain a licence statement, exclude the dataset and its weights from any
> distributable artefact, or retrain on a corpus with a clear licence — we already have
> one candidate with a Zenodo DOI."

**Do not soften this answer.** It is a recorded, unresolved, high-severity finding and
saying so demonstrates exactly the honesty the project is built on.

### 5.4 Engineering practice

**Q. How do you test this?**
> "299 backend test methods on `unittest`, all passing — 27 files, split into unit and
> integration. The most valuable ones are the *negative* tests: that missing imagery
> yields unassessed rather than safe, that a routing failure produces no fabricated
> routes, that an LLM outage still returns an explanation, and that imagery is never
> substituted when the provider rejects the request. The frontend has 58 checks in a
> hand-written harness, plus an Edge/CDP browser check. `pytest` is deliberately not
> installed — `requirements-dev.txt` is header-only under Rule 18."

**Q. What is your CI setup?**
> "There isn't one, and it's the most actionable gap. There's no `.github/workflows`, no
> Dockerfile for the core repo, no `tox` or `nox`. Every check runs manually. The
> single highest-value addition would be one workflow that installs from the lock file
> and runs the unittest discovery — that's recorded as finding F-11 with a proposed
> configuration."

**Q. Why SQLite rather than MySQL, given the TRD specifies MySQL?**
> "The TRD was written before any code existed. SQLite is a standard-library module, so
> it needs no server and no install. The schema mirrors the TRD §12 entity set and can
> be ported. But the specification still says MySQL, and the specification says a lot of
> things that are no longer true — that's finding F-01, and refreshing the spec is the
> top recommendation in the audit."

**Q. How do you keep secrets?**
> "All secrets live in the gitignored `.env`; `.env.example` carries names only. No
> credential literal appears in any source or config file. The `/api/config` endpoint
> returns a non-secret capability summary — `Settings.to_safe_dict()` is the only
> outward-facing method and it never emits secret values. The startup banner prints
> `mapillary_token=yes|no`."

**Q. What would you do next, in priority order?**
> 1. "Refresh the TRD and ARCHITECTURE documents — they still say no code exists. That
>    is actively misleading."
> 2. "Resolve the DATA-YOLO licence. Everything downstream of it is provisional."
> 3. "Re-evaluate the serving checkpoint on the date-atomic test split and publish one
>    unambiguous number."
> 4. "Add the CI workflow."
> 5. "Rebuild the shipped frontend bundle so the delivered UI matches the source."

### 5.5 Questions you should expect and must not fumble

| Question | Trap | Correct answer |
|---|---|---|
| "Your model is 97 % accurate, right?" | Agreeing | "No — mAP50 is 0.27 on the recorded evaluation. Recall is 0.31." |
| "Does it always pick the safest route?" | "Yes" | "No. It refuses when evidence is insufficient or scores tie — and right now, live, it refuses, because imagery timestamps are missing." |
| "Are the hospital results verified?" | "Yes" | "The OSM tags are echoed exactly as tagged and explicitly marked as not independently verified. We don't claim anything about beds, staffing or opening status." |
| "Did you train on the test set?" | Hand-waving | "No. The v1 evaluation used the `dataset.yaml` split; and the newer corpus is split by capture date, so leakage is prevented by construction. But the older `datayolo_prep` test split is a same-source scene-grouped list, not an independent holdout — that's a documented limitation of the published numbers." |
| "Is the score a probability?" | "Sort of" | "No. It's a deterministic ordinal score under a fixed policy, published with its coverage." |
| "Why is there no Docker?" | "Because…" | "`docs/ARCHITECTURE.md` proposes local development only, and Rule 19 gates containerisation. For a shared deployment it's the first thing I'd add after auth." |

## 6. Numbers you may quote

| Claim | Value | Status | Safe to quote? |
|---|---|---|---|
| Backend tests passing | 299 | **Measured** | ✅ |
| Frontend checks passing | 58 | **Measured** | ✅ |
| Frontend lint errors | 0 | **Measured** | ✅ |
| Backend source size | 50 modules, 8 590 lines | **Measured** | ✅ |
| Test source size | 27 `.py` files (24 test modules), 5 852 lines, 299 methods | **Measured** | ✅ |
| Pinned dependency drift | 0 of 40 | **Measured** | ✅ |
| Cross-split image leakage | 0 | **Measured** | ✅ |
| Intra-split duplicate groups (older corpus) | 49 | **Measured** | ✅ |
| mAP50 (v1) | 0.2731 val / 0.2615 test | Repo-reported | ✅ **with the label** |
| Recall (v1) | 0.3110 val / 0.3009 test | Repo-reported | ✅ **with the label** |
| Inference latency | 4.02 ms/image | Repo-reported | ⚠️ with the label and the checkpoint |
| v2 promotion | micro-F1 0.297 → 0.327 on a 601-image unseen set | Repo-reported | ⚠️ **not comparable to mAP50** |
| Live recommendation | currently `cannot_determine` | **Measured** | ✅ — lead with it |
| Overpass live lookup | `provider_error` from the audit host | **Measured** | ✅ as an environment note |

## 7. Phrases to avoid

| Avoid | Use instead |
|---|---|
| "AI-powered road safety" | "YOLO11 detection feeding a deterministic risk score" |
| "Accurate hazard detection" | "mAP50 0.2731 — the model's main limitation" |
| "Always recommends the safest route" | "Recommends only when the evidence supports it" |
| "Real-time" | "Typically under the configured client timeout; imagery acquisition dominates" |
| "Production-ready" | "Deployment-ready for a local, single-user evaluation" |
| "Verified hospital data" | "OpenStreetMap tags, echoed as tagged and marked unverified" |
| "The AI explains the route" | "A local LLM explains verified backend results, with a deterministic fallback" |

## 8. Demonstration of honesty — the strongest closing slide

End with this:

> "The defining property of this system is that it knows what it does not know. Missing
> imagery, stale imagery, insufficient coverage, tied scores, an unreachable provider, an
> unavailable LLM, an unverified OSM attribute — each of these has a defined, tested,
> user-visible outcome, and none of them is silently converted into a positive claim.
> `master_rules.md` Rule 9 says missing evidence must never be treated as proof of a
> safe road, and every one of the 20 rules is enforced somewhere in the code, with a
> configuration hash recorded on every score."

---

*All figures in this document are labelled measured, repo-reported or Unknown. The
measured figures were produced during the Phase 2 verification and the 2026-10-21
audit. No figure was estimated or inferred.*
