# PHASE_03 — Corrected Split-Proposal (v2) & Validation

> **Phase:** PHASE_03 — Dataset Integrity, Class-Mapping & Split Audit (approved follow-up)
> **Status:** proposals generated, **awaiting user review**
> **Generated (UTC):** 2026-10-11T19:39:40Z
> **Workspace:** `D:\New folder (3)`
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) ·
> [`../phases/PHASE_03.md`](../phases/PHASE_03.md)
> **Scope:** NEW split-proposal artefacts only. The original dataset, original labels and
> the four existing PHASE_03 artefacts were **not** modified. No split directories were
> created; no images were moved; no training was started.

---

## 1. Defects corrected

| # | Defect in prior artefacts | Correction in v2 |
|---|---|---|
| D1 | `parse_ts` (audit script) parsed **only camera filenames**; the 1,559 `vlcsnap-…` frames were never time-clustered, and the 136 `vlcsnap_2025-03-16-…` (underscore) frames were mis-parsed as untimed | A unified parser handles camera (`YYYYMMDD_HHMMSS`), `vlcsnap-…` (hyphen) **and** `vlcsnap_…` (underscore) timestamps |
| D2 | The 348 "timestamp-less" frames were treated as a spread-out population | The **212** genuinely untimed frames (211 `vlcsnap-NNNNN` + 1 `vlcsnap-00097-MSI`) are forced into **one indivisible group** |
| D3 | `group_id` column in the prior session-aware manifest was a coarse bucket (e.g. `vlcsnap-2025`) **not** the assignment grouping | v2 `proposed_group_id` is the **real** group used for assignment |
| D4 | Greedy shuffle assignment cannot hit 70/20/10 when a large group exists | Deterministic **descending-size, largest-remaining-deficit** assignment hits the targets exactly |

**Parse correction in figures:** the prior report's "348 timestamp-less" frames are
`212 genuinely untimed + 136 from capture day 2025-03-16`. Timestamped frames are therefore
1,797 (not 1,661), and there are **6 capture days** (02-16, 02-18, 02-19, 02-23, 02-26,
**03-16**), not 5.

## 2. Grouping method (both variants)

Read-only, deterministic (`seed = 42`), union-find over all 2,009 images using the
previously approved signals:

1. exact byte-identical (SHA-256);
2. near-duplicate (64-bit dHash, Hamming ≤ 5, recomputed to reproduce the approved hashes exactly — 0 mismatches);
3. session-aware same-date adjacency (unified timestamps) at the variant's threshold;
4. **forced merge of the 212 untimed frames into one group.**

Groups are assigned whole; a group never crosses a split.

## 3. Variants generated (both fail-safe, no overwrite)

| Manifest | Session threshold | Groups | Largest group | train / val / test |
|---|---|---|---|---|
| `split_manifest_proposal_sessionaware_v2.csv` (**primary**) | ≤ 5 s | 421 | 265 | **1406 / 402 / 201** |
| `split_manifest_proposal_sessionaware_v2_strict30s.csv` (alternative) | ≤ 30 s | 61 | 389 | **1406 / 402 / 201** |

Both hit the 70 / 20 / 10 targets exactly. The largest group is the forced untimed block
(212 numeric) optionally fused by near-duplicate linkage to part of the 2025-03-16 session
(53 frames at ≤ 5 s; 177 at ≤ 30 s).

## 4. Validation results (measured on the written files)

### 4.1 Coverage & uniqueness (both variants)
- rows 2,009 · unique 2,009 · missing 0 · extra 0 · duplicates 0; all stems present on disk.
- untimed frames (`is_untimed = yes`): 212, all in **one** group; blank `capture_ts`: 212.

### 4.2 Group integrity & leakage

| Check | primary (≤5 s) | strict30s (≤30 s) |
|---|---|---|
| Groups crossing train/val/test | **0** | **0** |
| Exact-identical groups crossing | **0** | **0** |
| dHash ≤ 5 pairs crossing | **0** | **0** |
| dHash ≤ 6 / ≤ 8 / ≤ 10 pairs crossing | 9 / 154 / 607 | 3 / 56 / 301 |
| Session ≤ 2 s / ≤ 5 s pairs crossing | **0 / 0** | **0 / 0** |
| Session ≤ 30 s pairs crossing (images) | 269 (461) | **0 (0)** |
| Session ≤ 60 s pairs crossing (images) | 296 (495) | 21 (42) |
| Session ≤ 300 s pairs crossing (images) | 319 (527) | 41 (79) |

