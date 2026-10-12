# SafeRoute AI — PHASE_02 Completion Report (recorded)

> **Phase:** PHASE_02 — Dataset Acquisition & Licence Approval Gate
> **Status:** **COMPLETE** (all mandatory PHASE_02 criteria satisfied)
> **Date recorded:** 2026-10-12
> **Workspace:** `D:\New folder (3)`
> **Record location:** `docs\reports\PHASE_02_report.md`
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) ·
> [`../phases/PHASE_02.md`](../phases/PHASE_02.md) ·
> [`../TRAINING_RULES.md`](../TRAINING_RULES.md) · [`../TRD.md`](../TRD.md)
> **Next phase (PHASE_03) authorised?** **NO — awaiting separate authorisation.**

This file is the recorded PHASE_02 completion report. It preserves the PHASE_02 evidence
gathered during the read-only investigation and adds the project owner's explicit approval
(§ A). No dataset file was modified, no download was performed, and no other project
documentation was changed. The `docs\phases\PHASE_00.md`–`PHASE_18.md` specifications, the
`docs\phases\README.md` index and `master_rules.md` were **not** edited.

---

## A. Recorded approval (auditability record)

| Field | Value |
|---|---|
| Approval date (actual) | **2026-10-12** |
| Approved by | Project owner (user), via explicit instruction in this session |
| Phase approved | PHASE_02 — Dataset Acquisition & Licence Approval Gate |
| Gates closed by this approval | **A1** (start PHASE_02), **A2** (specific dataset + licence), **A3** (accept already-present dataset; no download) |
| Gate A4 | Not triggered — dataset is inside the workspace |

**Verbatim decisions recorded (project owner):**

1. Dataset **"Road Damage Dataset: Potholes, Cracks and Manholes"** (Zenodo record `18528034`,
   DOI `10.5281/zenodo.18528034`), under **CC BY 4.0**, is approved for the initial YOLO11
   pothole-and-crack detector.
2. The existing local archive is accepted. **Do not download another copy.**
3. The stale DOI in the bundled README and the discrepancy between the dataset's three classes
   and the project's intended classes are **acknowledged for PHASE_03**.

**Binding constraints carried forward from this approval:**

- **Attribution (CC BY 4.0) is retained and mandatory** for all uses of this dataset (§ 2 below).
- **Class boundary preserved:** the dataset's `manhole` annotations (class id 2) **must never be
  silently relabelled** as `pothole` or `crack`. Any class mapping is a PHASE_03 decision requiring
  its own approval.
- No download / copy / relabel / modification occurs without separate explicit approval (Rule 19).

**Evidence referenced for this approval** (read-only): the Zenodo public API records cited in § 4
and the appendix, the local archive hash, the bundled dataset `README.md`, and the local COCO JSON
structure. Full details in § 4, § 6 and the Appendix.

---

## B. PHASE_02 — Completion Report (§11 template)

