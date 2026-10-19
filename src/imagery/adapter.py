"""SafeRoute AI — Permitted Imagery Acquisition Adapter.

Phase ID: PHASE_14
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 1, 8, 9, 14, 19.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from src.imagery.interfaces import ImageryProvider
from src.imagery.matcher import SegmentImageryMatcher
from src.imagery.schemas import (
    ImageRef,
    ImageryResult,
    ImageryStatus,
    ImageryUnavailable,
)
from src.imagery.staleness import StalenessEvaluator
from src.routing.schemas import RouteSegment

DEFAULT_IMAGERY_CONFIG = Path("config/imagery.yaml")
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class PermittedImageryAdapter(ImageryProvider):
    """Retrieves road imagery strictly from documented permitted sources (Rule 8).
    
    Hard Invariants:
    - Rule 8: Only approved open sources (e.g. CC-BY 4.0, CC-BY-SA 4.0) are accessed.
    - Rule 9: Missing, stale, or unmatched imagery yields explicit Unavailable results, NEVER safe verdicts.
    - Rule 1: Stored imagery is kept strictly inside the workspace.
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        demo_mode: Optional[bool] = None,
    ):
        if config_dict is not None:
            self.config = config_dict
        else:
            p = Path(config_path) if config_path else (WORKSPACE_ROOT / DEFAULT_IMAGERY_CONFIG)
            if p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            else:
                self.config = {}

        # PHASE_23B: demo imagery is OFF unless explicitly requested (Rule 9, 20).
        # When enabled, local sample frames are returned only as clearly-labelled
        # demo imagery with NO synthesized geographic coordinates.
        if demo_mode is None:
            demo_cfg = self.config.get("demo", {}) or {}
            demo_mode = bool(demo_cfg.get("enabled", False))
        self.demo_mode = bool(demo_mode)

        self.sources_cfg = self.config.get("sources", {})
        self.storage_cfg = self.config.get("storage", {})
        self.matching_cfg = self.config.get("matching", {})
        self.staleness_cfg = self.config.get("staleness", {})

        # Storage directory inside workspace (Rule 1)
        rel_cache = self.storage_cfg.get("cache_dir", "data/imagery")
        self.storage_dir = (WORKSPACE_ROOT / rel_cache).resolve()
        if self.storage_cfg.get("create_if_missing", True):
            self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.matcher = SegmentImageryMatcher(
            search_radius_meters=float(self.matching_cfg.get("search_radius_meters", 25.0)),
            max_images_per_segment=int(self.matching_cfg.get("max_images_per_segment", 3)),
        )
        self.staleness_evaluator = StalenessEvaluator(
            max_age_days=int(self.staleness_cfg.get("max_age_days", 180)),
            flag_as_limitation=bool(self.staleness_cfg.get("flag_stale_as_limitation", True)),
        )

        # In-memory candidate catalog. Local sample frames are indexed as
        # coordinate-less demo entries (never matchable); real candidates are
        # supplied explicitly via ``register_candidate_images``.
        self._catalogue: List[Dict[str, Any]] = []
        self._load_local_archive_catalog()

    @property
    def provider_name(self) -> str:
        return "permitted_imagery_adapter"

    def register_candidate_images(self, candidates: List[Dict[str, Any]]) -> None:
        """Register candidate image records into the spatial catalog."""
        self._catalogue.extend(candidates)

    def is_source_permitted(self, source_name: str) -> Tuple[bool, str, str]:
        """Verify whether a source is legally permitted under policy (Rule 8).
        
        Returns:
            (is_permitted: bool, licence: str, reason: str)
        """
        src = self.sources_cfg.get(source_name)
        if not src:
            return False, "UNKNOWN", f"Source '{source_name}' is not in the approved permitted sources registry."

        if not src.get("enabled", False):
            reason = src.get("reason", f"Source '{source_name}' is explicitly disabled.")
            return False, src.get("licence", "PROPRIETARY"), reason

        return True, src.get("licence", "OPEN_DATA"), "Permitted"

    def get_imagery_for_segment(
        self,
        segment: RouteSegment,
        permitted_source: Optional[str] = None,
    ) -> ImageryResult:
        """Fetch permitted imagery matching a route segment."""
        source_name = permitted_source or "workspace_dashcam_v1"
        is_allowed, licence, reason = self.is_source_permitted(source_name)

        # Guardrail: Rejection of disallowed/unpermitted sources (Rule 8)
        if not is_allowed:
            unavail = ImageryUnavailable(
                segment_id=segment.segment_id,
                reason=ImageryStatus.DISALLOWED_SOURCE,
                message=reason,
                limitations=[f"disallowed_imagery_source_{source_name}", "missing_imagery_not_safe"],
            )
            return ImageryResult(
                segment_id=segment.segment_id,
                status=ImageryStatus.DISALLOWED_SOURCE,
                images=[],
                unavailable_detail=unavail,
                source=source_name,
                licence=licence,
                limitations=unavail.limitations,
            )

        # Filter catalogue candidates for this source. Demo entries (no verified
        # geography) are held aside so they can never be spatially matched; they
        # are returned only when demo mode is explicitly enabled.
        source_candidates = [c for c in self._catalogue if c.get("source") == source_name]
        if not source_candidates:
            unavail = ImageryUnavailable(
                segment_id=segment.segment_id,
                reason=ImageryStatus.MISSING,
                message=f"No imagery files found in source '{source_name}' repository.",
                limitations=["missing_imagery_not_safe"],
            )
            return ImageryResult(
                segment_id=segment.segment_id,
                status=ImageryStatus.MISSING,
                images=[],
                unavailable_detail=unavail,
                source=source_name,
                licence=licence,
                limitations=unavail.limitations,
            )

        demo_candidates = [c for c in source_candidates if c.get("is_demo")]
        matchable_candidates = [c for c in source_candidates if not c.get("is_demo")]

        # Perform spatial matching within the configured buffer (ARCHITECTURE §8)
        matches = self.matcher.match_candidates(segment, matchable_candidates)
        if not matches:
            # PHASE_23B: demo imagery is only ever used when explicitly enabled,
            # and it is disclosed as NOT geographically matched (Rule 9, Rule 20).
            if self.demo_mode and demo_candidates:
                return self._demo_result(segment, source_name, licence, demo_candidates)

            unavail = ImageryUnavailable(
                segment_id=segment.segment_id,
                reason=ImageryStatus.UNMATCHED,
                message=f"No road imagery found within {self.matcher.radius_m}m buffer of segment geometry.",
                limitations=["unmatched_segment_imagery", "missing_imagery_not_safe"],
            )
            return ImageryResult(
                segment_id=segment.segment_id,
                status=ImageryStatus.UNMATCHED,
                images=[],
                unavailable_detail=unavail,
                source=source_name,
                licence=licence,
                limitations=unavail.limitations,
            )

        # Build ImageRef records with staleness inspection
        image_refs: List[ImageRef] = []
        result_limitations: List[str] = []
        has_any_stale = False
        now_iso = datetime.now(timezone.utc).isoformat()

        for cand, dist_m in matches:
            cap_date = cand.get("captured_at")
            is_stale, age_days, stale_note = self.staleness_evaluator.evaluate(cap_date)

            if is_stale:
                has_any_stale = True
                if stale_note:
                    result_limitations.append(stale_note)

            status_str = "stale" if is_stale else "available"
            img_ref = ImageRef(
                image_id=cand.get("image_id", "img_unknown"),
                file_path=str(cand.get("file_path", "")),
                source=source_name,
                licence=licence,
                retrieved_at=now_iso,
                captured_at=cap_date,
                coordinates=tuple(cand["coordinates"]) if cand.get("coordinates") else None,
                distance_to_segment_m=dist_m,
                is_stale=is_stale,
                status=status_str,
            )
            image_refs.append(img_ref)

        overall_status = ImageryStatus.STALE if has_any_stale else ImageryStatus.AVAILABLE
        return ImageryResult(
            segment_id=segment.segment_id,
            status=overall_status,
            images=image_refs,
            unavailable_detail=None,
            source=source_name,
            licence=licence,
            limitations=result_limitations,
        )

    def _load_local_archive_catalog(self) -> None:
        """Index local workspace sample frames as coordinate-less demo entries.

        PHASE_23B: the previous implementation anchored these frames at synthetic
        Bengaluru coordinates (``77.5946 + idx*0.001`` / ``12.9716 + idx*0.001``),
        which made unrelated sample images look like geographically matched route
        evidence. That is removed. Local sample frames are indexed with
        ``coordinates=None`` and ``is_demo=True`` so the spatial matcher can never
        match them to a real route segment. They are only ever returned when
        ``demo_mode`` is explicitly enabled, and always carry an ``is_demo`` marker
        plus a disclosure limitation (Rule 9, Rule 20).

        Indexing them (rather than omitting them entirely) lets a segment with no
        verified imagery resolve to an honest ``UNMATCHED`` instead of an
        ambiguous empty-source result.
        """
        qual_dir = WORKSPACE_ROOT / "logs" / "evaluation" / "qualitative_samples"
        if not qual_dir.is_dir():
            return

        for img_p in sorted(list(qual_dir.glob("*.jpg"))):
            self._catalogue.append({
                "image_id": f"demo_{img_p.stem}",
                "file_path": str(img_p.resolve()),
                "source": "workspace_dashcam_v1",
                "coordinates": None,  # no verified geographic location
                "captured_at": None,  # freshness cannot be verified (honest staleness)
                "is_demo": True,
            })

    def _demo_result(
        self,
        segment: RouteSegment,
        source_name: str,
        licence: str,
        demo_candidates: List[Dict[str, Any]],
    ) -> ImageryResult:
        """Build an explicitly-disclosed demo imagery result (never route evidence)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        image_refs: List[ImageRef] = []
        has_any_stale = False
        # PHASE_25: the configured per-segment image cap applies to the demo path
        # too, so enabling demo mode cannot multiply inference work by the whole
        # archive (config/imagery.yaml -> matching.max_images_per_segment).
        for cand in demo_candidates[: self.matcher.max_images]:
            is_stale, _age, _stale_note = self.staleness_evaluator.evaluate(cand.get("captured_at"))
            if is_stale:
                has_any_stale = True
            image_refs.append(ImageRef(
                image_id=str(cand.get("image_id", "demo_unknown")),
                file_path=str(cand.get("file_path", "")),
                source=source_name,
                licence=licence,
                retrieved_at=now_iso,
                captured_at=cand.get("captured_at"),
                coordinates=None,
                distance_to_segment_m=None,
                is_stale=is_stale,
                status="stale" if is_stale else "available",
                is_demo=True,
            ))
        limitations = [
            "demo_imagery_not_geographically_matched",
            "demo_imagery_not_route_evidence",
            "missing_imagery_not_safe",
        ]
        return ImageryResult(
            segment_id=segment.segment_id,
            status=ImageryStatus.STALE if has_any_stale else ImageryStatus.AVAILABLE,
            images=image_refs,
            unavailable_detail=None,
            source=source_name,
            licence=licence,
            limitations=limitations,
        )
