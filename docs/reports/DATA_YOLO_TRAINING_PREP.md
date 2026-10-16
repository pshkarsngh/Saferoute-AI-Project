# DATA-YOLO Training-Preparation Report (two-class pothole / crack)

**Stage:** DATA-YOLO training preparation (audit + split + config) — **preparation only, no training**
**Date:** 2026-10-16
**Scope:** turn the labelled part of `DATA-YOLO` into a two-class (0=pothole, 1=crack) training candidate **without**
modifying DATA-YOLO, the original labels, the current model, or the serving configuration.
**Generator:** `scripts/prepare_datayolo_2class.py` (reads DATA-YOLO read-only; writes only to `data/datayolo_prep/`).

> Safety: DATA-YOLO is opened read-only. Nothing is written under `DATA-YOLO/`. Images are exposed in the prep tree as
> NTFS **hard links** (byte-identical, no duplication); labels are **byte-for-byte copies** of the originals (never
> edited or remapped). All outputs live under the isolated directory `data/datayolo_prep/`.

---

## 1. DATA-YOLO layout — paths and counts

Labelled detection set root: `DATA-YOLO\Datasets\dataset\dataset\`

| Split | Image dir | Images | Label dir | Label files |
|---|---|---:|---|---:|
| train | `train\images\` | 2,236 | `train\labels\` | 2,236 |
| valid | `valid\images\` | 480 | `valid\labels\` | 480 |
| test | `test\images\` | 20 | `test\labels\` | **0 (unlabelled)** |

- Label format: clean 5-field YOLO (`cls xc yc w h`). No `data.yaml` exists anywhere in DATA-YOLO.
- Formats present in the labelled set: `.jpg`, `.jpeg`, `.png`.
- The rest of DATA-YOLO is **not** detection data and was ignored: `Datasets2` (number-plate VOC XML),
  `Road_crack` (semantic masks), `Road_Condition_Dataset` (classification), and the large unlabelled image folders.

## 2. Class mapping (verified, not assumed)

- Label class IDs were verified against the COCO JSONs (`category_id − 1`): **0 = pothole, 1 = cracks, 2 = open_manhole**
  (100 % agreement on train + valid).
- This matches SafeRoute's target mapping **0 = pothole, 1 = crack**.
- **Decision:** keep only classes `{0,1}`. Any image containing a class-2 (open_manhole) box is **excluded** — never
  relabelled. Cost: 821 images excluded; of these only **3** also contained crack boxes (8 crack boxes lost in total).

## 3. Label audit (whole labelled set, 2,736 images)

| Check | Result |
|---|---:|
| labels missing | 20 (all `test/`, unlabelled) |
| label files empty | 106 (all `train/` background images; `valid/` 0) |
| malformed YOLO rows | **0** |
| invalid class IDs | **0** |
| normalised coords out of range | **0** |
| images that fail to decode (OpenCV) | **0** |
| extension/content mismatch | **29** (27 WebP-as-`.jpg`, 2 PNG-as-`.jpg`) — all decode successfully |
| `test/` labels available | **none** → DATA-YOLO `test/` is unusable as a benchmark |

The 29 extension mismatches are readable but **must not be re-encoded** (would alter the source); they are kept as-is
and remain in the eligible set.

## 4. Duplicates and augmentation / base-image relationships

- Offline augmentation is pervasive: of the 1,789 eligible images, **1,132 carry `_aug*` suffixes** and 657 are
  originals (`_aug_flip`, `_aug_vertical_flip`, `_aug_rotate`, `_aug_brightness_contrast`).
- Exact byte-duplicates exist **and cross the original splits** (e.g. `train\1001.jpg` ≡ `test\istockphoto-…jpg`;
  `train\1002_aug_flip.jpg` ≡ `valid\1002_aug_flip.jpg`; `1002.jpg` ≡ `1098.jpg`).
- **Grouping rule used:** two images join the same scene-group if they are byte-identical (`sha256`) **or** share a base
  stem (after stripping `_aug…`). Result: **644 scene-groups** for 1,789 eligible images.
  - Group-size histogram: 1 → 221 groups, 2 → 142, 3 → 92, 4 → 50, 5 → 98, 6 → 9, 7 → 13, 8 → 8, 9 → 9, 10 → 1, 18 → 1
    (largest group = 18, base `259`).
  - **36 groups contain members from both the original `train` and `valid` splits.**
- **Original-split leakage diagnostic:** if the original `train`/`valid` assignment were reused verbatim,
  **148 / 332 (44.6 %)** of eligible `valid` images would share a scene-group with `train`. → the original split is
  **not safe** to reuse; a grouped re-split is required.

## 5. Proposed split (scene-grouped, reproducible)

Groups (not images) are assigned with `random.Random(seed=42)`: ~15 % to `val`, ~15 % to `test`, remainder `train`.
No scene-group spans more than one split.

| Split | Images | Pothole boxes | Crack boxes | Imgs w/ pothole | Imgs w/ crack |
|---|---:|---:|---:|---:|---:|
| train | 1,251 | 1,025 | 736 | 638 | 643 |
| val | 269 | 230 | 139 | 148 | 127 |
| test (same-source hold-out) | 269 | 250 | 155 | 148 | 129 |

- `manifests/val_dedup.txt` = **103** images, one representative per val group (prefer a non-aug original) for an
  **unbiased** metric without in-group autocorrelation.
- Validation checks (all pass): no image in two splits; every manifest image/label exists; manifests contain only
  classes {0,1}; no group spans splits; val_dedup ⊆ val; all eligible images assigned exactly once.
- **Caveat:** the grouped `test` list is **same-source** (same domain as train) and is **not an independent benchmark**.
  It exists only because the SafeRoute training harness requires a `test:` key (see §7). DATA-YOLO's own `test/` split
  has no labels and cannot be used.

## 6. Dataset configuration

- **No reusable DATA-YOLO config exists** (no `*.yaml` in DATA-YOLO). A new one was created **inside** the separate
  preparation directory:
  - `data/datayolo_prep/dataset.yaml` → `names: {0: pothole, 1: crack}`, `train/val/test` → the grouped manifests.
  - This is **separate from** `data/dataset.yaml` (the serving v2 dataset) and does not overwrite it.

## 7. Training an experimental candidate (documented, NOT run)

The existing entry point is unchanged: `scripts/train_baseline.py <config-name>` (config resolved under `config/`).
A dedicated, clearly-marked experimental config was created: **`config/training_datayolo.yaml`**.

Exact command (run only after this report is approved):

```
.venv\Scripts\python.exe scripts\train_baseline.py training_datayolo.yaml
```

Why it cannot overwrite the serving model:

- `paths.name = saferoute-yolo11-datayolo-exp` → output goes to `models/training/saferoute-yolo11-datayolo-exp/`
  (v2 lives in `models/training/saferoute-yolo11-v2/`).
- `paths.log_dir = logs/training/saferoute-yolo11-datayolo-exp` → separate run record/log.
- `dataset.config_path = data/datayolo_prep/dataset.yaml` → the isolated prep dataset.
- The serving config `config/detection.yaml` (→ v2 `best.pt`, sha256 `B6354A56…8800BA`) is untouched and is **never read
  or written** by this run.
- `model.pretrained_weights` defaults to `yolo11n.pt`. To *transfer-learn from the current detector* instead, change it
  to `models/training/saferoute-yolo11-v2/weights/best.pt` (read-only; still writes to the new output dir).

Reference (v2, for exact-consistency): `config/training_improved.yaml` + `data/dataset.yaml`, 150 epochs, AdamW,
batch 16, imgsz 640, seed 42.

## 8. Summary

- **Eligible (pothole/crack-only, labelled) images: 1,789** across **644 scene-groups**.
- Labelled images in DATA-YOLO: **2,716** (train 2,236 + valid 480); `test/` 20 images are unlabelled.
- **Exclusions by reason** (2,736 audited):

  | Reason | Count |
  |---|---:|
  | contains class-2 (open_manhole) | 821 (train 673 / valid 148) |
  | empty background label | 106 (train) |
  | unlabelled `test/` split | 20 |
  | **total excluded** | **947** |

- Prepared class distribution: train 1,025 pothole + 736 crack boxes; val 230 + 139; test(same-source) 250 + 155.
- Additional related copy counted: 1,132 eligible images are `_aug*` copies of 657 originals; 36 groups mix original
  train+valid → grouping required and applied.

## Unresolved / data-quality issues

1. **Licensing / provenance of DATA-YOLO remains unresolved** (not investigated further in this task, per instruction).
   Rights to reuse/redistribute cannot yet be asserted — resolve before any deployed use.
2. **No independent benchmark.** No labelled `test/`, and any DATA-YOLO hold-out is same-source; real generalisation
   must be measured on a separate capture (SafeRoute/Mapillary), not on this data.
3. **Domain shift** vs the Italian GoPro SafeRoute dataset (heterogeneous resolutions/stock photos here).
4. **29 mislabelled-extension files** (27 WebP, 2 PNG) — usable, but format-strict tooling should account for them.
5. **Perceptual near-duplicate check only** (dHash): same-scene/different-crop relations cannot be fully excluded
   without a human visual review.
6. Observation: the v2 run's split pointed at `data/pothole_crack_manhole/data/labels/` (polygon, 9-field), which
   Ultralytics auto-converted from segments; `labels-YOLO/` was not the path used. Unrelated to this prep but worth
   noting for label-source consistency.

## Files created (all new; nothing modified)

| Path | Purpose |
|---|---|
| `scripts/prepare_datayolo_2class.py` | audit + split + config generator (read-only on DATA-YOLO) |
| `data/datayolo_prep/dataset.yaml` | proposed two-class dataset config |
| `data/datayolo_prep/manifests/{train,val,test,val_dedup}.txt` | grouped split lists |
| `data/datayolo_prep/manifest.csv` | per-eligible-image record (group, split, classes) |
| `data/datayolo_prep/original_split_audit.csv` | untouched record of every original split assignment |
| `data/datayolo_prep/MANIFEST.json` | reproducibility, counts, exclusions, validation |
| `data/datayolo_prep/images/`, `labels/`, `.gitignore` | hard-linked images + copied labels (bulk ignored by git) |
| `config/training_datayolo.yaml` | proposed **experimental** training config (not promoted) |
| `docs/reports/DATA_YOLO_TRAINING_PREP.md` | this report |

## Next action

**Do not train.** Review this report and the proposed config. On approval, the candidate can be trained with the
command in §7 into a separate output directory; the serving v2 checkpoint and `config/detection.yaml` stay untouched.