```
PHASE_02 — Completion Report
============================
Date (actual):          2026-10-12
Record location:        D:\New folder (3)\docs\reports\PHASE_02_report.md
Approval reference:     Explicit project-owner approval, 2026-10-12 (this session):
                        (1) approves dataset "Road Damage Dataset: Potholes, Cracks and
                            Manholes", Zenodo record 18528034, DOI 10.5281/zenodo.18528034,
                            licence CC BY 4.0, for the initial YOLO11 pothole-and-crack detector;
                        (2) accepts the existing local archive (no further download);
                        (3) acknowledges the stale bundled-README DOI and the dataset's
                            3 classes vs the project's intended classes, for PHASE_03.

1. Dataset identity
   - Name:               "Road Damage Dataset: Potholes, Cracks and Manholes"
   - Source / URL:       Zenodo (CERN) — https://zenodo.org/records/18528034
                         DOI 10.5281/zenodo.18528034 (version), concept DOI 10.5281/zenodo.17834372
   - Version / date:     Latest version of concept 17834372; published 2026-02-08, revision 5
                         (concept's prior version: record 17834373, v0.1.0, published 2025-12-05)
   - Retrieval date:     Not recorded in shipped evidence. Local file timestamp 2026-10-11 22:17:52
                         (copy time, not a verified retrieval date). Approval recorded 2026-10-12.

2. Licence & provenance
   - Licence:            Creative Commons Attribution 4.0 International (CC BY 4.0)
                         (Zenodo record metadata: license.id = "cc-by-4.0"; access_right = open)
   - Permitted use:      Model training is permitted. CC BY 4.0 §2(a)(1) grants a "worldwide,
                         royalty-free, non-sublicensable, non-exclusive, irrevocable license to
                         ... reproduce and Share the Licensed Material ... and ... produce,
                         reproduce, and Share Adapted Material." No NonCommercial/ShareAlike terms.
   - Restrictions:       Attribution required (see below); no endorsement; indicate modifications.
   - Training permitted? YES — as declared by the Zenodo source record for this dataset.
                         (Not inferable from the local files; permission is established only from
                         the external source record, not from the local COCO metadata.)
   - Key excerpts:       CC BY 4.0 §3(a)(1): "If You Share the Licensed Material ... You must:
                         retain ... identification of the creator(s) ...; a copyright notice; a
                         notice that refers to this Public License; a notice that refers to the
                         disclaimer of warranties; a URI or hyperlink to the Licensed Material";
                         and "indicate if You modified the Licensed Material."
                         CC BY 4.0 §3(b): "No endorsement."
   - Attribution:        Preview: Giordani, Enrico (Sapienza University of Rome); Arcioni, Lorenzo
                         (Sapienza); Gil-Martín, Manuel (Universidad Politécnica de Madrid);
                         Marini, Marco Raoul (Sapienza). Credit the creators, keep a copyright
                         notice, state the licence (CC BY 4.0) with a link, keep the warranty
                         disclaimer, link to the material URI, and indicate any modifications.
                         The bundled README requests citation of https://doi.org/10.5281/zenodo.17834373
                         (superseded); the current citation is 10.5281/zenodo.18528034
                         (concept 10.5281/zenodo.17834372).

3. Location
   - Path:               D:\New folder (3)\data\pothole_crack_manhole\data\
                         Archive: D:\New folder (3)\data\raw\data.zip
   - Inside workspace?   YES — both under D:\New folder (3)\ (Rule 1 satisfied).
   - Authorisation ref:  n/a (inside workspace; Gate A4 not triggered).

4. Contents (as found — counted, not modified)
   - Images:             2,009 (.jpg)
   - Annotation files:   2,009 polygon labels (labels/) + 2,009 YOLO labels (labels-YOLO/)
                         COCO JSON: 2,009 images, 4,737 annotations
   - Declared format:    YOLO (labels-YOLO/), normalized polygon (labels/), COCO JSON
                         (annotations_coco.json)
   - Declared classes:   id 0 = Pothole, id 1 = Crack, id 2 = Manhole  (three classes only)
                         per-class instances (labels-YOLO and COCO agree):
                         pothole 1,261 · crack 2,519 · manhole 957
   - Total size:         extracted set 194,786,682 bytes (~185.8 MiB); 6,031 files
                         archive 194,163,315 bytes (~185.2 MiB); 6,035 zip entries
   - Checksum/manifest:  LOCAL  data.zip  MD5    317862054545467ff00be611db8ff07e
                                        SHA256 c7b7247c611efa0a12eb8b998583da496f90c9b4859e9e1de2c1b06adbb80cef
                         EXPECTED (README-cited DOI 17834373, "archive.zip"):
                                        md5:ef8b402e9f7ee7d2e64919f21ad6ab6a, size 193,459,929
                                        => MISMATCH (superseded version)
                         EXPECTED (approved DOI 18528034, "data.zip"):
                                        md5:317862054545467ff00be611db8ff07e, size 194,163,315
                                        => EXACT MATCH (size + MD5)
                         => The approved local archive matches the approved Zenodo artifact
                            byte-for-byte. It does not match the superseded version cited in the
                            dataset's bundled README (risk R1).

5. Risks noted
   - R1 Stale citation: bundled README points to superseded DOI 10.5281/zenodo.17834373 (v0.1.0);
     local bytes match the approved record 10.5281/zenodo.18528034. Both are CC BY 4.0.
     ACKNOWLEDGED by the project owner for PHASE_03.
   - R2 No licence/provenance inside the local data: annotations_coco.json has top-level keys only
     (images, annotations, categories); no "info" or "licenses" field; no LICENSE/COPYING file is
     bundled. Permission must NOT be inferred from the local files.
   - R3 Class mismatch: dataset has 3 classes (pothole, crack, manhole); project target has 7
     (pothole, crack, damaged_patch, waterlogging, uneven_surface, speed_bump, other). "manhole" is
     not a target class; 5 target classes are absent. ACKNOWLEDGED for PHASE_03; no silent relabel.
   - R4 No train/val/test split present (single images/ pool); split policy, test isolation and
     leakage checking are PHASE_03.
   - R5 Integrity not yet measured: image decode, image–label pairing, malformed/empty labels,
     duplicates. PHASE_03. No cleanliness is claimed here.
   - R6 Attribution obligation (CC BY 4.0) is active for any published use.

6. Validation results
   V1 Licence documented ............ PASS — CC BY 4.0 recorded from the source record; training use
                                              stated as permitted (source licence text captured).
   V2 Provenance recorded ........... PASS — publisher, DOI, concept DOI, version, dates captured.
   V3 Location verified ............. PASS — inside D:\New folder (3)\.
   V4 Contents counted .............. PASS — 2,009 images; 4,018 label files; 4,737 COCO annotations.
   V5 Format identified ............. PASS — YOLO + normalized polygon + COCO JSON, from actual files.
   V6 Identity captured ............. PASS — sizes recorded; MD5 matches the approved Zenodo artifact;
                                              SHA256 also recorded.
   V7 Risks listed .................. PASS — R1–R6 above.
   V8 No modification ............... PASS — no dataset file altered; no download performed
                                              (Zenodo API / CC legal-code lookups are read-only
                                              metadata queries).

7. Gate status
   - G1 provenance & licence: PASS — licence documented (CC BY 4.0, permits training); provenance
                                   verified against the approved record (checksum match); explicit
                                   owner approval recorded 2026-10-12 (§ A).
   - G2 location:             PASS — verified inside the approved workspace.
   PHASE_02 gates A1/A2/A3: PASS (§ A). Gate A4: not applicable.

8. Limitations / honesty note
   - This phase documents provenance and licence only. It does NOT assert the dataset is clean,
     balanced, correctly annotated, split, or duplicate-free; those are PHASE_03 measurements.
   - No metrics are reported. No files created, modified or deleted other than this recorded
     completion report. No packages installed. No dataset copied/downloaded. No splits prepared.
     No training performed.
   - The licence conclusion rests on the external Zenodo record; the local copy carries no licence
     metadata. This is documentation of a licence, not legal advice.
   - Class coverage (manhole vs the 7 target classes) and integrity remain PHASE_03 scope.
   - The phase index docs\phases\README.md still lists PHASE_02 as "Not started" and carries a
     blanket "all phases Not started" note; it was NOT edited (it is part of the frozen governance
     baseline and editing it was not requested). See "Open items" below.

9. Result: COMPLETE
   Next phase authorised? NO (awaiting separate authorisation for PHASE_03)
```

