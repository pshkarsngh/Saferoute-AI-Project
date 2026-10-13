# SafeRoute AI — Phase 02: Dataset Acquisition & Licence Approval Gate

> **Phase ID:** PHASE_02
> **Status:** Complete — approved and documented (see [`../reports/PHASE_02_report.md`](../reports/PHASE_02_report.md))
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

- [x] The dataset licence is recorded and **permits** the intended use, or the dataset is
      rejected and an alternative sought. *(Creative Commons Attribution 4.0 International / CC BY 4.0 approved by user; permits derivative ML training).*
- [x] The dataset location is confirmed compliant with Rule 1, with evidence. *(Located at `D:\New folder (3)\data\pothole_crack_manhole\data\`).*
- [x] Image and annotation counts are recorded and consistent with the source's claims (any
      mismatch noted). *(2,009 images, 2,009 polygon labels, 2,009 labels-YOLO, 4,737 COCO annotations).*
- [x] A dataset identity (name, source, version, checksum/manifest) is recorded. *(Zenodo concept 17834372 / record 18528034; archive MD5 & SHA256 recorded).*
- [x] No file was modified and no unapproved download occurred. *(Audited strictly read-only; no modifications).*
- [x] Completion report submitted and accepted. *(Filed in `docs/reports/PHASE_02_report.md` & `docs/reports/PHASE_02_completion_report.md`; approved).*

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

## 11. Completion report

> The formal completion report has been filed, accepted, and recorded:
> - Full record: [`docs/reports/PHASE_02_report.md`](../reports/PHASE_02_report.md)
> - Summary report: [`docs/reports/PHASE_02_completion_report.md`](../reports/PHASE_02_completion_report.md)

```
PHASE_02 — Completion Report
============================
Date (actual):          2026-10-12
Approval reference:     Project owner explicit approval recorded 2026-10-12 (docs/reports/PHASE_02_report.md § A)

1. Dataset identity
   - Name:               Road Damage Dataset: Potholes, Cracks, and Manholes
   - Source / URL:       Zenodo (Record 18528034 / Concept 10.5281/zenodo.17834372)
   - Version / date:     2026-02-08, revision 5 (bundled README cites DOI 10.5281/zenodo.17834373)
   - Retrieval date:     Local archive timestamp 2026-10-11 22:17:52

2. Licence & provenance
   - Licence:            Creative Commons Attribution 4.0 International (CC BY 4.0)
   - Permitted use:      Commercial and non-commercial research, sharing, and adaptation with attribution
   - Restrictions:       Attribution required; preserve copyright notice; no additional legal/tech restrictions
   - Training permitted? Yes (CC BY 4.0 permits derivative works including ML training)
   - Key excerpts:       "You are free to: Share — copy and redistribute the material in any medium or format; Adapt — remix, transform, and build upon the material for any purpose, even commercially."

3. Location
   - Path:               D:\New folder (3)\data\pothole_crack_manhole\data\
   - Inside workspace?   Yes (Rule 1 compliant)
   - Authorisation ref:  Workspace-local (no external authorization needed)

4. Contents (as found)
   - Images:             2,009 JPG files
   - Annotation files:   2,009 polygon labels, 2,009 YOLO-format labels, 1 annotations_coco.json (4,737 annotations)
   - Declared format:    YOLO axis-aligned bbox + polygon + COCO JSON
   - Declared classes:   0=Pothole, 1=Crack, 2=Manhole
   - Total size:         194,786,682 bytes (~185.76 MiB extracted); data.zip 194,163,315 bytes (~185.17 MiB)
   - Checksum/manifest:  data.zip MD5: 317862054545467FF00BE611DB8FF07E | SHA256: C7B7247C611EFA0A12EB8B998583DA496F90C9B4859E9E1DE2C1B06ADBB80CEF

5. Risks noted
   - Stale DOI in bundled README (17834373) vs current Zenodo record (18528034).
   - Class scope mismatch: SafeRoute targets 7 hazard categories; dataset provides 3 (Pothole, Crack, Manhole). Class boundary must be preserved without silent relabelling.
   - Manhole class inclusion requires downstream handling policy.

6. Validation results
   V1 PASS (CC BY 4.0 documented)
   V2 PASS (Provenance and Zenodo record captured)
   V3 PASS (Location verified inside workspace)
   V4 PASS (2,009 images and annotations verified)
   V5 PASS (YOLO format confirmed ready)
   V6 PASS (Archive size and SHA256/MD5 recorded)
   V7 PASS (Risks documented)
   V8 PASS (Read-only, no modifications or unapproved downloads)

7. Gate status
   - G1 provenance & licence: PASS (CC BY 4.0 approved by user)
   - G2 location:            PASS (Workspace-local verified)

8. Limitations / honesty note
   - Cleanliness, balance, and annotation accuracy are not asserted here; to be evaluated in PHASE_03.
   - External licence attribution verified against Zenodo record 18528034.

9. Result: COMPLETE
   Next phase authorised? Awaiting separate user approval for PHASE_03.
```
