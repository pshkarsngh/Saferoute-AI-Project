# Phase 47 — Consolidated Completion Checklist

**Phase:** 47
**Date (UTC):** 2026-11-11
**Repository:** `D:\COde\Major project\Saferoute-AI-Project`
**Git HEAD:** `b3ee84fc2f2de50eb1fdba6d48d8729179ed49f0` (branch `main`, 53 uncommitted entries)
**Companion report:** [`phase47_application_verification.md`](phase47_application_verification.md)
**Detector evaluation:** `NOT_ASSESSED`

> This is the single consolidated list of everything still outstanding. It separates work
> that is **safe to execute now** (A), work that **requires your explicit approval** (B),
> and work that **requires external resources or human labour** (C). It does not fabricate
> any approval, licence, annotation, metric or checkpoint.

---

## 0. State at a glance

| Workstream | Status | Blocker |
|---|---|---|
| Application code, API, UI, routing, geocoding, facilities, persistence | **DONE / verified** | — |
| Deterministic risk engine, thresholds, aggregation | **DONE / frozen** | Protected; must not change |
| Grounded LLM + deterministic fallback | **DONE / verified** | — |
| Deployment hardening (body cap, headers, secret redaction) | **DONE / verified** | — |
| Model identity, provenance, recommendation gate | **DONE / verified** | — |
| Automated test suite | **DONE — 469 tests `OK`** | — |
| Documentation truthfulness | **DONE** | Rule 1 path conflict still open |
| Genuine `saferoute-yolo11-v2` checkpoint | **BLOCKED** | Artifact absent |
| Independent evaluation dataset | **BLOCKED** | No approved source, no data |
| Annotations / reviewers / adjudication | **BLOCKED** | No human labour assigned |
| Independent detector evaluation | **BLOCKED** | Both prerequisites above |
| Commit / release tag / push | **AWAITING APPROVAL** | B1 |
| Production deployment | **NOT STARTED** | B12, C11 |

**Bottom line:** all software that can be completed without new data, model weights,
dependencies, secrets, or protected-safety changes is **complete**. What remains is
authorization, artifact recovery, licensed data, and human annotation.

---

## A. Safe to execute now — no approval required

These tasks needed no new dataset, no model download, no dependency install, no secret, and
no change to the deterministic risk formula, thresholds, checkpoint or smoke marker.
**All A tasks are complete.** Only recurring verification remains.

| ID | Task | Dependency | Owner / approval | Acceptance criterion | Status |
|---|---|---|---|---|---|
| A1 | Run the full automated suite after every change | none | engineer | `Ran 469 tests … OK`, 0 failures | **DONE** (`29.862 s`) |
| A2 | Fix LLM cache so only grounded replies are stored | none | engineer | Rejected reply is regenerated, not replayed; regression test passes | **DONE** |
| A3 | Add request-body cap and security headers | none | engineer | `413 payload_too_large`; `nosniff` / `DENY` / `no-referrer` present | **DONE** |
| A4 | Register checkpoint identity for provenance | none | engineer | `model_versions` row matches the effective `model_version` | **DONE** |
| A5 | Expose LLM fallback count in `/api/health` | none | engineer | Counter present and increments on fallback | **DONE** |
| A6 | Report the effective bind address, not only the configured port | none | engineer | `effective_bind.port` equals the live port under `--port 8765` | **DONE** |
| A7 | Add truthful implementation-status banners to PRD/TRD/ARCHITECTURE | none | engineer | Banner states implemented, active workspace, smoke/`NOT_ASSESSED` status | **DONE** |
| A8 | Re-verify protected artifacts against the Phase 44 baseline | none | engineer | All 11 artifacts `MATCH` | **DONE** |
| A9 | Live end-to-end probe of every endpoint | running app | engineer | Health/config/routes/analyze/hazards/comparison/explanation/facilities all correct or honestly failed | **DONE** |
| A10 | Run the read-only evaluation preflight | none | engineer | Confirms the blocker without side effects (exits `2`) | **DONE** |
| A11 | Re-run A1 + A9 before any demo | none | engineer | Same evidence reproduced on the demo machine | **RECURRING** |
| A12 | Keep `data/imagery/` and `.env` out of version control | none | engineer | `.gitignore` covers both; no secret in any tracked file | **DONE** (existing) |

**There are no remaining A tasks that change application behaviour.**

---

## B. Requires your explicit approval

Each item below is a decision or authorization only the project owner/operator can give.
No work in this section has been started.

