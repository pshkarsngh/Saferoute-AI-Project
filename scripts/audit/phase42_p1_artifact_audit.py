#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SafeRoute AI — Phase 42 / P1 artifact recovery audit.

This command writes the three required Phase 42 machine-readable artifacts in an
explicitly blocked state when the genuine v2 checkpoint and/or the independent
dataset are unavailable. It never runs inference and never emits detector
metrics.

If both the genuine checkpoint hash and a complete ``data/independent`` layout
are detected, the command refuses to write a blocked report and instructs the
operator to run ``scripts/evaluate_independent.py``.

Exit codes
----------
0  Blocked audit artifacts written (status NOT_ASSESSED).
2  Audit could not run (config drift, unexpected state, genuine artifacts
   detected, or an I/O error).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.evaluation.artifact_audit import (  # noqa: E402
    DEFAULT_MAX_HAMMING_DISTANCE,
    write_audit_artifacts,
)
from src.evaluation.evaluator import ProductionParityError  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 42 P1 artifact recovery / blocked-report audit",
    )
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--detection-config", type=Path, default=None)
    parser.add_argument("--severity-config", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--search-root",
        type=Path,
        action="append",
        default=[],
        help=(
            "Root to search for model artifacts (repeatable). The searched roots "
            "and every candidate hash are recorded in the manifest."
        ),
    )
    parser.add_argument(
        "--candidate-image-dir",
        type=Path,
        default=None,
        help="Unannotated candidate imagery (default: data/imagery/mapillary)",
    )
    parser.add_argument(
        "--reference-image-dir",
        type=Path,
        action="append",
        default=[],
        help="Reference corpus image directory (repeatable)",
    )
    parser.add_argument(
        "--skip-candidate-overlap",
        action="store_true",
        help="Do not run the exploratory candidate/reference hash probe",
    )
    parser.add_argument(
        "--max-hamming",
        type=int,
        default=DEFAULT_MAX_HAMMING_DISTANCE,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = Path(args.workspace_root).resolve()
    output_dir = Path(args.output_dir) if args.output_dir else workspace / "reports"

    try:
        summary = write_audit_artifacts(
            workspace,
            detection_config=args.detection_config,
            severity_config=args.severity_config,
            output_dir=output_dir,
            search_roots=args.search_root,
            candidate_image_dir=args.candidate_image_dir,
            reference_image_dirs=args.reference_image_dir,
            check_candidate_overlap=not args.skip_candidate_overlap,
            max_hamming_distance=args.max_hamming,
        )
    except ProductionParityError as exc:
        print(f"PRODUCTION PARITY ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        print(f"ARTIFACT AUDIT ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2))
    print("\nBLOCKED AUDIT — status NOT_ASSESSED; no detector inference was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
