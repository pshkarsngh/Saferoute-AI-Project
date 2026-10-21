# 04 — Dataset and Labeling

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Method:** read-only file enumeration, label-row parsing and SHA-256 duplicate scanning.
> **Related:** [`05-preprocessing-and-feature-engineering.md`](05-preprocessing-and-feature-engineering.md) ·
> [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) ·
> [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md)

---

## 1. Dataset inventory

| Dataset path | Role | Images | Label rows | Notes |
|---|---|---:|---:|---|
| `DATA-YOLO/` | Upstream source | — | — | **Licence unresolved** (F-08) |
| `data/datayolo_prep/` | 2-class preparation output | **1 789** | **2 535** | 0 empty labels |
| `data/derived_2class/` | Derived v2 corpus | **2 009** on disk / **1 792** labelled | **3 420** | 336 empty labels; class 0 = 1 166, class 1 = 2 254 |
| `data/splits_v2/` | Date-atomic split of the above | 1 792 assigned + 212 quarantined | — | train 1 398 / val 178 / test 216 |
| `data/pothole_crack_manhole/data/` | Third-party corpus | — | — | Carries Zenodo DOI `10.5281/zenodo.17834373` |

Split breakdown of `data/datayolo_prep`:

| Split | Images | Label rows | Class 0 (pothole) | Class 1 (crack) | Empty labels |
|---|---:|---:|---:|---:|---:|
| `train` | 1 251 | — | — | — | 0 |
| `val` | 269 | — | — | — | 0 |
| `test` | 269 | — | — | — | 0 |
| **Total** | **1 789** | **2 535** | **1 505** | **1 030** | **0** |

Class balance: **59.4 % pothole / 40.6 % crack** by instance. Mild imbalance; both
classes are represented in every split.

## 2. Label format

YOLO detection format — one `.txt` per image, one object per line:

```
<class_id> <x_center> <y_center> <width> <height>
```

All four geometry values are normalised to `[0, 1]` relative to image width and height.
Example verbatim from a real label file:

```
0 0.412109 0.617188 0.113281 0.089844
1 0.736328 0.552734 0.062500 0.041016
0 0.181641 0.744141 0.074219 0.060547
```

The two classes are:

| Class ID | Name | Base severity (`config/hazard_severity.yaml`) |
|---:|---|---:|
| `0` | `pothole` | 3.0 |
| `1` | `crack` | 1.5 |

A third upstream class, `open_manhole` (class 2), exists in the source corpus but is
**excluded, never relabelled** — see §3.

## 3. `data/datayolo_prep/MANIFEST.json`

The preparation manifest is the authoritative provenance record for this dataset.

| Field | Value |
|---|---|
| `images_total` | 2 736 |
| `eligible` | 1 789 |
| groups | 644 |
| Exclusion `contains_class2_manhole` | 821 |
| Exclusion `empty_background_label` | 106 |
| Exclusion `unlabelled_test_split` | 20 |

**Reading:** 947 of 2 736 source images were excluded (821 because they contain an
open manhole that the 2-class checkpoint cannot represent, 106 with an empty background
label, 20 belonging to an unlabelled test split). The remaining 1 789 are the eligible
2-class corpus.

The manifest also records a **leakage diagnostic on the original split**: 148 of 332
validation images also appear in the training set. The preparation pipeline therefore
re-groups by scene before splitting, which is why the original split was not reused.

## 4. Class policy — what is *not* trained

`config/detection.yaml` is explicit about the boundary between the project's target
hazard taxonomy and what the checkpoint actually learned.

**Supported (trained):** `0: pothole`, `1: crack`

**Present in the target taxonomy but not trained — reported as unsupported, never
fabricated (Rules 5, 9):**

- `manhole`
- `damaged_patch`
- `waterlogging`
- `uneven_surface`
- `speed_bump`

This is the correct implementation of Rule 5. The detector emits
`unsupported_class` for anything outside `{pothole, crack}` rather than guessing.

## 5. Split integrity and leakage

### 5.1 SHA-256 duplicate scan — `data/datayolo_prep`

| Scope | Duplicate groups | Files involved |
|---|---:|---:|
| Within `train` | 33 | 71 |
| Within `val` | 7 | — |
| Within `test` | 9 | — |
| **Across splits (train ∩ val ∩ test)** | **0** | **0** |

**Cross-split leakage is zero.** The 49 intra-split duplicate groups (F-14) mean the
effective training set is smaller than its nominal size — they inflate the apparent
sample count without adding information — but they do **not** contaminate the test
split.