| ID | Decision / authorization | Why it needs approval | Owner | Acceptance criterion |
|---|---|---|---|---|
| B1 | **Commit and/or push** the Phase 42–47 working tree | Rule 19; no VCS action without approval | Project owner | You state the exact scope (e.g. "commit all Phase 47 changes") and target branch/remote |
| B2 | **Resolve `master_rules.md` Rule 1** (`D:\New folder (3)` vs the active repo) | Rule 1 is authoritative; the old path no longer exists | Project owner | `master_rules.md` amended, or a written waiver recorded; docs stop carrying an unresolved conflict |
| B3 | **Accept the recovered genuine checkpoint** and authorize removing the smoke marker | Protected artifact; must not be relabelled | Model owner | Genuine file hash `B6354A56…8800BA` verified, provenance recorded, marker removed **only** as part of restoration |
| B4 | **Retire v2 or promote a new model identity** (e.g. the v3 candidate) | Naming/provenance decision; v3 is unevaluated | Model owner + project owner | Signed decision: either "v2 remains blocked" or "v2 retired; new identity `<name>` promoted" |
| B5 | **Approve ≥1 imagery source and accept its licence** | Rule 8; licence/terms are a legal commitment | Dataset governance owner | `docs/datasets/sources.yaml` records `permission_status: approved`, `approved_for_acquisition: true`, evidence URL/date/approver |
| B6 | **Approve annotation labour** (2 reviewers + 1 adjudicator) | Human time/cost; Rule 19 | Project owner | Named annotators A/B and adjudicator, agreed protocol and deadline |
| B7 | **Authorize detector inference and writing the evaluation output** | Rule 19; evaluation is a formal claim | Operator | Written go-ahead; new output path `reports/phase47_independent_evaluation.json` |
| B8 | **Enable safety recommendations** for a validated model | Changes a protected gate; safety-critical | Project owner + model owner | Only after B3/B4 + C9 pass; `detection_validated=true`; gate change reviewed and tested |
| B9 | **Install any new dependency** (e.g. `pytest`) or tool | Rule 19 | Project owner | Approved package list and version pin |
| B10 | **Overwrite or retire the Phase 42 baseline evaluation** | Preserve audit history | Project owner | Explicit approval naming the file and reason |
| B11 | **Change the serving model/config** beyond the current `qwen2.5:3b` | Affects reproducibility | Project owner | Approved model id + config hash recorded |
| B12 | **Any real deployment** (public host, TLS, auth, monitoring) | Security/ops exposure | Project owner + operator | Deployment plan approved; TLS + auth + rate limiting + backups in place |

---

## C. Requires external resources or human work

These cannot be produced by code alone. None can start until the corresponding B approval is
given.

| ID | Task | Depends on | Owner | Acceptance criterion | Evidence artifact |
|---|---|---|---|---|---|
| C1 | **Name a dataset governance owner** | — | Project owner | A named accountable person | decision record |
| C2 | **Verify licence/terms for ≥1 source** and record evidence | C1, B5 | Governance owner | Permission verified with URL, date, approver | `docs/datasets/sources.yaml` |
| C3 | **Acquire/collect ≥12 independent sessions** (1,500–3,000 images) across road types, lighting, weather, cameras and regions, plus verified negatives | C2, B5 | Dataset owner | ≥12 session ids; negatives included; provenance per image | `data/independent/` + acquisition manifest |
| C4 | **Split and ingest** the acquisition | C3 | Dataset owner | `split_acquisition.py` then `ingest_acquisition.py --dry-run` then real ingest succeed | split/ingest reports |
| C5 | **Annotate A/B + adjudicate** at `annotation-v1` | C3, B6 | Annotation lead | Two independent reviews + adjudication for every image | `annotation_review.csv`, `adjudication.csv` |
| C6 | **Build a verified reference-session registry** | C3 | Dataset owner | `verified=true`, `session_id_quality=verified_collection_session`, camera/route ids | `reports/phase43_reference_registry.json` replacement |
| C7 | **Freeze the dataset and pass preflight** | C4–C6 | Dataset owner | `freeze_dataset.py --frozen-by <owner>`; `preflight_dataset.py` exits `0` with `dataset_ready=true` | freeze + preflight JSON |
| C8 | **Recover the genuine v2 checkpoint** *or* train and freeze a new model under a new identity | B3/B4 | Model owner | Hash `B6354A56…8800BA` restored, or new checkpoint trained on the frozen dataset with its own identity | checkpoint + provenance JSON |
| C9 | **Run the approved independent evaluation** | C7, C8, B7 | Operator | `evaluate_independent.py` runs with the genuine model and frozen dataset; `NOT_ASSESSED` replaced by measured metrics | `reports/phase47_independent_evaluation.json` |
| C10 | **Review metrics and decide the release claim** | C9 | Project owner + model owner | Written decision: publish metrics, keep gate closed, or retrain | decision record |
| C11 | **Provide storage/GPU capacity** for the dataset and any retraining | C3/C8 | Operator | ≥ dataset size free disk; GPU available for training | environment check |
| C12 | **Privacy/legal review** for operator-collected imagery (faces, plates) | C3 | Governance owner | Review signed; redaction policy if required | review record |

