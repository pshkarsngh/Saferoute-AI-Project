# Phase 43 — P3 Annotation Specification (v1)

> **Status:** specification frozen; **no annotations performed**
> **Annotation version:** `annotation-v1`
> **Classes:** `0 = pothole`, `1 = crack`
> **Applies to:** `data/independent/` frozen evaluation dataset

This document is the annotation contract. A label file that contradicts it must
not be frozen. The version string `annotation-v1` is recorded in every review row,
every adjudication row, and in `manifests/independent_manifest.json`.

---

## 1. Class definitions

The serving detector supports exactly two classes. No other class may appear in a
label file.

| id | name | Definition |
|---|---|---|
| `0` | `pothole` | A distinct depression or hole in the road surface caused by material loss or structural failure, bounded by visible pavement edges. Includes patched potholes only when the depression is still visually distinct. |
| `1` | `crack` | A linear fracture in the road surface: longitudinal, transverse, diagonal, block, alligator/fatigue cracking. Includes sealed cracks only when the crack line remains visible. |

Not annotated as either class:

- manhole covers, drain grates, utility covers;
- painted markings, shadows, tar seams, tyre marks;
- gravel, patching, resurfacing boundaries without a fracture/depression;
- vegetation, debris, animals, vehicles, people;
- damage on non-road surfaces (kerbs, footpaths, walls).

An image may contain both classes. Each distinct hazard gets its own box.

---

## 2. Bounding-box rules

Labels use the YOLO format, one box per line:

```
<class_id> <cx> <cy> <w> <h>
```

All four coordinates are normalised to `[0, 1]` against the **original** image
width and height. Do not resize first. The Phase 42 validator allows at most 1%
boundary overrun and clamps it; larger overruns are rejected.

### 2.1 Tightness

- A box must tightly enclose the visible extent of the hazard.
- Include the whole pothole rim / crack length within the image.
- Do not pad boxes to a fixed size, and do not shrink to the darkest core.
- One hazard = one box. Do not split one pothole into several boxes.
- Do not merge two separated hazards into one box.

### 2.2 Partially visible hazards

- If the hazard is cut by the image border but a usable portion is visible,
  annotate the visible portion and extend the box to the border.
- If less than roughly one quarter of the hazard is visible, or the visible part
  is not identifiable as pothole/crack, mark the image `uncertain` rather than
  guessing.
- If the hazard is mostly occluded by a vehicle/person but the visible evidence
  is unambiguous, annotate the visible portion and note the occlusion.

### 2.3 Overlapping hazards

- Do **not** merge overlapping boxes. Each hazard keeps its own box even when
  boxes intersect.
- A pothole inside an alligator-crack patch gets both a `pothole` box and a
  `crack` box where each is independently visible.
- If two candidates might be the same physical defect (e.g. a crack that has
  spalled into a pothole), adjudication decides the class; exactly one box per
  physical defect unless both classes are genuinely present.

### 2.4 Low-visibility hazards

- Annotate when a trained human can identify the hazard with reasonable
  confidence (wet surface, dusk, motion blur, glare, shadow).
- Do not annotate a shape you cannot distinguish from texture, staining or a
  shadow.
- Do not "helpfully" annotate hazards you infer from context but cannot see.
- Low-visibility images that are labelable are still valid evaluation images;
  record the `lighting`/`weather` value in the acquisition manifest.

### 2.5 Ambiguous road damage

- If two annotators could reasonably disagree on class (crack vs pothole) or on
  extent, the image is adjudicated. Adjudication records the chosen outcome; the
  ambiguity itself is kept in the review notes.
- Persistent ambiguity after adjudication → `final_status = uncertain`, and the
  image is **moved out of** `images/*` before freeze.

---

## 3. Negatives, uncertainty and exclusion

The dataset distinguishes three states. They are not interchangeable.

| State | Label file | Adjudication | In frozen split? |
|---|---|---|---|
| Positive | ≥ 1 box | `outcome` ∈ {`agree`, `corrected_a`, `corrected_b`, `new_annotation`}, `final_status = accepted` | yes |
| **Verified negative** | **empty file (0 bytes)** | `outcome = verified_negative`, `final_status = accepted` | yes |
| Uncertain | — | `final_status = uncertain` | **no** — move out of `images/*` |
| Excluded | — | `final_status = excluded` | **no** — move out of `images/*` |

Rules:

- A **missing** label file is a validation error. It is not a negative.
- A **verified negative** requires both reviewers to have recorded `box_count = 0`
  and adjudication to confirm `verified_negative`. An unreviewed empty file is
  rejected.