### 5.2 SHA-256 duplicate scan — `data/derived_2class`

| Scope | Result |
|---|---|
| Duplicates overall | 5 groups |
| Within a split | 0 |
| Across splits | 0 |

The derived v2 corpus is cleaner than `datayolo_prep` on both counts.

### 5.3 `data/splits_v2` — date-atomic splitting

| Split | Images | Capture dates |
|---|---:|---|
| `train` | 1 398 | 2025-02-18, 2025-02-19 |
| `val` | 178 | 2025-02-16, 2025-02-23, 2025-03-16 |
| `test` | 216 | 2025-02-26 |
| `quarantined` | 212 | excluded from all splits |

Splitting by **capture date** rather than randomly means a frame cannot leak from train
into test through a near-duplicate neighbour — the leakage risk is removed by
construction rather than detected after the fact. The 212 quarantined images are held
out rather than discarded, which is consistent with Rule 15's "do not silently discard
data".

### 5.4 The `datayolo_prep` test split is not an independent holdout

**F-15.** `data/datayolo_prep/dataset.yaml` declares a `test:` key, but the manifest and
the dataset YAML both state that this is a **same-source, scene-grouped list**, not an
independent benchmark. Any accuracy conclusion drawn from it is weaker than an
independent holdout would support, and this must be stated whenever those numbers are
quoted.

`data/splits_v2` is the structurally stronger artefact and should be the basis for any
future headline metric.

### 5.5 The class-2 "corrupt image" effect on the v1 and v2 training runs

**F-37.** `config/training_canonical.yaml` records a defect that materially qualifies
every published metric:

> The original `data/dataset.yaml` declares `nc=2` but the source labels contain class-2
> (manhole) rows in **759 of 2 009** images. Ultralytics treats any label with
> `class >= nc` as corrupt and **discards the whole image**, so v1 and v2 were silently
> trained on only **861 of 1 406** images and evaluated on **264 of 402** (val) and
> **125 of 201** (test).

**What this means.**

| Quantity | Nominal (split file) | Actually used |
|---|---:|---:|
| Train images | 1 406 | **861** (61 %) |
| Validation images | 402 | **264** (66 %) |
| Test images | 201 | **125** (62 %) |

The failure mode was **silent** — Ultralytics drops the offending image and continues,
so nothing in the training log signals a problem. The effective evaluation set was
roughly two thirds of the nominal one, and the v1 metrics in
`logs/evaluation/evaluation_record.json` were measured on that reduced set.

**How it was fixed.** `config/training_canonical.yaml` was created as the single
documented canonical training workflow. It trains on the audited derived two-class
corpus (`data/dataset_v2.yaml` + `data/splits_v2`, date-atomic, **zero** corrupt
images), where the manhole box is removed **in the derived labels only** — the original
annotation is preserved unchanged, so nothing is silently relabelled (Rule 15).

**Assessment.** This is a well-diagnosed, well-documented defect, and the project
detected and fixed it. It remains open in two respects:

1. The **published metrics are still the ones measured under the defect.** The v1
   evaluation record refers to a 264/125-image evaluation, not to 402/201. Any quoted
   accuracy must be labelled accordingly.
2. The **v2 checkpoint that actually serves traffic** was promoted on a different
   601-image micro-set, and no evaluation of the serving checkpoint on the clean
   `data/splits_v2` test split exists. That measurement is the single highest-value
   next step (see [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) §7).

**Positive reading.** The project did exactly what Rule 15 and Rule 17 ask: it found a
data-integrity defect, diagnosed the mechanism, documented the cause in a config file,
and built a corrected dataset rather than patching labels in place. That belongs in the
project's favour — but the *metrics* it produced still need one clean re-measurement.

## 6. Serving dataset configurations

| File | Points to | Splits |
|---|---|---|
| `data/dataset.yaml` | `data/pothole_crack_manhole/data` | train 1 406 / val 402 / test 201 |
| `data/dataset_v2.yaml` | `data/derived_2class` | train 1 398 / val 178 / test 216 (+ quarantined 212) |

`config/detection.yaml` selects the **serving checkpoint** from
`models/training/saferoute-yolo11-v2/weights/best.pt`, which was trained against the v2
corpus.

## 7. Licence and attribution — the unresolved item

**F-08 / F-09. This is the most serious open item in the project.**

