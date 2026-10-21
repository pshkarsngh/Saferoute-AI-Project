# 12 — Team Contribution Template

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Purpose:** a fill-in record of what each team member actually contributed, so that
> the division of labour can be demonstrated rather than asserted.
> **Related:** [`10-code-walkthrough.md`](10-code-walkthrough.md) ·
> [`15-traceability-matrix.md`](15-traceability-matrix.md)

---

## 1. How to use this template

1. Copy the block in §3 once per team member.
2. Fill every field. If a field genuinely does not apply, write **"Not applicable"** —
   do not delete the row. A visibly empty field is ambiguous; an explicit
   "Not applicable" is a statement.
3. **Every commit reference must be verifiable.** Use the format `<repo>:<short-sha>`.
   The outer repository uses short SHAs like `53f7f63`; the nested frontend repository
   uses short SHAs like `8449593`. Note which repository each commit belongs to — the
   frontend is a **separate Git repository** and its commits do **not** appear in the
   outer repository's history.
4. Verify the references before submitting. `git log --oneline` in the relevant
   repository is the check.

## 2. Repository and branch reference

Fill this once for the project.

| Item | Value |
|---|---|
| Core repository path | `D:\New folder (3)` |
| Core repository branch | `main` |
| Core repository HEAD at audit | `53f7f63` |
| Frontend repository path | `D:\New folder (3)\frontend\Frontend\project frontend` |
| Frontend repository branch | `main` |
| Frontend repository HEAD at audit | `8449593` |
| Governing rules document | `master_rules.md` |
| Audit document set | `docs/project-audit/` (16 files, `00`–`15`) |

> **Important.** Because the frontend is a nested repository excluded by the outer
> `.gitignore`, `git log` in the workspace root will **not** show frontend work.
> Contributions must be recorded against the correct repository.

## 3. Per-member record

Copy this block for each team member.

---

### Team member: `<Full Name>`

**Role:** `<e.g. Backend / Detection / Frontend / Data / Docs / Integration>`

**Primary ownership**

| Area owned | Where the work lives |
|---|---|
| `<module or feature>` | `<path/to/file(s)>` |

**Modules created or substantially rewritten**

| Path | What it does | Lines | Commit |
|---|---|---:|---|
| `<path>` | `<one-line description>` | `<n>` | `<repo>:<sha>` |

**Modules modified**

| Path | Nature of the change | Commit |
|---|---|---|
| `<path>` | `<what changed and why>` | `<repo>:<sha>` |

**Tests written**

| Test file | Methods | What it protects | Commit |
|---|---:|---|---|
| `<tests/unit/test_*.py>` | `<n>` | `<the specific behaviour>` | `<repo>:<sha>` |

**Configuration owned**

| Config file | Keys introduced or changed | Rationale | Commit |
|---|---|---|---|
| `<config/*.yaml>` | `<key.path>` | `<why this value>` | `<repo>:<sha>` |

**Datasets or model artefacts contributed**

| Artefact | Path | Provenance / licence status | Commit |
|---|---|---|---|
| `<name>` | `<path>` | `<provenance — or "Licence unresolved">` | `<repo>:<sha>` |

**Documentation written**

| Document | Path | Commit |
|---|---|---|
| `<name>` | `<path>` | `<repo>:<sha>` |

**Rules engaged** — tick the rules this member's work directly serves:

`[ ]` 1 Workspace isolation · `[ ]` 2 Follow documented requirements ·
`[ ]` 3 Incremental development · `[ ]` 4 YOLO11 · `[ ]` 5 Hazard classes ·
`[ ]` 6 OpenCV · `[ ]` 7 Deterministic risk engine · `[ ]` 8 Permitted imagery ·
`[ ]` 9 Missing coverage · `[ ]` 10 Routing · `[ ]` 11 Facilities ·
`[ ]` 12 LLM boundaries · `[ ]` 13 Security · `[ ]` 14 Testing ·
`[ ]` 15 Dataset integrity · `[ ]` 16 Hardware awareness · `[ ]` 17 Documentation ·
`[ ]` 18 Minimal changes · `[ ]` 19 No unauthorized actions ·
`[ ]` 20 Honest demonstration

**Measurements personally performed and recorded**

| Measurement | How performed | Result | Where recorded |
|---|---|---|---|
| `<what>` | `<command or method>` | `<actual result>` | `<path>` |

> Only record measurements you actually performed. Do not restate a number produced by
> someone else without saying so. Rule 14 is explicit that measured results must be
> separated from estimates.

**Known limitations of this member's contribution**

| Limitation | Why it remains | What would resolve it |
|---|---|---|
| `<limitation>` | `<reason>` | `<action>` |

> This section is not a confession of failure. It is a demonstration that you know the
> boundary of your own work — which is the same discipline the system itself is built on
> (Rule 9).

---

## 4. Worked example (illustrative — replace with real data)

The block below shows the expected level of detail. **The names, commits and figures in
it are illustrative placeholders and must not be copied into a real submission.**

---

### Team member: `<Example Name>`

**Role:** Frontend / Integration

**Primary ownership**

