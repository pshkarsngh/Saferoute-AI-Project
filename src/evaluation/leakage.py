"""SafeRoute AI — Phase 42 leakage protection.

Independence is not just a different folder. This module checks that collection
sessions do not straddle split boundaries, that exact/near-duplicate imagery is
disclosed, and that the independent set does not reuse known reference sessions
or scenes.

Perceptual hashing (dHash-style 64-bit DCT hash) is implemented with OpenCV so no
extra dependency is introduced.
"""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .dataset_validation import DatasetInventory, compute_file_sha256


class LeakageError(ValueError):
    """Raised when leakage analysis cannot be performed."""


@dataclass(frozen=True)
class LeakageIssue:
    kind: str
    severity: str
    detail: str
    image_ids: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "detail": self.detail,
            "image_ids": list(self.image_ids),
        }


@dataclass(frozen=True)
class DuplicateGroup:
    kind: str
    image_ids: Tuple[str, ...]
    session_ids: Tuple[str, ...]
    distance: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "image_ids": list(self.image_ids),
            "session_ids": list(self.session_ids),
            "hamming_distance": self.distance,
        }


@dataclass(frozen=True)
class LeakageReport:
    issues: Tuple[LeakageIssue, ...]
    duplicate_groups: Tuple[DuplicateGroup, ...]
    checked_images: int
    checked_reference_images: int
    session_count: int
    methods: Tuple[str, ...]

    @property
    def errors(self) -> Tuple[LeakageIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> Tuple[LeakageIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def is_clean(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, object]:
        return {
            "checked_images": self.checked_images,
            "checked_reference_images": self.checked_reference_images,
            "session_count": self.session_count,
            "is_clean": self.is_clean,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [issue.to_dict() for issue in self.issues],
            "duplicate_groups": [group.to_dict() for group in self.duplicate_groups],
            "methods": list(self.methods),
        }


def _decode_grayscale(path: Path):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment guarantees cv2
        raise LeakageError("OpenCV/numpy are required for perceptual hashing") from exc
    raw = path.read_bytes()
    buffer = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        raise LeakageError(f"Cannot decode image for perceptual hashing: {path}")
    return image


def perceptual_hash(path: Path, hash_size: int = 8) -> int:
    """Return a 64-bit DCT perceptual hash for an image file."""
    import cv2
    import numpy as np

    image = _decode_grayscale(Path(path))
    resized = cv2.resize(
        image, (32, 32), interpolation=cv2.INTER_AREA
    ).astype(np.float32)
    dct = cv2.dct(resized)
    low = dct[:hash_size, :hash_size].flatten()
    median = float(np.median(low[1:])) if low.size > 1 else float(np.median(low))
    value = 0
    for coefficient in low:
        value = (value << 1) | (1 if float(coefficient) > median else 0)
    return value


def hamming_distance(left: int, right: int) -> int:
    return int(bin(int(left) ^ int(right)).count("1"))


def _union_find_groups(
    ids: Sequence[str],
    hashes: Mapping[str, int],
    max_hamming_distance: int,
) -> List[List[str]]:
    parent = {image_id: image_id for image_id in ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if hamming_distance(hashes[left], hashes[right]) <= max_hamming_distance:
                union(left, right)

    grouped: Dict[str, List[str]] = {}
    for image_id in ids:
        grouped.setdefault(find(image_id), []).append(image_id)
    return [sorted(group) for group in grouped.values() if len(group) > 1]


def check_session_boundaries(inventory: DatasetInventory) -> List[LeakageIssue]:
    """Flag any collection session that appears in more than one split."""
    by_session: Dict[str, Set[str]] = {}
    for image in inventory.images:
        if image.session_id:
            by_session.setdefault(image.session_id, set()).add(image.split)
    issues: List[LeakageIssue] = []
    for session_id, splits in sorted(by_session.items()):
        if len(splits) > 1:
            issues.append(
                LeakageIssue(
                    kind="session_crosses_split",
                    severity="error",
                    detail=(
                        f"Session {session_id!r} appears in multiple splits: "
                        f"{sorted(splits)}. Whole sessions must remain on one side."
                    ),
                )
            )
    return issues


def find_duplicate_groups(
    inventory: DatasetInventory,
    max_hamming_distance: int = 8,
) -> List[DuplicateGroup]:
    """Find exact and near-duplicate images within the evaluated split."""
    by_hash: Dict[str, List[str]] = {}
    by_id = {image.image_id: image for image in inventory.images}
    for image in inventory.images:
        if image.sha256:
            by_hash.setdefault(image.sha256, []).append(image.image_id)

    groups: List[DuplicateGroup] = []
    exact_ids: Set[str] = set()
    for _, ids in sorted(by_hash.items()):
        if len(ids) > 1:
            sessions = tuple(
                sorted(
                    {
                        by_id[image_id].session_id
                        for image_id in ids
                        if by_id[image_id].session_id
                    }
                )
            )
            groups.append(
                DuplicateGroup(
                    kind="exact_duplicate",
                    image_ids=tuple(sorted(ids)),
                    session_ids=sessions,
                    distance=0,
                )
            )
            exact_ids.update(ids)

    remaining = [image.image_id for image in inventory.images if image.image_id not in exact_ids]
    if len(remaining) > 1:
        hashes = {
            image.image_id: perceptual_hash(image.image_path)
            for image in inventory.images
            if image.image_id in remaining
        }
        for group in _union_find_groups(remaining, hashes, max_hamming_distance):
            sessions = tuple(
                sorted(
                    {
                        by_id[image_id].session_id
                        for image_id in group
                        if by_id[image_id].session_id
                    }
                )
            )
            groups.append(
                DuplicateGroup(
                    kind="near_duplicate",
                    image_ids=tuple(group),
                    session_ids=sessions,
                )
            )
    return groups


def reference_session_ids_from_csv(
    path: Path,
    column: str = "session_id",
) -> Set[str]:
    """Read reference session ids from a CSV with a session column."""
    if not Path(path).is_file():
        raise LeakageError(f"Reference session CSV not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames and column not in reader.fieldnames:
            raise LeakageError(
                f"{path} has no '{column}' column (found {reader.fieldnames})"
            )
        return {
            str(row[column]).strip()
            for row in reader
            if row.get(column) not in (None, "")
        }


def analyze_leakage(
    inventory: DatasetInventory,
    *,
    reference_session_ids: Optional[Iterable[str]] = None,
    reference_image_paths: Optional[Iterable[Path]] = None,
    max_hamming_distance: int = 8,
    check_near_duplicates: bool = True,
) -> LeakageReport:
    """Run all leakage checks and return a transparent report.

    Error-level issues mean the dataset cannot be treated as independent.
    Warnings are disclosed but do not by themselves fail the gate.
    """
    issues: List[LeakageIssue] = list(check_session_boundaries(inventory))
    methods = ["session_boundary_check", "sha256_exact_duplicate_check"]

    missing_sessions = inventory.missing_session_count
    if missing_sessions:
        issues.append(
            LeakageIssue(
                kind="missing_session_metadata",
                severity="warning",
                detail=(
                    f"{missing_sessions}/{inventory.image_count} image(s) have no "
                    "session_id; adjacent-frame independence cannot be verified."
                ),
            )
        )

    duplicate_groups: List[DuplicateGroup] = []
    if check_near_duplicates:
        methods.append("dct_perceptual_hash_near_duplicate_check")
        duplicate_groups = find_duplicate_groups(inventory, max_hamming_distance)
        for group in duplicate_groups:
            if len(group.session_ids) > 1:
                issues.append(
                    LeakageIssue(
                        kind=f"{group.kind}_across_sessions",
                        severity="error",
                        detail=(
                            f"{group.kind} group spans sessions {list(group.session_ids)}: "
                            "the same scene appears in different collection sessions."
                        ),
                        image_ids=group.image_ids,
                    )
                )
            else:
                issues.append(
                    LeakageIssue(
                        kind=f"{group.kind}_within_session",
                        severity="warning",
                        detail=(
                            f"{group.kind} group of {len(group.image_ids)} images within "
                            "one session; repeated frames are not independent observations."
                        ),
                        image_ids=group.image_ids,
                    )
                )
    else:
        methods.append("perceptual_hash_disabled")

    reference_sessions = {
        str(session) for session in (reference_session_ids or ()) if session not in (None, "")
    }
    if reference_sessions:
        methods.append("reference_session_overlap_check")
        independent_sessions = set(inventory.sessions)
        overlap = sorted(independent_sessions & reference_sessions)
        if overlap:
            issues.append(
                LeakageIssue(
                    kind="reference_session_overlap",
                    severity="error",
                    detail=f"Independent data reuses reference sessions: {overlap}",
                )
            )

    reference_paths = [Path(path) for path in (reference_image_paths or ())]
    checked_reference = 0
    if reference_paths:
        methods.append("reference_image_hash_check")
        independent_hashes = {
            image.sha256: image.image_id
            for image in inventory.images
            if image.sha256
        }
        independent_phash = (
            {
                image.image_id: perceptual_hash(image.image_path)
                for image in inventory.images
            }
            if check_near_duplicates
            else {}
        )
        for reference_path in reference_paths:
            if not reference_path.is_file():
                raise LeakageError(f"Reference image not found: {reference_path}")
            checked_reference += 1
            reference_hash = compute_file_sha256(reference_path)
            if reference_hash in independent_hashes:
                issues.append(
                    LeakageIssue(
                        kind="reference_exact_duplicate",
                        severity="error",
                        detail=(
                            f"Reference image {reference_path.name} is byte-identical "
                            f"to independent image {independent_hashes[reference_hash]}"
                        ),
                    )
                )
                continue
            if check_near_duplicates:
                reference_phash = perceptual_hash(reference_path)
                for image_id, image_phash in independent_phash.items():
                    if hamming_distance(reference_phash, image_phash) <= max_hamming_distance:
                        issues.append(
                            LeakageIssue(
                                kind="reference_near_duplicate",
                                severity="error",
                                detail=(
                                    f"Reference image {reference_path.name} is visually "
                                    f"near-duplicate of independent image {image_id}"
                                ),
                                image_ids=(image_id,),
                            )
                        )
                        break

    return LeakageReport(
        issues=tuple(issues),
        duplicate_groups=tuple(duplicate_groups),
        checked_images=inventory.image_count,
        checked_reference_images=checked_reference,
        session_count=len(inventory.sessions),
        methods=tuple(methods),
    )


__all__ = [
    "DuplicateGroup",
    "LeakageError",
    "LeakageIssue",
    "LeakageReport",
    "analyze_leakage",
    "check_session_boundaries",
    "find_duplicate_groups",
    "hamming_distance",
    "perceptual_hash",
    "reference_session_ids_from_csv",
]
