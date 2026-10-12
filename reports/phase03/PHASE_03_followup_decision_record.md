# PHASE_03 — Follow-up Decision Record (split candidate & annotation policy)

> **Phase:** PHASE_03 — Dataset Integrity, Class-Mapping & Split Audit (approved follow-up)
> **Status:** decisions recorded; **no training authorised**, **no derived labels generated**
> **Date (actual):** 2026-10-12
> **Workspace:** `D:\New folder (3)`
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) ·
> [`../phases/PHASE_03.md`](../phases/PHASE_03.md) ·
> [`PHASE_03_report.md`](../reports/PHASE_03_report.md)

This record captures the user's follow-up authorisation. It does **not** authorise training,
PHASE_04, split-directory creation, or the generation/modification of any training labels.

---

## A. Split-manifest decision

| Item | Decision |
|---|---|
| Selected candidate | `reports/phase03/split_manifest_proposal_sessionaware_v2_strict30s.csv` |
| Status | **Selected candidate for further review ONLY.** Not fully approved. Not training-authorised. |
| Primary manifest | `reports/phase03/split_manifest_proposal_sessionaware_v2.csv` — preserved unchanged |
| Existing proposals | `split_manifest_proposal.csv`, `split_manifest_proposal_sessionaware.csv` — preserved unchanged |
| Validation retained | `reports/phase03/split_manifest_proposal_v2_validation.json` and `split_manifest_proposal_v2_validation.md` |
| Split directories | **none created**; no images or labels copied or moved |

**Recorded candidate facts** (measured, for review only): strict-30 s grouping · 61 groups ·
largest group 389 · train/val/test = **1406 / 402 / 201** · 0 group / exact / dHash≤5 /
session≤5 s / session≤30 s crossings · boxes (pothole/crack/manhole) 896/1864/701 ·
226/481/165 · 139/174/91.  Residual risk (disclosed): ≤60 s crossing 21 pairs (42 images);
≤300 s 41 pairs (79 images); dHash 6–10 crossing 3 / 56 / 301; the 212-frame untimed block
and the 2025-03-16 day concentrate in train. **Not leakage-free.**

**ADOPTED SPLIT POLICY (user decision, 2026-10-12 — closure):** whole-capture-day holdout with
the untimed block co-located with its near-duplicate partner day 2025-03-16.

| Item | Decision |
|---|---|
| Policy | whole-capture-day holdout (sessions = calendar capture days; `vlcsnap_numeric` 212 frames co-located with 2025-03-16) |
| train | 2025-02-18 + 2025-02-19 = **1,402** images · boxes pothole 897 / crack 1,670 / manhole 751 |
| val | 2025-03-16∪untimed (348) + 2025-02-23 (39) + 2025-02-16 (3) = **390** · pothole 266 / crack 555 / manhole 89 |
| test | 2025-02-26 = **217** images · pothole 98 / crack 294 / manhole 115 |
| Ratio | 69.8 / 19.4 / 10.8 — **~0.8 % deviation from 70/20/10 explicitly accepted by user** |
| Leakage (measured) | session adjacencies ≤300 s = **0**; exact = **0**; test↔train dHash ≤6 = **0**, ≤8 = 5 pairs, ≤10 = 41 pairs; total dHash 6/8/10 = 7/66/298 pairs. **Not leakage-free.** |
| Existing proposals | all previous manifest CSVs preserved unchanged (proposal history only) |
| Manifest for adopted policy | NOT written to disk; deterministic composition documented here; generating it is a separate pre-training approval |
| **Gate A4 — class mapping** | **CONFIRMED (2026-10-12):** id 0=pothole → `pothole`, id 1=crack → `crack`, id 2=manhole → `unsupported` (excluded, **never** relabelled) |

## B. Annotation policy — APPROVED (P1–P6), with clarification

Approved as clarified:

- **Clip only** verified, geometrically justified edge-rounding errors in **future derived** labels.
- Documented maximum overshoot is **0.01562** normalised units. If an overshoot **exceeds** this
  bound, **exclude and disclose** the affected annotation — never silently clamp.
- **Recompute** boxes after clipping; retain only valid, non-zero-area boxes.
- **Exclude** the single zero-area crack annotation from future derived training labels; **do not
  relabel or delete** its original annotation.
- **Preserve** the original dataset and labels byte-for-byte.
- **Record** clipping, exclusion, before/after counts, and validation results for any future
  derived-label operation.
- Continue excluding **class 2 (manhole)** from the initial detector without relabelling.

> **This approval does NOT authorise generating or modifying any training labels.**

## C. Audit lists generated (read-only source inspection)

| Artefact | Rows | Purpose |
|---|---|---|
| `reports/phase03/annotation_clip_candidates_v1.csv` | 62 | verified edge-rounding clip candidates |
| `reports/phase03/annotation_manual_review_v1.csv` | 1 | annotation flagged for manual review |
| `reports/phase03/annotation_exclusion_list_v1.csv` | 2 | zero-area crack object to exclude + boundary over-bound (EXCEEDS_BOUND) exclusion |

