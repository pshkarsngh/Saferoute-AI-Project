# Independent evaluation dataset — governance

This directory holds the **contracts and tooling documentation** for the Phase 42
independent evaluation dataset. It does not contain imagery.

## Current state

| Item | State |
|---|---|
| Approved imagery sources | 0 |
| `data/independent/` | intentionally absent |
| Reference registry | proxy-only, `verified=false` |
| Dataset status | `NOT_ASSESSED` |
| Detector evaluation | blocked (dataset + genuine v2 missing) |

`data/independent/` is not created empty on purpose. An empty directory would
falsely suggest the Phase 42 P1 `independent_dataset_missing` blocker had been
addressed.

## Documents

- [`ACQUISITION_PLAN_V1.md`](ACQUISITION_PLAN_V1.md) — sources, coverage,
  provenance, session model and approval gates (P2).
- [`ANNOTATION_SPEC_V1.md`](ANNOTATION_SPEC_V1.md) — classes, bounding-box rules,
  uncertainty handling, A/B review and adjudication (P3).
- [`sources.yaml`](sources.yaml) — source/licence registry. Approves nothing by
  default.
- [`templates/`](templates/) — CSV headers for acquisition, reviews,
  adjudication, sessions and the reference registry.

## Workflow

```
approve sources (human decision, recorded in sources.yaml)
  → collect/export approved imagery + draft acquisition manifest
  → scripts/phase43/split_acquisition.py
  → scripts/phase43/ingest_acquisition.py --dry-run   # then without --dry-run
  → annotate (A + B) and adjudicate
  → replace proxy registry with a verified collection-session registry
  → scripts/phase43/freeze_dataset.py --frozen-by <owner>
  → scripts/phase43/preflight_dataset.py
```

`freeze_dataset.py` refuses to write a frozen manifest while any provenance,
geometry, session, review or leakage error remains. Preflight never loads the
detector.

## Produced dataset layout (once real data exists)

```
data/independent/
  images/{train,val,test}/
  labels/{train,val,test}/
  manifests/
    acquisition_manifest.csv
    collection_sessions.csv
    annotation_review.csv
    adjudication.csv
    training_sessions.csv
    independent_manifest.json
    dataset_hashes.json
  dataset.yaml
  README.md
```

`dataset_hashes.json` is a content-hash attestation, not a cryptographic
signature.

## Non-negotiable rules

- No unapproved download or licence acceptance.
- No undocumented imagery and no fabricated annotations/reviewers.
- Whole sessions and routes stay in one split; adjacent frames are not
  independent observations.
- Missing evidence is `NOT_ASSESSED`, never defaulted to safe.
- The test split is locked and must not be used for tuning.
