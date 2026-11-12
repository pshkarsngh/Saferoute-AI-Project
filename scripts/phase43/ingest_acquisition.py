#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 43 / P2.2 — validate and ingest approved acquisition imagery.

Copies already-held, human-approved imagery into ``data/independent/`` only after
provenance, licence, duplicate and reference-overlap checks pass. It downloads
nothing and never mutates the staged source files.

Exit codes
----------
0  Ingestion (or dry run) succeeded.
2  Validation failed, source not approved, or existing output present.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.datasets.acquisition import (  # noqa: E402
    AcquisitionError,
    ingest_acquisition,
)
from src.datasets.common import list_images  # noqa: E402
from src.datasets.sources import (  # noqa: E402
    SourceRegistryError,
    load_source_registry,
)


def _collect_images(directories) -> list:
    images = []
    for directory in directories or []:
        images.extend(list_images(Path(directory)))
    return images


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and ingest approved independent imagery"
    )
    parser.add_argument("--acquisition-csv", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Dataset root (default: data/independent)",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=None,
        help="Source registry (default: docs/datasets/sources.yaml)",
    )
    parser.add_argument(
        "--reference-image-dir",
        type=Path,
        action="append",
        default=[],
        help="Reference corpus image directory (repeatable)",
    )
    parser.add_argument("--max-hamming", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into a non-empty output images tree",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON report (default: reports/phase43_ingest.json)",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = WORKSPACE_ROOT
    output_root = args.output_root or (workspace / "data" / "independent")
    sources_path = args.sources or (workspace / "docs" / "datasets" / "sources.yaml")
    output = args.output or (workspace / "reports" / "phase43_ingest.json")

    try:
        sources = load_source_registry(sources_path)
    except (SourceRegistryError, ValueError, OSError) as exc:
        print(f"source registry error: {exc}", file=sys.stderr)
        return 2

    reference_images = _collect_images(args.reference_image_dir)
    try:
        report = ingest_acquisition(
            args.acquisition_csv,
            args.staging_dir,
            output_root,
            sources=sources,
            reference_image_paths=reference_images,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            max_hamming_distance=args.max_hamming,
        )
    except (AcquisitionError, ValueError, OSError) as exc:
        print(f"ingest error: {exc}", file=sys.stderr)
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    audit = report.get("audit", {})
    print(f"status: {report.get('status')}")
    print(f"records: {audit.get('record_count', 0)}")
    for warning in audit.get("warnings", []):
        print(f"warning: {warning}")
    for error in audit.get("errors", []):
        print(f"error: {error}", file=sys.stderr)
    print(f"report: {output}")
    return 0 if report.get("status") in {"READY", "INGESTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
