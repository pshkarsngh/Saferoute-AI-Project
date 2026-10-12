# PHASE_03 — Split-Leakage Review v1 (focus: strict-30 s candidate)

> **Phase:** PHASE_03 — Dataset Integrity, Class-Mapping & Split Audit (approved follow-up)
> **Status:** **REVIEW-ONLY — no manifest modified, no split regenerated, no final strategy selected**
> **Date (actual):** 2026-10-12
> **Candidate under review:** `reports/phase03/split_manifest_proposal_sessionaware_v2_strict30s.csv`
> **Workspace:** `D:\New folder (3)`
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) ·
> [`../phases/PHASE_03.md`](../phases/PHASE_03.md) ·
> [`../TRAINING_RULES.md`](../TRAINING_RULES.md) (gates **G8**, **G9**) ·
> [`docs/reports/PHASE_03_report.md`](../../docs/reports/PHASE_03_report.md)

This review is strictly analytical. It evaluates the existing manifests, the recorded
validation results, and independent read-only recomputations. **The strict-30 s candidate is
kept unchanged and remains review-only.** No grouping constraint is silently relaxed; no
strategy is selected.

---

## 1. Evidence base and method

**Evidence used (all existing, read-only):**
- `split_manifest_proposal_sessionaware_v2_strict30s.csv` (2,009 rows; the candidate).
- `split_manifest_proposal_sessionaware_v2.csv` (primary ≤5 s variant).
- `split_manifest_proposal_v2_validation.json` / `.md` (generation-time validation records).
- `split_manifest_proposal.csv`, `split_manifest_proposal_sessionaware.csv` (prior proposals).
- `dataset_audit.json`, `dataset_audit_report.md`, `PHASE_03_report.md` (audit facts).
- `PHASE_03_followup_decision_record.md` (recorded candidate facts and policy).

**Recomputation method (verified figures below):** read-only inline Python 3.12 (standard
library only; no script file written, no packages imported beyond `csv/datetime/collections`).
Duplicate-group detection and group-integrity checks read the manifest directly. dHash
crossings use the per-image 64-bit `dhash_hex` column (Hamming distance, unordered pairs across
different splits). Session adjacencies use the `capture_ts` column, same calendar day,
sorted ascending.

**Convention used in this review — two session-crossing measures must be distinguished:**
- **(a) Adjacent-frame gaps:** only *consecutive* frames of a day (sorted by time) whose
  timestamp gap falls in the window and whose splits differ. This is the measure that exactly
  reproduces the recorded validation figures (see §3.3).
- **(b) All-pairs within window:** *any* two same-day frames in different splits whose timestamp
  gap falls in the window. This is a stricter measure recomputed here; it is **not** present in
  the original validation records.

Terms: "VERIFIED" = reproduced from manifests/records read-only with exact figures.
"UNTESTED / HYPOTHESIS" = plausible but not proven by available data (e.g., would require
visual inspection or additional capture metadata).

---

## 2. Leakage classes evaluated separately

### 2.1 Exact duplicates (byte-identical)

| Claim | Result |
|---|---|
| Audit record | 5 exact-ShA-256 groups / 10 images, all `vlcsnap` frames |
| Recomputed from strict-30 s manifest | **5 groups / 10 images**, exact-cross-split pairs = **0** |
| Group membership | Each exact-identical image pair shares a `proposed_group_id`; groups never cross splits |

**Assessment (VERIFIED):** exact duplicates are fully neutralised — identical pixels never
appear in two splits. This is the strongest possible leakage class and it is closed.

### 2.2 Perceptual-hash near-duplicates (64-bit dHash)

| Threshold | Cross-split pairs (recorded) | Cross-split pairs (recomputed) | Distinct images (recomputed) |
|---|---|---|---|
| ≤ 5 | 0 | **0** | 0 |
| ≤ 6 | 3 | **3** | 5 |
| ≤ 8 | 56 | **56** | 58 |
| ≤ 10 | 301 | **301** | 173 |

**Verified crossing pairs at dHash ≤ 6** (all capture day 2025-02-19, gap in parentheses):
- `…14h27m15s411` [train] ↔ `…17h03m26s014` [val] — hd 6 (~2h36m)
- `…14h59m07s946` [train] ↔ `…17h03m49s630` [val] — hd 6 (~2h05m)
- `…17h01m22s346` [train] ↔ `…17h03m49s630` [val] — hd 6 (~2m27s)