---

## C. Acceptance-criteria check (PHASE_02 §7)

| Criterion | Status | Evidence |
|---|---|---|
| Licence recorded and permits intended use | ✔ | CC BY 4.0, Zenodo records 18528034 / 17834373; § B.2 |
| Location confirmed compliant with Rule 1 | ✔ | Both paths under `D:\New folder (3)\`; § B.3 |
| Image/annotation counts recorded (mismatch noted) | ✔ | 2,009 images / 4,737 annotations; source states no count, so no mismatch to reconcile; § B.4 |
| Dataset identity recorded (name, source, version, checksum) | ✔ | § B.1, § B.4 |
| No file modified, no unapproved download | ✔ | Read-only; § B.6 V8 |
| Completion report submitted and accepted | ✔ | This record + owner approval 2026-10-12 (§ A) |

**Stop conditions (§8) re-checked:** none triggered — licence permits training; dataset is inside
the workspace; location verified; format/class differences are explicitly deferred to PHASE_03
(§8.4 says "handled in PHASE_03"); no unapproved download/credential/paid service was required.

---

## D. Open items (PHASE_03 scope — not PHASE_02 blockers)

These do **not** prevent PHASE_02 completion; they are the documented inputs to PHASE_03:

1. **Class reconciliation** — map the dataset's 3 classes to the project's intended classes; decide
   explicitly how `manhole` (id 2) is treated. **Never silently relabel manhole as pothole/crack.**
2. **Stale citation cleanup** — the bundled `README.md` cites the superseded DOI; PHASE_03 may
   record/repoint the correct citation (`10.5281/zenodo.18528034` / concept `10.5281/zenodo.17834372`)
   only with its own approval (Rules 18/19). The bundled README was not edited now.
3. **Integrity audit** — decode check, image–label pairing, malformed/empty labels, duplicates.
4. **Split policy** — define train/validation/test, test isolation and leakage checks.
5. **Governance index** — `docs\phases\README.md` status row(s) still read "Not started"; updating
   the index to reflect completed phases is a documentation-governance action needing explicit
   authorisation (not performed here).

---

## E. Compliance / no-action statement

- All operations remained inside `D:\New folder (3)` (Rule 1).
- Only this report file was created; no existing file was modified or deleted (Rules 18/19).
- No dataset was downloaded or copied; the existing local archive was **not** modified (Rule 19, § B.6 V8).
- No packages installed; no virtual environment created; no dataset splits prepared; no training
  started (Rules 3/4/19).
- The read-only lookups performed were: the Zenodo public API record metadata (records 17834373,
  18528034 and the versions list) and the Creative Commons CC BY 4.0 legal-code text. These are
  metadata/licence queries, not dataset downloads.
- Attribution obligations under CC BY 4.0 are retained (§ A, § B.2).

---

## Appendix — evidence log (read-only)

**A. Zenodo record metadata**

- Concept: DOI `10.5281/zenodo.17834372` (recid 17834372).
- Record `17834373` (superseded; cited by bundled README):
  - DOI `10.5281/zenodo.17834373`; version `0.1.0`; published `2025-12-05`;
    licence `cc-by-4.0`; access `open`.
  - File `archive.zip` — size `193,459,929`; `md5:ef8b402e9f7ee7d2e64919f21ad6ab6a`.
- Record `18528034` (approved; matches local archive):
  - DOI `10.5281/zenodo.18528034`; published `2026-02-08`; revision `5`; `is_last = true`;
    licence `cc-by-4.0`; access `open`; resource type `dataset`.
  - File `data.zip` — size `194,163,315`; `md5:317862054545467ff00be611db8ff07e`.
  - Creators: Giordani, Enrico (Sapienza University of Rome); Arcioni, Lorenzo (Sapienza,
    ORCID 0009-0001-0963-3993); Gil-Martín, Manuel (Universidad Politécnica de Madrid,
    ORCID 0000-0002-4285-6224); Marini, Marco Raoul (Sapienza, ORCID 0000-0002-2540-2570).

**B. Local archive**

- Path: `D:\New folder (3)\data\raw\data.zip`
- Size: `194,163,315` bytes · MD5 `317862054545467ff00be611db8ff07e` ·
  SHA256 `c7b7247c611efa0a12eb8b998583da496f90c9b4859e9e1de2c1b06adbb80cef`
- Zip entries: `6,035` (2009 `.jpg`, 4018 `.txt`, scripts + `annotations_coco.json` + `README.md`;
  includes directory entries). Top-level folder: `data`.

**C. Extracted dataset**

- Path: `D:\New folder (3)\data\pothole_crack_manhole\data\`
- `images/` 2,009 `.jpg` (640×360); `labels/` 2,009 polygon `.txt`; `labels-YOLO/` 2,009 YOLO `.txt`.
- `annotations_coco.json`: keys `images, annotations, categories` only (no `info`, no `licenses`);
  2,009 images; 4,737 annotations; categories `0=pothole, 1=crack, 2=manhole`.
- Per-class instances: pothole `1,261`; crack `2,519`; manhole `957`.
- Total extracted size: `194,786,682` bytes; `6,031` files.

**D. Commands/queries used (all read-only)**

- PowerShell file inventory, counts and `Get-FileHash` (MD5/SHA256) on `data.zip`.
- `System.IO.Compression.ZipFile` enumeration of `data.zip` (no extraction).
- JSON parse of `annotations_coco.json` (read-only).
- HTTPS GET `https://zenodo.org/api/records/17834373`
- HTTPS GET `https://zenodo.org/api/records/17834373/versions`
- HTTPS GET `https://zenodo.org/api/records/18528034`
- HTTPS GET `https://creativecommons.org/licenses/by/4.0/legalcode.txt`
