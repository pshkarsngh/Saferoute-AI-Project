#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 43 / P2.1 — audit approved imagery sources.

Reads ``docs/datasets/sources.yaml`` and reports which sources (if any) may be
used for acquisition. It grants no approval itself and downloads nothing.

Exit codes
----------
0  Audit written (regardless of whether any source is approved).
2  Registry missing or structurally invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.datasets.sources import (  # noqa: E402
    SourceRegistryError,
    audit_source_registry,
    load_source_registry,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 43 source/licence audit")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Source registry YAML (default: docs/datasets/sources.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON report path (default: reports/phase43_source_audit.json)",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = args.workspace_root.resolve()
    registry_path = args.registry or (workspace / "docs" / "datasets" / "sources.yaml")
    output = args.output or (workspace / "reports" / "phase43_source_audit.json")

    try:
        sources = load_source_registry(registry_path)
    except (SourceRegistryError, ValueError, OSError) as exc:
        print(f"source registry error: {exc}", file=sys.stderr)
        return 2

    audit = audit_source_registry(sources, workspace=workspace)
    report = {
        "phase": "43",
        "work_package": "P2.1",
        "kind": "source_and_permission_audit",
        "registry": str(registry_path),
        **audit,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"approved sources: {audit['approved_count']}")
    for warning in audit["warnings"]:
        print(f"warning: {warning}")
    for error in audit["errors"]:
        print(f"error: {error}", file=sys.stderr)
    print(f"report: {output}")
    if audit["errors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
