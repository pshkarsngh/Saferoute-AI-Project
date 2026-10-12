# SafeRoute AI — Phase 03: Dataset Integrity, Class-Mapping & Split Audit

> **Phase ID:** PHASE_03
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_02`](./PHASE_02.md) — Dataset Acquisition & Licence Approval Gate
> **Successor:** [`PHASE_04`](./PHASE_04.md) — Workspace Virtual Environment & Dependencies
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Perform the **mandatory dataset integrity audit** defined in `TRD.md` §4.3 and
`TRAINING_RULES.md` §2 (gates **G3–G9**). Audit the real files to determine, with evidence:
image–label pairing, class IDs and distribution, malformed/empty annotations, corrupt images,
duplicates, and train/validation/test split integrity (leakage).

The audit is **read-only**. Any correction (relabelling, re-splitting, deduplication) is a
separate, explicitly approved action (Rule 15, Rule 19).

---

## 2. Scope

### In scope
- File counts per split and across splits (G3).
- Decodability of every image, or a documented sampled subset (G4).
- Annotation parsing, coordinate normalisation and range checks (G5).
- Actual format and class-ID discovery from the data (G6).
- Data hygiene: empty labels, invalid boxes, duplicates, corrupt files (G7).
- Split documentation and cross-split leakage detection (G8).
- Test-set isolation confirmation (G9).
- Production of a **class-mapping proposal** and a **split manifest**.

### Out of scope
- Modifying, relabelling, deleting, re-splitting or deduplicating any file (Rule 19).
- Training (PHASE_08).
- Setting final training hyperparameters (PHASE_07).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_02 complete and accepted | Dataset identified, licensed, located |
| P2 | A read-only tool capable of decoding images / parsing annotations | Existing packages only |
| P3 | User approval to run the audit | Rule 3 |

---

## 4. Detailed procedure

1. **Enumerate files.** Count images and label files per split (train/val/test) and in total.
   Record any split that is absent.
2. **Image–label pairing.** For each image, check a matching label exists, and vice versa.
   Count unpaired images (`no label`) and orphan labels (`no image`).
3. **Decode check.** Attempt to decode each image (or a documented random sample with a stated
   sample size and seed). Count failures and record filenames.
4. **Annotation parse.** Parse each label file:
   - line format `class_id cx cy w h`;
   - from 5 tokens per line;
   - `class_id` is an integer;
   - `cx cy w h` are in `[0,1]` and sane (`w>0`, `h>0`).
   Count malformed lines and out-of-range boxes.
5. **Class discovery & distribution.** Build the **actual** class-ID histogram (boxes per ID,
   images per ID). Record how IDs map to names if a names file/README exists. Flag severe
   imbalance and classes with zero or near-zero instances.
6. **Empty labels.** Count images with zero objects. Do **not** treat empty labels as verified
   true negatives (Rule 15).
7. **Duplicate / near-duplicate detection.** Perceptual hashing or embedding similarity within
   and across splits. Record suspected duplicates and cross-split matches.
8. **Split integrity & leakage.** Verify no image (or near-identical image) appears in more than
   one split. Record the split policy used by the source and any suspected leakage.
9. **Path safety.** Confirm all dataset references are workspace-relative or inside the approved
   location; reject external/absolute-outside references (Rule 1).
10. **Produce artefacts (reports only):**
    - `dataset_audit_report` (counts, failures, distributions);
    - `class_mapping_proposal` (actual IDs → proposed SafeRoute classes);
    - `split_manifest` (list of images per split, with hashes).
11. **Write the completion report** (§11).

> Any script used for the audit must be **read-only** against the dataset and saved inside the
> workspace (e.g. `D:\New folder (3)\scripts\audit\`). Creating such a script requires approval.

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_03. |
| A2 | User approves any audit script before it runs. |
| A3 | Any **correction** to the data (relabel, delete, re-split, dedupe) requires a **new, separate** approval and its own plan (Rule 15, Rule 19). |
| A4 | Resolution of a class-ID mismatch (actual vs proposed) requires user acceptance of the mapping proposal. |

**Mandatory gate mapping:** this phase supplies evidence for **G3–G9**. Training remains
blocked until every applicable gate passes.

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Counts recorded | Image & label counts per split and total recorded. |
| V2 | Pairing complete | Unpaired images and orphan labels counted (should be 0 or explained). |
| V3 | Decode results | All images decode, or failures enumerated and quantified. |
| V4 | Annotation validity | Malformed lines and out-of-range boxes counted (0 or explained). |
| V5 | Class mapping | Actual IDs recorded; proposal maps each to a SafeRoute class or "unsupported". |
| V6 | Distribution captured | Per-class box and image counts recorded. |
| V7 | Duplicates | Duplicate/near-duplicate findings recorded. |
| V8 | Leakage checked | Cross-split overlap reported (should be none). |
| V9 | Test isolation | Test set confirmed unused for training/selection. |
| V10 | Path safety | No dataset reference resolves outside the approved location. |
| V11 | Read-only | No dataset file was modified. |

---

## 7. Acceptance criteria

- [ ] A written audit report exists with real counts and failure lists.
- [ ] Actual annotation format and class IDs are recorded from the data.
- [ ] A class-ID → SafeRoute class mapping is proposed (including any "unsupported" classes).
- [ ] A split manifest exists and leakage status is stated.
- [ ] Test set is isolated.
- [ ] No dataset file was modified.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. Image–label pairing failures are widespread or unexplained.
2. A large fraction of images fail to decode.
3. Class IDs cannot be reconciled with a defensible mapping to the target classes.
4. Cross-split leakage is found (do not train on leaked data; raise for a re-split decision).
5. The test set has been used for training/selection by the source.
6. Any dataset reference resolves outside the approved location (Rule 1).
7. Completing the audit would require modifying the dataset (needs separate approval).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation / path safety | §4.9, V10 |
| Rule 5 Hazard classes | §4.5, V5 |
| Rule 15 Dataset integrity | Whole phase |
| Rule 16 Hardware (indirect) | n/a |
| Rule 19 No unauthorized actions | §5 A3, V11 |
| TRD §4.3 audit list | §4.1–§4.9 |
| TRAINING_RULES §2 G3–G9 | §5, V1–V9 |

---

## 10. Honesty note

The audit reports **what the files actually contain**. It does not improve, clean, balance or
"fix" the dataset. A class with no instances is reported as absent and cannot be claimed as
detectable (Rule 5, Rule 20).

---

## 11. Completion report template

```
PHASE_03 — Dataset Integrity Audit Report
=========================================
Date (actual):          <YYYY-MM-DD>
Dataset path:           <path>
Audit sampled?          <all images / sample N with seed S>

