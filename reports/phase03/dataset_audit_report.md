# PHASE_03 — Dataset Audit Report (measured)

- Generated (UTC): 2026-10-11T19:14:11.534661+00:00
- Dataset: `D:\New folder (3)\data\pothole_crack_manhole\data`
- Read-only: True
- Versions: Python 3.12.10, numpy 2.5.3, cv2 5.0.0
- Config: near_hamming=5, time_gap_sec=2, seed=42

## 1. Counts
- images: 2009
- labels-YOLO: 2009
- labels (polygon): 2009
- train/val/test: **none present** (single pool)

## 2. Pairing
- images without YOLO label: 0
- YOLO labels without image: 0
- images without polygon label: 0
- polygon labels without image: 0

## 3. Decode
- decoded ok: 2009
- failures: 0 []
- dimensions: {'640x360': 2009}

## 4. Annotations
- malformed YOLO lines: 0
- out-of-range YOLO boxes: 0
- zero-size YOLO boxes: 1
- beyond-image-bounds YOLO boxes: 63
- invalid class-id YOLO: 0 []
- malformed polygon lines: 0
- out-of-range polygon: 45
- zero-extent polygon: 1
- invalid class-id polygon: 0 []

## 5. Actual format & class IDs
- format: YOLO txt (`labels-YOLO/`) + normalized polygon txt (`labels/`) + COCO JSON
- IDs found (YOLO boxes): {0: 1261, 1: 2519, 2: 957}
- boxes by name: {'pothole': 1261, 'crack': 2519, 'manhole': 957}
- images containing each class: {'pothole': 795, 'crack': 1375, 'manhole': 759}
- names provenance: bundled `README.md` and COCO `categories` ({0: 'pothole', 1: 'crack', 2: 'manhole'})

## 6. Class mapping proposal (see class_mapping_proposal.md)

## 7. Empty labels
- images with 0 objects: 0

## 8. Duplicates / near-duplicates
- exact duplicate groups: 5
- content groups (exact+near+time): 1771
- multi-image groups: 118 (356 images)

## 9. Split integrity & leakage
- source policy: not documented (single-pool dataset)
- cross-split overlap: n/a - no source splits
- grouping signals: ['exact byte duplicate (sha256)', 'near duplicate (dHash hamming <= 5)', 'same-date capture adjacency (<= 2s) as source/session signal']
- residual risk: Frames from the same capture run may still be visually distinct yet share a source/session/road segment; filenames encode capture time only, so true session/device/segment identity is NOT provable from the data. The proposed split keeps content/time groups intact to reduce leakage; residual risk noted.

## 10. Proposed split (NOT created)
- method: group-aware (content+time groups kept intact), deterministic seed (seed 42)
- images per split: {'train': 1406, 'val': 402, 'test': 201}
- boxes per class per split: {'train': {'crack': 1741, 'pothole': 863, 'manhole': 697}, 'val': {'crack': 537, 'pothole': 264, 'manhole': 172}, 'test': {'manhole': 88, 'pothole': 134, 'crack': 241}}
- created on disk: False

## 11. COCO reconciliation
- total boxes YOLO vs COCO: 4737 vs 4737
- images YOLO vs COCO: [2009, 2009]
- per-class [YOLO, COCO]: {'pothole': [1261, 1261], 'crack': [2519, 2519], 'manhole': [957, 957]}
- COCO bad bbox / bad ref / bad category: 46 / 0 / 0
- COCO has info/licenses: False / False

## 12. Path safety
- dataset inside workspace: True
- unsafe file names: 0