**Assessment (VERIFIED):** at the near-identical threshold (dHash ≤ 5) the candidate is clean
(0 crossings). At looser similarity the residual grows monotonically: 3 / 56 / 301 pairs, with
173 images (8.6 % of the dataset) involved at dHash ≤ 10. All listed ≤6 pairs are same-day
frames from the same capture day (02-19) — moderate near-duplicates, not byte-identical.
Whether dHash 6–10 pairs are *visually significant* (same road object vs. same road surface) is
**UNTESTED** — it would require inspecting the image pairs; no image content was examined here.

### 2.3 Session / time-based leakage

Two measures, same manifest:

| Window | Adjacent-frame gaps (a) | All-pairs within window (b) |
|---|---|---|
| ≤ 30 s | 0 pairs / 0 images | 0 pairs / 0 images (all within-group, no split difference) |
| ≤ 60 s | **21 pairs / 42 images** | 252 pairs / 151 images |
| ≤ 300 s | **41 pairs / 79 images** | 11,045 pairs / 953 images |

- (a) is **VERIFIED** to reproduce the recorded validation exactly (21/42 and 41/79). Because
  the ≤30 s grouping was applied, every cross-split **adjacent** frame gap is > 30 s; the 21/41
  figures are the direct same-day group-boundary adjacencies that fall in the 31–60 s and
  31–300 s ranges.
- (b) is recomputed here (same read-only input) and is far larger: within 300 s, 11,045
  unordered cross-split pairs involve 953 images (~47 % of the dataset). This measure counts
  frames that are *not* necessarily consecutive scenes; it overstates "same scene" if distinct
  passes occur within five minutes. Conversely, the official 41-pair figure understates total
  time-adjacent overlap because it counts only consecutive-frame boundaries. Both are raw-time
  proxies; neither proves identical scene content (**UNTESTED**).
- Group-level integrity is **VERIFIED**: 61 groups, largest 389, **0 groups cross splits**;
  each split (train 1406 / val 402 / test 201) is composed of whole groups.

**Assessment:** the candidate fully removes ≤30 s co-session adjacency and near-identical
duplicates, but time-based leakage above the grouping threshold persists and is material under
the stricter all-pairs measure. The exact severity depends on ground truth about what is "the
same scene", which filenames alone cannot establish.

---

## 3. The 212 genuinely timestamp-less frames

- Count (VERIFIED): 212 rows, `is_untimed = yes`, blank `capture_ts`; all in **one**
  `proposed_group_id` (in the strict-30 s manifest this is group `g0006`).
- **The indivisible block is larger than the 212:** read-only inspection of the manifest shows
  `g0006` = **389 images** = 212 untimed (`vlcsnap_numeric`) + 114 `vlcsnap_underscore_ts`
  (2025-03-16) + 53 `vlcsnap_hyphen_ts` (2025-02-19) + 10 `camera`. The untimed frames were
  fused with timestamped frames by near-duplicate linkage and ≤30 s session adjacency at
  generation time (documented in `split_manifest_proposal_v2_validation.md` §3).
- Placement (VERIFIED): the whole 389-image block is assigned to **train** (train-only: 212
  untimed; 10/10 camera of the block; 114/114 underscore; 53/53 hyphen).
- Consequences:
  1. **val/test contain zero genuinely timestamp-less frames**, so that sub-population cannot
     be evaluated in val/test at all.
  2. 10.6 % of the dataset (212) is thereby train-only, and the fused block (19.4 % of the
     dataset) is forced wholly into train — a measurable distribution bias, not a leak between
     splits.
  3. The fusion is evidence that some untimed frames are scenes *also seen* in timestamped
     frames; whether this is true content duplication vs. merely coincident grouping edges is
     **UNTESTED** (would require image-level review).

---

## 4. Capture-day distribution across splits (2025-03-16 and the rest)

**2025-03-16 (136 frames, `vlcsnap_underscore_ts`)** — VERIFIED distribution:
train **127** (group `g0006`: 114 + group `g0059`: 13) · val **5** (group `g0060`) · test **4**
(group `g0061`). 114 of 136 frames (83.8 %) are fused into the 389-image train block; only
**9 frames (6.6 %)** reach val/test, as two tiny whole groups of 5 and 4.

**Other capture days (VERIFIED from manifest):**