1. Counts
   - train images/labels: <n>/<n>
   - val   images/labels: <n>/<n>
   - test  images/labels: <n>/<n>
   - total:               <n>

2. Pairing
   - images without label: <n>   <list>
   - labels without image: <n>   <list>

3. Decode
   - decoded ok:  <n>
   - failures:    <n>  <list>

4. Annotations
   - malformed lines: <n>
   - out-of-range boxes: <n>

5. Actual format & class IDs
   - format:  <YOLO/COCO/VOC/other>
   - IDs found: <id: count, ...>
   - names file/provenance: <path or "none">

6. Class mapping proposal (actual ID -> SafeRoute class)
   <table: id | actual name | proposed SafeRoute class | supported? | instances>

7. Empty labels
   - images with 0 objects: <n>

8. Duplicates / near-duplicates
   - within split: <n>   across splits: <n>

9. Split integrity & leakage
   - policy: <documented policy or "not documented">
   - leakage found: <none / list>

10. Test isolation
   - test used for training/selection? <no/yes>

11. Path safety
   - references outside approved location: <none / list>

12. Files modified
   - <none>  (audit is read-only)

13. Validation results
   V1 <pass/fail + evidence> ... V11 <pass/fail + evidence>

14. Gate status
   G3 <pass/fail> G4 <..> G5 <..> G6 <..> G7 <..> G8 <..> G9 <..>

15. Limitations / honesty note
   <class imbalance, absent classes, sampling caveats>

16. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
