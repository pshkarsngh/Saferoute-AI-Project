"""P3 — deterministic, session-atomic split assignment.

Frames from one collection session must never be divided across train/val/test.
Assignment is derived from a salted SHA-256 of the session id, so it is
reproducible without depending on filesystem order.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .common import SPLITS

DEFAULT_RATIOS = (0.70, 0.15, 0.15)
DEFAULT_SALT = "phase43-v1"


class SplitError(ValueError):
    """Raised when split assignment cannot be performed safely."""


def _session_score(session_id: str, salt: str) -> int:
    return int(hashlib.sha256(f"{salt}:{session_id}".encode("utf-8")).hexdigest(), 16)


def assign_session_splits(
    session_ids: Iterable[str],
    *,
    ratios: Sequence[float] = DEFAULT_RATIOS,
    salt: str = DEFAULT_SALT,
    min_sessions: int = 3,
) -> Dict[str, str]:
    """Assign every whole session to one split, deterministically.

    Sessions are ordered by a salted hash and allocated train/val/test from the
    computed counts. With at least ``min_sessions`` sessions every split gets at
    least one session, so a held-out evaluation split always exists.
    """
    unique = sorted({str(session_id).strip() for session_id in session_ids if str(session_id).strip()})
    if not unique:
        return {}
    if len(ratios) != 3 or any(ratio < 0 for ratio in ratios):
        raise SplitError(f"ratios must be three non-negative values, got {ratios}")
    total = float(sum(ratios))
    if total <= 0:
        raise SplitError("ratios must sum to a positive value")
    normalised = [ratio / total for ratio in ratios]

    ordered = sorted(unique, key=lambda session_id: (_session_score(session_id, salt), session_id))
    count = len(ordered)

    if count == 1:
        return {ordered[0]: "test"}
    if count == 2:
        return {ordered[0]: "train", ordered[1]: "test"}

    n_val = max(1, round(count * normalised[1]))
    n_test = max(1, round(count * normalised[2]))
    # Leave at least one session for train.
    while n_val + n_test >= count:
        if n_val >= n_test and n_val > 1:
            n_val -= 1
        elif n_test > 1:
            n_test -= 1
        else:
            break
    n_train = count - n_val - n_test
    if n_train < 1:
        raise SplitError(
            f"cannot allocate three non-empty splits from {count} session(s)"
        )

    assignment: Dict[str, str] = {}
    for index, session_id in enumerate(ordered):
        if index < n_train:
            assignment[session_id] = "train"
        elif index < n_train + n_val:
            assignment[session_id] = "val"
        else:
            assignment[session_id] = "test"
    return assignment


def _field(record: Any, name: str) -> str:
    if isinstance(record, Mapping):
        return str(record.get(name) or "").strip()
    return str(getattr(record, name, "") or "").strip()


def validate_session_atomicity(
    records: Iterable[Any],
    *,
    session_field: str = "capture_session_id",
    split_field: str = "split",
    route_field: str = "route_id",
    image_field: str = "image_id",
) -> List[str]:
    """Return error strings for session/route leakage across splits."""
    errors: List[str] = []
    by_session: Dict[str, Dict[str, Any]] = {}
    by_route: Dict[str, Dict[str, Any]] = {}
    seen_images: Dict[str, str] = {}

    for record in records:
        session_id = _field(record, session_field)
        route_id = _field(record, route_field)
        split = _field(record, split_field)
        image_id = _field(record, image_field)
        if session_id:
            info = by_session.setdefault(session_id, {"splits": set(), "images": 0})
            info["splits"].add(split)
            info["images"] += 1
        if route_id:
            info = by_route.setdefault(route_id, {"splits": set(), "images": 0})
            info["splits"].add(split)
            info["images"] += 1
        if image_id:
            if image_id in seen_images:
                errors.append(
                    f"duplicate image_id {image_id!r} appears in both "
                    f"{seen_images[image_id]!r} and {split!r}"
                )
            seen_images[image_id] = split

    for session_id, info in sorted(by_session.items()):
        if len(info["splits"]) > 1:
            errors.append(
                f"session {session_id!r} crosses splits {sorted(info['splits'])}"
            )
    for route_id, info in sorted(by_route.items()):
        if len(info["splits"]) > 1:
            errors.append(
                f"route {route_id!r} crosses splits {sorted(info['splits'])}"
            )
    return errors


__all__ = [
    "DEFAULT_RATIOS",
    "DEFAULT_SALT",
    "SplitError",
    "assign_session_splits",
    "validate_session_atomicity",
]