| Day | Images | train / val / test | Whole-day single split? |
|---|---|---|---|
| 2025-02-16 | 3 | 3 / 0 / 0 | yes (2 groups, both train) |
| 2025-02-18 | 581 | 326 / 226 / 29 | no (day distributed) |
| 2025-02-19 | 821 | 513 / 155 / 153 | no (day distributed) |
| 2025-02-23 | 39 | 8 / 16 / 15 | no (6 groups, none cross splits, but day is spread) |
| 2025-02-26 | 217 | 217 / 0 / 0 | yes (single group `g0058`) |
| 2025-03-16 | 136 | 127 / 5 / 4 | no (4 groups; 114 fused into train block) |
| (untimed) | 212 | 212 / 0 / 0 | yes (fused into `g0006`, train) |

**Assessment:** four of six capture days (02-18, 02-19, 02-23, 03-16) appear in more than one
split at the *group* level, so no group crosses splits but **same-day temporal sub-sessions do
cross splits**. 02-26 and 02-16 are whole-day train. The 03-16 day is overwhelmingly a training
day, with only 9 frames in validation/test — those 9 frames are *not* representative of that
capture session, and the 114 fused frames make it impossible to hold the day out without
breaking the ≤30 s / near-duplicate grouping that produced `g0006`.

---

## 5. Does the current validation data support a defensible independent test set?

**Short answer: no — the strict-30 s candidate does not support a *temporally independent*
test set.** It supports a *group-isolated* test set at the ≤30 s / dHash ≤5 level, with a
disclosed residual. Reasons (all VERIFIED or explicitly curated above):

1. **No full-day holdout exists.** Every capture day appears in train; 02-26 (217), 02-16 (3),
   and the fused 389-block are train-only, and the other four days are spread across splits.
   A test image and some training images were therefore captured on the same calendar day and,
   at the upper bound, within minutes of each other.
2. **Direct temporal adjacencies remain:** 21 adjacent pairs (42 images) at ≤60 s and 41 pairs
   (79 images) at ≤300 s; up to 11,045 pairings (953 images) inclusively within 300 s under the
   all-pairs measure.
3. **Moderate near-duplicates remain:** dHash ≤6/≤8/≤10 cross-split pairs 3 / 56 / 301.
4. **Test-set size and class depth are limited:** test = 201 images with crack 174 boxes (vs.
   1,864 train) and pothole 139 — small for stable per-class measurement; the 03-16 day (an
   entire capture session) is almost absent from test.
5. **`vlcsnap_numeric` (10.6 %) cannot be measured in val/test at all.**

A *temporally independent* test set cannot be carved from this data without either (a) holding
out complete days/sessions, which then become small and unrepresentative (02-23: 39 images, 0
manhole; 02-16: 3 images), or (b) breaking the current grouping that fuses 114×03-16 into the
389-image block. Either move trades leakage for distribution quality; nothing is free from the
filenames alone.

---

## 6. Mitigation options — comparison only (no selection)

None of the options is selected here; each is analysed for leakage reduction, distribution
trade-offs, feasibility, and the validation that would be required. Grouping constraints are
not silently relaxed in any option.

### Option 1 — Keep the strict-30 s candidate and disclose residual leakage
- **Leakage reduction:** none beyond the current design (≤30 s session + dHash ≤5 + exact
  duplication closed; residual exactly as §2–§4).
- **Distribution trade-offs:** unchanged; all current biases persist (untimed block train-only,
  03-16 concentrated in train, four days spread).
- **Feasibility:** maximum — no new data or regrouping required.
- **Requires / validation:** an explicit documented residual-leakage limitation before G8/G9
  acceptance; a sensitivity check of likely test-metric inflation is advisable once training is
  authorised. Test results could be optimistic on same-scene similarity.

### Option 2 — Group the entire known capture day into one split (day holdout)
- **Leakage reduction:** removes same-day co-session leakage entirely for the held-out day(s).
- **Distribution trade-offs:** only small days can be wholly held out without collapsing the
  split target — 02-23 (39 images, **0 manhole boxes**, crack 47 boxes) or 02-16 (3 images).
  Holding out 03-16 (136 images) is impossible under the current grouping because 114 of its
  frames are fused into the indivisible 389-image train block; separating them would **require
  breaking the ≤30 s / near-duplicate linkage for that day**, i.e., a documented deviation.
  02-26 (217) could be held out whole but is a single evening burst; representing a full day
  of that burst would leave train with no 02-26 imagery.
