# Phase 47 — Application Verification and Demo-Readiness Report

**Phase:** 47
**Date (UTC):** 2026-11-11
**Repository:** `D:\COde\Major project\Saferoute-AI-Project`
**Git HEAD:** `b3ee84fc2f2de50eb1fdba6d48d8729179ed49f0` (branch `main`, working tree dirty — **nothing committed**)
**Detector evaluation:** `NOT_ASSESSED` (unchanged; no genuine checkpoint, no independent dataset)
**Overall application verdict:** **PASS — runs end-to-end**
**Overall release verdict:** **DEMO-READY ONLY** as an honest, non-validated research demo.
**Production / safety claim:** **NOT SUPPORTED** and must not be made.

> Evidence key: **VERIFIED** = executed in this phase and observed. **CODE-VERIFIED** =
> inspected in source. **NOT TESTED** = not exercised. **BLOCKED** = prerequisite absent.
> No metric, licence, approval, annotation or checkpoint was fabricated. No detector
> accuracy claim is made anywhere in this document.

---

## 1. What was asked and what was verified

The goal was a complete, working, demo-ready application — not another audit. This phase
therefore (a) fixed remaining safe software defects, (b) re-ran the full automated suite,
(c) ran the real application with live providers, and (d) re-verified that every protected
safety artifact is byte-identical to the frozen Phase 44 baseline.

| Question | Answer | Evidence |
|---|---|---|
| Does the full test suite pass? | **Yes — 469 tests, `OK`** | §2.1 |
| Does the real app start and serve the UI + API? | **Yes** | §2.2 |
| Are all API endpoints reachable and correct? | **Yes** (with honest external-provider failures reported) | §2.2 |
| Is the detector presented as genuine? | **No** — `SMOKE_SUBSTITUTE`, `detection_validated=false` | §2.4 |
| Are safety recommendations emitted for a non-validated model? | **No** — gate returns `recommendation: null` | §2.4 |
| Is the risk formula / thresholds / checkpoint unchanged? | **Yes — all 11 protected artifacts MATCH** | §2.5 |
| Is the LLM grounded and fallback-safe? | **Yes** — rejected replies fall back and are no longer cached | §2.6 |
| Is the detector validated on independent data? | **No — `NOT_ASSESSED`** | §4 |
| Is this a production release? | **No** | §4 |

---

## 2. Executed evidence

### 2.1 Automated test suite — **VERIFIED**

Command (PowerShell, from the repository root):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Observed result after all Phase 47 edits:

```
Ran 469 tests in 29.862s
OK
```

`pytest` is not installed and no dependency was added (Rule 19). The launcher writes to
stderr, so PowerShell may report exit code `1` even on success; the authoritative signal is
`Ran … OK`.

New/updated tests added in this phase:

| Test | What it proves |
|---|---|
| `test_rejected_reply_is_not_cached` | A reply that fails grounding is regenerated, never replayed from cache |
| `test_oversized_request_body_is_rejected` | Bodies over 1 MiB get `413 payload_too_large` before buffering |
| `test_http_health_endpoint` (extended) | Security headers present; `effective_bind.port` equals the real bound port |
| `test_model_identity_is_registered` | The resolved checkpoint identity is persisted for provenance |

### 2.2 Live application — **VERIFIED**

Launched exactly as a user would:

```powershell
.\.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8765
```

Startup banner observed:

```
SafeRoute AI running.
  UI + API : http://127.0.0.1:8765/
  routing=multi imagery=mapillary facilities=overpass geocoding=nominatim llm=on mapillary_token=yes
```

Live probe results (read-only against `http://127.0.0.1:8765`):

| Check | Observed | Verdict |
|---|---|---|
| `GET /api/health` | `200`, `status=ok`, `model_status=SMOKE_SUBSTITUTE`, `detection_validated=false` | PASS |
| Health providers | routing `multi`, imagery `mapillary`, facilities `overpass`, geocoding `nominatim`, llm `ollama` | PASS |
| `GET /api/config` | `200`, token present but **not exposed**, `llm_model=qwen2.5:3b`, `effective_bind={host:127.0.0.1, port:8765}` | PASS |
| `GET /runtime-config.js` | `200`, same-origin `apiBaseUrl: ""`, security headers present | PASS |
| `GET /` | `200`, `text/html`, serves the SPA root | PASS |
| Invalid coordinate (`POST /api/analyze`) | `400 invalid_coordinates` with field-level detail | PASS |
| `POST /api/geocode` | `200`, `status=ok`, 1 candidate | PASS |
| `POST /api/routes` | `200`, `status=ok`, provider `multi`, **2 routes actually returned** | PASS |
| `POST /api/analyze` | `200`, `partially_assessed`, 2 routes, `recommendation=null` | PASS |
| Analyze cannot-determine reason | `no_sufficiently_assessed_route` — all scored routes relied on stale imagery | PASS (honest) |
| Analyze explanation source | `ollama` (live grounded LLM) | PASS |
| `GET /api/analysis/{id}/hazards` | `200` | PASS |
| `GET /api/analysis/{id}/comparison` | `200` | PASS |
| `GET /api/analysis/{id}/explanation` | `200` | PASS |
| `POST /api/facilities` | `200`; one run returned 213 facilities `provider_status=ok`, another returned `provider_error` with 0 facilities | PASS (honest upstream variance) |

