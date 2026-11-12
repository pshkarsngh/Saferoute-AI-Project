#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 43 / P3.3 — Phase 42 dataset preflight (read-only).

Re-checks the frozen independent dataset against the Phase 42 harness contract:
frozen hashes, dataset parsing/geometry, provenance, annotation/QC evidence,
verified negatives, session/duplicate/reference leakage.

This command never loads the detector. A ``PASS``/``CONDITIONAL`` dataset status
does not unblock detector evaluation; the genuine v2 checkpoint is still needed.

Exit codes
----------
0  Dataset checks pass (PASS or CONDITIONAL).
2  Dataset is NOT_ASSESSED or FAIL, or the dataset is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.datasets.common import list_images  # noqa: E402
from src.datasets.preflight import preflight_dataset  # noqa: E402


def _collect_images(directories) -> list:
    images = []
    for directory in directories or []:
        images.extend(list_images(Path(directory)))
    return images


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 42 dataset preflight")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Dataset root (default: data/independent)",
    )
    parser.add_argument("--reference-registry", type=Path, default=None)
    parser.add_argument(
        "--reference-image-dir",
        type=Path,
        action="append",
        default=[],
        help="Reference corpus image directory (repeatable)",
    )
    parser.add_argument("--max-hamming", type=int, default=8)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON report (default: reports/phase43_dataset_preflight.json)",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = WORKSPACE_ROOT
    dataset_root = args.dataset_root or (workspace / "data" / "independent")
    output = args.output or (workspace / "reports" / "phase43_dataset_preflight.json")

    report = preflight_dataset(
        dataset_root,
        reference_registry_path=args.reference_registry,
        reference_image_paths=_collect_images(args.reference_image_dir),
        max_hamming_distance=args.max_hamming,
        workspace=workspace,
    )
    payload = {
        "phase": "43",
        "work_package": "P3.3",
        "kind": "phase42_dataset_preflight",
        **report,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"status: {report['status']}")
    print(f"dataset_ready: {report['dataset_ready']}")
    print(f"detector_evaluation_blocked_by_model: {report['detector_evaluation_blocked_by_model']}")
    for check in report.get("checks", []):
        print(f"[{check['status']}] {check['check']}: {check['detail']}")
    for warning in report.get("warnings", []):
        print(f"warning: {warning}")
    for error in report.get("errors", []):
        print(f"error: {error}", file=sys.stderr)
    print(f"report: {output}")
    return 0 if report["status"] in {"PASS", "CONDITIONAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