---

## 1. Critical path (minimum unblock sequence)

```
C1  name dataset governance owner
 └─ B5  approve ≥1 source + accept licence
     └─ C2  record licence evidence
         └─ C3  acquire ≥12 independent sessions + negatives
             ├─ C4  split + ingest
             ├─ C5  annotate A/B + adjudicate        (B6)
             ├─ C6  verified session registry
             └─ C12 privacy/legal review
                 └─ C7  freeze + preflight (exit 0)
                     └─ C8  restore genuine v2 OR train new identity   (B3/B4)
                         └─ B7  authorize evaluation
                             └─ C9  run evaluate_independent.py
                                 └─ C10 review metrics
                                     └─ B8  (optional) enable recommendations
```

Exact commands for the final steps (unchanged from Phase 45):

```powershell
# Read-only preflight — must exit 0 before evaluation
.\.venv\Scripts\python.exe scripts\evaluate_independent.py --preflight-only

# Full evaluation — approval-gated; do not run until C7 and C8 are complete
.\.venv\Scripts\python.exe scripts\evaluate_independent.py `
  --dataset-yaml data/independent/dataset.yaml `
  --manifest data/independent/manifests/independent_manifest.json `
  --reference-sessions data/independent/manifests/training_sessions.csv `
  --reference-image-dir data/derived_2class/images `
  --output reports/phase47_independent_evaluation.json
```

**Never** pass `--allow-smoke-substitute` for a real evaluation. That flag is harness-only and
produces `NOT_ASSESSED`; it is not v2 evidence.

---

## 2. Definition of done

### 2.1 Demo-ready (achieved)

- [x] App starts with one command and serves UI + API on one port.
- [x] Every endpoint returns a correct result or an honest failure.
- [x] 469 automated tests pass.
- [x] Detector identity is labelled `SMOKE_SUBSTITUTE`, `validated: false`.
- [x] Recommendations are suppressed for the non-validated model.
- [x] LLM explanations are grounded, with a deterministic fallback.
- [x] Secrets are never exposed; security headers and body cap are active.
- [x] Protected risk/checkpoint artifacts are byte-identical to baseline.
- [x] Limitations are documented in the UI, README and reports.

### 2.2 Validated release (blocked)

- [ ] A named dataset governance owner exists (C1).
- [ ] ≥1 source is licence-approved with evidence (B5, C2).
- [ ] ≥12 independent sessions are acquired with verified negatives (C3).
- [ ] A/B annotation and adjudication are complete (C5).
- [ ] A verified reference-session registry replaces the proxy registry (C6).
- [ ] The dataset is frozen and preflight exits `0` (C7).
- [ ] The genuine v2 checkpoint is restored, or a new model identity is promoted (C8).
- [ ] Independent evaluation produces measured metrics (C9).
- [ ] The project owner reviews the metrics and records a release decision (C10).
- [ ] Recommendations are enabled only if the validated gate passes (B8).
- [ ] The release is committed/tagged and deployed with TLS/auth (B1, B12).

---

## 3. Exact asks — copy/paste approvals

To unblock the **checkpoint track**, reply with one of:

> **B3:** "I authorize restoring the genuine `saferoute-yolo11-v2` checkpoint with SHA-256
> `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` and removing the
> smoke marker as part of that restoration."

or

> **B4:** "I formally retire `saferoute-yolo11-v2` and authorize promoting a new model
> identity, to be evaluated under its own name."

To unblock the **dataset track**, reply with:

> **C1/B5/B6:** "I name `<person>` as dataset governance owner. I approve source `<name>`
> under licence `<licence>` and authorize acquisition. I approve annotation labour for two
> reviewers and one adjudicator."

To unblock the **release track**, reply with:

> **B1:** "Commit all Phase 47 changes to `main` as `<message>`." (and, if desired, "push to
> `<remote>`")

---

## 4. What must never happen

- Never present `p0-smoke-substitute` as `saferoute-yolo11-v2` or as a validated detector.
- Never quote the smoke mAP numbers as detector performance.
- Never change the deterministic risk formula or thresholds to improve a result.
- Never enable recommendations without a passed independent evaluation.
- Never fabricate annotations, metrics, licences or approvals.
- Never bypass `evaluate_independent.py` preflight or use `--allow-smoke-substitute` as v2 evidence.
- Never commit `.env`, tokens, personal data or secrets.
