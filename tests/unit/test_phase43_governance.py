"""Phase 43 P2/P3 governance tests.

These tests exercise the *tooling*, never real imagery or real annotation. Every
fixture is synthetic and lives in a temporary directory. The suite asserts the
central safety property: missing evidence yields ``NOT_ASSESSED`` (or a refusal),
never ``PASS`` and never fabricated detector performance.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.datasets.annotation import validate_annotation_evidence
from src.datasets.acquisition import (
    AcquisitionError,
    AcquisitionRecord,
    ingest_acquisition,
    load_acquisition_csv,
    validate_acquisition,
)
from src.datasets.common import (
    ACQUISITION_COLUMNS,
    ADJUDICATION_COLUMNS,
    DATASET_VERSION,
    DEFAULT_ANNOTATION_VERSION,
    FreezeStatus,
    REVIEW_COLUMNS,
    sha256_file,
)
from src.datasets.freeze import (
    compute_dataset_hashes,
    freeze_dataset,
    verify_frozen_hashes,
)
from src.datasets.preflight import preflight_dataset
from src.datasets.reference import (
    PROXY_QUALITY,
    build_reference_registry,
    load_reference_registry,
    write_reference_registry,
)
from src.datasets.sources import (
    SourceRecord,
    SourceRegistryError,
    audit_source_registry,
    load_source_registry,
)
from src.datasets.splitting import (
    assign_session_splits,
    validate_session_atomicity,
)
from src.evaluation.dataset_validation import collect_dataset

ANNOTATION_VERSION = DEFAULT_ANNOTATION_VERSION
DATASET_VERSION_UNDER_TEST = DATASET_VERSION


def _approved_source(source_id: str = "test_source") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        name="Synthetic test source",
        licence_id="TEST-LICENCE",
        licence_url="https://example.invalid/licence",
        permission_status="approved",
        approved_for_acquisition=True,
        reference_only=False,
        evidence="tests/unit/test_phase43_governance.py",
        notes="synthetic",
    )


def _write_image(path: Path, seed: int) -> None:
    rng = np.random.default_rng(seed)
    image = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"could not write {path}")


def _write_csv(path: Path, columns, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _acquisition_row(
    image_id: str,
    split: str,
    *,
    session_id: str = "sess-1",
    source_id: str = "test_source",
    permission_status: str = "approved",
    file: str | None = None,
    duplicate_of: str | None = None,
) -> dict:
    return {
        "image_id": image_id,
        "file": file or f"images/{split}/{image_id}.jpg",
        "source_id": source_id,
        "split": split,
        "licence_id": "TEST-LICENCE",
        "licence_evidence": "tests/fixtures/licence.txt",
        "permission_status": permission_status,
        "original_or_derived": "original",
        "derived_from": "",
        "capture_session_id": session_id,
        "camera_id": f"cam-{session_id}",
        "capture_date": "2026-01-0" + session_id[-1] if session_id[-1].isdigit() else "2026-01-01",
        "latitude": "12.9716",
        "longitude": "77.5946",
        "location_accuracy_m": "10",
        "country": "IN",
        "region": "KA",
        "road_type": "urban_arterial",
        "surface_condition": "dry",
        "weather": "clear",
        "lighting": "daylight",
        "condition": "daylight_clear_dry",
        "route_id": f"route-{session_id}",
        "segment_id": "seg-1",
        "segment_length_m": "100",
        "distance_km": "0.1",
        "notes": duplicate_of or "",
    }


def _build_case(root: Path, *, verified_reference: bool = True):
    """Create a tiny, fully-evidenced independent dataset under ``root``."""
    dataset = root / "independent"
    source = _approved_source()
    rows = []
    review_rows = []
    adjudication_rows = []

    plan = {
        "train": [("tr-1", "sess-1", 1, 1), ("tr-2", "sess-2", 2, 1)],
        "val": [("va-1", "sess-3", 3, 0)],
        "test": [("te-1", "sess-4", 4, 2), ("te-2", "sess-5", 5, 0)],
    }
    for split, items in plan.items():
        for image_id, session_id, seed, boxes in items:
            image_path = dataset / "images" / split / f"{image_id}.jpg"
            _write_image(image_path, seed)
            label_path = dataset / "labels" / split / f"{image_id}.txt"
            label_path.parent.mkdir(parents=True, exist_ok=True)
            if boxes == 0:
                label_path.write_text("", encoding="utf-8")
            else:
                label_path.write_text(
                    "\n".join(
                        f"0 0.{4 + index}{index} 0.5 0.2 0.2" for index in range(boxes)
                    )
                    + "\n",
                    encoding="utf-8",
                )
            rows.append(_acquisition_row(image_id, split, session_id=session_id))
            for role, reviewer in (
                ("annotator_a", "alice"),
                ("annotator_b", "bob"),
            ):
                review_rows.append(
                    {
                        "image_id": image_id,
                        "reviewer_id": reviewer,
                        "role": role,
                        "annotation_version": ANNOTATION_VERSION,
                        "review_status": "approved",
                        "box_count": boxes,
                        "reviewed_at": "2026-01-10T10:00:00Z",
                        "note": "",
                    }
                )
            adjudication_rows.append(
                {
                    "image_id": image_id,
                    "adjudicator_id": "carol",
                    "annotation_version": ANNOTATION_VERSION,
                    "outcome": "verified_negative" if boxes == 0 else "agree",
                    "final_status": "accepted",
                    "resolved_box_count": boxes,
                    "decided_at": "2026-01-11T10:00:00Z",
                    "note": "",
                }
            )

    _write_csv(
        dataset / "manifests" / "acquisition_manifest.csv",
        ACQUISITION_COLUMNS,
        rows,
    )
    _write_csv(
        dataset / "manifests" / "annotation_review.csv", REVIEW_COLUMNS, review_rows
    )
    _write_csv(
        dataset / "manifests" / "adjudication.csv",
        ADJUDICATION_COLUMNS,
        adjudication_rows,
    )

    reference_dir = root / "reference_images"
    _write_image(reference_dir / "ref-1.jpg", 99)
    _write_image(reference_dir / "ref-2.jpg", 98)

    if verified_reference:
        registry_rows = [
            {
                "session_id": "ref-session-1",
                "session_id_quality": "verified_collection_session",
                "verified": "true",
                "split": "train",
                "image_count": 2,
                "capture_date": "2025-01-01",
                "camera_ids": "cam-ref",
                "route_ids": "route-ref",
                "evidence": "synthetic",
            }
        ]
    else:
        registry_rows = [
            {
                "session_id": "dateproxy-2025-01-01",
                "session_id_quality": PROXY_QUALITY,
                "verified": "false",
                "split": "train",
                "image_count": 2,
                "capture_date": "2025-01-01",
                "camera_ids": "",
                "route_ids": "",
                "evidence": "synthetic",
            }
        ]
    registry_path = root / "training_sessions.csv"
    _write_csv(registry_path, list(registry_rows[0].keys()), registry_rows)

    policy = root / "policy.md"
    policy.write_text("# synthetic annotation policy\n", encoding="utf-8")
    return {
        "dataset": dataset,
        "source": source,
        "registry": registry_path,
        "reference_dir": reference_dir,
        "policy": policy,
        "rows": rows,
        "review_rows": review_rows,
        "adjudication_rows": adjudication_rows,
    }


class Phase43TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="phase43_")
        self.root = Path(self._tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


class SourceRegistryTests(Phase43TestCase):
    def test_committed_registry_approves_nothing(self) -> None:
        path = Path(__file__).resolve().parents[2] / "docs" / "datasets" / "sources.yaml"
        sources = load_source_registry(path)
        audit = audit_source_registry(sources, workspace=path.parents[2])
        self.assertGreaterEqual(len(sources), 1)
        self.assertEqual(audit["approved_count"], 0)
        self.assertFalse(audit["acquisition_allowed"])

    def test_approved_flag_requires_approved_permission(self) -> None:
        path = self.root / "sources.yaml"
        path.write_text(
            "sources:\n"
            "  - source_id: bad\n"
            "    permission_status: pending\n"
            "    approved_for_acquisition: true\n",
            encoding="utf-8",
        )
        with self.assertRaises(SourceRegistryError):
            load_source_registry(path)


class ReferenceRegistryTests(Phase43TestCase):
    def test_proxy_registry_never_claims_verified(self) -> None:
        manifest = self.root / "split_manifest.csv"
        _write_csv(
            manifest,
            ["stem", "capture_date", "split", "kept"],
            [
                {"stem": "a", "capture_date": "2025-01-01", "split": "train", "kept": "True"},
                {"stem": "b", "capture_date": "2025-01-01", "split": "train", "kept": "True"},
                {"stem": "c", "capture_date": "2025-01-02", "split": "val", "kept": "True"},
            ],
        )
        registry = build_reference_registry(manifest)
        self.assertFalse(registry.verified)
        self.assertTrue(registry.proxy_only)
        self.assertEqual(registry.quality, PROXY_QUALITY)
        self.assertEqual(registry.session_count, 2)
        self.assertTrue(all(row["verified"] == "false" for row in registry.rows))

    def test_registry_flags_date_spanning_splits(self) -> None:
        manifest = self.root / "split_manifest.csv"
        _write_csv(
            manifest,
            ["stem", "capture_date", "split", "kept"],
            [
                {"stem": "a", "capture_date": "2025-01-01", "split": "train", "kept": "True"},
                {"stem": "b", "capture_date": "2025-01-01", "split": "test", "kept": "True"},
            ],
        )
        registry = build_reference_registry(manifest)
        self.assertTrue(registry.errors)
        self.assertTrue(any("spans multiple splits" in e for e in registry.errors))

    def test_load_proxy_registry_is_not_verified(self) -> None:
        path = self.root / "registry.csv"
        _write_csv(
            path,
            ["session_id", "session_id_quality", "verified", "image_count"],
            [
                {
                    "session_id": "dateproxy-2025-01-01",
                    "session_id_quality": PROXY_QUALITY,
                    "verified": "false",
                    "image_count": "5",
                }
            ],
        )
        registry = load_reference_registry(path)
        self.assertFalse(registry.verified)
        self.assertEqual(registry.image_count, 5)


class SplittingTests(Phase43TestCase):
    def test_assignment_is_deterministic_and_atomic(self) -> None:
        sessions = [f"sess-{index}" for index in range(10)]
        first = assign_session_splits(sessions, salt="fixed")
        second = assign_session_splits(reversed(sessions), salt="fixed")
        self.assertEqual(first, second)
        self.assertEqual(set(first.values()), {"train", "val", "test"})

        rows = [
            {"image_id": f"img-{index}-{copy}", "capture_session_id": session, "split": split, "route_id": ""}
            for index, (session, split) in enumerate(first.items())
            for copy in range(2)
        ]
        self.assertEqual(validate_session_atomicity(rows), [])

    def test_atomicity_detects_cross_split_session(self) -> None:
        rows = [
            {"image_id": "a", "capture_session_id": "s1", "split": "train"},
            {"image_id": "b", "capture_session_id": "s1", "split": "test"},
        ]
        errors = validate_session_atomicity(rows)
        self.assertTrue(any("crosses splits" in error for error in errors))


class AcquisitionTests(Phase43TestCase):
    def test_valid_acquisition_passes(self) -> None:
        case = _build_case(self.root)
        records, _ = load_acquisition_csv(
            case["dataset"] / "manifests" / "acquisition_manifest.csv"
        )
        audit = validate_acquisition(
            records,
            sources={case["source"].source_id: case["source"]},
            images_root=case["dataset"],
            reference_image_paths=list(case["reference_dir"].glob("*.jpg")),
        )
        self.assertTrue(audit.ok, audit.errors)
        self.assertEqual(audit.split_counts, {"train": 2, "val": 1, "test": 2})

    def test_unapproved_source_is_rejected(self) -> None:
        case = _build_case(self.root)
        records, _ = load_acquisition_csv(
            case["dataset"] / "manifests" / "acquisition_manifest.csv"
        )
        unapproved = SourceRecord(
            **{**case["source"].to_dict(), "approved_for_acquisition": False}
        )
        audit = validate_acquisition(
            records,
            sources={unapproved.source_id: unapproved},
            images_root=case["dataset"],
        )
        self.assertFalse(audit.ok)
        self.assertTrue(any("not approved" in error for error in audit.errors))

    def test_duplicate_bytes_are_rejected(self) -> None:
        case = _build_case(self.root)
        dataset = case["dataset"]
        # Copy one train image over another: identical bytes, new name.
        shutil.copy2(dataset / "images/train/tr-1.jpg", dataset / "images/train/tr-2.jpg")
        records, _ = load_acquisition_csv(
            dataset / "manifests" / "acquisition_manifest.csv"
        )
        audit = validate_acquisition(
            records,
            sources={case["source"].source_id: case["source"]},
            images_root=dataset,
        )
        self.assertFalse(audit.ok)
        self.assertTrue(
            any("duplicate" in error.lower() for error in audit.errors), audit.errors
        )

    def test_undocumented_image_is_rejected(self) -> None:
        case = _build_case(self.root)
        _write_image(case["dataset"] / "images/train/extra.jpg", 77)
        records, _ = load_acquisition_csv(
            case["dataset"] / "manifests" / "acquisition_manifest.csv"
        )
        audit = validate_acquisition(
            records,
            sources={case["source"].source_id: case["source"]},
            images_root=case["dataset"],
        )
        self.assertFalse(audit.ok)
        self.assertTrue(any("undocumented" in error for error in audit.errors))

    def test_reference_exact_match_is_rejected(self) -> None:
        case = _build_case(self.root)
        reference = case["reference_dir"] / "ref-1.jpg"
        shutil.copy2(case["dataset"] / "images/test/te-1.jpg", reference)
        records, _ = load_acquisition_csv(
            case["dataset"] / "manifests" / "acquisition_manifest.csv"
        )
        audit = validate_acquisition(
            records,
            sources={case["source"].source_id: case["source"]},
            images_root=case["dataset"],
            reference_image_paths=[reference],
        )
        self.assertFalse(audit.ok)
        self.assertTrue(audit.reference_exact_matches)

    def test_ingest_refuses_unapproved_source(self) -> None:
        case = _build_case(self.root)
        source = SourceRecord(
            **{**case["source"].to_dict(), "approved_for_acquisition": False}
        )
        staging = self.root / "staging"
        staging.mkdir()
        for split in ("train", "val", "test"):
            for image in (case["dataset"] / "images" / split).glob("*.jpg"):
                target = staging / "images" / split / image.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, target)
        report = ingest_acquisition(
            case["dataset"] / "manifests" / "acquisition_manifest.csv",
            staging,
            self.root / "out",
            sources={source.source_id: source},
            dry_run=True,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["written"])

    def test_ingest_dry_run_and_copy(self) -> None:
        case = _build_case(self.root)
        staging = self.root / "staging"
        staging.mkdir()
        for split in ("train", "val", "test"):
            for image in (case["dataset"] / "images" / split).glob("*.jpg"):
                target = staging / "images" / split / image.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, target)

        acquisition_csv = self.root / "staged_manifest.csv"
        _write_csv(acquisition_csv, ACQUISITION_COLUMNS, case["rows"])
        out = self.root / "out"

        dry = ingest_acquisition(
            acquisition_csv,
            staging,
            out,
            sources={case["source"].source_id: case["source"]},
            dry_run=True,
        )
        self.assertEqual(dry["status"], "READY")
        self.assertFalse(out.exists())

        written = ingest_acquisition(
            acquisition_csv,
            staging,
            out,
            sources={case["source"].source_id: case["source"]},
        )
        self.assertEqual(written["status"], "INGESTED")
        self.assertTrue((out / "manifests" / "acquisition_manifest.csv").is_file())
        self.assertTrue((out / "images" / "test" / "te-1.jpg").is_file())

        again = ingest_acquisition(
            acquisition_csv,
            staging,
            out,
            sources={case["source"].source_id: case["source"]},
        )
        self.assertEqual(again["status"], "FAIL")
        self.assertTrue(any("already contains" in e for e in again["audit"]["errors"]))


class AnnotationTests(Phase43TestCase):
    def _validate(self, case, **overrides):
        label_counts = {"tr-1": 1, "tr-2": 1, "va-1": 0, "te-1": 2, "te-2": 0}
        split_by_image = {
            "tr-1": "train",
            "tr-2": "train",
            "va-1": "val",
            "te-1": "test",
            "te-2": "test",
        }
        reviews = overrides.get("reviews", case["review_rows"])
        adjudications = overrides.get("adjudications", case["adjudication_rows"])
        return validate_annotation_evidence(
            reviews,
            adjudications,
            expected_annotation_version=ANNOTATION_VERSION,
            label_counts=label_counts,
            split_by_image=split_by_image,
            expected_images=list(label_counts),
        )

    def test_valid_evidence_passes(self) -> None:
        case = _build_case(self.root)
        audit = self._validate(case)
        self.assertTrue(audit.ok, audit.errors)
        self.assertEqual(audit.verified_negative_ids, ("te-2", "va-1"))
        self.assertEqual(audit.adjudicated_image_count, 5)

    def test_same_reviewer_for_both_roles_is_rejected(self) -> None:
        case = _build_case(self.root)
        reviews = [dict(row) for row in case["review_rows"]]
        for row in reviews:
            row["reviewer_id"] = "same-person"
        audit = self._validate(case, reviews=reviews)
        self.assertFalse(audit.ok)
        self.assertTrue(
            any("not independent" in error or "same reviewer" in error for error in audit.errors),
            audit.errors,
        )

    def test_missing_adjudication_is_rejected(self) -> None:
        case = _build_case(self.root)
        audit = self._validate(case, adjudications=case["adjudication_rows"][:-1])
        self.assertFalse(audit.ok)
        self.assertTrue(any("no adjudication" in error for error in audit.errors))

    def test_negative_without_verified_negative_outcome_is_rejected(self) -> None:
        case = _build_case(self.root)
        adjudications = [dict(row) for row in case["adjudication_rows"]]
        for row in adjudications:
            if row["image_id"] == "te-2":
                row["outcome"] = "agree"
        audit = self._validate(case, adjudications=adjudications)
        self.assertFalse(audit.ok)
        self.assertTrue(any("verified negative" in error for error in audit.errors))

    def test_excluded_image_still_in_split_is_rejected(self) -> None:
        case = _build_case(self.root)
        adjudications = [dict(row) for row in case["adjudication_rows"]]
        for row in adjudications:
            if row["image_id"] == "te-1":
                row["final_status"] = "excluded"
        audit = self._validate(case, adjudications=adjudications)
        self.assertFalse(audit.ok)
        self.assertTrue(
            any("still present in a frozen split" in error for error in audit.errors)
        )


class FreezeAndPreflightTests(Phase43TestCase):
    def _freeze(self, case, *, verified_reference=True, write=False):
        registry_path = case["registry"]
        if not verified_reference:
            rows = [
                {
                    "session_id": "dateproxy-2025-01-01",
                    "session_id_quality": PROXY_QUALITY,
                    "verified": "false",
                    "split": "train",
                    "image_count": 2,
                    "capture_date": "2025-01-01",
                    "camera_ids": "",
                    "route_ids": "",
                    "evidence": "synthetic",
                }
            ]
            _write_csv(registry_path, list(rows[0].keys()), rows)
        return freeze_dataset(
            case["dataset"],
            sources={case["source"].source_id: case["source"]},
            dataset_version=DATASET_VERSION_UNDER_TEST,
            annotation_version=ANNOTATION_VERSION,
            frozen_by="test-suite",
            policy_path=case["policy"],
            reference_registry_path=registry_path,
            reference_image_paths=list(case["reference_dir"].glob("*.jpg")),
            write=write,
        )

    def test_freeze_happy_path_passes_and_hashes_match_phase42(self) -> None:
        case = _build_case(self.root)
        result = self._freeze(case, write=True)
        self.assertEqual(result.status, FreezeStatus.PASS, result.errors + result.warnings)
        self.assertTrue(result.written)
        self.assertTrue((case["dataset"] / "dataset.yaml").is_file())
        self.assertTrue(
            (case["dataset"] / "manifests" / "independent_manifest.json").is_file()
        )

        inventory = collect_dataset(
            case["dataset"] / "dataset.yaml",
            manifest_path=case["dataset"] / "manifests" / "independent_manifest.json",
            split="test",
            require_session_metadata=True,
        )
        hashes = compute_dataset_hashes(case["dataset"])
        self.assertEqual(
            hashes["per_split"]["test"]["dataset_sha256"], inventory.dataset_sha256
        )
        self.assertTrue(verify_frozen_hashes(case["dataset"])["ok"])

    def test_freeze_with_proxy_registry_is_not_assessed(self) -> None:
        case = _build_case(self.root)
        result = self._freeze(case, verified_reference=False, write=False)
        self.assertEqual(result.status, FreezeStatus.NOT_ASSESSED)
        self.assertFalse(result.written)

    def test_tampering_is_detected(self) -> None:
        case = _build_case(self.root)
        result = self._freeze(case, write=True)
        self.assertEqual(result.status, FreezeStatus.PASS)
        label = case["dataset"] / "labels" / "test" / "te-1.txt"
        label.write_text("0 0.1 0.1 0.1 0.1\n", encoding="utf-8")
        verification = verify_frozen_hashes(case["dataset"])
        self.assertFalse(verification["ok"])
        self.assertTrue(verification["mismatches"])

    def test_preflight_missing_dataset_is_not_assessed(self) -> None:
        report = preflight_dataset(self.root / "does-not-exist")
        self.assertEqual(report["status"], "NOT_ASSESSED")
        self.assertFalse(report["dataset_ready"])
        self.assertTrue(report["detector_evaluation_blocked_by_model"])

    def test_preflight_verified_dataset_passes(self) -> None:
        case = _build_case(self.root)
        self._freeze(case, write=True)
        report = preflight_dataset(
            case["dataset"],
            reference_registry_path=case["registry"],
            reference_image_paths=list(case["reference_dir"].glob("*.jpg")),
            workspace=self.root,
        )
        self.assertEqual(report["status"], "PASS", report["errors"] + report["warnings"])
        self.assertTrue(report["dataset_ready"])
        self.assertTrue(report["detector_evaluation_blocked_by_model"])

    def test_preflight_proxy_registry_is_not_assessed(self) -> None:
        case = _build_case(self.root)
        self._freeze(case, verified_reference=False, write=True)
        report = preflight_dataset(
            case["dataset"],
            reference_registry_path=case["registry"],
            reference_image_paths=list(case["reference_dir"].glob("*.jpg")),
            workspace=self.root,
        )
        self.assertEqual(report["status"], "NOT_ASSESSED")
        self.assertFalse(report["dataset_ready"])


if __name__ == "__main__":
    unittest.main()
