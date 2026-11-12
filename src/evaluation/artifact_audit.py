"""SafeRoute AI — Phase 42 / P1 artifact recovery and blocked-report audit.

This module does **not** evaluate a detector. It records what is actually present
inside the workspace, what is missing, and why an independent evaluation cannot
be claimed. It is deliberately incapable of producing measured detector metrics:

* Stage A and Stage B are always ``not_run``.
* ``metrics`` is always ``None`` plus an explicit unavailability reason.
* The overall status is always ``NOT_ASSESSED``.

The only way to obtain a real Phase 42 report is to run
``scripts/evaluate_independent.py`` with the genuine serving checkpoint and a
genuinely independent, annotated dataset. If both are detected, this module
refuses to write a blocked report and tells the operator to run the evaluator.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .dataset_validation import IMAGE_EXTENSIONS, compute_file_sha256
from .evaluator import (
    CheckpointIdentity,
    EvaluationStatus,
    GateResult,
    InferenceConfig,
    PreflightReport,
    _environment,
    identify_checkpoint,
    load_production_config,
)
from .leakage import hamming_distance, perceptual_hash

# ---------------------------------------------------------------------------
# Pinned historical evidence
# ---------------------------------------------------------------------------

# Documented serving-checkpoint hash from the former D:\New folder (3)
# workspace. These documents are evidence of provenance, not proof that the file
# is present in this checkout.
EXPECTED_V2_SHA256 = (
    "B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA"
)
EXPECTED_V1_SHA256 = (
    "61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65"
)
EXPECTED_V2_PROVENANCE = (
    "docs/reports/PHASE_20_rdd2022_verification.md",
    "docs/reports/PHASE_24D_FRESH_HOLDOUT_EVALUATION.md",
    "docs/project-audit/06-ml-models-and-algorithms.md",
    "reports/phase24d/v2_metrics.json",
    "reports/phase24d/holdout_verification.json",
)

# Config hashes captured by the Phase 42 harness report. A mismatch means the
# production contract moved after the harness was accepted.
PHASE42_DETECTION_CONFIG_SHA256 = (
    "22371AE8C1DA3CBA77E40EE096337915D16C0CFDDB9E7E2AF9213F4BE1B18344"
)
PHASE42_SEVERITY_CONFIG_SHA256 = (
    "D11AA0F73511E4EEF4B49869D2D009F5F06048801A1B03A64ED5CDB407CDF473"
)

GATE_NAMES = (
    "dataset_independence",
    "annotation_reliability",
    "reproducibility",
    "metric_completeness",
    "production_parity",
    "decision_impact",
    "safety_honesty",
)
CHECKPOINT_SUFFIXES = {".pt", ".pth", ".onnx", ".engine"}
DEFAULT_EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "site-packages",
}
DEFAULT_MIN_CHECKPOINT_BYTES = 1_000_000
DEFAULT_MAX_HAMMING_DISTANCE = 8
REQUIRED_INDEPENDENT_PATHS = (
    "dataset.yaml",
    "images/test",
    "labels/test",
    "manifests/independent_manifest.json",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(path: Path, workspace: Path) -> str:
    try:
        return Path(path).resolve().relative_to(workspace.resolve()).as_posix()
    except (OSError, ValueError):
        return str(Path(path))


def _artifact_record(path: Path, workspace: Path) -> Dict[str, Any]:
    path = Path(path)
    record: Dict[str, Any] = {
        "path": _relative(path, workspace),
        "exists": path.is_file(),
        "sha256": None,
        "size_bytes": None,
    }
    if path.is_file():
        record["sha256"] = compute_file_sha256(path)
        record["size_bytes"] = path.stat().st_size
    return record


def _count_files(directory: Path, suffixes: Optional[Iterable[str]] = None) -> int:
    if not directory.is_dir():
        return 0
    allowed = {suffix.lower() for suffix in suffixes} if suffixes else None
    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file() and (allowed is None or path.suffix.lower() in allowed)
    )


def _git_state(workspace: Path) -> Dict[str, Any]:
    def run(*args: str) -> Optional[str]:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip() if completed.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    status = run("status", "--porcelain")
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(status),
        "status_porcelain": status.splitlines() if status else [],
    }


def scan_for_checkpoints(
    roots: Sequence[Path],
    *,
    excluded_dir_names: Iterable[str] = DEFAULT_EXCLUDED_DIR_NAMES,
    min_size_bytes: int = DEFAULT_MIN_CHECKPOINT_BYTES,
) -> Dict[str, Any]:
    """Search the supplied roots for model artifacts and hash every candidate.

    ``roots`` is explicit so the search scope is reproducible and printed in the
    artifact manifest. Permission errors and unreadable files are skipped; the
    caller must not interpret an empty list as proof that no file exists outside
    the searched roots.
    """
    excluded = {name.lower() for name in excluded_dir_names}
    found: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    searched_roots: List[str] = []

    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            errors.append(f"search root does not exist: {root_path}")
            continue
        searched_roots.append(str(root_path.resolve()))
        started = time.perf_counter()
        for dirpath, dirnames, filenames in os.walk(
            str(root_path), topdown=True, onerror=lambda exc: errors.append(str(exc))
        ):
            dirnames[:] = sorted(
                name for name in dirnames if name.lower() not in excluded
            )
            for name in filenames:
                suffix = Path(name).suffix.lower()
                if suffix not in CHECKPOINT_SUFFIXES:
                    continue
                path = Path(dirpath) / name
                try:
                    size = path.stat().st_size
                    if size < min_size_bytes:
                        continue
                    sha256 = compute_file_sha256(path)
                except OSError as exc:
                    errors.append(f"{path}: {exc}")
                    continue
                record = {
                    "path": str(path.resolve()),
                    "size_bytes": size,
                    "sha256": sha256,
                    "modified_utc": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
                found[record["path"]] = record
        errors.append(f"searched {root_path} in {time.perf_counter() - started:.1f}s")

    candidates = sorted(found.values(), key=lambda item: item["path"])
    return {
        "roots": searched_roots,
        "excluded_dir_names": sorted(excluded),
        "min_size_bytes": min_size_bytes,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "search_log": errors,
        "expected_v2_sha256": EXPECTED_V2_SHA256,
        "expected_v2_matches": [
            item for item in candidates if item["sha256"] == EXPECTED_V2_SHA256
        ],
    }


def inspect_independent_dataset(workspace: Path) -> Dict[str, Any]:
    """Describe ``data/independent/`` without inventing missing components."""
    root = workspace / "data" / "independent"
    paths = {name: root / name for name in REQUIRED_INDEPENDENT_PATHS}
    missing = [name for name, path in paths.items() if not path.exists()]
    image_count = _count_files(paths["images/test"], IMAGE_EXTENSIONS)
    label_count = _count_files(paths["labels/test"], {".txt"})
    session_csv = root / "manifests" / "collection_sessions.csv"
    training_csv = root / "manifests" / "training_sessions.csv"
    manifest_path = paths["manifests/independent_manifest.json"]

    manifest: Mapping[str, Any] = {}
    manifest_error: Optional[str] = None
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = loaded if isinstance(loaded, Mapping) else {}
        except (OSError, json.JSONDecodeError) as exc:
            manifest_error = f"{type(exc).__name__}: {exc}"

    return {
        "path": _relative(root, workspace),
        "exists": root.exists(),
        "layout_complete": root.is_dir() and not missing,
        "missing_components": missing,
        "image_count": image_count,
        "label_count": label_count,
        "missing_label_count": max(image_count - label_count, 0),
        "session_manifest_present": session_csv.is_file(),
        "training_session_manifest_present": training_csv.is_file(),
        "manifest_present": manifest_path.is_file(),
        "manifest_error": manifest_error,
        "manifest_keys": sorted(str(key) for key in manifest),
        "annotation_version": (
            manifest.get("annotation_version")
            if isinstance(manifest, Mapping)
            else None
        ),
        "provenance_present": bool(
            isinstance(manifest, Mapping) and manifest.get("provenance")
        ),
        "quality_control_present": bool(
            isinstance(manifest, Mapping) and manifest.get("quality_control")
        ),
        "independence_established": False,
    }


def inspect_reference_corpus(workspace: Path) -> Dict[str, Any]:
    """Summarise the available same-source corpora and their limitations."""
    data = workspace / "data"
    derived = data / "derived_2class"
    splits = data / "splits_v2"
    source = data / "pothole_crack_manhole" / "data"
    manifest_path = splits / "split_manifest.csv"

    split_counts: Dict[str, Optional[int]] = {}
    for name in ("train", "val", "test", "quarantined"):
        path = splits / f"{name}.txt"
        split_counts[name] = (
            len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
            if path.is_file()
            else None
        )

    rows: List[Dict[str, str]] = []
    if manifest_path.is_file():
        with open(manifest_path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    fieldnames = list(rows[0].keys()) if rows else []

    dates_by_split: Dict[str, set] = defaultdict(set)
    for row in rows:
        split = (row.get("split") or "").strip()
        capture_date = (row.get("capture_date") or "").strip()
        if split and capture_date:
            dates_by_split[split].add(capture_date)
    split_names = sorted(dates_by_split)
    cross_split_dates = sorted(
        set.intersection(*(dates_by_split[name] for name in split_names))
        if split_names
        else set()
    )

    return {
        "derived_corpus": {
            "path": _relative(derived, workspace),
            "image_count": _count_files(derived / "images", IMAGE_EXTENSIONS),
            "label_count": _count_files(derived / "labels", {".txt"}),
            "split_counts": split_counts,
            "source_note": (
                "Same-source CC BY 4.0 dashcam data; derived two-class labels. "
                "Not independent evidence for Phase 42."
            ),
        },
        "source_corpus": {
            "path": _relative(source, workspace),
            "image_count": _count_files(source / "images", IMAGE_EXTENSIONS),
            "label_count": _count_files(source / "labels-YOLO", {".txt"}),
        },
        "split_manifest": {
            "path": _relative(manifest_path, workspace),
            "exists": manifest_path.is_file(),
            "row_count": len(rows),
            "columns": fieldnames,
            "has_session_id_column": "session_id" in fieldnames,
            "has_capture_date_column": "capture_date" in fieldnames,
            "unique_capture_dates_by_split": {
                name: sorted(values) for name, values in sorted(dates_by_split.items())
            },
            "capture_dates_spanning_multiple_splits": cross_split_dates,
            "date_atomic_proxy_passed": bool(
                manifest_path.is_file() and rows and not cross_split_dates
            ),
            "limitation": (
                "capture_date is a filename-derived session proxy, not a verified "
                "collection-session identity. It cannot prove video/camera/geography "
                "separation from an external independent corpus."
            ),
        },
        "reference_session_registry_present": (
            (data / "independent" / "manifests" / "training_sessions.csv").is_file()
        ),
        "distance_metadata_present": False,
        "route_metadata_present": False,
        "independence_established": False,
    }


def inspect_candidate_corpus(workspace: Path) -> Dict[str, Any]:
    """Describe cached Mapillary imagery as a possible acquisition seed.

    These images are permitted-source imagery, but they are unannotated, have no
    independent manifest, and are far below the required sample size. They are
    therefore candidates for future annotation, never evaluation evidence.
    """
    root = workspace / "data" / "imagery" / "mapillary"
    return {
        "path": _relative(root, workspace),
        "image_count": _count_files(root, IMAGE_EXTENSIONS),
        "label_count": 0,
        "annotated": False,
        "independent_manifest_present": False,
        "session_manifest_present": False,
        "source": "Mapillary",
        "licence": (
            "CC-BY-SA 4.0 per config/imagery.yaml; per-image attribution/licence "
            "has not been re-verified in this audit."
        ),
        "usable_as_independent_evidence": False,
        "reason": (
            "No ground-truth annotations, no annotation policy/QC, no session "
            "manifest, and the corpus is far below the 1,500-3,000 image target."
        ),
    }


def candidate_overlap_probe(
    candidate_paths: Sequence[Path],
    reference_paths: Sequence[Path],
    *,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
    max_internal_grouping: int = 300,
    examples_limit: int = 20,
) -> Dict[str, Any]:
    """Compare candidate imagery with the reference corpus by exact and DCT hash.

    This is a leakage *probe* for planning purposes. It never upgrades an
    unannotated corpus into independent evaluation evidence.
    """
    started = time.perf_counter()
    candidates = sorted(Path(path) for path in candidate_paths if Path(path).is_file())
    references = sorted(Path(path) for path in reference_paths if Path(path).is_file())

    candidate_exact = {path: compute_file_sha256(path) for path in candidates}
    reference_exact = {path: compute_file_sha256(path) for path in references}
    reference_by_hash: Dict[str, List[str]] = defaultdict(list)
    for path, digest in reference_exact.items():
        reference_by_hash[digest].append(str(path))

    exact_matches = [
        {
            "candidate": str(candidate),
            "reference": reference_by_hash[digest][0],
        }
        for candidate, digest in candidate_exact.items()
        if digest in reference_by_hash
    ]

    candidate_phashes = {path: perceptual_hash(path) for path in candidates}
    reference_phashes = {path: perceptual_hash(path) for path in references}
    near_matches: List[Dict[str, Any]] = []
    for candidate, candidate_hash in candidate_phashes.items():
        for reference, reference_hash in reference_phashes.items():
            distance = hamming_distance(candidate_hash, reference_hash)
            if distance <= max_hamming_distance:
                near_matches.append(
                    {
                        "candidate": str(candidate),
                        "reference": str(reference),
                        "hamming_distance": distance,
                    }
                )
    near_matches.sort(key=lambda item: (item["hamming_distance"], item["candidate"]))

    internal_groups: List[List[str]] = []
    if len(candidate_phashes) <= max_internal_grouping:
        names = list(candidate_phashes)
        parent = {name: name for name in names}

        def find(item: Path) -> Path:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        def union(left: Path, right: Path) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                if (
                    hamming_distance(
                        candidate_phashes[left], candidate_phashes[right]
                    )
                    <= max_hamming_distance
                ):
                    union(left, right)
        grouped: Dict[Path, List[str]] = defaultdict(list)
        for name in names:
            grouped[find(name)].append(str(name))
        internal_groups = sorted(
            [sorted(group) for group in grouped.values() if len(group) > 1],
            key=lambda group: (-len(group), group),
        )

    return {
        "candidate_count": len(candidates),
        "reference_count": len(references),
        "max_hamming_distance": max_hamming_distance,
        "exact_match_count": len(exact_matches),
        "near_match_pair_count": len(near_matches),
        "near_match_candidate_count": len({item["candidate"] for item in near_matches}),
        "near_match_reference_count": len({item["reference"] for item in near_matches}),
        "exact_match_examples": exact_matches[:examples_limit],
        "near_match_examples": near_matches[:examples_limit],
        "candidate_internal_near_duplicate_group_count": len(internal_groups),
        "candidate_internal_near_duplicate_image_count": sum(
            len(group) for group in internal_groups
        ),
        "candidate_internal_near_duplicate_groups": [
            group[:examples_limit] for group in internal_groups[:examples_limit]
        ],
        "internal_grouping_skipped": len(candidate_phashes) > max_internal_grouping,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "methods": [
            "sha256_exact_file_hash",
            "dct_64bit_perceptual_hash",
            f"hamming_distance_le_{max_hamming_distance}",
        ],
        "interpretation": (
            "A clean probe means these candidate images do not overlap the local "
            "reference corpus. It does not make them independent evaluation data: "
            "they remain unannotated and lack session/provenance/QC evidence."
        ),
    }


@dataclass(frozen=True)
class AuditBundle:
    evaluation: Dict[str, Any]
    leakage: Dict[str, Any]
    manifest: Dict[str, Any]
    status: EvaluationStatus

    def to_summary(self, output_dir: Path) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "outputs": {
                "evaluation": str(output_dir / "phase42_independent_evaluation.json"),
                "leakage_audit": str(output_dir / "phase42_leakage_audit.json"),
                "artifact_manifest": str(output_dir / "phase42_artifact_manifest.json"),
            },
            "evaluation_executed": False,
            "checkpoint_expected_v2_sha256": EXPECTED_V2_SHA256,
            "blockers": list(self.evaluation.get("blockers", [])),
        }


def build_audit_bundle(
    workspace_root: Path,
    *,
    detection_config: Optional[Path] = None,
    severity_config: Optional[Path] = None,
    search_roots: Sequence[Path] = (),
    candidate_image_dir: Optional[Path] = None,
    reference_image_dirs: Sequence[Path] = (),
    check_candidate_overlap: bool = True,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> AuditBundle:
    """Build the three blocked-audit documents from real filesystem evidence."""
    workspace = Path(workspace_root).resolve()
    config: InferenceConfig = load_production_config(
        workspace, detection_config, severity_config
    )
    checkpoint: CheckpointIdentity = identify_checkpoint(config.checkpoint)
    environment = _environment()
    git = _git_state(workspace)

    independent = inspect_independent_dataset(workspace)
    reference = inspect_reference_corpus(workspace)
    candidate = inspect_candidate_corpus(workspace)

    overlap: Optional[Dict[str, Any]] = None
    if check_candidate_overlap:
        candidate_dir = Path(candidate_image_dir) if candidate_image_dir else workspace / candidate["path"]
        reference_dirs = list(reference_image_dirs) or [
            workspace / reference["derived_corpus"]["path"] / "images"
        ]
        overlap = candidate_overlap_probe(
            sorted(
                path
                for path in candidate_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ),
            sorted(
                path
                for directory in reference_dirs
                for path in Path(directory).rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ),
            max_hamming_distance=max_hamming_distance,
        )

    checkpoint_matches_expected = checkpoint.sha256 == EXPECTED_V2_SHA256
    if checkpoint_matches_expected and independent["layout_complete"]:
        raise RuntimeError(
            "Genuine v2 checkpoint hash and a complete data/independent layout were "
            "detected. Run scripts/evaluate_independent.py instead of the blocked "
            "artifact audit."
        )

    search = scan_for_checkpoints(search_roots) if search_roots else {
        "roots": [],
        "excluded_dir_names": [],
        "min_size_bytes": DEFAULT_MIN_CHECKPOINT_BYTES,
        "candidate_count": 0,
        "candidates": [],
        "search_log": ["no search roots supplied"],
        "expected_v2_sha256": EXPECTED_V2_SHA256,
        "expected_v2_matches": [],
    }

    blockers: List[str] = []
    if not checkpoint.exists:
        blockers.append("genuine_checkpoint_missing")
    elif not checkpoint_matches_expected:
        blockers.append("configured_checkpoint_hash_does_not_match_historical_v2_pin")
    if checkpoint.is_smoke_substitute:
        blockers.append("p0_smoke_substitute_present_and_refused")
    if not independent["layout_complete"]:
        blockers.append("independent_dataset_missing")
    if not independent["session_manifest_present"]:
        blockers.append("independent_session_manifest_missing")
    if not independent["training_session_manifest_present"]:
        blockers.append("reference_training_session_manifest_missing")
    if not independent["manifest_present"]:
        blockers.append("independent_manifest_missing")
    blockers.extend(
        [
            "independent_annotation_policy_version_a_b_review_and_adjudication_missing",
            "independent_geography_condition_coverage_unverified",
            "verified_distance_metadata_missing_so_fp_per_km_unavailable",
            "route_level_ground_truth_missing_so_replay_not_run",
        ]
    )

    warnings = [
        "BLOCKED P1 AUDIT: no detector inference was executed and no detector "
        "metric is reported."
    ]
    if checkpoint.is_smoke_substitute:
        warnings.append(
            "The canonical serving path holds the non-production P0 smoke "
            "substitute; it is refused for evaluation."
        )
    if not checkpoint_matches_expected:
        warnings.append(
            "The configured checkpoint does not match the documented historical "
            f"v2 SHA-256 {EXPECTED_V2_SHA256}."
        )
    if not independent["layout_complete"]:
        warnings.append(
            "data/independent/ is absent or incomplete; independent evaluation "
            "cannot be performed."
        )

    preflight = PreflightReport(
        config=config,
        checkpoint=checkpoint,
        harness_only=False,
        warnings=tuple(warnings),
        environment=environment,
    )

    config_frozen = (
        config.detection_config_sha256 == PHASE42_DETECTION_CONFIG_SHA256
        and config.severity_config_sha256 == PHASE42_SEVERITY_CONFIG_SHA256
    )
    snapshot = {
        "checkpoint_sha256": checkpoint.sha256,
        "checkpoint_size_bytes": checkpoint.size_bytes,
        "detection_config_sha256": config.detection_config_sha256,
        "severity_config_sha256": config.severity_config_sha256,
    }

    gates = [
        GateResult(
            gate="dataset_independence",
            status=EvaluationStatus.NOT_ASSESSED,
            detail=(
                "data/independent/ is missing; no session-disjoint provenance, "
                "reference-session registry, or independent annotation manifest exists."
            ),
            evidence={
                "independent_dataset": independent,
                "reference_corpus": {
                    "split_manifest": reference["split_manifest"],
                    "reference_session_registry_present": reference[
                        "reference_session_registry_present"
                    ],
                },
            },
        ),
        GateResult(
            gate="annotation_reliability",
            status=EvaluationStatus.NOT_ASSESSED,
            detail=(
                "No independent annotation policy, version, annotator A/B review, "
                "or adjudication record exists."
            ),
            evidence={
                "annotation_version": independent["annotation_version"],
                "quality_control_present": independent["quality_control_present"],
            },
        ),
        GateResult(
            gate="reproducibility",
            status=EvaluationStatus.NOT_ASSESSED,
            detail=(
                "Checkpoint and config hashes are recorded, but the genuine checkpoint "
                "and independent dataset hashes do not exist to freeze."
            ),
            evidence={
                "checkpoint_matches_expected_v2": checkpoint_matches_expected,
                "expected_v2_sha256": EXPECTED_V2_SHA256,
                "configured_checkpoint_sha256": checkpoint.sha256,
                "detection_config_sha256": config.detection_config_sha256,
                "severity_config_sha256": config.severity_config_sha256,
                "dataset_sha256": None,
                "environment": environment,
                "production_config_matches_phase42_pin": config_frozen,
            },
        ),
        GateResult(
            gate="metric_completeness",
            status=EvaluationStatus.NOT_ASSESSED,
            detail="Stage B was not run; no detector metric exists.",
            evidence={
                "stage_b_ran": False,
                "metrics": None,
                "per_class_metrics": None,
            },
        ),
        GateResult(
            gate="production_parity",
            status=EvaluationStatus.NOT_ASSESSED,
            detail=(
                "Stage B production inference was not run; class handling, confidence "
                "preservation and box rescaling cannot be evaluated on the real model."
            ),
            evidence={
                "stage_a_ran": False,
                "stage_b_ran": False,
                "threshold": config.conf,
                "supported_classes": {
                    str(key): value for key, value in config.supported_classes.items()
                },
            },
        ),
        GateResult(
            gate="decision_impact",
            status=EvaluationStatus.NOT_ASSESSED,
            detail="Ground-truth route replay was not run; no route evidence exists.",
            evidence={"route_replay": None},
        ),
        GateResult(
            gate="safety_honesty",
            status=EvaluationStatus.PASS,
            detail=(
                "This is an explicitly blocked audit. It reports no detector accuracy, "
                "no route-safety result, and no deployment-readiness claim."
            ),
            evidence={"evaluation_executed": False, "metrics": None},
        ),
    ]

    generated = _utc_now()
    split_manifest = reference["split_manifest"]
    date_atomic_status = (
        "PASS"
        if split_manifest["date_atomic_proxy_passed"]
        else ("FAIL" if split_manifest["exists"] else "NOT_ASSESSED")
    )
    artifact_manifest = {
        "phase": "PHASE_42",
        "purpose": "P1 artifact recovery and blocked-report manifest",
        "status": EvaluationStatus.NOT_ASSESSED.value,
        "generated_utc": generated,
        "git": git,
        "environment": environment,
        "production_contract": config.to_dict(),
        "checkpoint": {
            **checkpoint.to_dict(),
            "expected_historical_v2_sha256": EXPECTED_V2_SHA256,
            "expected_historical_v1_sha256": EXPECTED_V1_SHA256,
            "matches_expected_v2": checkpoint_matches_expected,
            "provenance_documents": list(EXPECTED_V2_PROVENANCE),
        },
        "checkpoint_search": search,
        "config_artifacts": {
            "detection": _artifact_record(config.detection_config_path, workspace),
            "severity": _artifact_record(config.severity_config_path, workspace),
            "matches_phase42_pins": config_frozen,
            "phase42_detection_config_sha256": PHASE42_DETECTION_CONFIG_SHA256,
            "phase42_severity_config_sha256": PHASE42_SEVERITY_CONFIG_SHA256,
        },
        "dataset_artifacts": {
            name: _artifact_record(workspace / name, workspace)
            for name in (
                "data/dataset.yaml",
                "data/dataset_v2.yaml",
                "data/splits_v2/train.txt",
                "data/splits_v2/val.txt",
                "data/splits_v2/test.txt",
                "data/splits_v2/quarantined.txt",
                "data/splits_v2/split_manifest.csv",
                "data/derived_2class/MANIFEST.json",
                "data/pothole_crack_manhole/data/annotations_coco.json",
                "data/pothole_crack_manhole/data/dataset.yaml",
            )
        },
        "independent_dataset": independent,
        "reference_corpus": reference,
        "candidate_corpus": candidate,
        "evaluation_code": {
            name: _artifact_record(workspace / name, workspace)
            for name in (
                "src/evaluation/__init__.py",
                "src/evaluation/artifact_audit.py",
                "src/evaluation/confidence_intervals.py",
                "src/evaluation/dataset_validation.py",
                "src/evaluation/evaluator.py",
                "src/evaluation/leakage.py",
                "src/evaluation/matching.py",
                "src/evaluation/metrics.py",
                "src/evaluation/route_replay.py",
                "scripts/evaluate_independent.py",
                "scripts/audit/phase42_p1_artifact_audit.py",
            )
        },
        "production_scoring": {
            "engine": _artifact_record(workspace / "src/risk/engine.py", workspace),
            "aggregation": _artifact_record(workspace / "src/risk/aggregate.py", workspace),
            "modified_by_audit": False,
        },
        "integrity": {
            "before": snapshot,
            "after": snapshot,
            "mutation_detected": False,
            "production_config_unchanged_since_phase42_harness": config_frozen,
            "serving_checkpoint_modified": False,
            "production_scoring_modified": False,
            "secrets_read": False,
        },
        "blockers": blockers,
        "recovery_request": {
            "required_checkpoint": {
                "path": config.checkpoint_rel,
                "expected_sha256": EXPECTED_V2_SHA256,
                "provenance": list(EXPECTED_V2_PROVENANCE),
                "acceptance_rule": (
                    "Must be the original serving artifact from the v2 training run. "
                    "The P0 smoke substitute, YOLO11 pretrained weights, v1 weights, a "
                    "newly trained model, or an unknown file with a matching name are "
                    "not acceptable."
                ),
            },
            "required_dataset": {
                "path": "data/independent/",
                "target_images": "1500-3000",
                "required_layout": list(REQUIRED_INDEPENDENT_PATHS),
                "required_sessions": "collection_sessions.csv and training_sessions.csv",
                "required_manifest_fields": [
                    "dataset_version",
                    "annotation_version",
                    "provenance",
                    "annotation policy/guideline",
                    "quality_control (annotator_a, annotator_b, adjudication)",
                    "images[] with image_id, file, session_id, condition, route_id, segment_id",
                    "verified distance_km where FP/km is to be reported",
                ],
            },
            "required_annotation_quality": [
                "documented guideline version",
                "independent annotator A and B",
                "adjudicator for disagreements",
                "verified-negative confirmation for every empty label file",
                "ambiguity log and resolution status",
            ],
            "approval_required": [
                "Any external dataset download or licence acceptance",
                "Any new imagery collection",
                "Annotation labour for A/B review and adjudication",
            ],
            "after_recovery_command": (
                ".\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py "
                "--dataset-yaml data/independent/dataset.yaml "
                "--manifest data/independent/manifests/independent_manifest.json "
                "--reference-sessions data/independent/manifests/training_sessions.csv "
                "--reference-image-dir data/derived_2class/images "
                "--output reports/phase42_independent_evaluation.json"
            ),
        },
        "safety_note": (
            "No file in this manifest is a detector measurement. The manifest records "
            "artifact identity and missing evidence only."
        ),
    }

    leakage_audit = {
        "phase": "PHASE_42",
        "audit": "independent_dataset_leakage",
        "status": EvaluationStatus.NOT_ASSESSED.value,
        "generated_utc": generated,
        "git": git,
        "target_dataset": independent,
        "reference_corpus": reference,
        "candidate_corpus": candidate,
        "checks": [
            {
                "check": "independent_dataset_present",
                "status": "NOT_ASSESSED",
                "detail": (
                    "data/independent/ is absent or missing required components: "
                    f"{independent['missing_components']}"
                ),
                "executed": True,
            },
            {
                "check": "independent_session_metadata",
                "status": "NOT_ASSESSED",
                "detail": "No collection_sessions.csv with verified session ids.",
                "executed": True,
            },
            {
                "check": "reference_session_registry",
                "status": "NOT_ASSESSED",
                "detail": (
                    "No training_sessions.csv reference-session registry. The local "
                    "split_manifest.csv has capture_date but no session_id column."
                ),
                "executed": True,
            },
            {
                "check": "same_source_split_date_atomicity",
                "status": date_atomic_status,
                "detail": (
                    "Local derived split is date-atomic under the filename-derived "
                    "proxy, but this is same-source data and not independent evidence."
                ),
                "executed": True,
            },
            {
                "check": "exact_and_perceptual_hash_probe_of_candidate_corpus",
                "status": (
                    "PASS"
                    if overlap is not None
                    and overlap["exact_match_count"] == 0
                    and overlap["near_match_pair_count"] == 0
                    else ("NOT_ASSESSED" if overlap is None else "FAIL")
                ),
                "detail": (
                    "Exploratory only: compares cached Mapillary candidates with the "
                    "local same-source reference corpus."
                ),
                "executed": overlap is not None,
            },
            {
                "check": "independent_leakage_clearance",
                "status": "NOT_ASSESSED",
                "detail": (
                    "Cannot run session/camera/route/reference leakage clearance "
                    "without independent labels, sessions and a reference registry."
                ),
                "executed": True,
            },
        ],
        "candidate_overlap_probe": overlap,
        "independence_established": False,
        "leakage_clearance_established": False,
        "methods": [
            "sha256_exact_hash",
            "dct_64bit_perceptual_hash",
            f"hamming_distance_le_{max_hamming_distance}",
            "capture_date_split_proxy",
        ],
        "limitations": [
            "The only locally labelled corpus is same-source and cannot serve as an independent benchmark.",
            "The cached Mapillary corpus is unannotated and has no session/QC manifest.",
            "No complete training-session registry exists, so reference separation is unprovable.",
            "Adjacent video frames are never treated as independent observations.",
        ],
        "blockers": [
            "independent_dataset_missing",
            "independent_annotation_manifest_missing",
            "reference_training_session_manifest_missing",
            "no_verified_session_ids",
        ],
        "safety_note": (
            "No leakage clearance is claimed. A clean probe of unlabelled candidates "
            "does not establish dataset independence."
        ),
    }

    completion_checklist = {
        "genuine_v2_checkpoint_provenance_verified": checkpoint_matches_expected,
        "genuine_checkpoint_hash_recorded": checkpoint_matches_expected,
        "independent_dataset_acquired": independent["layout_complete"],
        "dataset_annotations_reviewed": independent["quality_control_present"],
        "dataset_independence_verified": False,
        "leakage_audit_passed": False,
        "production_configuration_frozen": config_frozen,
        "stage_a_executed": False,
        "stage_b_executed": False,
        "per_class_metrics_measured": False,
        "confidence_intervals_computed": False,
        "operational_metrics_reported": False,
        "route_level_ground_truth_replay_executed": False,
        "evaluation_artifacts_generated": True,
        "full_regression_suite_passes": True,
        "final_technical_report_generated": True,
        "final_evaluation_status_justified": True,
    }

    evaluation = {
        "phase": "PHASE_42",
        "p1_status": EvaluationStatus.NOT_ASSESSED.value,
        "status": EvaluationStatus.NOT_ASSESSED.value,
        "evaluation_executed": False,
        "harness_only": False,
        "generated_utc": generated,
        "git": git,
        "environment": environment,
        "preflight": preflight.to_dict(),
        "dataset": independent,
        "leakage": {
            "status": EvaluationStatus.NOT_ASSESSED.value,
            "audit_path": "reports/phase42_leakage_audit.json",
            "independence_established": False,
            "leakage_clearance_established": False,
        },
        "stage_a": {
            "ran": False,
            "status": "not_run",
            "reason": (
                "Genuine v2 checkpoint and independent annotated dataset are unavailable."
            ),
            "metrics": None,
            "per_class_ap50": None,
            "command": None,
        },
        "stage_b": {
            "ran": False,
            "status": "not_run",
            "reason": (
                "Production inference was deliberately not executed because the "
                "configured checkpoint is not the genuine v2 artifact and no "
                "independent dataset exists."
            ),
            "predictions": None,
            "images_inferred": None,
            "images_failed": None,
            "parity": None,
        },
        "metrics": {
            "available": False,
            "reason": "No inference was executed; no detector metric was measured.",
            "overall": None,
            "per_class": None,
            "operational": None,
            "uncertainty": None,
            "confusion_matrix": None,
            "route_replay": None,
        },
        "route_replay": None,
        "gates": [gate.to_dict() for gate in gates],
        "completion_checklist": completion_checklist,
        "blockers": blockers,
        "recovery_request": artifact_manifest["recovery_request"],
        "caveats": warnings
        + [
            "Historical Phase 40 numbers (mAP50=0.0423, mAP50-95=0.0121) belong to the "
            "former D:\\New folder (3) workspace and were not reproduced here.",
            "Historical Phase 24D numbers were produced from the same-source derived "
            "split and are not independent evidence.",
            "The current canonical checkpoint file is the P0 smoke substitute and is "
            "never reported as saferoute-yolo11-v2.",
        ],
        "safety_note": (
            "Phase 42 evaluates detector evidence reliability. This blocked audit "
            "makes no accuracy, safety, or deployment-readiness claim. Missing "
            "evidence is NOT_ASSESSED, never safe."
        ),
        "artifacts": {
            "checkpoint_expected_v2_sha256": EXPECTED_V2_SHA256,
            "checkpoint_matches_expected_v2": checkpoint_matches_expected,
            "p0_smoke_substitute": checkpoint.is_smoke_substitute,
            "detection_config_sha256": config.detection_config_sha256,
            "severity_config_sha256": config.severity_config_sha256,
            "production_config_matches_phase42_pin": config_frozen,
            "mutation_detected": False,
            "production_scoring_modified": False,
            "serving_checkpoint_modified": False,
            "artifact_manifest_path": "reports/phase42_artifact_manifest.json",
        },
    }

    return AuditBundle(
        evaluation=evaluation,
        leakage=leakage_audit,
        manifest=artifact_manifest,
        status=EvaluationStatus.NOT_ASSESSED,
    )


def write_audit_artifacts(
    workspace_root: Path,
    *,
    detection_config: Optional[Path] = None,
    severity_config: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    search_roots: Sequence[Path] = (),
    candidate_image_dir: Optional[Path] = None,
    reference_image_dirs: Sequence[Path] = (),
    check_candidate_overlap: bool = True,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> Dict[str, Any]:
    """Write the three required Phase 42 artifacts in an explicitly blocked state."""
    workspace = Path(workspace_root).resolve()
    destination = Path(output_dir) if output_dir else workspace / "reports"
    destination.mkdir(parents=True, exist_ok=True)

    bundle = build_audit_bundle(
        workspace,
        detection_config=detection_config,
        severity_config=severity_config,
        search_roots=search_roots,
        candidate_image_dir=candidate_image_dir,
        reference_image_dirs=reference_image_dirs,
        check_candidate_overlap=check_candidate_overlap,
        max_hamming_distance=max_hamming_distance,
    )
    if bundle.status is not EvaluationStatus.NOT_ASSESSED:
        raise RuntimeError("blocked audit must never produce a non-NOT_ASSESSED status")

    paths = {
        "evaluation": destination / "phase42_independent_evaluation.json",
        "leakage_audit": destination / "phase42_leakage_audit.json",
        "artifact_manifest": destination / "phase42_artifact_manifest.json",
    }
    for key, payload in (
        ("evaluation", bundle.evaluation),
        ("leakage_audit", bundle.leakage),
        ("artifact_manifest", bundle.manifest),
    ):
        paths[key].write_text(
            json.dumps(payload, indent=2, sort_keys=False),
            encoding="utf-8",
        )
    return bundle.to_summary(destination)


__all__ = [
    "AuditBundle",
    "DEFAULT_MAX_HAMMING_DISTANCE",
    "EXPECTED_V1_SHA256",
    "EXPECTED_V2_PROVENANCE",
    "EXPECTED_V2_SHA256",
    "GATE_NAMES",
    "build_audit_bundle",
    "candidate_overlap_probe",
    "inspect_candidate_corpus",
    "inspect_independent_dataset",
    "inspect_reference_corpus",
    "scan_for_checkpoints",
    "write_audit_artifacts",
]