- **Feasibility:** partially feasible only for small days; the large days cannot be isolated
  without weakening grouping or accepting severe ratio/representativeness shifts.
- **Requires / validation:** re-run a deterministic day-holdout manifest; verify group
  integrity, exact/dHash/≤30 s crossings = 0, box counts per split (manhole absence in 02-23
  must be disclosed), and re-check 70/20/10 interference from the 389-block and 217-block.

### Option 3 — Stronger source-session grouping or perceptual connected components
- **Leakage reduction:** unioning ≤60 s/≤300 s adjacencies and/or dHash ≤10 nearest-neighbour
  links would close the residual classes at those thresholds.
- **Distribution trade-offs:** this is the **chaining trap** — transitive union over a long
  capture chain merges nearly the entire video population into one component (the ≤5 s variant
  already reached a max group of 265; ≤30 s reached 389; longer windows merge a majority of the
  2,009 frames). The result is few giant groups, likely destroying exact 70/20/10 attainability
  and forcing nearly all data into one split.
- **Feasibility:** possible to compute, but likely infeasible to keep a meaningful val/test at
  the required ratios; would need to review component sizes before any assignment.
- **Requires / validation:** component-size distribution, giant-component audit, and a
  re-check of whether a 70/20/10 assignment even exists; if not, the constraint must be
  formally revisited with the user (not silently relaxed).

### Option 4 — Obtain additional independent capture sessions for validation/test
- **Leakage reduction:** the only route to a genuinely independent test set (different capture
  day/location/session, no same-day adjacency, no near-duplicate linkage to training).
- **Distribution trade-offs:** improves representativeness of val/test; requires the new data
  to be class/condition-compatible with pothole+crack scope; introduces new licensing/compliance
  obligations (Rules 8, 15, 19; CC BY 4.0 attribution remains mandatory for the current
  dataset).
- **Feasibility:** depends on user approval and availability of a permitted source; a new
  capture is an out-of-scope dataset action that requires its own authorisation.
- **Requires / validation:** the full G3–G9 audit pipeline for the new captures (decode,
  pairing, annotation validity, duplicates) plus cross-split duplicate/session checks between
  the new validation/test frames and the existing training pool.

### Combination note
Options are not mutually exclusive: the strongest practical reading of the evidence is that
neither keep-and-disclose alone (Option 1) nor regrouping alone (Options 2/3) yields a
*temporally independent* test set from the current data; Option 4 (new captures) is the only
option that plausibly delivers true independence. Option 2 for one small day would still leave
a small, unrepresentative test (e.g., 02-23 has no manhole and few crack boxes). No combination
is recommended or selected here.

---

## 7. Verified results vs. untested hypotheses (summary)

**VERIFIED (recomputed from manifests/records, read-only):**
- Exact-duplicate groups 5 / 10 images; 0 exact cross-split pairs.
- dHash cross-split pairs: ≤5 = 0, ≤6 = 3, ≤8 = 56, ≤10 = 301 (matches validation).
- Adjacent-frame session crossings: ≤30 s = 0, ≤60 s = 21 pairs/42 imgs, ≤300 s = 41/79
  (matches validation exactly).
- 61 groups, largest = 389 (`g0006`), 0 groups cross splits; 1406 / 402 / 201.
- Untimed 212 in one group, train-only; `g0006` composition = 212 untimed + 114×03-16 +
  53×02-19 + 10 camera.
- 2025-03-16 distribution: train 127 / val 5 / test 4, via 4 groups; 114 fused into `g0006`.
- 2025-02-26 = single 217-image group, train-only.

**UNTESTED / HYPOTHESIS (not provable from filenames alone):**
- Whether dHash 6–10 cross-split pairs and >30 s same-day adjacencies are the *same road
  scene* — would require image-level review.
- Whether the 212 untimed frames fused into `g0006` truly duplicate timestamped scenes.
- Whether test-set metrics would be materially inflated by residual leakage (quantifiable only
  post-training, against a later independent holdout).

**Honesty statement:** the strict-30 s candidate is **not leakage-free**. The current available
evidence does not support a defensible temporally-independent test set; the candidate offers a
group-isolated test set with measured, disclosed residual leakage. This review changes no
manifest, creates no splits, and selects no final strategy.