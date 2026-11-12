# Phase 46 — Evidence Acquisition and Independent Dataset Preparation Plan

**Phase:** 46
**Date (UTC):** 2026-11-11T17:49:30Z
**Repository:** `D:\COde\Major project\Saferoute-AI-Project`
**Git HEAD:** `b3ee84fc2f2de50eb1fdba6d48d8729179ed49f0` (branch `main`, 46 uncommitted entries)
**Status:** `BLOCKED` — planning/evidence-gathering only; **no acquisition, annotation, inference, or retraining performed**
**Detector evaluation:** `NOT_ASSESSED` (unchanged from Phase 45)

> This report is a plan and an evidence record. It does not acquire imagery, accept a
> licence, approve a source, create annotations, name reviewers, or evaluate a detector.
> Every statement below is either directly verified in this workspace (with the command
> or file that produced it) or explicitly marked **UNVERIFIED** / **NOT ASSESSED**.

---

## 1. Executive summary

| Question | Answer | Status |
|---|---|---|
| Is the genuine `saferoute-yolo11-v2` checkpoint present locally? | **No.** 0 of 11 candidates match the registered SHA-256. | **BLOCKED** |
| Is the canonical serving path genuine v2? | **No.** It holds the P0 smoke substitute (`19619F99…B916D0`). | **BLOCKED** |
| Is a v3 candidate present? | Yes, but it is a separate, unevaluated model identity — not v2. | **BLOCKED** |
| Are any imagery sources approved for acquisition? | **No.** 0 of 4 candidates approved. | **BLOCKED** |
| Is there an independent dataset? | **No.** `data/independent/` does not exist. | **BLOCKED** |
| Can the 1,253 cached Mapillary images be used as-is? | **No.** No provenance, licence evidence, capture time, GPS, camera, or session identity. | **BLOCKED** |
| Are annotations / A-B review / adjudication present? | **No.** Zero annotation rows exist for any candidate corpus. | **BLOCKED** |
| Is the reference-session registry verified? | **No.** Proxy-only (`filename_date_proxy`, `verified=false`). | **BLOCKED** |
| Is the detector result reportable? | **No.** No metrics exist; evaluation remains `NOT_ASSESSED`. | **NOT ASSESSED** |

**Conclusion:** Phase 46 confirms the Phase 45 `BLOCKED` verdict with additional,
finer-grained evidence. The two independent prerequisites — a hash-verified genuine v2
checkpoint and an approved, provenanced, annotated independent corpus — are both absent.
This report defines exactly what evidence is required to remove each blocker, in the
order the existing Phase 43 tooling enforces.

---

## 2. Scope and constraints honoured

Performed:

- Read `reports/phase45_validation_readiness.md`, `reports/phase44_p0_completion.md`,
  `master_rules.md`, and Phase 42/43 governance documents.
- Searched authorised local locations for the genuine v2 checkpoint and hashed every
  candidate.
- Reviewed the four candidate sources in `docs/datasets/sources.yaml`.
- Inspected the existing Mapillary cache (counts, hashes, dimensions, EXIF, perceptual
  near-duplicates, cross-corpus overlap) without downloading anything.
- Read the frozen acquisition/annotation contracts and Phase 43 tooling to align the
  plan with real acceptance logic.

**Not performed (and deliberately not performed):**

| Prohibited action | State |
|---|---|
| Detector inference / evaluation | Not run |
| Retraining or fine-tuning | Not run |
| Checkpoint substitution or relabelling | Not done |
| Image download / acquisition | Not done |
| Fabricated provenance, annotations, reviewers, metrics | Not done |
| Risk formula / threshold / recommendation-eligibility changes | Not done |
| Checkpoint / smoke-marker changes | Not done |
| Dependency installation | Not done |
| `sources.yaml` edits or licence acceptance | Not done |
| Git commit / push | Not done |
| Reading or printing `.env` / credentials | Not done (existence confirmed only) |

**Protected-artifact integrity after Phase 46** (SHA-256 recomputed at report time, all
unchanged relative to Phase 44/45):

