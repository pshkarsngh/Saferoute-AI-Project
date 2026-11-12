#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 43 / P3.3 — freeze the independent evaluation dataset.

Validates provenance, labels, session atomicity, two-review/adjudication evidence
and reference separation, then writes ``dataset.yaml``, the Phase 42 manifest and
a content-hash attestation. Refuses to write a frozen manifest while any error
remains. This command never runs inference.

Exit codes
----------
0  Freeze written (status PASS, CONDITIONAL or NOT_ASSESSED).
2  Freeze refused (status FAIL) or inputs unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.datasets.common import (  # noqa: E402
    DATASET_VERSION,
    DEFAULT_ANNOTATION_VERSION,
    list_images,
    utc_now,
)
from src.datasets.freeze import FreezeError, freeze_dataset  # noqa: E402
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
    parser = argparse.ArgumentParser(description="Freeze the independent dataset")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Dataset root (default: data/independent)",
    )
    parser.add_argument("--dataset-version", default=DATASET_VERSION)
    parser.add_argument("--annotation-version", default=DEFAULT_ANNOTATION_VERSION)
    parser.add_argument("--frozen-by", required=True)
    parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Annotation specification (default: docs/datasets/ANNOTATION_SPEC_V1.md)",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=None,
        help="Source registry (default: docs/datasets/sources.yaml)",
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
        "--no-write",
        action="store_true",
        help="Validate only; do not write manifests/hashes",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON report (default: reports/phase43_freeze.json)",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = WORKSPACE_ROOT
    dataset_root = args.dataset_root or (workspace / "data" / "independent")
    policy = args.policy or (workspace / "docs" / "datasets" / "ANNOTATION_SPEC_V1.md")
    sources_path = args.sources or (workspace / "docs" / "datasets" / "sources.yaml")
    output = args.output or (workspace / "reports" / "phase43_freeze.json")

    if not dataset_root.is_dir():
        payload = {
            "phase": "43",
            "work_package": "P3.3",
            "kind": "dataset_freeze",
            "generated_utc": utc_now(),
            "status": "NOT_ASSESSED",
            "frozen": False,
            "written": False,
            "dataset_root": str(dataset_root),
            "reason": "dataset_missing",
            "errors": [f"dataset root does not exist: {dataset_root}"],
            "warnings": [],
            "note": (
                "No independent dataset exists yet. Freezing is refused; no "
                "dataset.yaml or manifest was written."
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"dataset root does not exist: {dataset_root}", file=sys.stderr)
        print(f"report: {output}")
        return 2
    try:
        sources = load_source_registry(sources_path)
    except (SourceRegistryError, ValueError, OSError) as exc:
        print(f"source registry error: {exc}", file=sys.stderr)
        return 2

    try:
        result = freeze_dataset(
            dataset_root,
            sources=sources,
            dataset_version=args.dataset_version,
            annotation_version=args.annotation_version,
            frozen_by=args.frozen_by,
            policy_path=policy,
            reference_registry_path=args.reference_registry,
            reference_image_paths=_collect_images(args.reference_image_dir),
            write=not args.no_write,
            max_hamming_distance=args.max_hamming,
        )
    except (FreezeError, ValueError, OSError) as exc:
        print(f"freeze error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "phase": "43",
        "work_package": "P3.3",
        "kind": "dataset_freeze",
        "generated_utc": utc_now(),
        **result.to_dict(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"status: {result.status.value}")
    print(f"frozen: {payload['frozen']}")
    print(f"images: {result.split_counts}")
    for warning in result.warnings:
        print(f"warning: {warning}")
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"report: {output}")
    return 0 if result.status.value != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
