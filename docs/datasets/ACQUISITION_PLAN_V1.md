# Phase 43 — P2 Independent Dataset Acquisition Plan (v1)

> **Status:** plan established; acquisition **NOT STARTED** and **NOT APPROVED**
> **Owner:** dataset governance owner (to be named by the operator)
> **Applies to:** Phase 42 independent evaluation of `saferoute-yolo11-v2`

This plan defines how an independent evaluation corpus is acquired. It does not
authorise any download, purchase, licence acceptance, or field collection. Those
actions require explicit human approval recorded against the source registry in
`docs/datasets/sources.yaml`.

---

## 1. Objective

Build a genuinely independent, traceable, annotated road-imagery corpus for
evaluating the two-class serving detector (`0 = pothole`, `1 = crack`) without
reusing training/validation imagery, sessions, cameras, routes, or scenes.

Target size: **1,500–3,000 images**. The corpus must support per-class AP,
precision, recall, F1, miss rate, condition-group analysis, and (only with
verified distance) false positives per kilometre.

The independent **test** split is locked. It must never be used for training,
threshold tuning, model selection, or prompt iteration.

---

## 2. Non-negotiable constraints

1. No unapproved download or licence acceptance.
2. No undocumented imagery. Every file needs an acquisition-manifest row.
3. No P0 smoke substitute, pretrained YOLO weights, v1 checkpoint, newly trained
   model, or similarly named file may stand in for genuine v2.
4. No claim of detector performance until the genuine checkpoint and the frozen
   dataset both exist and the Phase 42 evaluation is actually run.
5. Whole collection sessions stay on one side of every split.
6. Adjacent video frames are never treated as independent observations.
7. Missing evidence is reported as `NOT_ASSESSED`, never defaulted to safe.

---

## 3. Source strategy

| Source class | Use | Approval gate |
|---|---|---|
| Operator-collected dashcam/phone imagery | Preferred | Written permission, privacy review, collection plan |
| Re-usable street-level imagery (e.g. Mapillary) | Candidate | Per-image licence/attribution verified; API terms accepted; token approved |
| Existing training corpus | Reference only | Never independent; used only for leakage comparison |
| Public benchmark datasets | Candidate | Licence verified; overlap with existing corpus measured; not used for tuning |

The source registry currently approves **zero** sources. A source becomes usable
only when `permission_status: approved` and `approved_for_acquisition: true` are
recorded with evidence.

---

## 4. Coverage design

The corpus must deliberately cover, not merely accumulate:

| Dimension | Minimum expectation |
|---|---|
| Hazard class | Potholes, cracks, both-class images, difficult negatives |
| Road type | Urban arterial, residential, rural, highway/service road |
| Surface | Dry, wet, repaired, gravel/dirt, mixed |
| Lighting | Daylight, low light/dusk, night, deep shadow, glare |
| Weather | Clear, overcast, rain (where safely captured) |
| Camera | At least 3 distinct devices/vehicles |
| Session | At least 12 independent sessions, spread across dates and geography |
| Geography | At least 3 distinct regions/local-government areas |
| Negatives | Verified negatives for manholes, shadows, paint, joints, texture |

A coverage matrix is maintained in the acquisition manifest (columns
`road_type`, `surface_condition`, `weather`, `lighting`, `condition`) and
summarised in every audit. Under-covered cells are reported, not hidden.

---

## 5. Session and grouping model

A **collection session** is one continuous capture by one camera/vehicle on one
date and route. Session identity is assigned by the operator before ingestion.

Rules:

- Every image belongs to exactly one `capture_session_id`.
- A session may contain many frames; they are **not** independent samples.
- Sessions, cameras, and routes are never split across train/val/test.
- The evaluation test set must come from sessions that do not appear in the
  independent train/val splits and do not appear in the reference registry.
- A reference registry of existing training/validation sessions is required. The
  currently available registry is a filename-date **proxy** and cannot prove
  separation; a verified registry must replace it before PASS is possible.

---

## 6. Provenance requirements (per image)

Every row in `manifests/acquisition_manifest.csv` must record:

| Field | Required | Notes |
|---|---|---|
| `image_id` | yes | Stable unique id; never reused |
| `file` | yes | Dataset-relative path, `images/<split>/...` |
| `source_id` | yes | Must exist in `sources.yaml` and be approved |
| `split` | yes | `train`, `val`, or `test`; session-atomic |
| `licence_id`, `licence_evidence` | yes | Evidence path/URL/contract id |
| `permission_status` | yes | Must be `approved` to ingest |
| `original_or_derived` | yes | `original` or `derived`; derived needs `derived_from` |
| `capture_session_id` | yes | Session identity, not a filename guess |
| `camera_id` | yes | Device or video identifier |
| `capture_date` | yes | ISO `YYYY-MM-DD` |
| `country`, `region` | recommended | Approximate location; blank is reported as unresolved |
| `latitude`, `longitude`, `location_accuracy_m` | optional | Only where permitted; never inferred |
| `road_type`, `surface_condition`, `weather`, `lighting`, `condition` | yes | Coverage and condition grouping |
| `route_id`, `segment_id`, `segment_length_m`, `distance_km` | optional | Required only for route replay / FP/km |
| `notes` | optional | Free text, no personal data |

Blank optional fields are explicitly counted as unresolved provenance. They are
never silently filled.

---

## 7. Acquisition workflow

```
P2.1 source approval
      ↓
P2.2 collect/export approved imagery to a staging directory
      ↓
write acquisition_manifest.csv (draft, no split)
      ↓
scripts/phase43/split_acquisition.py   (session-atomic split assignment)
      ↓
scripts/phase43/ingest_acquisition.py  (provenance + duplicate + reference checks)
      ↓
P3 annotation (A/B + adjudication)
      ↓
scripts/phase43/freeze_dataset.py
      ↓
scripts/phase43/preflight_dataset.py
```

At no point does ingestion overwrite an existing dataset silently. An existing
`images/` tree requires an explicit overwrite decision.

---

## 8. Leakage controls

1. Exact SHA-256 duplicate check within the independent corpus.
2. DCT perceptual-hash near-duplicate check (Hamming ≤ 8 by default).
3. Exact and perceptual comparison against the reference corpus.
4. Session-level split atomicity.
5. Route-level split atomicity where `route_id` exists.
6. Reference-session overlap check.
7. Explicit unresolved-provenance report.

A clean image-level hash probe is not proof of independence. Provenance, session
identity, and a verified reference registry are also required.

---

## 9. Storage and privacy

- Store originals read-only; ingestion copies, never mutates, source files.
- Strip or avoid faces, number plates, and personal data where feasible. If not
  feasible, record the privacy decision in the manifest notes/evidence.
- Do not commit large raw imagery to git unless the repository policy explicitly
  allows it. Keep hashes and manifests under version control.
- Record licence/attribution text alongside the dataset README.

---

## 10. Approval checklist

Before any acquisition starts, the operator must approve:

- [ ] source id(s) and licence/terms;
- [ ] evidence location for permission;
- [ ] geographic scope and capture dates;
- [ ] privacy handling (faces/plates);
- [ ] storage location and retention;
- [ ] who owns session-id assignment;
- [ ] who performs annotation A, B, and adjudication.

Until every box is checked and the source registry is updated, acquisition
remains blocked and the dataset status remains `NOT_ASSESSED`.
