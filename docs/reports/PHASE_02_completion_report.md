# PHASE_02 — Completion Report
**Date (actual):** 2026-10-12  
**Approval reference:** User approved starting PHASE_02 following master_rules.md and PHASE_02.md (2026-10-12). No download/copy/modify actions performed.  
**Status:** COMPLETE

## 0. Corrections history
- **This edit (2026-10-12):** Corrected dataset size units (extracted dir 194,786,682 bytes / ~185.76 MiB; added archive identity). Incorporated existing workspace provenance/licence references (Zenodo), separating locally verified facts from prior-reported external verification. Clarified README DOI (17834373) vs approved Zenodo record/concept (18528034 / 17834372). Corrected V1/V6 validation statuses and acceptance criteria to reflect missing local licence metadata while noting prior-recorded licence evidence. Preserved original content; added corrections and verification notes below.

## 1. Dataset identity
- **Name:** Road Damage Dataset: Potholes, Cracks, and Manholes (pothole_crack_manhole)
- **Source / URL:** Zenodo (CERN) — see §2 provenance notes. Bundled README cites `https://doi.org/10.5281/zenodo.17834373` (superseded). Prior PHASE_02/03 records identify approved Zenodo record `18528034` (DOI `10.5281/zenodo.18528034`) with concept `10.5281/zenodo.17834372`.
- **Version / date:** Bundled README gives no version/date. Prior recorded evidence: latest version of concept 17834372; published 2026-02-08, revision 5 (record 18528034). Record 17834373 (v0.1.0, 2025-12-05) is superseded.
- **Retrieval date:** Not recorded in shipped/local evidence. Local archive timestamp `2026-10-11 22:17:52` (copy time only — **not** a verified retrieval date).

## 2. Licence & provenance
- **Licence:** Not explicitly stated in `README.md` (no CC/MIT/Apache/ODbL/other licence text found). 
- **Permitted use:** README states "intended for object detection research and evaluation". 
- **Restrictions:** Not specified.
- **Training permitted?** Unclear from README text — "research and evaluation" is stated; no explicit "commercial use" / redistribution terms visible.
- **Key excerpts:** "This dataset contains images of road surfaces with potholes, cracks, and manholes, along with polygon-based, YOLO-compatible, and COCO JSON annotations. It is intended for object detection research and evaluation."