| Question | Answer |
|---|---|
| Does `DATA-YOLO/` contain a LICENSE file? | **Not found** |
| …a COPYING file? | **Not found** |
| …a NOTICE file? | **Not found** |
| …a TERMS file? | **Not found** |
| …any licence text anywhere in the repository for DATA-YOLO? | **Not found** |
| Is `DATA-YOLO/Pushkar Singh Baghel.pdf` a licence? | **No** — it is a personal résumé (a CV), not a licence grant. |
| Is `DATA-YOLO/Road_crack/README.md` informative? | **No** — the file is **0 bytes**. |
| Is the gap already recorded? | **Yes** — `docs/reports/DATA_YOLO_TRAINING_PREP.md` L139 records the same open item, and it is still unresolved. |

### 7.1 What *is* licensed

| Asset | Licence / attribution | Evidence |
|---|---|---|
| Mapillary imagery | CC-BY-SA 4.0, "(c) Mapillary contributors" | `config/imagery.yaml` `sources.mapillary.licence`; `src/imagery/mapillary_provider.py` docstring |
| `workspace_dashcam_v1` local archive | CC-BY 4.0, "Roboflow Universe / Pothole, Crack & Manhole Dataset" | `config/imagery.yaml` `sources.workspace_dashcam_v1` |
| OSM data (routing, facilities, geocoding) | ODbL, "© OpenStreetMap contributors" | `src/geocoding/nominatim.py` docstring; `config/facilities.yaml` header |
| `data/pothole_crack_manhole/data/` | Zenodo DOI `10.5281/zenodo.17834373` | `data/pothole_crack_manhole/data/README.md` |
| Map tiles | OpenFreeMap Liberty style | frontend map style constant |

### 7.2 Why this matters

Rule 15 requires licence verification *before* training; Rule 1 requires all artefacts to
stay inside the workspace. A dataset whose licence cannot be established is a risk to
(a) redistribution of the derived corpus and the trained weights, (b) any claim that the
model is legally usable, and (c) any submission that includes the dataset.

### 7.3 Recommended resolution paths

1. Obtain a written licence statement from the dataset's publisher and record it in
   `DATA-YOLO/LICENSE` plus a citation in `docs/`.
2. If no licence can be obtained, **exclude** the dataset and all weights trained on it
   from any distributable artefact and document the exclusion explicitly.
3. Re-train on a dataset with a clear licence — `data/pothole_crack_manhole/data/`
   already carries a Zenodo DOI, making it the natural candidate — and supersede
   `saferoute-yolo11-v2`.

Option 3 also addresses the accuracy weakness documented in
[`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md).

## 8. File-system note — hard links

The images under `data/datayolo_prep/` are **NTFS hard links** to the originals in
`DATA-YOLO/`, not copies. Consequences:

- Disk usage is shared; the dataset appears larger than it is on disk.
- Deleting or modifying a file in one location affects the other. This is a live hazard
  for anyone performing a "cleanup" of `DATA-YOLO/` and expecting `data/datayolo_prep/`
  to be unaffected. **No such cleanup was performed during this audit.**
- `scripts/prepare_datayolo_2class.py` is the tool that created the links and is the
  authority on the layout.

## 9. Dataset-related findings summary

| ID | Finding | Severity |
|---|---|---|
| F-08 | No licence file anywhere for `DATA-YOLO/` | **High** |
| F-09 | The gap was already raised in `DATA_YOLO_TRAINING_PREP.md` and remains open | Medium (process) |
| F-14 | 49 intra-split duplicate image groups in `data/datayolo_prep` | Medium |
| F-15 | `datayolo_prep`'s `test:` split is a same-source scene-grouped list, not an independent holdout | Medium |
| F-37 | v1/v2 were trained and evaluated on a silently reduced image set (861/1 406 train, 264/402 val, 125/201 test) because Ultralytics discards images containing class ≥ `nc` labels | Medium |
| — | `derived_2class` has 336 empty-label images | Low — empty labels are a legitimate negative class and are handled explicitly |
| — | Cross-split leakage is **zero** in both corpora | Positive finding |
| — | Date-atomic splitting in `splits_v2` removes leakage by construction | Positive finding |
| — | The manhole class is excluded, never relabelled | Positive finding — correct Rule 5 behaviour |

---

*All counts were produced by enumerating files and parsing label rows during the
2026-10-21 audit. Duplicates were detected by SHA-256 over file bytes. No dataset file
was created, modified, moved or deleted.*
