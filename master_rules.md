# SafeRoute AI — Master Rules

> **Status:** Authoritative root-level engineering rules for the SafeRoute AI project.
> **Scope:** Applies to every phase, contributor, script, dataset, model and document in this project.
> **Effective date:** 2026-10-11

This file is the project's root-level engineering rules document. It must be followed
alongside the approved PRD, TRD and architecture documents once those are created.
Where this file and another approved document conflict, the conflict must be raised and
resolved explicitly — it must never be silently overridden.

---

## Project objective

Build **SafeRoute AI**, an intelligent road-safety navigation system that compares
available routes using road-hazard detection, deterministic risk scoring, permitted
route imagery, and grounded AI explanations.

Intended pipeline:

```
USER → DESTINATION INPUT → ROUTING PROVIDER → AVAILABLE ROUTES → ROAD IMAGERY
     → OPENCV → YOLO11 HAZARD DETECTION → HAZARD AGGREGATION
     → DETERMINISTIC RISK ENGINE → ROUTE SAFETY COMPARISON
     → GROUNDED LLM EXPLANATION → FRONTEND
```

Up to four routes are compared **when they are actually returned**. Never invent routes,
detections, scores, image coverage or facility counts.

---

## Rules

1. **Workspace isolation.** All project files, datasets, source code, model weights,
   virtual environments, documentation, logs and outputs must remain inside
   `D:\New folder (3)`. Do not create project files elsewhere.

2. **Follow documented requirements.** Treat this file as the project's root-level
   engineering rules. Follow it alongside the approved PRD, TRD and architecture
   documents once created. Never silently override an approved requirement.

3. **Incremental development.** Complete one approved phase at a time. Verify the
   result before moving to the next phase.

4. **YOLO11.** Use Ultralytics YOLO11 for road-hazard detection. Do not start training
   until dataset availability, annotations, split integrity, environment compatibility
   and GPU availability have been checked.

5. **Hazard classes.** Target potholes, cracks, damaged road patches, waterlogging,
   uneven/subsided surfaces, speed bumps and other hazards. Report unsupported or
   untrained classes honestly.

6. **OpenCV.** Use a consistent, documented preprocessing pipeline for training and
   inference. Apply only preprocessing that is justified and tested.

7. **Deterministic risk engine.** The backend risk engine calculates safety scores
   using documented formulas and verified detector outputs. The LLM must never
   calculate or invent safety scores.

8. **Route imagery.** Use only imagery sources whose access and reuse are permitted.
   Never assume that routing APIs grant permission to download or reuse street-level
   imagery.

9. **Missing coverage.** Missing, stale, inaccessible or insufficient imagery must be
   disclosed as unknown or unassessed. Never treat missing evidence as proof of a safe
   road.

10. **Routing.** Display only routes actually returned by the selected routing provider.
    Show fewer than four when fewer valid alternatives are available.

11. **Facilities.** Keep nearby facilities separate from the road-hazard score unless an
    explicit, documented and approved requirements change establishes a separate
    facility-aware ranking policy. Never silently mix facility counts into the hazard
    score.

12. **LLM boundaries.** The LLM may parse user preferences and explain verified backend
    results. It must not fabricate routes, road conditions, hazards, facilities,
    measurements or safety claims.

13. **Security.** Never commit API keys, credentials, personal data or secrets to source
    code. Use local environment configuration and document safe setup.

14. **Testing.** Provide reproducible commands and report actual results. Separate
    measured metrics from estimates and planned work. Never fabricate successful tests,
    precision, recall, F1 or mAP.

15. **Dataset integrity.** Verify licences, annotation formats, class IDs, image-label
    pairing and train/validation/test leakage before training. Do not silently relabel
    or discard data.

16. **Hardware awareness.** Check available RAM, disk space, GPU VRAM and
    CUDA-compatible PyTorch before selecting training settings.

17. **Documentation.** Record architecture decisions, dependencies, commands, dataset
    provenance, model versions, limitations and known issues.

18. **Minimal changes.** Inspect relevant files before editing. Preserve existing work,
    avoid unnecessary dependencies and do not rewrite unrelated files.

19. **No unauthorized actions.** Do not download datasets, install packages, call paid
    APIs, create credentials, modify existing datasets or start training without
    explicit approval for that phase.

20. **Honest demonstration.** Clearly distinguish working features, simulated features,
    sample data, missing coverage and unvalidated capabilities.