## 3. Location
- **Path:** `D:\New folder (3)\data\pothole_crack_manhole\data\`
- **Inside workspace?** Yes.
- **Authorisation ref:** Not required (inside workspace). No external storage used.

## 4. Contents (as found)
- **Images:** 2009 files (`images\*.jpg`)
- **Annotation files:** 
  - `labels\` — 2009 polygon label files (4-point quadrilaterals, normalized)
  - `labels-YOLO\` — 2009 YOLO-format files (axis-aligned bbox, normalized) — ready for YOLO
  - `annotations_coco.json` — COCO JSON annotations (bbox in pixels)
- **Declared format:** Mixed (YOLO format present in labels-YOLO; polygon in labels; COCO in annotations_coco.json)
- **Declared classes:** 0=Pothole, 1=Crack, 2=Manhole (3 classes)
- **Total size (extracted `data\`):** 194,786,682 bytes (**≈ 185.76 MiB**)
- **Archive:** `D:\New folder (3)\data\raw\data.zip` — 194,163,315 bytes (**≈ 185.17 MiB**), LastWriteTime 2026-10-11 22:17:52
- **Checksum/manifest:** 
  - `data\raw\data.zip` (MD5): 317862054545467FF00BE611DB8FF07E
  - `data\raw\data.zip` (SHA256): C7B7247C611EFA0A12EB8B998583DA496F90C9B4859E9E1DE2C1B06ADBB80CEF
  - `annotations_coco.json` (MD5): 8D877AE14AE43B6290CE63F3308C4DCF
  - `YOLO-conversion-script.py` (MD5): EDFCD4CF1BCA53EAFA0DC987C39C0E82
  - `COCO-conversion-script.py` (MD5): E446F67394532C3BE282AFD6B974D53E
  - **Local→external identity:** Local archive MD5 matches the value attributed to Zenodo record `18528034` in existing workspace records; this is **consistent** with that record, but external Zenodo API lookup was not independently re-executed in this review.

## 5. Risks noted
- **Licence ambiguity:** No explicit licence type/version/terms in the bundled dataset files (`README.md` has no licence text; `annotations_coco.json` has no `info/licenses`; no `LICENSE/COPYING`). Training permission is not inferable from local files. Existing workspace records (e.g. `docs\reports\PHASE_02_report.md`) state **CC BY 4.0** for the Zenodo record `18528034` (external verification) — this is **prior-reported** evidence; it was not independently re-verified here. "Research and evaluation" in README alone may be insufficient depending on deployment goals.
- **Citation mismatch (stale DOI in bundled README):** Bundled README cites `10.5281/zenodo.17834373` (superseded). Prior records identify `10.5281/zenodo.18528034` (record) and concept `10.5281/zenodo.17834372` as the current version. These are **different** DOIs and must not be treated as identical.
- **Class mismatch vs SafeRoute target:** SafeRoute targets potholes, cracks, damaged road patches, waterlogging, uneven/subsided surfaces, speed bumps, other. This dataset provides pothole/crack/manhole only (3 classes). Manhole is present but not in SafeRoute’s primary target list.
- **Annotation format variation:** Both polygon and converted YOLO/COCO forms exist. Using converted forms requires verifying conversion correctness (handled in PHASE_03).
- **Provenance incomplete locally:** Original source URL/version/retrieval date not specified in the bundled README; external source/metadata exist in prior workspace records but require careful separation between local facts and prior-reported external evidence.
- **Potential domain mismatch:** Images collected for general road damage; may differ from SafeRoute’s intended deployment conditions.
- **COCO metadata:** `annotations_coco.json` contains `images`, `annotations`, `categories` only (no `info`/`licenses`) — confirms no local licence metadata.

## 6. Validation results
- V1 Licence documented: **PARTIAL** (no explicit licence text in local dataset files; licence metadata absent from COCO. Existing workspace records state CC BY 4.0 for Zenodo record 18528034 — **prior-reported external evidence**, not independently re-verified in this review.)
- V2 Provenance recorded: **PARTIAL** (name/structure and local archive identity recorded; bundled README cites DOI 17834373 which differs from prior-recorded 18528034/17834372. Source URL/version/retrieval date not determinable from local files alone.)
- V3 Location verified: **PASS** (inside workspace `D:\New folder (3)\data\pothole_crack_manhole\data`)
- V4 Contents counted: **PASS** (2009 images; 2009 polygon labels; 2009 labels-YOLO; COCO JSON present with 4,737 annotations)
- V5 Format identified: **PASS** (YOLO axis-aligned bbox present; polygon/COCO also available)
- V6 Identity captured: **PARTIAL** (extracted size/MB corrected, archive size/hash/identity recorded; full external artifact match to Zenodo 18528034 is prior-reported evidence)
- V7 Risks listed: **PASS** (licence ambiguity, citation mismatch between README DOI and approved record, class mismatch, provenance gaps noted)
- V8 No modification: **PASS** (read-only inspection; no files altered, no unapproved download)

## 7. Gate status
- **G1 provenance & licence:** PARTIAL — no local licence text/provenance; citation in bundled README (DOI 17834373) differs from prior-recorded approved references (18528034 / 17834372). Prior workspace records indicate CC BY 4.0 for record 18528034 (external), but this is **prior-reported** rather than independently re-verified here. Requires clarification before relying on the dataset for production use.
- **G2 location:** PASS — dataset located inside approved workspace.

## 8. Limitations / honesty note
- **Corrections applied:** This revision corrects size/units, adds archive identity (MD5/SHA256), clarifies DOI references, and corrects V1/V6/acceptance criteria. Previous statements were incomplete; corrections are documented above without removing the original record of the review.
- **Locally verified vs prior-reported:** Local facts (counts, sizes, hashes, file presence, absence of local licence metadata) are verified. External attribution to Zenodo record 18528034/licence CC BY 4.0 is drawn from prior workspace reports and is **prior-reported**, not independently re-verified here.
- **Citation mismatch:** Bundled README cites DOI `10.5281/zenodo.17834373` (superseded); prior records reference `10.5281/zenodo.18528034` (record) and concept `10.5281/zenodo.17834372`. These differ and must not be conflated.
- This phase documents the existing dataset only; no assertions about cleanliness, balance, class coverage adequacy, or annotation correctness.
- Licence terms must be clarified/confirmed by dataset owner/source if commercial or broader use is intended. "Research and evaluation" alone is insufficient without explicit licence terms; the absence of local licence metadata means permission must not be inferred solely from local files.
- SafeRoute’s hazard classes include additional classes not present (waterlogging, damaged patches, uneven surfaces, speed bumps, other); manhole exists but may need policy decisions.
- No download/copy/relabel/modify performed; integrity audit (PHASE_03) will measure splits, pairing, leakage, corrupt images, malformed annotations.

## 9. Result: COMPLETE / BLOCKED / STOPPED
**Result:** COMPLETE  
**Next phase authorised?** NO — awaiting user review and explicit approval before proceeding to PHASE_03. Gates G1 is PARTIAL (no local licence metadata; citation mismatch; external licence attribution is prior-reported); G2 is PASS.

## 10. PHASE_02 acceptance criteria (re-checked)
| Criterion | Status | Evidence |
|---|---|---|
| Licence recorded and permits intended use | **PARTIAL** | No explicit licence in local files; `annotations_coco.json` has no `info/licenses`; prior records cite CC BY 4.0 (external) — prior-reported, not independently re-verified. |
| Location confirmed compliant with Rule 1, with evidence | **PASS** | Dataset and archive inside `D:\New folder (3)`. |
| Image/annotation counts recorded, consistent with source claims | **PASS** | 2,009 images; 2,009 polygon labels; 2,009 labels-YOLO; 4,737 COCO annotations. Source claims not stated locally; no mismatch asserted. |
| Dataset identity recorded (name, source, version, checksum) | **PARTIAL** | Name recorded. Source/version limited by local files; archive size+hashes recorded. External DOI/version (18528034/17834372) from prior records. |
| No file modified, no unapproved download | **PASS** | Read-only; only this report written (authorized). |
| Completion report submitted and accepted | **UNVERIFIED** | Submitted; acceptance pending user review.