Notes:

- Analysis latency observed between **2.1 s** (warm caches) and **26.0 s** (cold imagery +
  live LLM). No timeout or 5xx occurred.
- The facilities endpoint depends on public Overpass mirrors. When a mirror rate-limits, the
  API returns `provider_error` and an empty list — it never invents facilities (Rule 11).
- The mapillary token was **not** printed or returned; only `mapillary_token_present=true`.

### 2.3 Deployment and security hardening — **VERIFIED**

| Control | Implementation | Test |
|---|---|---|
| Request-body cap | `MAX_REQUEST_BYTES = 1 MiB`; rejected before buffering with `413 payload_too_large` | `test_oversized_request_body_is_rejected` |
| Security headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` on JSON, JS, static and SPA responses | `test_http_health_endpoint` + live probe |
| Static path traversal | Resolved path must remain under `frontend/` | existing tests |
| Secret redaction | `/api/config` exposes presence only; startup banner prints `yes/no` | existing tests + live probe |
| Same-origin browser base | Empty `apiBaseUrl` → UI uses `location.origin`, so `--port` works without a rebuild | live probe |
| Effective bind truthfulness | `/api/health` and `/api/config` report the **actual** bound port, not the configured default | `test_http_health_endpoint` |

### 2.4 Model identity, provenance and the recommendation gate — **VERIFIED**

- Resolved status: `SMOKE_SUBSTITUTE`, `validated: false`.
- Serving checkpoint SHA-256: `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0`
  (5,443,482 bytes) — the P0 smoke substitute, **not** `saferoute-yolo11-v2`.
- The smoke marker `P0_SMOKE_SUBSTITUTE.json` is present and intact.
- Every stored analysis is stamped with the effective `model_version`, and startup now
  registers the full identity (status, path, hash, `validated`) in `model_versions`.
- The pipeline gate suppresses recommendations whenever `detection_validated=false`. Live
  proof: `recommendation: null`, `recommendation_status: cannot_determine`.
- The UI badge (`frontend/model-status.js`) renders the same status from `/runtime-config.js`.

**The application never calls the smoke model a genuine detector.** It is labelled
`P0 smoke substitute (NOT validated)` in health, config, runtime config and the UI.

### 2.5 Protected-artifact integrity — **VERIFIED**

All 11 artifacts recorded in `reports/phase44_evidence/final_hashes.json` were re-hashed in
this phase:

| Artifact | Result |
|---|---|
| `config/detection.yaml` | MATCH |
| `config/hazard_severity.yaml` | MATCH |
| `config/risk_engine.yaml` | MATCH |
| `src/risk/engine.py` | MATCH |
| `src/risk/aggregate.py` | MATCH |
| `models/training/saferoute-yolo11-v2/weights/best.pt` | MATCH |
| `models/training/saferoute-yolo11-v2/P0_SMOKE_SUBSTITUTE.json` | MATCH |
| `frontend/assets/index-CXsvefbt.js` | MATCH |
| `frontend/index.html` | MATCH |
| `frontend/model-status.js` | MATCH |
| `frontend/backup/phase44_pre_edit/index-CXsvefbt.js` | MATCH |

**No risk formula, threshold, checkpoint, smoke marker or built frontend bundle was changed.**

### 2.6 LLM grounding and cache correctness — **VERIFIED**

- Live model: Ollama `qwen2.5:3b` at `http://127.0.0.1:11434`, bounded 45 s timeout.
- Observed: grounded replies returned with `source: "ollama"`; rejected replies fall back to
  the deterministic template.
- **Defect fixed:** the reply cache previously stored a reply *before* grounding validation,
  so a rejected reply could be replayed for up to an hour. Caching now happens only after
  grounding succeeds. A regression test locks this in.
- `llm_fallback_count` is exposed in `/api/health` so silent degradation is observable.
- Grounding still rejects invented routes, hazards, scores and safety claims (Rules 7, 12).

### 2.7 Documentation truthfulness — **VERIFIED**

`docs/PRD.md`, `docs/TRD.md` and `docs/ARCHITECTURE.md` still described the system as
"nothing implemented" and named the historical workspace `D:\New folder (3)`. Each now
carries a clearly separated **Implementation status (2026-11-11)** banner stating:

- the system is implemented and runnable;
- the active workspace is `D:\COde\Major project\Saferoute-AI-Project`;
- the canonical checkpoint is a P0 smoke substitute, `validated: false`;
- independent evaluation is `NOT_ASSESSED` and **no detector accuracy claim is made**.

The original design content was not rewritten or deleted.

---

## 3. Changes made in this phase (all safe, authorized, non-protected)

| File | Change | Why | Rule / source |
|---|---|---|---|
| `src/llm/explainer.py` | Cache only grounded replies; add `fallback_count` | A rejected reply must never be replayed | Rule 12; audit 08 |
| `src/api/app.py` | 1 MiB body cap + `413 payload_too_large`; security headers; effective bind; model registration | Deployment hardening and truthful runtime reporting | audit F-12; Rule 17 |
| `src/api/store.py` | `register_model_version()` | Join every analysis to the artifact that produced it | Rule 17 |
| `tests/unit/test_api.py` | Security, body-cap, provenance and effective-bind tests | Regression protection | Rule 14 |
| `tests/unit/test_repeat_analysis_caching.py` | Rejected-reply-not-cached test | Regression protection | Rule 14 |
| `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md` | Status banners only | Remove stale "not implemented" claims | Rule 17, Rule 20 |
| `config/app.yaml` | `app.llm.model: "qwen2.5:3b"` | Match the model actually installed locally | Rule 17 |

No dependency was installed, no dataset downloaded, no licence accepted, no protected
artifact modified, and no commit or push was made.

---

## 4. Honest limitations — what this demo does **not** prove

1. **The detector is not genuine.** The serving checkpoint is a P0 smoke substitute trained
   for 8 epochs on a small 2-class set. Its smoke validation numbers
   (mAP50 `0.115`, mAP50-95 `0.0386`) are **not** detector performance claims and must never
   be quoted as v1/v2 accuracy.
2. **The genuine `saferoute-yolo11-v2` checkpoint is absent.** Expected SHA-256
   `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA`; 0 of 11 local
   candidates match it.
3. **No independent evaluation exists.** `data/independent/` is absent; 0 of 4 imagery
   sources are approved; there are no real annotations, A/B reviews, adjudication files or
   verified collection-session registry. Detector evaluation is `NOT_ASSESSED`.
4. **No safety recommendation is enabled.** This is by design: the validation gate returns
   `cannot_determine` for a non-validated model. The demo therefore shows *analysis*, not a
   safety verdict.
5. **Route evidence is stale for the demo corridor.** Live Mapillary imagery for the test
   origin/destination is beyond the policy age, so routes are `partially_assessed` and the
   reason is disclosed. This is correct behaviour, not a failure.
6. **External providers are best-effort.** Nominatim, OSRM/Valhalla-style routing, Overpass
   and Mapillary can rate-limit or fail. The API reports the failure honestly; facility
   counts may be `0` with `provider_error`.
7. **LLM acceptance is not 100%.** In the earlier live probe, 7/10 fresh prompts passed
   grounding; the rest correctly fell back. The deterministic fallback is always available.
8. **`master_rules.md` Rule 1 still names `D:\New folder (3)`.** That directory no longer
   exists. The conflict is raised explicitly in the docs and in the checklist; only the
   project owner can amend the rule.
9. **Nothing is committed.** The working tree contains the Phase 42–47 changes. A release
   tag or push requires explicit approval.
10. **No production deployment was performed.** This was a local, single-process demo on
    `127.0.0.1`. TLS, authentication, rate limiting at the edge, backups and monitoring are
    out of scope for this phase.

---

## 5. Reproduction

```powershell
# 1. Full suite (expect: Ran 469 tests ... OK)
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# 2. Start the real app (UI + API on one port)
.\.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8765

# 3. Open http://127.0.0.1:8765/ and search for a route, or probe:
#    GET  /api/health
#    GET  /api/config
#    POST /api/routes      {"origin":{...},"destination":{...}}
#    POST /api/analyze     {"origin":{...},"destination":{...}}

# 4. Read-only evaluation preflight (still expected to exit 2 today)
.\.venv\Scripts\python.exe scripts\evaluate_independent.py --preflight-only
```

---

## 6. Sign-off

- **Application functionality:** verified working end-to-end on 2026-11-11.
- **Automated tests:** 469 passed, 0 failed.
- **Protected safety logic:** byte-identical to the frozen Phase 44 baseline.
- **Detector validation:** `NOT_ASSESSED` — must remain so until a genuine checkpoint and an
  independently annotated dataset exist and the approved evaluation is run.
- **Release posture:** suitable for an honest demo of the *system*; **not** a validated
  road-safety product.

The exact remaining work, owners and approvals are listed in
[`phase47_completion_checklist.md`](phase47_completion_checklist.md).