| Artifact | SHA-256 | Bytes |
|---|---|---|
| `models/training/saferoute-yolo11-v2/weights/best.pt` | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | 5,443,482 |
| `models/training/saferoute-yolo11-v2/P0_SMOKE_SUBSTITUTE.json` | `8B69C24E7B86976B3038BBA4B5BBFB639094EDC852FBAA4DC49EB933AF795D05` | 2,002 |
| `models/training/saferoute-yolo11-v1/weights/best.pt` | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | 5,443,482 |
| `models/training/_tmp_v3_candidate/candidate_v3/weights/best.pt` | `8574AB43C84C47FE7AF8030FAAC681A135024A73D2B740910B47425677EC472D` | 21,251,427 |
| `config/detection.yaml` | `22371AE8C1DA3CBA77E40EE096337915D16C0CFDDB9E7E2AF9213F4BE1B18344` | 1,698 |
| `config/hazard_severity.yaml` | `D11AA0F73511E4EEF4B49869D2D009F5F06048801A1B03A64ED5CDB407CDF473` | 2,498 |
| `config/imagery.yaml` | `0A092A50D61F911B4130CAC5DEB47C1AC8CF08EB8E89B1B3B8D5F1D4805F07F4` | 2,360 |
| `docs/datasets/sources.yaml` | `7318DF947132891A230D878AABAAED30E765CDBD16D169EF4BF33F6C2B273C8B` | 2,534 |
| `docs/datasets/ACQUISITION_PLAN_V1.md` | `5DD2DCE835939DFD38E4B083CAD5961B1E0404C36CA7EFDE72949928EFFFA632` | 7,861 |
| `docs/datasets/ANNOTATION_SPEC_V1.md` | `864373B3AFC4186C437EC93988D5F3279DA62785593E8671E4B76AA794CC6C97` | 9,657 |
| `scripts/evaluate_independent.py` | `846245AE9135DDDE889BD0A5975A0F2B5C60B4FB1D14B88CE5DE10C5528317E1` | 6,591 |
| `scripts/phase43/audit_sources.py` | `E31D7E5CCF7A44ED9CC9C1B8296AC91A060A6F7AB7C32DE73C2321476F149B9E` | 2,566 |
| `scripts/phase43/build_reference_registry.py` | `B0B471FDDE42842CDA144E385D1E11BF43A67B40DC2D0307DCFBEA348695D8F2` | 3,157 |
| `scripts/phase43/split_acquisition.py` | `C02FDD1B0591EF44FD81F5A890E84970B1BD524D4FA54FFE289A7DBF9B81CDC4` | 3,851 |
| `scripts/phase43/ingest_acquisition.py` | `CCA657550880A765F7A5F864CE6A89ADF4A8367D053A9C303CD9F71944E1B5A4` | 4,092 |
| `scripts/phase43/freeze_dataset.py` | `B3B795FB4E5B4E241609A50BA32908C0A44F32B53E086347F3B132A6F6DDCE98` | 5,683 |
| `scripts/phase43/preflight_dataset.py` | `8021BBF1295BEA6394104E565F2197C7CF2985FFFBC467E051F97B0838454E2B` | 3,414 |
| `src/datasets/acquisition.py` | `7CB25A6BB4F46330827DCB83E3F1C3B2E543C31324C3E8D51448147759041D92` | 24,791 |
| `src/datasets/annotation.py` | `C21512662D4E9ECE63637F3EF29EC93DA7885385FAB7CB6AE03310FCFCB6FE64` | 13,812 |
| `src/datasets/common.py` | `606A712A857A9BE9D2C596915B3A62F0BFD3F48ADA8B08FD1C97E779EBD50F87` | 6,833 |
| `src/datasets/freeze.py` | `ABE8A6BCE8395CD5019F24CA7E445BDCE08593222827046D3D41C5739B6E38D6` | 32,169 |
| `src/datasets/preflight.py` | `3EFA64876CAE0AC5EC9832FF5CB59FE2872FD69BF8FF897DA36F794F009CCFBB` | 11,734 |
| `src/datasets/reference.py` | `091829D0D42F578A8980F6ED2638B3FDF8E09293134980B3790F7B7DEB6437B0` | 10,748 |
| `src/datasets/sources.py` | `2259FCB5673F1456396354D4EE9BE9888B639BD52F7127A016BFF71DD3F6C06C` | 5,452 |
| `src/datasets/splitting.py` | `80E637D8E904306DB69B8467B6993BA7BFDA461B6190814573215FF6E2A5AD6B` | 4,840 |
| `src/evaluation/leakage.py` | `17E370E2F26051F8AF75D1C120DE0FEEB0222A1995CDAD7D053E58745A890339` | 14,472 |

---

## 3. Checkpoint retrieval and hash verification

### 3.1 Registered identities

| Identity | Expected SHA-256 | Notes |
|---|---|---|
| Genuine `saferoute-yolo11-v2` | `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` | Pinned in Phase 42; required for evaluation |
| Genuine `saferoute-yolo11-v1` | `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65` | Pinned; also absent |
| P0 smoke substitute (occupies v2 path) | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | **NOT v2** |
| v3 candidate | `8574AB43C84C47FE7AF8030FAAC681A135024A73D2B740910B47425677EC472D` | **NOT v2**; unevaluated |

