"""P3 — annotation review and adjudication evidence validation.

The dataset cannot be frozen on one person's labels. Every image in a frozen
split needs two independent reviews (annotator A and B) and an adjudication
record. Empty label files are accepted only when adjudication explicitly marks
them as verified negatives.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .common import (
    ADJUDICATION_COLUMNS,
    ADJUDICATION_OUTCOMES,
    FINAL_STATUSES,
    REVIEW_COLUMNS,
    REVIEW_ROLES,
    REVIEW_STATUSES,
    SPLITS,
)


class AnnotationError(ValueError):
    """Raised when review/adjudication files are structurally unusable."""


def _read_csv(path: Path, required: Sequence[str], kind: str) -> Tuple[List[Dict[str, str]], List[str]]:
    path = Path(path)
    if not path.is_file():
        raise AnnotationError(f"{kind} file not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        missing = [name for name in required if name not in fieldnames]
        if missing:
            raise AnnotationError(
                f"{path} is missing required columns: {missing}. Found: {fieldnames}"
            )
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def load_review_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    return _read_csv(path, REVIEW_COLUMNS, "annotation review")


def load_adjudication_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    return _read_csv(path, ADJUDICATION_COLUMNS, "adjudication")


@dataclass(frozen=True)
class AnnotationAudit:
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]
    image_count: int
    reviewed_image_count: int
    adjudicated_image_count: int
    verified_negative_ids: Tuple[str, ...]
    excluded_ids: Tuple[str, ...]
    uncertain_ids: Tuple[str, ...]
    agreement_count: int
    agreement_fraction: Optional[float]
    reviewer_ids: Tuple[str, ...]
    annotator_a_ids: Tuple[str, ...]
    annotator_b_ids: Tuple[str, ...]
    adjudicator_ids: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "image_count": self.image_count,
            "reviewed_image_count": self.reviewed_image_count,
            "adjudicated_image_count": self.adjudicated_image_count,
            "verified_negative_count": len(self.verified_negative_ids),
            "verified_negative_ids": list(self.verified_negative_ids),
            "excluded_count": len(self.excluded_ids),
            "excluded_ids": list(self.excluded_ids),
            "uncertain_count": len(self.uncertain_ids),
            "uncertain_ids": list(self.uncertain_ids),
            "agreement_count": self.agreement_count,
            "agreement_fraction": self.agreement_fraction,
            "reviewer_ids": list(self.reviewer_ids),
            "annotator_a_ids": list(self.annotator_a_ids),
            "annotator_b_ids": list(self.annotator_b_ids),
            "adjudicator_ids": list(self.adjudicator_ids),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int_field(row: Mapping[str, Any], name: str, errors: List[str], image_id: str) -> Optional[int]:
    text = _text(row.get(name))
    if text == "":
        errors.append(f"image {image_id!r}: {name} is empty")
        return None
    try:
        value = int(text)
    except ValueError:
        errors.append(f"image {image_id!r}: {name} is not an integer: {text!r}")
        return None
    if value < 0:
        errors.append(f"image {image_id!r}: {name} must be non-negative")
        return None
    return value


def validate_annotation_evidence(
    review_rows: Sequence[Mapping[str, str]],
    adjudication_rows: Sequence[Mapping[str, str]],
    *,
    expected_annotation_version: str,
    label_counts: Mapping[str, int],
    split_by_image: Mapping[str, str],
    expected_images: Sequence[str],
) -> AnnotationAudit:
    errors: List[str] = []
    warnings: List[str] = []
    expected = list(dict.fromkeys(str(image_id) for image_id in expected_images))
    expected_set = set(expected)
    version = str(expected_annotation_version or "").strip()
    if not version:
        errors.append("expected_annotation_version is empty")

    reviews_by_image: Dict[str, List[Mapping[str, str]]] = {}
    reviewer_ids = set()
    annotator_a_ids = set()
    annotator_b_ids = set()
    for row in review_rows:
        image_id = str(row.get("image_id") or "").strip()
        if not image_id:
            errors.append("annotation review row has a blank image_id")
            continue
        if image_id not in expected_set:
            # Excluded/uncertain images may legitimately be absent from the split.
            warnings.append(
                f"review row references image {image_id!r} that is not in a split"
            )
        reviewer_id = str(row.get("reviewer_id") or "").strip()
        role = str(row.get("role") or "").strip().lower()
        row_version = str(row.get("annotation_version") or "").strip()
        status = str(row.get("review_status") or "").strip().lower()
        if not reviewer_id:
            errors.append(f"image {image_id!r}: reviewer_id is empty")
        if role not in REVIEW_ROLES:
            errors.append(
                f"image {image_id!r}: role must be one of {sorted(REVIEW_ROLES)}, "
                f"got {role!r}"
            )
        if not version or row_version != version:
            errors.append(
                f"image {image_id!r}: review annotation_version {row_version!r} "
                f"does not match frozen version {version!r}"
            )
        if status not in REVIEW_STATUSES:
            errors.append(
                f"image {image_id!r}: review_status must be one of "
                f"{sorted(REVIEW_STATUSES)}, got {status!r}"
            )
        _int_field(row, "box_count", errors, image_id)
        if reviewer_id:
            reviewer_ids.add(reviewer_id)
        if role == "annotator_a" and reviewer_id:
            annotator_a_ids.add(reviewer_id)
        if role == "annotator_b" and reviewer_id:
            annotator_b_ids.add(reviewer_id)
        reviews_by_image.setdefault(image_id, []).append(row)

    adjudication_by_image: Dict[str, Mapping[str, str]] = {}
    adjudicator_ids = set()
    excluded_ids: List[str] = []
    uncertain_ids: List[str] = []
    verified_negative_ids: List[str] = []
    for row in adjudication_rows:
        image_id = str(row.get("image_id") or "").strip()
        if not image_id:
            errors.append("adjudication row has a blank image_id")
            continue
        if image_id in adjudication_by_image:
            errors.append(f"image {image_id!r}: duplicate adjudication row")
            continue
        adjudication_by_image[image_id] = row
        adjudicator_id = str(row.get("adjudicator_id") or "").strip()
        row_version = str(row.get("annotation_version") or "").strip()
        outcome = str(row.get("outcome") or "").strip().lower()
        final_status = str(row.get("final_status") or "").strip().lower()
        if not adjudicator_id:
            errors.append(f"image {image_id!r}: adjudicator_id is empty")
        else:
            adjudicator_ids.add(adjudicator_id)
        if not version or row_version != version:
            errors.append(
                f"image {image_id!r}: adjudication annotation_version "
                f"{row_version!r} does not match frozen version {version!r}"
            )
        if outcome not in ADJUDICATION_OUTCOMES:
            errors.append(
                f"image {image_id!r}: outcome must be one of "
                f"{sorted(ADJUDICATION_OUTCOMES)}, got {outcome!r}"
            )
        if final_status not in FINAL_STATUSES:
            errors.append(
                f"image {image_id!r}: final_status must be one of "
                f"{sorted(FINAL_STATUSES)}, got {final_status!r}"
            )
        _int_field(row, "resolved_box_count", errors, image_id)
        if final_status == "excluded":
            excluded_ids.append(image_id)
        elif final_status == "uncertain":
            uncertain_ids.append(image_id)
        if image_id in expected_set and final_status in {"excluded", "uncertain"}:
            errors.append(
                f"image {image_id!r} is marked {final_status!r} but still present in "
                "a frozen split; move excluded/uncertain images out of images/*"
            )
        if outcome == "verified_negative":
            verified_negative_ids.append(image_id)

    reviewed_image_count = 0
    adjudicated_image_count = 0
    agreement_count = 0
    for image_id in expected:
        rows = reviews_by_image.get(image_id, [])
        roles = [str(row.get("role") or "").strip().lower() for row in rows]
        if len(rows) != 2:
            errors.append(
                f"image {image_id!r}: expected exactly two reviews, found {len(rows)}"
            )
        if roles.count("annotator_a") != 1 or roles.count("annotator_b") != 1:
            errors.append(
                f"image {image_id!r}: reviews must contain exactly one annotator_a "
                f"and one annotator_b (found {roles})"
            )
        reviewer_pair = {
            str(row.get("reviewer_id") or "").strip()
            for row in rows
            if str(row.get("reviewer_id") or "").strip()
        }
        if len(reviewer_pair) < 2:
            errors.append(
                f"image {image_id!r}: reviews are not independent (reviewer ids "
                f"are not distinct: {sorted(reviewer_pair)})"
            )
        if rows:
            reviewed_image_count += 1
        if all(_text(row.get("review_status")).lower() == "approved" for row in rows):
            counts = {_text(row.get("box_count")) for row in rows}
            if len(counts) == 1:
                agreement_count += 1

        adjudication = adjudication_by_image.get(image_id)
        if adjudication is None:
            errors.append(f"image {image_id!r}: no adjudication record")
            continue
        adjudicated_image_count += 1
        final_status = str(adjudication.get("final_status") or "").strip().lower()
        outcome = str(adjudication.get("outcome") or "").strip().lower()
        split = split_by_image.get(image_id, "")
        if split == "test" and final_status != "accepted":
            errors.append(
                f"image {image_id!r}: locked test split requires final_status "
                f"'accepted', got {final_status!r}"
            )
        label_count = int(label_counts.get(image_id, 0))
        resolved = _text(adjudication.get("resolved_box_count"))
        if resolved != "" and resolved.isdigit() and int(resolved) != label_count:
            errors.append(
                f"image {image_id!r}: adjudicated resolved_box_count={resolved} but "
                f"the label file contains {label_count} box(es)"
            )
        if label_count == 0:
            if outcome != "verified_negative":
                errors.append(
                    f"image {image_id!r}: empty label file is not confirmed as a "
                    "verified negative (outcome must be 'verified_negative')"
                )
            review_counts = {_text(row.get("box_count")) for row in rows}
            if review_counts and review_counts != {"0"}:
                errors.append(
                    f"image {image_id!r}: empty label file but reviewers recorded "
                    f"box_count values {sorted(review_counts)}"
                )
        elif outcome == "verified_negative":
            errors.append(
                f"image {image_id!r}: marked verified_negative but label file has "
                f"{label_count} box(es)"
            )

    unexpected = [
        image_id
        for image_id, rows in reviews_by_image.items()
        if image_id not in expected_set
        and str(adjudication_by_image.get(image_id, {}).get("final_status") or "")
        .strip()
        .lower()
        == "accepted"
    ]
    if unexpected:
        errors.append(
            "review rows marked accepted but absent from every split: "
            + ", ".join(sorted(unexpected)[:10])
        )

    if annotator_a_ids and annotator_b_ids and annotator_a_ids == annotator_b_ids:
        errors.append(
            "annotator A and annotator B are the same reviewer id(s); independent "
            "review requires two different people"
        )

    total = len(expected)
    return AnnotationAudit(
        errors=tuple(errors),
        warnings=tuple(warnings),
        image_count=total,
        reviewed_image_count=reviewed_image_count,
        adjudicated_image_count=adjudicated_image_count,
        verified_negative_ids=tuple(sorted(set(verified_negative_ids))),
        excluded_ids=tuple(sorted(set(excluded_ids))),
        uncertain_ids=tuple(sorted(set(uncertain_ids))),
        agreement_count=agreement_count,
        agreement_fraction=(agreement_count / total) if total else None,
        reviewer_ids=tuple(sorted(reviewer_ids)),
        annotator_a_ids=tuple(sorted(annotator_a_ids)),
        annotator_b_ids=tuple(sorted(annotator_b_ids)),
        adjudicator_ids=tuple(sorted(adjudicator_ids)),
    )


__all__ = [
    "AnnotationAudit",
    "AnnotationError",
    "load_adjudication_csv",
    "load_review_csv",
    "validate_annotation_evidence",
]