- A verified negative is an image a human has inspected and confirmed contains no
  pothole and no crack. "No label yet" is not a negative.
- The locked **test** split accepts only `final_status = accepted`. Excluded and
  uncertain images must be removed from `images/test/` before freeze.

---

## 4. Review protocol

Every image in the frozen dataset requires **two independent reviews** and one
**adjudication**.

1. **Annotator A** produces the initial boxes and writes a review row with
   `role = annotator_a`.
2. **Annotator B** independently reviews the image (fresh look, not editing A's
   live file) and writes `role = annotator_b`.
3. Annotator A and B must be **different people**. The same reviewer id for both
   roles is a validation error.
4. **Adjudicator** resolves disagreements, may correct either annotation or add a
   box, and writes the final adjudication row.
5. The adjudicator's `resolved_box_count` must equal the number of lines in the
   final label file.

Review rows are append-only evidence. Do not rewrite history to make agreement
look higher; the agreement fraction is reported as recorded.

### 4.1 Review status values

`review_status` ∈ `approved`, `changes_requested`, `excluded`, `uncertain`.

`box_count` is the number of boxes that reviewer saw/produced for the image.

### 4.2 Adjudication outcomes

`outcome` ∈:

| outcome | Meaning |
|---|---|
| `agree` | A and B agreed; no change needed |
| `corrected_a` | A's annotation was corrected |
| `corrected_b` | B's annotation was corrected |
| `new_annotation` | A third reading produced the final boxes |
| `excluded_uncertain` | Image removed as unlabelable/out of scope |
| `verified_negative` | Image confirmed to contain no hazard; empty label file |

`final_status` ∈ `accepted`, `excluded`, `uncertain`.

---

## 5. Files and columns

All review evidence lives under `data/independent/manifests/`:

- `annotation_review.csv` — one row per reviewer per image.
- `adjudication.csv` — one row per image.
- `acquisition_manifest.csv` — provenance for every image (P2).
- `collection_sessions.csv` — session summary derived from provenance.
- `training_sessions.csv` — reference registry (proxy or verified).
- `independent_manifest.json` — frozen manifest consumed by Phase 42.
- `dataset_hashes.json` — content-hash attestation.

### 5.1 `annotation_review.csv`

```
image_id,reviewer_id,role,annotation_version,review_status,box_count,reviewed_at,note
```

- `role` = `annotator_a` or `annotator_b`.
- `annotation_version` = `annotation-v1` (must match the freeze version).
- `reviewed_at` = ISO-8601 timestamp.

### 5.2 `adjudication.csv`

```
image_id,adjudicator_id,annotation_version,outcome,final_status,resolved_box_count,decided_at,note
```

### 5.3 `training_sessions.csv` (reference registry)

```
session_id,session_id_quality,verified,split,image_count,capture_date,camera_ids,route_ids,evidence
```

- `verified` must be `true` and `session_id_quality` must be
  `verified_collection_session` for the Phase 42 independence gate to pass.
- The filename-date proxy currently produced by
  `scripts/phase43/build_reference_registry.py` sets `verified = false` and can
  never yield `PASS`.

---

## 6. Validation and freeze gates

Before freeze, all of the following must hold:

1. Every image has an acquisition row with approved source and licence evidence.
2. Every image has a label file; empty files are adjudicated verified negatives.
3. Boxes are within `[0, 1]` (≤1% tolerance), `w > 0`, `h > 0`, class ∈ {0, 1}.
4. Each session and route stays within one split.
5. Each image has two reviews from distinct reviewers, both A and B roles.
6. Each image has exactly one adjudication row at `annotation-v1`.
7. `resolved_box_count` equals the label line count.
8. The test split contains only `accepted` images.
9. No exact/perceptual duplicate against the reference corpus.
10. The reference registry is present and verified (otherwise `NOT_ASSESSED`).

`scripts/phase43/freeze_dataset.py` refuses to write a frozen manifest while any
error remains. `scripts/phase43/preflight_dataset.py` re-checks the frozen
artifacts without running inference.

---

## 7. Locked test split

- The test split is frozen at `annotation-v1`.
- It must never be used for training, threshold tuning, prompt changes, model
  selection, or annotation-policy iteration.
- Any change to test content requires a new dataset version and a new freeze; the
  old hashes are retained, not overwritten in place.
- `dataset_hashes.json` records `test_split_sha256` so silent edits are detected.

---

## 8. What this specification does not do

It does not create imagery, labels, reviewers, or agreement scores. A dataset can
only satisfy it through real collection and real human annotation.
