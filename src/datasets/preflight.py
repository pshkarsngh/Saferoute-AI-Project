"""P3 — read-only Phase 42 dataset preflight.

This checks the frozen independent dataset against the exact contract the Phase
42 evaluator consumes. It never runs inference and never touches the checkpoint.
A dataset can be ``PASS`` here while detector evaluation remains blocked by the
missing genuine v2 artifact.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..evaluation.dataset_validation import (
    DatasetValidationError,
    collect_dataset,
)
from ..evaluation.leakage import analyze_leakage, reference_session_ids_from_csv
from .common import CLASS_NAMES, FreezeStatus, SPLITS, utc_now
from .freeze import verify_frozen_hashes
from .reference import load_reference_registry


def _read_adjudication(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("image_id") or "").strip(): dict(row)
            for row in csv.DictReader(handle)
        }


def preflight_dataset(
    root: Path,
    *,
    reference_registry_path: Optional[Path] = None,
    reference_image_paths: Sequence[Path] = (),
    max_hamming_distance: int = 8,
    workspace: Optional[Path] = None,
) -> Dict[str, Any]:
    root = Path(root).resolve()
    dataset_yaml = root / "dataset.yaml"
    manifest_path = root / "manifests" / "independent_manifest.json"
    hashes_path = root / "manifests" / "dataset_hashes.json"

    report: Dict[str, Any] = {
        "tool_version": "phase43-v1",
        "generated_utc": utc_now(),
        "dataset_root": str(root),
        "dataset_yaml": str(dataset_yaml),
        "checks": [],
        "errors": [],
        "warnings": [],
        "status": FreezeStatus.NOT_ASSESSED.value,
        "dataset_ready": False,
        "detector_evaluation_blocked_by_model": True,
        "note": (
            "Dataset readiness only. Phase 42 detector evaluation additionally "
            "requires the genuine saferoute-yolo11-v2 checkpoint."
        ),
    }

    def check(name: str, status: str, detail: str, **evidence: Any) -> None:
        report["checks"].append(
            {"check": name, "status": status, "detail": detail, "evidence": evidence}
        )

    if not dataset_yaml.is_file():
        check("dataset_yaml_present", "NOT_ASSESSED", f"missing {dataset_yaml}")
        report["reason"] = "dataset_missing"
        return report
    if not manifest_path.is_file():
        check("manifest_present", "NOT_ASSESSED", f"missing {manifest_path}")
        report["reason"] = "manifest_missing"
        return report

    frozen = verify_frozen_hashes(root)
    report["frozen_hashes"] = frozen
    if frozen.get("ok"):
        check(
            "dataset_hashes_match_frozen_attestation",
            "PASS",
            "Recomputed image/label hashes match dataset_hashes.json.",
            combined_sha256=frozen.get("recomputed_combined_sha256"),
        )
    else:
        check(
            "dataset_hashes_match_frozen_attestation",
            "FAIL",
            "Frozen dataset content changed or the attestation is missing.",
            mismatches=frozen.get("mismatches", [])[:20],
        )
        report["errors"].append("dataset hash mismatch")

    try:
        inventory = collect_dataset(
            dataset_yaml,
            manifest_path=manifest_path,
            workspace_root=workspace,
            split="test",
            require_session_metadata=True,
        )
    except (DatasetValidationError, ValueError, OSError) as exc:
        check("dataset_parses", "FAIL", f"{type(exc).__name__}: {exc}")
        report["errors"].append(str(exc))
        report["status"] = FreezeStatus.FAIL.value
        return report
    check(
        "dataset_parses",
        "PASS",
        f"{inventory.image_count} test image(s) parsed with valid YOLO geometry.",
        image_count=inventory.image_count,
        class_counts=inventory.class_counts,
        sessions=len(inventory.sessions),
    )
    report["dataset"] = {
        "image_count": inventory.image_count,
        "class_counts": inventory.class_counts,
        "session_count": len(inventory.sessions),
        "missing_session_count": inventory.missing_session_count,
        "dataset_sha256": inventory.dataset_sha256,
        "image_sha256": inventory.image_sha256,
        "label_sha256": inventory.label_sha256,
        "dataset_version": inventory.dataset_version(),
        "annotation_version": inventory.annotation_version(),
        "warnings": list(inventory.warnings),
    }

    recorded_hashes = {}
    if hashes_path.is_file():
        try:
            import json

            recorded_hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            recorded_hashes = {}
    recorded_test = (
        (recorded_hashes.get("per_split") or {}).get("test", {}) or {}
    ).get("dataset_sha256")
    if recorded_test and recorded_test == inventory.dataset_sha256:
        check(
            "test_split_hash_matches_phase42_inventory",
            "PASS",
            "Frozen test-split hash equals the Phase 42 inventory hash.",
            dataset_sha256=inventory.dataset_sha256,
        )
    elif recorded_test:
        check(
            "test_split_hash_matches_phase42_inventory",
            "FAIL",
            "Frozen test-split hash differs from the Phase 42 inventory hash.",
            recorded=recorded_test,
            recomputed=inventory.dataset_sha256,
        )
        report["errors"].append("test split hash mismatch")
    else:
        check(
            "test_split_hash_matches_phase42_inventory",
            "NOT_ASSESSED",
            "No recorded test-split hash.",
        )

    provenance = inventory.provenance or {}
    annotation = inventory.annotation or {}
    qc = inventory.quality_control or {}
    policy = (
        annotation.get("policy")
        or annotation.get("guideline")
        or annotation.get("annotation_policy")
    )
    version = inventory.annotation_version()
    annotator_a = bool(qc.get("annotator_a") or qc.get("independent_annotator_a"))
    annotator_b = bool(qc.get("annotator_b") or qc.get("independent_annotator_b"))
    adjudication = bool(qc.get("adjudication") or qc.get("third_reviewer"))
    if provenance:
        check("provenance_recorded", "PASS", "Manifest provenance is present.")
    else:
        check("provenance_recorded", "NOT_ASSESSED", "Manifest has no provenance.")
        report["errors"].append("provenance missing")
    if version and policy and annotator_a and annotator_b and adjudication:
        check(
            "annotation_evidence",
            "PASS",
            "Annotation version, policy, A/B review and adjudication are recorded.",
        )
    else:
        check(
            "annotation_evidence",
            "NOT_ASSESSED",
            "Annotation version/policy/A-B/adjudication evidence is incomplete.",
            version=version,
            policy=policy,
            annotator_a=annotator_a,
            annotator_b=annotator_b,
            adjudication=adjudication,
        )
        report["errors"].append("annotation evidence incomplete")

    adjudication_rows = _read_adjudication(root / "manifests" / "adjudication.csv")
    negative_ids = set(inventory.negative_image_ids)
    unverified_negatives: List[str] = []
    for image_id in sorted(negative_ids):
        row = adjudication_rows.get(image_id, {})
        if (
            str(row.get("outcome") or "").strip().lower() != "verified_negative"
            or str(row.get("final_status") or "").strip().lower() != "accepted"
        ):
            unverified_negatives.append(image_id)
    if unverified_negatives:
        check(
            "verified_negatives_distinguished",
            "FAIL",
            f"{len(unverified_negatives)} empty-label image(s) lack adjudicated "
            "verified-negative status.",
            image_ids=unverified_negatives[:20],
        )
        report["errors"].append("unverified negatives in test split")
    else:
        check(
            "verified_negatives_distinguished",
            "PASS",
            f"{len(negative_ids)} empty-label image(s) are adjudicated verified negatives.",
            verified_negative_count=len(negative_ids),
        )

    registry = None
    if reference_registry_path is not None and Path(reference_registry_path).is_file():
        try:
            registry = load_reference_registry(Path(reference_registry_path))
        except ValueError as exc:
            report["warnings"].append(f"reference registry unreadable: {exc}")
    reference_sessions = set()
    if registry is not None:
        reference_sessions = set(registry.session_ids())
    elif reference_registry_path is not None and Path(reference_registry_path).is_file():
        reference_sessions = reference_session_ids_from_csv(Path(reference_registry_path))

    leakage = analyze_leakage(
        inventory,
        reference_session_ids=reference_sessions,
        reference_image_paths=reference_image_paths,
        max_hamming_distance=max_hamming_distance,
    )
    report["leakage"] = leakage.to_dict()
    if leakage.errors:
        check(
            "leakage",
            "FAIL",
            "; ".join(issue.detail for issue in leakage.errors[:3]),
            issue_count=len(leakage.errors),
        )
        report["errors"].append("leakage errors")
    elif leakage.warnings:
        check(
            "leakage",
            "CONDITIONAL",
            "; ".join(issue.detail for issue in leakage.warnings[:3]),
            issue_count=len(leakage.warnings),
        )
        report["warnings"].extend(issue.detail for issue in leakage.warnings)
    else:
        check("leakage", "PASS", "Session, duplicate and reference checks are clean.")

    if registry is None:
        check(
            "reference_registry",
            "NOT_ASSESSED",
            "No reference-session registry supplied; independence is unproven.",
        )
        report["warnings"].append("reference registry missing")
    elif registry.proxy_only:
        check(
            "reference_registry",
            "NOT_ASSESSED",
            "Reference registry is proxy-only (filename-derived dates), not verified "
            "collection sessions.",
            quality=registry.quality,
        )
        report["warnings"].append("reference registry proxy-only")
    elif registry.errors:
        check("reference_registry", "FAIL", "; ".join(registry.errors))
        report["errors"].append("reference registry errors")
    else:
        check(
            "reference_registry",
            "PASS",
            f"Verified registry with {registry.session_count} session(s).",
        )

    if not reference_image_paths:
        report["warnings"].append(
            "No reference imagery supplied; image-level cross-corpus duplicate "
            "checking is incomplete."
        )

    # ------------------------------------------------------------------ status
    if report["errors"]:
        report["status"] = FreezeStatus.FAIL.value
    elif registry is None or registry.proxy_only:
        report["status"] = FreezeStatus.NOT_ASSESSED.value
    elif report["warnings"] or any(
        item["status"] == "CONDITIONAL" for item in report["checks"]
    ):
        report["status"] = FreezeStatus.CONDITIONAL.value
    else:
        report["status"] = FreezeStatus.PASS.value
    report["dataset_ready"] = report["status"] in {
        FreezeStatus.PASS.value,
        FreezeStatus.CONDITIONAL.value,
    }
    return report


__all__ = ["preflight_dataset"]