Each row identifies the file, image, YOLO line, class, measured anomaly, related polygon line,
category, verification, proposed action and reason. All lists are ASCII and workspace-relative.

### Reconciliation against the audit inventory

| Audit inventory | This task | Match |
|---|---|---|
| Derived YOLO boxes beyond `[0,1]` = 63 | clip 62 + manual 1 = **63** | ✅ |
| Polygon vertices outside `[0,1]` = 45 lines | polygon_edge_rounding 44 + manual 1 = **45** | ✅ |
| Zero-size YOLO box / zero-extent polygon = 1 | exclusion list = **1** | ✅ |
| Class split of the 63 | crack 51 · manhole 8 · pothole 4 | ✅ |

**Clip candidate breakdown:** 44 `polygon_edge_rounding` (verified; polygon-driven) +
18 `derived_box_float_boundary` (verified; polygon within `[0,1]`, derived box at the boundary
within float tolerance; clip is a no-op). Classes: crack 50 · pothole 4 · manhole 8 (manhole
is out of detector scope).

**Flagged for manual review (1):** `labels-YOLO/vlcsnap-2025-02-18-23h26m05s423.txt` line 3
(crack) — polygon overshoot **0.015625**, which marginally exceeds the documented rounded bound
**0.01562**. Proposed action per the stated rule: *exclude and disclose*; however it is
geometrically a legitimate edge-rounding case at the documented maximum, so the bound
interpretation (0.01562 exact vs the rounded value of 0.015625) needs your decision before
this one object is clipped or excluded.

**RESOLVED (2026-10-12, authorised follow-up):** the user decided this boundary annotation is
**excluded from future derived training labels**. Measured polygon overshoot **0.015625**
exceeds the documented clipping bound **0.01562**, so per policy P1 item 4 it is *exclude and
disclose* — never clamped. The annotation was added to
`reports/phase03/annotation_exclusion_list_v1.csv` (row for
`vlcsnap-2025-02-18-23h26m05s423.txt` line 3, category `EXCEEDS_BOUND`), and it is **not**
present in `annotation_clip_candidates_v1.csv`. The manual-review row in
`annotation_manual_review_v1.csv` is marked `manual_review_resolved_excluded`. It is not
simultaneously presented as eligible for clipping and excluded. The zero-area crack exclusion
(`vlcsnap-00058.txt`) remains in the same list but is separately identified by its
`measured_anomaly` and `reason`. No derived training labels were generated or modified, and
the original YOLO label, polygon label, image and COCO source annotations are preserved.

**Discrepancy note:** the only discrepancy found was the above rounded-bound boundary case,
now resolved (excluded and disclosed); all other counts reconcile exactly with the audit
inventory. No object was found whose polygon overshoot materially exceeded the documented
maximum.

## D. Report typo correction

- File: `docs/reports/PHASE_03_report.md` § C (zero-size box row).
- Change: `class 2 (manhole)` → `class 1 (crack)` (single token change).
- Before edit — MD5 `2CEC7019B88775EA8DECF2BE6DF9D760`, SHA-256
  `E190134BA63ABF59A9E66BD5C2A8EADE771599E729AA8F29A8395F172DF2D4B8`, 14,843 bytes, 291 lines.
- After edit — see final verification below. No other content changed.
- **Residual wording note (corrected 2026-10-12, authorised follow-up):** the same row's trailing
  wording “; excluded from pothole/crack scope” was inconsistent because the object is a crack
  (in scope). It was corrected in this follow-up; see
  [`docs/reports/PHASE_03_report.md`](../reports/PHASE_03_report.md) § C. No other content changed.

## E. Compliance / verification

- All work stayed inside `D:\New folder (3)` (Rule 1).
- Original dataset, labels and COCO annotations are byte-for-byte unchanged; archive MD5
  `317862054545467FF00BE611DB8FF07E` (Rule 19; verified below).
- Existing split proposals preserved; no split directories created; no images/labels moved,
  renamed or deleted.
- No derived training labels generated or modified.
- No packages installed, no downloads, no new dependencies.
- No gate marked passed without evidence.

## F. Remaining blockers

1. **Split policy — DECIDED (2026-10-12):** whole-capture-day holdout, train 1,402 / val 390 /
   test 217 (test = 2025-02-26), ratio deviation accepted, residual leakage disclosed
   (§ A). G8/G9 evidence is complete and the decisions are recorded; the written adopted-
   policy manifest is a separate pre-training approval. **The split is not leakage-free.**
2. **Gate A4 — CONFIRMED (2026-10-12):** pothole/crack supported; manhole → unsupported,
   never relabelled (§ A).
3. **Report wording** — **RESOLVED (2026-10-12):** the inconsistent “excluded from pothole/crack
   scope” sentence in `docs/reports/PHASE_03_report.md` was corrected (see § D).
4. **Derived-label generation** — still unauthorised and not performed.
5. **CC BY 4.0 attribution** remains mandatory.
6. PHASE_04 / YOLO11 training remain blocked.
