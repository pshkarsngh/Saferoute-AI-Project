# PHASE_03 — Class Mapping Proposal

Actual dataset classes (from `labels-YOLO/`, `labels/`, `annotations_coco.json`, `README.md`):

| id | actual name | proposed SafeRoute class | supported? | boxes |
|---|---|---|---|---|
| 0 | pothole | `pothole` | yes | 1261 |
| 1 | crack | `crack` | yes | 2519 |
| 2 | manhole | **`unsupported`** (excluded; never relabelled) | no | 957 |

Project target classes NOT covered by this dataset (0 instances):
`damaged_patch`, `waterlogging`, `uneven_surface`, `speed_bump`, `other`.

Initial detector scope: **pothole + crack only**.
