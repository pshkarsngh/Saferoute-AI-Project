"""SafeRoute AI — Permitted Imagery Acquisition Interfaces.

Phase ID: PHASE_14
Follows TRD §10.1, ARCHITECTURE §8, master_rules.md Rule 8.
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.imagery.schemas import ImageryResult
from src.routing.schemas import RouteSegment


class ImageryProvider(ABC):
    """Abstract protocol for permitted road imagery retrieval.
    
    Invariants:
    - Rule 8: Only retrieves imagery from explicit, documented permitted sources.
    - Rule 9: Never assumes unavailable imagery implies safe roads.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name identifier."""
        pass

    @abstractmethod
    def get_imagery_for_segment(
        self,
        segment: RouteSegment,
        permitted_source: Optional[str] = None,
    ) -> ImageryResult:
        """Fetch permitted road imagery matching the route segment.
        
        Returns:
            ImageryResult with ImageRef objects if available, or explicit
            ImageryUnavailable detail if missing, stale, inaccessible, or disallowed.
        """
        pass
