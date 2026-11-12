"""SafeRoute AI — Phase 43 independent-dataset governance.

This package implements the P2/P3 data-governance pipeline that prepares (but
does not fabricate) an independent evaluation dataset for the Phase 42 harness.

Modules
-------
common       Shared paths, hashing, YAML/JSON helpers and constants.
acquisition  Provenance schema validation and safe ingestion.
reference    Reference-session registry built from existing training data.
splitting    Deterministic, session-atomic split assignment.
annotation   Annotation-review and adjudication validation.
freeze       Dataset freeze: validation, hashes and manifest generation.
preflight    Read-only Phase 42 dataset readiness check.

Design rules
------------
* Nothing here acquires external imagery. Ingestion only accepts files the
  operator already holds and only when the source is explicitly approved.
* No annotation is invented. Review/adjudication evidence must be supplied by
  real reviewers.
* A filename-derived capture date is a *proxy* session id, never a verified
  collection session. A proxy-only reference registry can never yield PASS.
* Missing evidence is reported, never silently defaulted.
"""

from .acquisition import (
    AcquisitionAudit,
    AcquisitionError,
    AcquisitionRecord,
    ingest_acquisition,
    load_acquisition_csv,
    validate_acquisition,
)
from .annotation import (
    AnnotationAudit,
    AnnotationError,
    load_adjudication_csv,
    load_review_csv,
    validate_annotation_evidence,
)
from .common import (
    ALLOWED_ORIGINALITY,
    ALLOWED_PERMISSION_STATUS,
    CLASS_NAMES,
    DATASET_VERSION,
    REVIEW_ROLES,
    TOOL_VERSION,
    FreezeStatus,
)
from .freeze import (
    FreezeError,
    FreezeResult,
    compute_dataset_hashes,
    freeze_dataset,
    verify_frozen_hashes,
)
from .preflight import preflight_dataset
from .reference import (
    ReferenceRegistry,
    build_reference_registry,
    load_reference_registry,
)
from .sources import (
    SourceRecord,
    SourceRegistryError,
    audit_source_registry,
    load_source_registry,
)
from .splitting import (
    assign_session_splits,
    validate_session_atomicity,
)

__all__ = [
    "ALLOWED_ORIGINALITY",
    "ALLOWED_PERMISSION_STATUS",
    "AcquisitionAudit",
    "AcquisitionError",
    "AcquisitionRecord",
    "AnnotationAudit",
    "AnnotationError",
    "CLASS_NAMES",
    "DATASET_VERSION",
    "FreezeError",
    "FreezeResult",
    "FreezeStatus",
    "REVIEW_ROLES",
    "ReferenceRegistry",
    "SourceRecord",
    "SourceRegistryError",
    "TOOL_VERSION",
    "assign_session_splits",
    "audit_source_registry",
    "build_reference_registry",
    "compute_dataset_hashes",
    "freeze_dataset",
    "ingest_acquisition",
    "load_acquisition_csv",
    "load_adjudication_csv",
    "load_reference_registry",
    "load_review_csv",
    "load_source_registry",
    "preflight_dataset",
    "validate_acquisition",
    "validate_annotation_evidence",
    "validate_session_atomicity",
    "verify_frozen_hashes",
]
