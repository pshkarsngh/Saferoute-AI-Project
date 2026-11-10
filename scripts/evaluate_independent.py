#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SafeRoute AI — Phase 42 independent detector evaluation CLI.

This command measures the configured serving checkpoint on an independently
collected dataset. It is read-only with respect to the checkpoint, production
configuration, risk engine and dataset. It writes the report JSON you request,
plus optional Stage A run artifacts under ``reports/phase42_stage_a`` (disable
Stage A with ``--no-stage-a`` if no run directory should be created).

Typical use (after independent data exists)::

    .\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py ^
        --dataset-yaml data/independent/dataset.yaml ^
        --manifest data/independent/manifests/independent_manifest.json ^
        --output reports/phase42_independent_evaluation.json

Preflight only (verify checkpoint + config contract, no inference)::

    .\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py --preflight-only

Exit codes
----------
0  Report produced (PASS / CONDITIONAL / NOT_ASSESSED)
1  Report produced with FAIL
2  Input/integrity error (missing checkpoint, smoke substitute, config drift,
   invalid or empty dataset)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.evaluation.dataset_validation import (  # noqa: E402
    DatasetValidationError,
    IMAGE_EXTENSIONS,
)
from src.evaluation.evaluator import (  # noqa: E402
    EvaluationError,
    IndependentEvaluator,
    ModelIntegrityError,
    ProductionParityError,
    SmokeSubstituteError,
)
from src.evaluation.leakage import (  # noqa: E402
    LeakageError,
    reference_session_ids_from_csv,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 42 independent YOLO11 detector evaluation",
    )
    parser.add_argument(
        "--dataset-yaml",
        type=Path,
        default=WORKSPACE_ROOT / "data" / "independent" / "dataset.yaml",
        help="Independent dataset YAML (default: data/independent/dataset.yaml)",
    )
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--split", default="test")
    parser.add_argument("--detection-config", type=Path, default=None)
    parser.add_argument("--severity-config", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=WORKSPACE_ROOT / "reports" / "phase42_independent_evaluation.json",
    )
    parser.add_argument(
        "--allow-smoke-substitute",
        action="store_true",
        help=(
            "Run harness validation against the P0 smoke substitute. The report is "
            "forced to NOT_ASSESSED and never describes the real v2 model."
        ),
    )
    parser.add_argument("--no-stage-a", action="store_true", help="Skip Ultralytics val")
    parser.add_argument("--no-stage-b", action="store_true", help="Skip production inference")
    parser.add_argument("--no-route-replay", action="store_true")
    parser.add_argument("--min-class-samples", type=int, default=30)
    parser.add_argument("--eligibility-min-score", type=float, default=60.0)
    parser.add_argument(
        "--reference-sessions",
        type=Path,
        default=None,
        help="CSV with a session_id column from the training/reference corpus",
    )
    parser.add_argument(
        "--reference-session-id",
        action="append",
        default=[],
        help="Explicit reference session id (repeatable)",
    )
    parser.add_argument(
        "--reference-image-dir",
        type=Path,
        default=None,
        help="Directory of reference images for exact/perceptual-hash comparison",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only verify checkpoint + production configuration",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    evaluator = IndependentEvaluator(
        workspace_root=WORKSPACE_ROOT,
        detection_config=args.detection_config,
        severity_config=args.severity_config,
        allow_smoke_substitute=args.allow_smoke_substitute,
    )

    try:
        if args.preflight_only:
            preflight = evaluator.preflight()
            print(json.dumps(preflight.to_dict(), indent=2))
            print(f"\nPREFLIGHT OK — checkpoint {preflight.checkpoint.sha256}")
            return 0

        reference_sessions = set(args.reference_session_id)
        if args.reference_sessions:
            reference_sessions |= reference_session_ids_from_csv(args.reference_sessions)
        reference_images = []
        if args.reference_image_dir:
            reference_images = sorted(
                path
                for path in Path(args.reference_image_dir).rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            )

        report = evaluator.run(
            args.dataset_yaml,
            manifest_path=args.manifest,
            split=args.split,
            run_stage_a=not args.no_stage_a,
            run_stage_b=not args.no_stage_b,
            run_route_replay=not args.no_route_replay,
            reference_session_ids=reference_sessions or None,
            reference_image_paths=reference_images or None,
            min_class_samples=args.min_class_samples,
            eligibility_min_score=args.eligibility_min_score,
            output_json=args.output,
        )
    except (SmokeSubstituteError, ModelIntegrityError) as exc:
        print(f"MODEL INTEGRITY ERROR: {exc}", file=sys.stderr)
        return 2
    except ProductionParityError as exc:
        print(f"PRODUCTION PARITY ERROR: {exc}", file=sys.stderr)
        return 2
    except (DatasetValidationError, LeakageError) as exc:
        print(f"DATASET ERROR: {exc}", file=sys.stderr)
        return 2
    except EvaluationError as exc:
        print(f"EVALUATION ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Phase 42 status: {report.status.value}")
    print(f"Harness only:    {report.harness_only}")
    print(f"Report written:  {args.output}")
    print("\nAcceptance gates:")
    for gate in report.gates:
        print(f"  {gate.status.value:<13} {gate.gate:<24} {gate.detail}")
    print(f"\n{report.safety_note}")
    return 1 if report.status.value == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