### 3.2 Canonical serving path state

`models/training/saferoute-yolo11-v2/weights/best.pt`

- SHA-256 `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0`, 5,443,482 bytes.
- This is byte-identical to `models/training/saferoute-yolo11-v1/weights/best.pt` and to
  `models/training/p0-smoke/weights/best.pt`.
- The adjacent marker `P0_SMOKE_SUBSTITUTE.json`
  (`8B69C24E7B86976B3038BBA4B5BBFB639094EDC852FBAA4DC49EB933AF795D05`) declares status
  `NON_PRODUCTION_P0_SMOKE_SUBSTITUTE` and states the original v2 artifact was not
  recoverable and must not be used for safety claims or production evaluation.
- **Decision:** the canonical path must continue to be treated as *not v2*. It must not be
  used, renamed, or reported as v2.

### 3.3 Search performed in Phase 46

- Documented historical location: `D:\New folder (3)\models\training\saferoute-yolo11-v2\weights\best.pt`.
  `D:\New folder (3)` **does not exist**. `D:\New folder` contains only an unrelated `.md`;
  `D:\New folder (2)` contains only a nested empty `New folder`. No `saferoute-yolo11-v2`
  directory and no `.pt` file ≥1 MB exist under any `D:\New folder*` path.
- Extended re-scan (files ≥1 MB, extensions `.pt/.pth/.onnx/.engine/.ckpt`, excluding
  `.git`, `.venv`, `node_modules`, `__pycache__`) across: repository, `D:\COde`,
  `C:\Users\pushk\Downloads`, `C:\Users\pushk\Documents`, `C:\Users\pushk\OneDrive`,
  `D:\New folder*`.
- Result: **11 candidates, 0 matches** for genuine v2 or v1.

Candidates found (all accounted for, none genuine v2):

