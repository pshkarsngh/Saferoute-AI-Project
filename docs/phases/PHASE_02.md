# SafeRoute AI — Phase 02: Dataset Acquisition & Licence Approval Gate

> **Phase ID:** PHASE_02
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_01`](./PHASE_01.md) — Workspace & Environment Audit
> **Successor:** [`PHASE_03`](./PHASE_03.md) — Dataset Integrity, Class-Mapping & Split Audit
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Establish, approve and document a **lawful, traceable dataset** for YOLO11 road-hazard
training. This phase resolves the dataset side of gates **G1 (provenance & licence)** and
**G2 (location)** from `TRAINING_RULES.md` §2, and confirms the dataset physically lives inside
the approved workspace (or another explicitly user-authorised location).

No download, copy, relabel or modification occurs without explicit approval (Rule 19).

---

## 2. Scope

### In scope
- Identify the candidate dataset(s) and their origin.
- Record **licence**, **terms of use**, **permitted purposes** and any attribution requirements.
- Record expected contents: image count, annotation format (YOLO/COCO/VOC), class list.
- Confirm the **storage location** and that it is inside `D:\New folder (3)` or explicitly
  authorised elsewhere (Rule 1).
- Record a **dataset identity** (name, source, version, and a checksum/manifest where practical).
- Define where the dataset will live and how it will be referenced (workspace-relative paths).

### Out of scope
- The integrity audit itself (PHASE_03).
- Converting formats or relabelling classes (would need separate approval).
- Training (PHASE_08).
- Installing packages (PHASE_04).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_01 complete and accepted | Environment known |
| P2 | A candidate dataset identified by the user | Or a decision to obtain one |
| P3 | Explicit user approval for any download/copy | Rule 19 |

---

## 4. Detailed procedure

1. **Identify the dataset.** Record name, publisher/owner, URL or delivery method, and date.
2. **Review the licence.** Read the actual licence text. Record:
   - licence type and version;
   - permitted uses (research / commercial / redistribution);
   - restrictions (e.g. no redistribution, attribution required, non-commercial only);
   - whether use for training an ML model is permitted;
   - whether derived weights may be used as proposed.
3. **Record provenance.** Source, retrieval date, version/tag, and any DOI/publication.
4. **Confirm storage location.** Preferred: inside `D:\New folder (3)\data\`. If the dataset
   must live elsewhere, obtain **explicit written authorisation** and record it (Rule 1).
5. **Record expected structure** (without altering files): top-level layout, image folder(s),
   annotation file(s)/folder(s), documentation/README shipped with the data.
6. **Compute a dataset identity.** Where practical, record file counts, total size, and a
   checksum or manifest hash of the annotation sets (read-only).
7. **List known risks.** Format mismatch, class mismatch, licence ambiguity, missing test set,
   staleness, or duplicate-heavy source.
8. **If acquisition is approved and required:** obtain the dataset by the approved method only,
   into the approved location, then re-verify counts and checksum.
9. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_02. |
| A2 | User explicitly approves the **specific** dataset and its licence before any download/copy. |
| A3 | User explicitly approves downloading **or** confirms an already-present dataset. |
| A4 | If storing outside the workspace, user gives explicit written authorisation. |

**Mandatory gate mapping:** this phase is the evidence-collection step for G1 and G2. Training
remains blocked until G1 and G2 pass (§PHASE_07 review).

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Licence documented | Licence text recorded; permitted use for model training stated. |
| V2 | Provenance recorded | Source, date, version captured. |
| V3 | Location verified | Dataset path is inside the workspace or explicitly authorised. |
| V4 | Contents counted | Image count and annotation file count recorded. |
| V5 | Format identified | Declared format (YOLO/COCO/VOC/other) recorded from actual files. |
| V6 | Identity captured | Size and (where practical) checksum/manifest recorded. |
| V7 | Risks listed | Known format/class/licence/split risks documented. |
| V8 | No modification | No dataset file altered; no unauthorised download performed. |

---

## 7. Acceptance criteria

- [ ] The dataset licence is recorded and **permits** the intended use, or the dataset is
      rejected and an alternative sought.
- [ ] The dataset location is confirmed compliant with Rule 1, with evidence.
- [ ] Image and annotation counts are recorded and consistent with the source's claims (any
      mismatch noted).
- [ ] A dataset identity (name, source, version, checksum/manifest) is recorded.
- [ ] No file was modified and no unapproved download occurred.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The licence does **not** clearly permit model training or the proposed use.
2. The dataset cannot be stored inside the workspace and no authorisation exists (Rule 1).
3. The dataset location cannot be verified, or it resolves outside approved boundaries.
4. The dataset's format/classes differ materially from the declared description and this is not
   yet reconciled (handled in PHASE_03).
5. Acquisition would require an unapproved download, credential or paid service (Rule 19).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Workspace isolation | §3 P, §4.4, V3, §8.2 |
| Rule 15 Dataset integrity | §4.3, §4.6, V1–V3 |
| Rule 17 Documentation | Whole phase |
| Rule 19 No unauthorized actions | §5, V8, §8.5 |
| TRAINING_RULES §2 G1, G2 | §5, V1–V3 |
| TRD §4.3.1 licence & provenance | §4.2–§4.3 |

---

## 10. Honesty note

This phase documents a dataset; it does **not** assert the dataset is clean, balanced or
correctly annotated. Those claims belong to PHASE_03 and must be **measured**, not assumed.
No metrics may be reported here.

---

## 11. Completion report template

```
PHASE_02 — Completion Report
============================
Date (actual):          <YYYY-MM-DD>
Approval reference:     <user approval of dataset + licence>

1. Dataset identity
   - Name:               <name>
   - Source / URL:       <source>
   - Version / date:     <version>
   - Retrieval date:     <YYYY-MM-DD>

2. Licence & provenance
   - Licence:            <type + version>
   - Permitted use:      <stated>
   - Restrictions:       <attribution / non-commercial / redistribution>
   - Training permitted? <yes/no/unclear>
   - Key excerpts:       <quotes>

3. Location
   - Path:               <absolute path>
   - Inside workspace?   <yes / authorised-elsewhere>
   - Authorisation ref:  <if elsewhere>

4. Contents (as found)
   - Images:             <count>
   - Annotation files:   <count>
   - Declared format:    <YOLO/COCO/VOC/other>
   - Declared classes:   <list>
   - Total size:         <size>
   - Checksum/manifest:  <value or "not computed + reason">

5. Risks noted
   <list>

6. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

7. Gate status
   - G1 provenance & licence: PASS / FAIL / PARTIAL
   - G2 location:            PASS / FAIL

8. Limitations / honesty note
   <unverified aspects; nothing about cleanliness asserted>

9. Result: COMPLETE / BLOCKED / STOPPED
   Next phase authorised? YES / NO (awaiting approval)
```
