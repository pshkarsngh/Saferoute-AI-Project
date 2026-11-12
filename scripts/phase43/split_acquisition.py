#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 43 / P2.2 — assign session-atomic splits.

Reads a draft acquisition CSV that has no trustworthy split assignment, assigns
whole ``capture_session_id`` groups to train/val/test deterministically, and
writes an updated CSV. It does not copy or download imagery.

Exit codes
----------
0  Splits assigned.
2  Input missing/invalid or session-atomicity could not be proven.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.datasets.splitting import (  # noqa: E402
    DEFAULT_RATIOS,
    DEFAULT_SALT,
    SplitError,
    assign_session_splits,
    validate_session_atomicity,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assign session-atomic train/val/test splits"
    )
    parser.add_argument("--acquisition-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument(
        "--session-column", default="capture_session_id", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--ratios",
        type=float,
        nargs=3,
        default=list(DEFAULT_RATIOS),
        metavar=("TRAIN", "VAL", "TEST"),
    )
    parser.add_argument("--salt", default=DEFAULT_SALT)
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    source = args.acquisition_csv.resolve()
    if not source.is_file():
        print(f"acquisition CSV not found: {source}", file=sys.stderr)
        return 2

    with open(source, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if args.session_column not in fieldnames:
        print(
            f"{source} has no {args.session_column!r} column (found {fieldnames})",
            file=sys.stderr,
        )
        return 2
    if "split" not in fieldnames:
        fieldnames.append("split")
    if not rows:
        print(f"{source} contains no rows", file=sys.stderr)
        return 2

    sessions = {str(row.get(args.session_column) or "").strip() for row in rows}
    sessions.discard("")
    if len(sessions) < 3:
        print(
            f"only {len(sessions)} session(s) found; at least 3 are required to "
            "populate train/val/test without splitting a session",
            file=sys.stderr,
        )
        return 2

    try:
        assignment = assign_session_splits(
            sessions, ratios=args.ratios, salt=args.salt
        )
    except SplitError as exc:
        print(f"split error: {exc}", file=sys.stderr)
        return 2

    for row in rows:
        session_id = str(row.get(args.session_column) or "").strip()
        row["split"] = assignment.get(session_id, "")

    errors = validate_session_atomicity(
        rows, session_field=args.session_column, split_field="split"
    )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    output = args.output_csv.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts = {
        split: sum(1 for row in rows if row.get("split") == split)
        for split in ("train", "val", "test")
    }
    print(f"sessions: {len(sessions)}")
    print(f"rows: {counts}")
    print(f"written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
