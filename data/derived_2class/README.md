# Derived two-class dataset — `data/derived_2class/`

Built by `scripts/build_derived_dataset_v2.py` for **PHASE 24C**, implementing the approved
PHASE 24B decisions:

- **D1 (M1)** — a derived **two-class** dataset (`0 pothole`, `1 crack`). The manhole label
  (class 2) is removed **only** here; the original annotations are preserved unchanged.
- **D2 (P-B)** — a date-atomic split; images with **no determinable capture date are quarantined**.
- **D3** — the single **zero-area** annotation is dropped **only** here.
- **D4** — one image kept per confirmed **exact-duplicate** group; every exclusion recorded.
- **D6** — a reproducibility manifest with source hashes is provided (`MANIFEST.json`).

## Layout

```
data/derived_2class/
  images/            junction/symlink -> ../../pothole_crack_manhole/data/images  (ORIGINAL bytes, no copy)
  labels/            derived two-class YOLO labels (0/1 only; class 2 and zero-area removed)
  MANIFEST.json      source hashes, split rule, exclusions, validation, artifact hashes
data/dataset_v2.yaml new dataset config (points at this root; original dataset.yaml untouched)
data/splits_v2/      train.txt / val.txt / test.txt / quarantined.txt / split_manifest.csv / SPLIT_NOTES.md
```

## Counts

| | Images | pothole boxes | crack boxes |
|---|---|---|---|
| **train** | 1,398 | 893 | 1,662 |
| **val** | 178 | 175 | 300 |
| **test** | 216 | 98 | 292 |
| **derived total** | **1,792** | **1,166** | **2,254** |
| quarantined (unknown date) | 212 | — | — |
| excluded (exact duplicates) | 5 | — | — |
| source total | 2,009 | 1,261 | 2,519 |

- **957 manhole boxes removed**; **1 zero-area row removed**.
- **336 derived images have empty labels** — images whose only boxes were manholes now serve as
  **background** images (YOLO convention). They are intentionally retained per decision M1.

## Limitations (honest)

1. **Capture dates come from filenames only.** Two files sharing a date are *assumed* to be one
   session; `vlcsnap-*` timestamps may reflect screenshot wall-clock rather than video content
   time. This grouping is a defensible proxy, **not** a verified session identity.
2. **212 images (`vlcsnap-NNNNN.jpg`) have no date** and are quarantined — their true session is
   unknown, so they cannot be proven disjoint from train/val/test.
3. **Not comparable to PHASE_09.** Membership changed, so the old test metrics (mAP@0.5 = 0.2615
   over 125 effectively-used images) do **not** carry over. A fresh single test evaluation is
   required (Rule 14) — **not performed in this phase**.
4. **Images are exposed via a junction** to the original folder, so the on-disk bytes remain the
   originals. Hash/dedup evidence refers to those original bytes.
5. **DATA-YOLO and RDD2022 remain excluded** (provenance/licence/conversion unresolved).
