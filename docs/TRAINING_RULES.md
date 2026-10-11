# SafeRoute AI — Training Rules

> **Project:** SafeRoute AI — Intelligent Road Safety Navigation System
> **Workspace:** `D:\New folder (3)`
> **Status:** Draft — pending approval
> **Version:** 0.1
> **Date:** 2026-10-11
> **Companion rules:** [`../master_rules.md`](../master_rules.md) (authoritative)
> **Companion documents:** [`PRD.md`](./PRD.md) · [`TRD.md`](./TRD.md) · [`ARCHITECTURE.md`](./ARCHITECTURE.md)

This document is subordinate to `master_rules.md`, `docs\PRD.md`, `docs\TRD.md` and
`docs\ARCHITECTURE.md`. Where any conflict arises, `master_rules.md` prevails and the
conflict must be raised and resolved explicitly — never silently overridden. These rules
**do not weaken** any rule in `master_rules.md`.

**Evidence convention:**

- **[VERIFIED]** — observed fact confirmed inside the workspace or by a read-only system query.
- **[PROPOSED] / [PROVISIONAL]** — recommended setting; **not validated, not installed, not trained**.
- **[UNKNOWN]** — requires a decision, verification or asset that does not yet exist.

**Current verified state [VERIFIED]:** the workspace contains only `master_rules.md` and the
four files in `docs\` (`PRD.md`, `TRD.md`, `ARCHITECTURE.md`, and this file). There is **no
dataset, no model checkpoint, no virtual environment, and no source code**. Training
**cannot** and **must not** begin without the approval gates in §2.

---

## 1. Training objective

Train an Ultralytics **YOLO11** road-hazard detector for SafeRoute AI that detects the seven
**proposed** classes below — **subject to verification against the actual dataset**:

| Proposed ID | Proposed class |
|---|---|
| 0 | `pothole` |
| 1 | `crack` |
| 2 | `damaged_patch` |
| 3 | `waterlogging` |
| 4 | `uneven_surface` |
| 5 | `speed_bump` |
| 6 | `other` |

**Hard constraints:**

- **Never assume** the dataset actually contains these seven classes.
- **Never assume** the dataset's annotation IDs already match this proposed order.
- The **actual** annotation format and class mapping must be read from the dataset and
  reconciled (via an approved, documented mapping) before any training. Discrepancies must
  be **reported**, not silently relabelled or discarded (Rules 5, 15).
- Only classes that are **present and trained** may be reported by inference. Unsupported or
  untrained classes must be disclosed honestly (Rule 5, 20).

The detector's objective is **hazard detection only**. It does **not** compute route safety
scores; that is the deterministic risk engine's responsibility (Rule 7).

---

## 2. Pre-training approval gates

**Do not start training until every applicable gate below passes.** If a mandatory gate
fails, **stop and report** the failure and the limitation. Do not silently skip a gate
(Rules 4, 15, 16, 19).

| # | Gate | Pass condition |
|---|---|---|
| G1 | Dataset provenance & licence | Source and licence documented; permitted use established (Rules 15, 17). |
| G2 | Dataset location | Dataset present **inside** the approved workspace `D:\New folder (3)`, **or** another location **explicitly authorized by the user** (Rule 1). |
| G3 | File count | Total image count recorded and matches expectation; documented on disk. |
| G4 | Images readable | Every image (or a documented sample) decodes successfully; unreadable files counted. |
| G5 | Annotations valid | Annotation files parse; boxes are normalized and within `[0,1]`; no malformed lines. |
| G6 | Format & class mapping verified | Actual annotation format (YOLO/COCO/VOC) and class IDs read from the data and recorded. |
| G7 | Data hygiene audit | Empty labels, invalid boxes, duplicate files and corrupt images audited and counted (Rule 15). |
| G8 | Splits documented | Train/validation/test splits documented; cross-split **leakage** checked (Rule 15). |
| G9 | Test isolation | Test data excluded from training and from model selection. |
| G10 | Environment recorded | Python and installed package versions recorded (PyTorch, Ultralytics, OpenCV, etc.). |
| G11 | GPU/CUDA verified | PyTorch **detects the intended GPU** and `torch.cuda.is_available() == True`. If not, **stop and report** before selecting any approved alternative (Rule 16). |
| G12 | Resources checked | Free disk space and available system/GPU memory measured (Rule 16). |
| G13 | Baseline plan recorded | A baseline training configuration **and** evaluation plan are written down before running. |

> **Current status:** G1, G2, G3–G9, G10–G13 are **all unmet [UNKNOWN]** — no dataset exists
> and the only observed PyTorch was CPU-only (`torch 2.14.0+cpu`, `torch.cuda.is_available()
> == False`) [VERIFIED]. **Training is therefore currently blocked.**

---

## 3. Model selection

- **Baseline: YOLO11n [PROPOSED].** Start with the smallest YOLO11 variant. Rationale: the
  project has a **short deadline** and **limited available memory** (16 GB RAM, ~8 GB VRAM
  with ~1.5 GB in use [VERIFIED]). A small model gives a fast, honest baseline.
- **YOLO11s / YOLO11m: later experiments [PROPOSED].** Consider a larger variant **only
  after** the baseline is measured and resources allow. A larger model is **not** a
  mandatory first run.
- **Pretrained checkpoint [UNKNOWN]:** do **not** download any pretrained checkpoint until
  its **source, licence, compatibility** (with the installed Ultralytics/PyTorch) **and user
  approval** are established (Rule 19). Record the exact checkpoint, source and licence.
- **Variant vs version:** record the **model variant** (e.g. `n`/`s`/`m`) **separately**
  from the **model version identifier**, so the version label remains stable across size
  experiments.
- **Version identifier:** use **`saferoute-yolo11-v1`** as the proposed version identifier.
  ⚠️ **Flagged inconsistency (do not edit the PRD):** `docs\PRD.md` §5 writes this as
  `safroute-yolo11-v1`, which conflicts with `saferoute-yolo11-v1` used in `docs\TRD.md`
  §5.6 and `docs\ARCHITECTURE.md` §5. This must be reconciled by an **approved documentation
  update**; until then, `saferoute-yolo11-v1` is used and the discrepancy remains open.

---

## 4. Reproducibility

Every training run must be reproducible from its recorded artifacts. Document all of the
following (Rules 14, 17):

- **Dataset identity**: name, source, and version/hash (e.g. a content hash/checksum of the
  dataset or a manifest) **where practical**.
- **Class mapping and split manifest**: the exact class-ID → class-name mapping and the list
  of images in each split.
- **Software versions**: Python, PyTorch, CUDA, Ultralytics, OpenCV, and OS/driver versions.
- **Model variant and checkpoint provenance**: variant (n/s/m) and the exact pretrained
  checkpoint used (source + licence).
- **Effective settings**: image size, batch size, epochs, workers, seed, optimizer,
  augmentation, AMP, early-stopping patience, and any other non-default option.
- **Run record**: the exact training command, timestamp, log path and output paths.
- **Environment/observations**: hardware, errors, warnings, and any configuration changes
  made during the run (with justification).
- **Naming**: checkpoint and experiment naming convention (see §7).

> **All numeric hyperparameters are [PROVISIONAL]** until the dataset and the GPU environment
> are verified. No specific batch size, image size, epoch count or worker count is
> guaranteed to work; values must be chosen from measured hardware headroom and the actual
> dataset (Rule 16).

---

## 5. Training and resource management

- **Configurable, not hard-coded.** All settings (paths, `imgsz`, `batch`, `epochs`,
  `workers`, `seed`, thresholds) come from documented configuration, not assumptions
  embedded in code (Rule 18).
- **Small, controlled baseline first.** After all §2 gates pass and approval is granted,
  begin with one small baseline run before any scaling.
- **Validation drives model selection; test stays untouched** until final evaluation.
- **Checkpoints and logs** are saved in **documented locations inside the workspace**
  (e.g. `models\training\saferoute-yolo11-v1\` and `logs\`) (Rule 1).
- **Safe interruption/resume:** support resuming from the last checkpoint after an
  interruption **without corrupting** previous runs or logs (TRD §5.5).
- **Out-of-memory (OOM) handling:** on OOM, stop cleanly, preserve logs/checkpoints, and
  reduce memory pressure via a documented, minimal change (e.g. lower `batch`, smaller
  `imgsz`, or enable AMP). Record the change and reason. Do not silently retry with
  arbitrary settings.
- **Never delete previous checkpoints or logs** without explicit approval (Rules 18, 19).
- **Stop conditions:** halt immediately if any path resolves **outside** the workspace, or
  if unexpected changes appear in the dataset/config (Rule 1).

---

## 6. Evaluation

Report all of the following **only when actually measured** (Rule 14). Never invent metrics,
describe an untested model as trained, or claim real-world road-safety accuracy from training
results alone.

- **Precision, recall and F1.**
- **mAP@0.5** and **mAP@0.5:0.95.**
- **Per-class performance** and **confusion analysis** (where supported).
- **False positives** and **false negatives** (qualitative + counts where possible).
- **Representative prediction examples** (images with detections, human-reviewed).
- **Dataset split counts** and **class distribution** (including imbalance).
- **Inference speed and memory use** where measurable.

**Honesty requirements:**

- Report **class imbalance** and any weak/under-trained classes plainly.
- Explicitly state limitations: small/biased datasets, unresolved class coverage, and
  that detection quality does **not** equal real-world road-safety accuracy.
- Keep the **test set isolated**; do not tune to test results.
- The **LLM never produces metrics** — all numbers come from the deterministic evaluation.

---

## 7. Checkpoint acceptance and rollback

A checkpoint is **promoted** (made the serving/approved model) only when all of the
following hold. **A checkpoint must not be promoted solely because training loss
decreased.**

**Accept when:**
- All §2 gates passed for the run and the environment/dataset were verified.
- **Validation** metrics (not test) meet the pre-recorded baseline plan, and per-class
  results are acceptable for the supported classes.
- **Qualitative error analysis** on held-out images shows no disqualifying failure mode.
- The run's configuration, logs and provenance are fully recorded (§4).

**Reject when:**
- Loss decreased but validation mAP/precision/recall did not improve **and** qualitative
  review reveals regressions; or
- Validation collapses on one or more supported classes; or
- Any fabrication of evidence, leakage, or mis-recorded configuration is suspected.

**Retain for comparison when:**
- The checkpoint is promising but not clearly better; keep it as a named experiment for
  side-by-side comparison rather than overwriting the current approved model.

**Rollback when:**
- A newly promoted checkpoint later proves worse in evaluation or in inference review.
  Restore the **previous validated checkpoint**; keep the failed one archived for analysis.
  Never delete checkpoints during rollback without explicit approval.

---

## 8. Safe integration

- **Separate responsibilities:** training, evaluation and inference remain distinct
  components. Inference must not re-train or mutate model state.
- **Consistent class mapping & preprocessing:** inference must use the **same documented
  class mapping** and the **same versioned preprocessing pipeline** (TRD §7 / ARCHITECTURE
  §6) as recorded for the model.
- **LLM boundaries:** the LLM must **not** modify detections, compute the hazard/risk score,
  or claim hazards the model did not detect (Rules 7, 12).
- **Missing imagery:** unknown/unavailable imagery must remain **unknown/unassessed**, never
  automatically safe (Rule 9).
- **No premature claims:** do **not** claim the complete SafeRoute AI system works until the
  relevant components have been implemented **and tested** (Rules 3, 14, 20).

---

## 9. Training run checklist

**Before a run**
- [ ] All §2 gates (G1–G13) pass; approvals obtained.
- [ ] Dataset licence, provenance, class mapping and split manifest recorded.
- [ ] GPU/CUDA verified; free disk and memory measured.
- [ ] Baseline configuration and evaluation plan recorded (§4).
- [ ] No path resolves outside `D:\New folder (3)`.

**During a run**
- [ ] Logs and checkpoints written to documented workspace paths.
- [ ] Versions, seed and effective settings captured.
- [ ] Watch for OOM/errors/warnings; on issues, stop cleanly and record (§5).
- [ ] Do not delete prior checkpoints/logs; make no unrecorded parameter changes.

**After a run**
- [ ] Validation metrics computed; test set still untouched.
- [ ] Per-class results, confusion, FP/FN and sample predictions reviewed.
- [ ] Checkpoint accepted / retained / rejected / rolled back per §7.
- [ ] Run record (command, timestamp, logs, paths) written up.
- [ ] Limitations and class imbalance reported honestly.

---

## 10. Open decisions

| # | Open decision | Status |
|---|---|---|
| 1 | Dataset source, licence and provenance | [UNKNOWN] — no dataset present |
| 2 | Actual annotation format and class mapping | [UNKNOWN] — must read from real data |
| 3 | Train/validation/test split policy and leakage check | [UNKNOWN] |
| 4 | GPU environment (CUDA-enabled PyTorch) | [UNKNOWN] — only CPU-only torch observed |
| 5 | Pretrained checkpoint source and licence | [UNKNOWN] |
| 6 | Model size (n/s/m) and training schedule | [PROVISIONAL] — baseline YOLO11n proposed |
| 7 | Hyperparameters (imgsz, batch, epochs, workers, seed) | [PROVISIONAL] — pending dataset/GPU |
| 8 | Final evaluation criteria and acceptance thresholds | [UNKNOWN] |
| 9 | Model-version spelling reconciliation (`saferoute-` vs `safroute-`) | [UNKNOWN] — needs approved doc change |
| 10 | Checkpoint/log retention & naming policy | [UNKNOWN] |

---

## Quality rules acknowledgement

This document distinguishes **[VERIFIED]** facts from **[PROPOSED]/[PROVISIONAL]** settings and
**[UNKNOWN]** items; does not weaken `master_rules.md`; claims nothing is installed, trained or
tested; adds no files, directories, packages, datasets or model weights; and does not silently
alter approved PRD/TRD/ARCHITECTURE decisions.