| SHA-256 | Bytes | Path (relative to repo unless noted) | Verdict |
|---|---|---|---|
| `0EBBC80D4A7680D14987A577CD21342B65ECFD94632BD9A8DA63AE6417644EE1` | 5,613,764 | `yolo11n.pt` | Base pretrained weights, not v2 |
| `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | 5,443,482 | `models/training/p0-smoke/weights/best.pt` | Smoke substitute |
| `7BA35DF6AE49C71C746E78AC714F62CC87B4882777286481F98A1427DDF8D5BC` | 5,443,482 | `models/training/p0-smoke/weights/last.pt` | Smoke substitute (last) |
| `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | 5,443,482 | `models/training/saferoute-yolo11-v1/weights/best.pt` | Smoke substitute copy |
| `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | 5,443,482 | `models/training/saferoute-yolo11-v2/weights/best.pt` | Smoke substitute copy |
| `8574AB43C84C47FE7AF8030FAAC681A135024A73D2B740910B47425677EC472D` | 21,251,427 | `models/training/_tmp_v3_candidate/candidate_v3/weights/best.pt` | v3 candidate |
| `1DAB13A0D35C840EDA5CCE121775179EF25154EFD36D221F7796308E958614AD` | 21,248,867 | `.../candidate_v3/weights/epoch0.pt` | v3 candidate (epoch) |
| `E8757625679EB05865614331D8673E7AA196519F16EEF10A54FFA55778A6FBB2` | 21,250,147 | `.../candidate_v3/weights/epoch10.pt` | v3 candidate (epoch) |
| `8574AB43C84C47FE7AF8030FAAC681A135024A73D2B740910B47425677EC472D` | 21,251,427 | `.../candidate_v3/weights/epoch20.pt` | v3 candidate (epoch, = best) |
| `0A68917AF5CCDDBD6B08E1CFDC541DFE3212A17787244CD8F4F890BC92FDC57D` | 21,252,451 | `.../candidate_v3/weights/last.pt` | v3 candidate (last) |
| `9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF` | 5,544,453 | `weights/yolo26n.pt` | Base pretrained weights, not v2 |

All 11 candidates are accounted for. None hashes to genuine v2 or v1.

- Phase 42's broader search over `D:\` and `C:\Users\pushk` recorded 6 candidates, also 0
  matches, with access-denied system paths documented in `reports/phase42_artifact_manifest.json`.
- No `.pt` blob exists in git history; no archive (`.zip/.tar/.7z`) containing weights exists
  in the workspace.

### 3.4 v3 candidate handling

- Path: `models/training/_tmp_v3_candidate/candidate_v3/weights/best.pt`
- SHA-256 `8574AB43C84C47FE7AF8030FAAC681A135024A73D2B740910B47425677EC472D`, 21,251,427 bytes.
- Identity label: `saferoute-yolo11-v3-candidate`.
- It is **not** the pinned v2 artifact, has no independent evaluation, and must never be
  relabelled as v2 or used to satisfy the v2 requirement.

### 3.5 Retrieval options (for the operator, not executed)

| Option | Action | Evidence required to accept | Status |
|---|---|---|---|
| R1 | Restore the genuine v2 file from an external backup/artifact store | File hashes to `B6354A56…800BA`; retrieval source + date recorded | **No backup location documented in workspace** |
| R2 | Recover from the original training environment (`D:\New folder (3)` machine) | Same hash + provenance note tying the path to Phase 20/24 training | **Original path absent on this machine** |
| R3 | Retrain v2 to the original recipe | Reproducible training record + new hash; **creates a new model identity**, not the pinned artifact | Out of Phase 46 scope; would not restore the pinned hash |
| R4 | Evaluate the v3 candidate instead | New identity, new pin, new evaluation report; never labelled v2 | Out of Phase 46 scope |

**Acceptance rule:** only R1/R2 can unblock evaluation of `saferoute-yolo11-v2`, and only
if the restored file hashes to `B6354A56…800BA`. Any other file is a different model
identity and requires its own explicit pin and governance decision.

---

## 4. Source permission review

Registry: `docs/datasets/sources.yaml` (SHA-256 `7318DF94…3C8B`). Audit record:
`reports/phase43_source_audit.json` (`approved_count: 0`, `acquisition_allowed: false`).

| source_id | Licence (project label) | permission_status | approved_for_acquisition | reference_only | Access conditions | Acquisition allowed now? |
|---|---|---|---|---|---|---|
| `mapillary` | `CC-BY-SA-4.0` | `pending_verification` | **false** | false | Mapillary API token; per-image attribution + share-alike + API terms not re-verified for evaluation use | **No** |
| `existing_same_source_corpus` | `CC-BY-4.0` | `pending_verification` | **false** | **true** | Already used for train/val; licence prior-reported, not re-verified | **No — and never independent** |
| `operator_capture` | `OPERATOR-OWNED` | `pending_operator_approval` | **false** | false | Written operator permission, collection plan, privacy review (faces/plates), named owner | **No** |
| `zenodo_18528034` | `CC-BY-4.0` | `pending_verification` | **false** | false | Record, licence and imagery unverified; relationship to existing corpus unknown | **No** |

Additional observations:

- `config/imagery.yaml` (`imagery-v1`, dated 2026-10-13) marks Mapillary and
  `workspace_dashcam_v1` as `enabled: true` with `ml_inference_permitted` and
  `local_storage_permitted`. That config is an *operational* permission record, **not** a
  dataset-governance approval. It cannot substitute for `approved_for_acquisition: true`.
- `google_street_view` is explicitly disabled (ToS §3.2.3 forbids automated download,
  caching, model ingestion) and must not be added.
- No source may be used until a human records licence evidence (URL/path + date) and flips
  `approved_for_acquisition` to `true`. Phase 46 did **not** edit this file.

---

## 5. Imagery inventory and provenance gaps

### 5.1 Corpus inventory

| Location | Images | Labels | Status |
|---|---|---|---|
| `data/derived_2class/images` | 2,009 | 1,792 (`.txt`) | Training-derived; **reference-only** |
| `data/pothole_crack_manhole/data` | 2,009 | 4,018 (`.txt`) | Source corpus; reference-only |
| `data/imagery/mapillary` | 1,253 | 0 | Unverified cache; **not manifestable as-is** |
| `data/independent` | — | — | **Absent** |

`data/derived_2class/MANIFEST.json` still records its source root as
`D:\New folder (3)\data\pothole_crack_manhole\data`, which no longer exists — a second
pointer to the missing original workspace.

### 5.2 Mapillary cache — measured facts

All values below were measured in this workspace; no imagery was downloaded.

| Property | Result |
|---|---|
| Files | 1,253 JPEG |
| Total bytes | 135,207,133 |
| Unique SHA-256 | 1,248 |
| Exact-duplicate groups | 2 |
| — group 1 | 5 byte-identical `320×240` files (5,536 bytes each) |
| — group 2 | 2 byte-identical `1024×768` files (83,619 bytes each) |
| Near-duplicate pairs (pHash Hamming ≤8) | **408** |
| EXIF capture timestamp | **0** |
| EXIF GPS | **0** |
| EXIF camera make/model | **0** |
| EXIF software | **0** |
| EXIF present at all | 39 files — 38 carry only `Copyright 2013`; 1 also has `ImageDescription` (`{"applied_s236562": true}`) |
| XMP / Mapillary attribution strings | **0** |
| JFIF marker | 1,253 (all) |

Dimensions distribution:

| Size | Count |
|---|---|
| 1024×576 | 647 |
| 1024×768 | 435 |
| 1023×614 | 92 |
| 1023×575 | 21 |
| 1024×473 | 20 |
| 1024×512 | 14 |
| 1024×771 | 10 |
| 1024×640 | 6 |
| 320×240 | 5 |
| 576×768 | 3 |

### 5.3 Provenance gaps

The cache has **no usable capture metadata**:

- No capture timestamp → cannot form collection sessions or verify capture-date coverage.
- No GPS → cannot verify geography, route, or distance; FP-per-km remains unavailable.
- No camera identity → cannot prove camera independence from the training corpus.
- No Mapillary image ID, sequence ID, or contributor ID stored alongside the files → the
  filename is a 16-digit numeric string, but there is **no sidecar** mapping it to
  Mapillary metadata, so the mapping is **UNVERIFIED**.
- No per-image licence/attribution record → CC-BY-SA-4.0 obligations cannot be evidenced.
- The provider code (`src/imagery/mapillary_provider.py`) requests
  `id,captured_at,compass_angle,geometry,thumb_1024_url` and persists no sidecar; even a
  fresh download would not, by itself, create an evaluation-grade manifest.

**Consequence:** the cache cannot be ingested, manifested, or frozen as independent
evaluation data. It must not be described as independent, licensed, or suitable.

### 5.4 Duplicate and placeholder findings

- The 5 identical `320×240` files are near-white (mean 248.33, std 35.63) and are
  **suspected placeholders**; their visual content was not assessed. They must be excluded
  from any candidate corpus.
- The 2 identical `1024×768` files are a straightforward duplicate pair.
- 408 near-duplicate pairs indicate sequential frames from a small number of drives, not
  independent samples. Without sequence IDs, session grouping cannot be proven.

### 5.5 Cross-corpus leakage probe (Mapillary vs. derived training corpus)

| Check | Result | Interpretation |
|---|---|---|
| Exact SHA-256 overlap | **0** | No byte-identical reuse |
| pHash Hamming ≤4 | 9 images | Flagged |
| pHash Hamming ≤8 | 76 images | Flagged |
| Pixel-level normalized correlation (9 closest) | **range −0.13 to 0.19** (max absolute 0.19) | **Not the same scene** |

**Conclusion:** the pHash flags are **texture false positives**, not leakage. However, the
existing leakage gate treats any reference near-duplicate at ≤8 as an **error**. If these
images were ingested unchanged, the preflight/freeze gate would hard-fail. The plan must
therefore either (a) use a source whose images are genuinely distinct, or (b) record an
adjudicated, evidence-backed exclusion of flagged images *without altering the gate*.
The gate must not be bypassed or weakened.

---

## 6. Acquisition plan

### 6.1 Target

Build a genuinely independent, traceable, annotated two-class (`0 = pothole`,
`1 = crack`) evaluation corpus of **1,500–3,000 images**, meeting
`docs/datasets/ACQUISITION_PLAN_V1.md`, with a locked test split and full provenance.

### 6.2 Acquisition options

| Option | Description | Independence risk | Licence path | Recommendation |
|---|---|---|---|---|
| **A — Operator capture** | New field collection by the operator with a documented collection plan | **Lowest** (new sessions, new cameras, new routes) | Operator-owned; written permission + privacy review | **Preferred** |
| **B — New Mapillary pull** | Fresh, *approved* Mapillary download with metadata sidecars (image id, sequence, captured_at, geometry, contributor) | Medium (must prove no overlap with training routes/cameras) | CC-BY-SA-4.0 with per-image attribution | Viable only after licence verification |
| **C — Zenodo 18528034** | External public corpus | **High/unknown** — relationship to existing corpus unverified; may be the same source | CC-BY-4.0, unverified | Not acceptable until independence proven |
| **D — Existing cache as-is** | Reuse `data/imagery/mapillary` | Unknown | No evidence | **Rejected** |
| **E — Existing derived corpus** | Reuse training data | **Zero independence** | n/a | **Rejected (reference-only)** |

### 6.3 Pre-acquisition steps (in order)

1. Operator names a **dataset governance owner** and a **privacy reviewer**.
2. Owner selects Option A or B and records the decision in `docs/datasets/sources.yaml`
   (licence evidence URL/path + date, `approved_for_acquisition: true`).
3. For Option A: approve a written collection plan (routes, sessions, cameras, dates,
   weather/lighting targets, privacy handling, distance logging).
4. For Option B: verify Mapillary terms for evaluation use, per-image attribution and
   share-alike handling; record the verification evidence.
5. Only then run acquisition. For Option B, persist a **metadata sidecar per image** at
   download time (do not rely on EXIF).

### 6.4 Manifest schema (matches tooling exactly)

The acquisition manifest must use the frozen columns in `src/datasets/common.py`
(`ACQUISITION_COLUMNS`, 27 columns):

```
image_id, file, source_id, split, licence_id, licence_evidence, permission_status,
original_or_derived, derived_from, capture_session_id, camera_id, capture_date,
latitude, longitude, location_accuracy_m, country, region, road_type, surface_condition,
weather, lighting, condition, route_id, segment_id, segment_length_m, distance_km, notes
```

Required non-empty (`ACQUISITION_REQUIRED_COLUMNS`, 16 columns):

```
image_id, file, source_id, split, licence_id, licence_evidence, permission_status,
original_or_derived, capture_session_id, camera_id, capture_date, condition,
road_type, surface_condition, weather, lighting
```

Constraints enforced by `validate_acquisition` / `ingest_acquisition`:

- `permission_status` must be exactly `approved` (`ALLOWED_PERMISSION_STATUS = {"approved"}`).
- `original_or_derived` ∈ {`original`, `derived`}; `derived` requires `derived_from`.
- `capture_date` must be ISO `YYYY-MM-DD`.
- `split` ∈ {`train`, `val`, `test`}.
- `licence_evidence` must point to a real, recorded evidence artifact.
- Source must be `approved_for_acquisition: true` in `sources.yaml`.
- Exact/near duplicates against the reference corpus are refused at ingestion.

Collection-session manifest (`COLLECTION_SESSION_COLUMNS`):

```
session_id, source_id, camera_id, capture_date, country, region, route_id, image_count, split
```

### 6.5 Provenance requirements per image

| Field | Requirement | Why |
|---|---|---|
| `image_id` | Stable unique ID, not the raw filename alone | Traceability |
| `source_id` | Must map to an approved registry entry | Licence gate |
| `licence_id` + `licence_evidence` | Project label + path/URL + retrieval date | Legal evidence |
| `permission_status` | `approved` | Ingestion gate |
| `capture_session_id` | One ID per contiguous drive/collection event | Session atomicity |
| `camera_id` | Physical device or feed identity | Camera independence |
| `capture_date` | ISO date from device log or verified metadata | Temporal coverage |
| `latitude`/`longitude`/`location_accuracy_m` | Verified GPS or explicit blank + reason | Geography/distance |
| `country`/`region`/`route_id`/`segment_id` | Verified route identity | Route independence |
| `road_type`/`surface_condition`/`weather`/`lighting`/`condition` | Observed at capture | Coverage analysis |
| `distance_km`/`segment_length_m` | Only if measured; otherwise blank | FP-per-km gating |

**Rule:** a blank required field is a hard ingestion failure. A fabricated value is worse
than a blank and is prohibited.

### 6.6 Session identity rules

- A session is the atomic unit. All frames from one session must share
  `capture_session_id` and must land in exactly one split.
- Minimum of 3 sessions overall (tool default) and ≥1 session per split.
- Sessions must be disjoint by camera **and** route from all reference/training sessions.
- If session identity cannot be proven from verified metadata, the corpus is
  **NOT_ASSESSED**, not CONDITIONAL.

### 6.7 Independence checks before ingestion

1. **Source independence** — approved source not used for training.
2. **Camera independence** — no `camera_id` shared with reference sessions.
3. **Route/geography independence** — no `route_id`/segment shared with reference sessions.
4. **Temporal independence** — capture dates outside reference capture windows (or justified).
5. **Exact-duplicate check** — SHA-256 vs. reference corpus = 0.
6. **Perceptual near-duplicate check** — pHash vs. reference; ≤8 requires adjudication.
7. **Session atomicity** — no session spans splits.

---

## 7. Annotation, review, and adjudication plan

Contract: `docs/datasets/ANNOTATION_SPEC_V1.md`, annotation version **`annotation-v1`**,
classes `0 = pothole`, `1 = crack` only.

### 7.1 Annotation

- YOLO-format `.txt` per image, one row per box, class id ∈ {0,1}.
- Every image must have a label file; verified negatives are empty files, explicitly
  recorded as reviewed.
- Boxes must follow the class definitions and geometry rules in the spec.
- Ambiguous cases are marked `uncertain`, not guessed.

### 7.2 Two-review requirement

Every image requires **two independent reviews** by different reviewers
(`role ∈ {annotator_a, annotator_b}`), recorded in `annotation_review.csv`:

```
image_id, reviewer_id, role, annotation_version, review_status, box_count, reviewed_at, note
```

- `annotation_version` must equal `annotation-v1` in every row.
- `review_status` ∈ {`approved`, `changes_requested`, `excluded`, `uncertain`}.
- Reviewer IDs must be real people; no invented reviewers.

### 7.3 Adjudication

Disagreements, `uncertain`, and `changes_requested` cases require an adjudicator distinct
from both reviewers, recorded in `adjudication.csv`:

```
image_id, adjudicator_id, annotation_version, outcome, final_status, resolved_box_count, decided_at, note
```

- Adjudicator must not be annotator A or B for that image.
- `final_status` must be a valid terminal status; `resolved_box_count` must match the
  final label file.

### 7.4 Human review requirements

| Role | Responsibility | Minimum |
|---|---|---|
| Annotator A | Primary annotation | 1 named person |
| Annotator B | Independent second review | 1 named person, different from A |
| Adjudicator | Resolve disagreements | 1 named person, different from A and B |
| QC lead | Spot-check + sign-off | 1 named person |
| Privacy reviewer | Faces/plates/consent | 1 named person |
| Governance owner | Licence/source approval | 1 named person |

**Effort estimate (planning only, not measured):** at 1,500–3,000 images, two reviews plus
adjudication of disagreements typically implies roughly 3–6 annotator-weeks depending on
hazard density and tooling. This is an estimate to be replaced by a measured pilot.

---

## 8. Split separation, leakage, and freeze criteria

### 8.1 Split assignment

- Tool: `scripts/phase43/split_acquisition.py` → `assign_session_splits`.
- Whole sessions assigned deterministically by salted SHA-256 (`salt = phase43-v1`,
  default ratios 70/15/15).
- `validate_session_atomicity` must confirm no session straddles splits.
- Test split is locked once frozen.

### 8.2 Leakage gates (as implemented in `src/evaluation/leakage.py` + `src/datasets/preflight.py`)

| Condition | Severity | Effect |
|---|---|---|
| Exact duplicate within corpus | error | Freeze refused |
| Near-duplicate within one session | warning | CONDITIONAL at best |
| Near-duplicate across sessions | error | Freeze refused |
| Reference near-duplicate ≤8 | error | Freeze refused |
| Session spans splits | error | Freeze refused |
| Reference session ID reused | error | Freeze refused |

The Mapillary cache's 76 cross-corpus pHash flags at ≤8 would trigger the reference gate.
They must be resolved by **evidence-backed exclusion** (documented as false positives with
pixel-level correlation), not by editing the gate.

### 8.3 Freeze status logic (`src/datasets/freeze.py`)

| Status | Condition |
|---|---|
| `FAIL` | Any error present |
| `NOT_ASSESSED` | No verified reference registry / missing evidence |
| `CONDITIONAL` | Warnings only |
| `PASS` | No errors, no warnings, reference registry `verified=true` with `verified_collection_session` quality |

Because the current reference registry is `filename_date_proxy` / `verified=false`, the
best achievable status today is `NOT_ASSESSED` even if a perfect independent corpus
appeared.

### 8.4 What must be true for PASS

1. Approved source(s) with licence evidence.
2. Complete acquisition manifest (all required fields non-empty).
3. Verified collection-session manifest (not proxy).
4. Verified reference-session registry (`verified_collection_session`).
5. Two reviews + adjudication for every image, all `annotation-v1`.
6. Zero leakage errors.
7. Frozen manifest + content-hash attestation written by `freeze_dataset.py`.
8. `preflight_dataset.py` returns `PASS`.

---

## 9. Required approvals and human work

| # | Approval / work | Owner | Blocks |
|---|---|---|---|
| 1 | Name dataset governance owner | Operator | Everything |
| 2 | Decide acquisition option (A/B) | Operator + governance owner | Acquisition |
| 3 | Approve source + record licence evidence in `sources.yaml` | Governance owner | Ingestion |
| 4 | Approve collection plan (Option A) | Governance owner + privacy reviewer | Capture |
| 5 | Verify Mapillary terms (Option B) | Governance owner | Download |
| 6 | Privacy review (faces/plates/consent) | Privacy reviewer | Any capture/use |
| 7 | Recruit/assign A, B, adjudicator, QC lead | Operator | Annotation |
| 8 | Verify reference-session registry from real training logs | ML owner | Freeze PASS |
| 9 | Restore genuine v2 checkpoint (hash-verified) | ML owner / operator | Evaluation |
| 10 | Approve the frozen dataset | Governance owner | Evaluation |
| 11 | Resolve `master_rules.md` workspace conflict (see §10) | Operator | Governance validity |

---

## 10. Blockers and conflicts

### 10.1 Hard blockers

| ID | Blocker | Evidence |
|---|---|---|
| B1 | Genuine v2 checkpoint absent | 0/11 candidates match `B6354A56…800BA`; original path gone |
| B2 | No approved imagery source | `approved_count: 0` in Phase 43 audit |
| B3 | No independent dataset | `data/independent/` absent |
| B4 | No annotations / A-B review / adjudication | Zero rows; no reviewers named |
| B5 | Reference registry unverified | `filename_date_proxy`, `verified=false` |
| B6 | Mapillary cache lacks provenance | 0 timestamps, 0 GPS, 0 camera, 0 attribution |
| B7 | Cross-corpus pHash gate would hard-fail 76 images | Pixel-level correlation 0.03–0.19 (false positives) |
| B8 | Verified distance metadata missing | FP-per-km unavailable |
| B9 | Route-level ground truth missing | Replay not runnable |

### 10.2 Governance conflict (must be raised, not silently resolved)

`master_rules.md` Rule 1 names the workspace as `D:\New folder (3)`, while the active
repository is `D:\COde\Major project\Saferoute-AI-Project`. `D:\New folder (3)` no longer
exists. Per the master rules' own preamble, conflicting documents must be raised and
resolved explicitly. Phase 46 records the conflict and does **not** rewrite the rule or
relocate data.

### 10.3 Residual risk

- The v3 candidate could be mistaken for v2 by a future contributor. Mitigation: identity
  labels + this report + the existing smoke marker.
- The Mapillary cache could be "discovered" later and mistaken for an independent corpus.
  Mitigation: this report's provenance section + a future `MANIFEST.json` marking it
  unverified.

---

## 11. Next steps (exact, in dependency order)

**Step 1 — Governance (no code).**
Name the governance owner; record the decision in `docs/datasets/sources.yaml` with
licence evidence and date; do not flip any flag until evidence exists.

**Step 2 — Checkpoint recovery (no inference).**
Restore the genuine v2 file from a documented backup; verify:

```powershell
Get-FileHash models\training\saferoute-yolo11-v2\weights\best.pt -Algorithm SHA256
# expected: B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA
```

If the hash differs, stop — it is not v2.

**Step 3 — Acquisition (only after Step 1 approval).**
Collect/prepare imagery; build the acquisition CSV using the template; then validate:

```powershell
.\.venv\Scripts\python.exe scripts\phase43\audit_sources.py
.\.venv\Scripts\python.exe scripts\phase43\split_acquisition.py --help
.\.venv\Scripts\python.exe scripts\phase43\ingest_acquisition.py --help
```

**Step 4 — Annotation (only after imagery is staged).**
Annotate per `annotation-v1`; produce `annotation_review.csv` and `adjudication.csv`.

**Step 5 — Freeze (only after reviews + verified reference registry).**

```powershell
.\.venv\Scripts\python.exe scripts\phase43\freeze_dataset.py --help
```

**Step 6 — Preflight (read-only).**

```powershell
.\.venv\Scripts\python.exe scripts\phase43\preflight_dataset.py --help
```

**Step 7 — Evaluation (only when Steps 2 + 6 pass).**
Then and only then run `scripts/evaluate_independent.py` against the hash-verified v2
checkpoint.

**Stop condition:** Phase 46 ends here. No further phase is started by this report.

---

## 12. Explicitly unverified / not assessed

| Item | State |
|---|---|
| Visual content/suitability of any Mapillary image | **Not assessed** (model cannot view images) |
| Whether Mapillary filenames map to live Mapillary IDs | **UNVERIFIED** (no sidecar) |
| Mapillary licence obligations for evaluation use | **UNVERIFIED** |
| Zenodo 18528034 content and independence | **UNVERIFIED** |
| Operator capture feasibility / routes / dates | **Not planned** |
| Annotation quality / inter-annotator agreement | **Not measured** |
| Detector accuracy, precision, recall, AP, FP-per-km | **NOT ASSESSED** |
| Route replay / recommendation eligibility | **Not run** |
| Effort estimates in §7.4 | **Planning estimates, not measured** |
| Locations outside the six scanned roots (e.g. other drives, cloud stores) | **Not searched** |

---

## 13. Sign-off

| Field | Value |
|---|---|
| Phase | 46 |
| Report | `reports/phase46_evidence_acquisition_plan.md` |
| Overall status | `BLOCKED` |
| Detector evaluation | `NOT_ASSESSED` |
| Acquisition performed | No |
| Annotation performed | No |
| Inference performed | No |
| Protected artifacts changed | No |
| Commits / pushes | None |
| Next gate | Operator approval of a source + checkpoint recovery |
