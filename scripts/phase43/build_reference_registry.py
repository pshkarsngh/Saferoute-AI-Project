#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 43 / P2.1 — build the reference-session registry.

Groups the existing training/validation corpus by its only available session
signal: the filename-derived capture date in ``data/splits_v2/split_manifest.csv``.

The output is explicitly **proxy-only** (``verified = false``). It must not be
described as verified collection sessions, and it cannot make the Phase 42
independence gate pass on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.datasets.reference import (  # noqa: E402
    ReferenceRegistryError,
    build_reference_registry,
    write_reference_registry,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 43 reference-session registry")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=None,
        help="Existing split manifest (default: data/splits_v2/split_manifest.csv)",
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=None,
        help="Existing image root for a count cross-check (optional)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Reference registry CSV (default: reports/phase43_training_sessions.csv)",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="JSON report (default: reports/phase43_reference_registry.json)",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = args.workspace_root.resolve()
    split_manifest = args.split_manifest or (
        workspace / "data" / "splits_v2" / "split_manifest.csv"
    )
    output_csv = args.output_csv or (
        workspace / "reports" / "phase43_training_sessions.csv"
    )
    output_json = args.output_json or (
        workspace / "reports" / "phase43_reference_registry.json"
    )

    try:
        registry = build_reference_registry(
            split_manifest, image_root=args.image_root
        )
    except (ReferenceRegistryError, ValueError, OSError) as exc:
        print(f"reference registry error: {exc}", file=sys.stderr)
        return 2

    report = write_reference_registry(
        registry, output_csv, json_report_path=output_json
    )
    print(f"sessions: {registry.session_count}")
    print(f"images: {registry.image_count}")
    print(f"verified: {registry.verified} (quality={registry.quality})")
    for warning in registry.warnings:
        print(f"warning: {warning}")
    for error in registry.errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"status: {report['status']}")
    print(f"registry: {output_csv}")
    print(f"report: {output_json}")
    return 2 if registry.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
