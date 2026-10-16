# PHASE 24C — derived split notes (`data/splits_v2/`)

This directory holds the **derived** split files for the approved P-B split. The original
`data/splits/*.txt` files are **not modified**.

## Split rule (date-atomic)

| Capture date | Split |
|---|---|
| 2025-02-18 | train |
| 2025-02-19 | train |
| 2025-03-16 | val |
| 2025-02-23 | val |
| 2025-02-16 | val |
| 2025-02-26 | test |
| **no determinable date** | **quarantine (excluded from all splits)** |

Guarantee: under this rule, **no capture date spans more than one split** (validated in
`MANIFEST.json → validation.checks.no_capture_date_spans_multiple_splits`).

## Files

- `train.txt`, `val.txt`, `test.txt` — absolute paths to derived images
  (`data/derived_2class/images/<stem>.jpg`), one per line.
- `quarantined.txt` — the 212 images with no determinable capture date.
- `split_manifest.csv` — one row per source image:
  `stem, capture_date, split, kept, exclude_reason, n_pothole_src, n_crack_src,
  n_manhole_dropped, n_zero_area_dropped, sha256_image, keeper_of`.

## Sizes

| Split | Images |
|---|---|
| train | 1,398 |
| val | 178 |
| test | 216 |
| quarantined | 212 |
| excluded (duplicates) | 5 |
| source | 2,009 |

## Limitations

- Dates are **filename-derived**; a shared date is treated as one session. See
  `data/derived_2class/README.md` for the full caveat.
- The 212 quarantined images are unused pending a separate decision.
- This split **breaks comparability** with PHASE_09 metrics; a fresh test evaluation is required.