The primary variant fully removes exact, near-duplicate (≤ 5) and ≤ 5 s session crossing.
It does **not** remove same-day, > 5 s co-session adjacency.

### 4.3 Class distribution (pothole / crack / manhole boxes)

| Split | primary boxes | primary imgs-with-class | strict30s boxes | strict30s imgs-with-class |
|---|---|---|---|---|
| train | 865 / 1904 / 660 | 546 / 1011 / 523 | 896 / 1864 / 701 | 589 / 1010 / 545 |
| val | 259 / 427 / 187 | 162 / 254 / 155 | 226 / 481 / 165 | 118 / 259 / 138 |
| test | 137 / 188 / 110 | 87 / 110 / 81 | 139 / 174 / 91 | 88 / 106 / 76 |

Totals are unchanged and reconcile: pothole 1,261 · crack 2,519 · manhole 957 = 4,737 boxes.
All three classes are present in every split in both variants.

### 4.4 Family & date placement (primary)
- `vlcsnap_numeric` (212): train only — by design (indivisible untimed group).
- `vlcsnap_underscore_ts` (136, day 2025-03-16): train 74 · val 37 · test 25 — **fragmented across splits at the group level** (no ≤ 5 s crossing, but same-day sub-sessions land in different splits).
- Capture days appear in multiple splits (e.g. 02-19 in train/val/test).

## 5. Residual leakage risk (honest statement)

- **Leakage is not eliminated.** No split can be certified leakage-free from filenames alone.
- The primary variant removes the leakage classes that were explicitly constrained (exact,
  dHash ≤ 5, session ≤ 5 s) and isolates the untimed block, but leaves **same-day co-session
  adjacency at gaps > 5 s** — measured at ≤ 30 s: 269 crossing pairs (461 images); at
  ≤ 300 s: 319 pairs (527 images). The 2025-03-16 capture day is represented in all three
  splits.
- The untimed block (212 frames) is 10.6 % of the data; it is placed **entirely in train**,
  so val/test contain no genuinely-untimed frames and cannot measure that sub-population.
- dHash 6–10 cross-split pairs remain (154 / 607 in the primary), i.e. moderately similar
  (not near-identical) imagery crosses splits.
- The `strict30s` variant removes ≤ 30 s crossing but still leaves ≤ 60 s (21 pairs) and
  ≤ 300 s (41 pairs); it also concentrates the 03-16 day further into train.

## 6. Distribution suitability (requirement 7)

The primary split is **suitable**: exact 70/20/10 sizes, all classes present, no group/exact/
near/session(≤5 s) crossing. The residual is a leakage-quality caveat, not a distribution
failure. The only material trade-off is the indivisible 265-image untimed block (13.2 %),
which forces it wholly into one split (train). No constraint was weakened to achieve this.

## 7. Artefacts created (all inside the workspace; originals untouched)

- `reports/phase03/split_manifest_proposal_sessionaware_v2.csv`
- `reports/phase03/split_manifest_proposal_sessionaware_v2_strict30s.csv`
- `reports/phase03/split_manifest_proposal_v2_validation.json` (machine-readable)
- this document

Not modified: `split_manifest_proposal.csv`, `split_manifest_proposal_sessionaware.csv`,
`dataset_audit.json`, `dataset_audit_report.md`, `class_mapping_proposal.md`, and
`docs/reports/PHASE_03_report.md`.

## 8. Gate status

| Gate | Status |
|---|---|
| A4 class mapping | **PASS** (user confirmed: pothole / crack supported; manhole unsupported, excluded, never relabelled) |
| G8 split integrity | Evidence improved (v2 primary: 0 constrained crossings) — **awaiting acceptance of the split policy** |
| G9 test isolation | Test isolated at the constrained level; residual same-day co-session risk disclosed — **awaiting acceptance** |
| A3 corrections | No correction applied; v2 manifests are proposals only |

## 9. Recommendation (awaiting approval)

1. Accept the **primary `…_v2.csv`** as the proposed split policy, acknowledging the measured
   residual (same-day > 5 s co-session; untimed block in train).
2. **Or** adopt `…_v2_strict30s.csv` if stronger same-day isolation is preferred (trade-off:
   the 03-16 day concentrates in train; test loses crack boxes: 188 → 174).
3. Approve (or amend) the annotation policy in `annotation_policy_proposal.md`.
4. Decide whether a full per-image anomaly clip/exclusion list should be generated next.