| Area owned | Where the work lives |
|---|---|
| Facilities presentation and backend consolidation | `frontend/.../src/services/facilities.ts`, `src/utils/facilityPresentation.ts`, `src/pages/RouteResults.tsx` |

**Modules created or substantially rewritten**

| Path | What it does | Lines | Commit |
|---|---|---:|---|
| `frontend/.../src/utils/facilityPresentation.ts` | Centralises facility wording and the `medical` → `medicalFacility` mapping | `<n>` | `frontend:<sha>` |

**Modules modified**

| Path | Nature of the change | Commit |
|---|---|---|
| `frontend/.../src/lib/api.ts` | Removed the browser-side Overpass client; facilities now go through `POST /api/facilities` | `frontend:<sha>` |
| `frontend/.../.env.example` | Removed `VITE_OVERPASS_URL` | `frontend:<sha>` |

**Tests written**

| Test file | Methods | What it protects | Commit |
|---|---:|---|---|
| `frontend/.../tools/browser-test/run.mjs` | 15 static checks | Asserts the browser issues no Overpass request | `frontend:<sha>` |

**Configuration owned**

| Config file | Keys introduced or changed | Rationale | Commit |
|---|---|---|---|
| `config/facilities.yaml` | `providers.overpass.{query_gap_seconds,query_deadline_seconds,base_urls,max_endpoints}`, `search.*`, `road_access.*` | Per-category queries with a 45 s budget; bounded road access | `core:<sha>` |

**Rules engaged:** 8, 9, 11, 12, 13, 17, 20

**Measurements personally performed and recorded**

| Measurement | How performed | Result | Where recorded |
|---|---|---|---|
| Backend suite | `python -m unittest discover -s tests` | `Ran 299 tests … OK` | `docs/reports/PHASE_29_HOSPITAL_ACCESSIBILITY.md` |
| Frontend checks | `npm run test:frontend` | 58 checks, 0 failures | same |
| Browser check | `node tools/browser-test/run.mjs http://127.0.0.1:8123` | All passed; no Overpass request from the browser | same |

**Known limitations of this member's contribution**

| Limitation | Why it remains | What would resolve it |
|---|---|---|
| The shipped `frontend/assets/` bundle was deliberately not rebuilt | Rebuilding would produce a large, hard-to-review binary diff | Rebuild and ship in a dedicated, approved change (finding F-06/F-18) |
| Live Overpass success path not confirmed end-to-end | All public mirrors unreachable from the audit host | Re-run `POST /api/facilities` from a host with working Overpass access |

---

## 5. Cross-member change matrix

Fill one row per commit that touched more than one member's area. This table is what
lets a reviewer see the integration points at a glance.

| Commit | Repo | Members involved | Files touched | Tests added/changed | Rules engaged |
|---|---|---|---|---|---|
| `<sha>` | `core` / `frontend` | `<names>` | `<paths>` | `<test file>` | `<rules>` |

## 6. Rules-engagement summary

One row per rule; tick the members who engaged with it.

| Rule | Summary | `<M1>` | `<M2>` | `<M3>` | `<M4>` |
|---:|---|:---:|:---:|:---:|:---:|
| 1 | Workspace isolation | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 2 | Follow documented requirements | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 3 | Incremental development | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 4 | YOLO11 | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 5 | Hazard classes | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 6 | OpenCV | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 7 | Deterministic risk engine | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 8 | Permitted imagery | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 9 | Missing coverage | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 10 | Routing | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 11 | Facilities separate | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 12 | LLM boundaries | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 13 | Security | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 14 | Testing | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 15 | Dataset integrity | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 16 | Hardware awareness | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 17 | Documentation | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 18 | Minimal changes | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 19 | No unauthorized actions | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| 20 | Honest demonstration | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

## 7. Completion checklist

Before submitting the contribution record, confirm each box.

- [ ] Every member has a completed §3 block.
- [ ] Every commit SHA was verified with `git log --oneline` in the **correct** repository.
- [ ] Every path referenced exists.
- [ ] Every measurement listed was actually performed by the member claiming it.
- [ ] No metric is presented as measured when it is repo-reported from another record.
- [ ] The DATA-YOLO licence status is stated accurately (currently **unresolved**) wherever
      the dataset is referenced.
- [ ] Known limitations are listed for every contribution — including the members' own.
- [ ] The dead-code items (`src/utils/safety.ts`, `src/services/routing.ts`,
      `src/components/Header/**`) are not claimed as active contributions.
- [ ] No secret value appears anywhere in the record.

## 8. A note on honesty in contribution records

The project's central engineering claim is that it never overstates what it knows. That
claim extends to how the work is described.

A contribution record that claims credit for dead code, or that presents a
repo-reported metric as personally measured, contradicts the system it describes. The
same discipline that produces `recommendation: null` when the evidence is insufficient
should produce `not applicable` or `Not found` in this document when that is the truth.

---

*This template is a project-specific artifact created for the 2026-10-21 audit. It adds
no new requirement; it operationalises Rule 14 ("report actual results") and Rule 17
("record … model versions, limitations and known issues") for the team record.*
