"""SafeRoute AI — Facilities Domain Data Contracts & Schemas.

Phase ID: PHASE_15 (contracts), extended in PHASE_29 (honest distance /
attribute presentation).

Follows PRD §4.7, TRD §4.7, ARCHITECTURE §8, master_rules.md Rules 11, 13, 20.

Facilities are presentation/context only. These schemas deliberately contain
NO score, risk or hazard fields: facilities must never enter the hazard score
or route ranking (Rule 11).

PHASE_29: the records now state explicitly HOW each distance was measured and
WHETHER the underlying OpenStreetMap attributes were verified:

* ``distance_kind`` distinguishes a straight-line (great-circle) distance from
  a road-network distance. A road distance / road travel time is only ever
  present when a real routing provider actually returned one.
* ``osm_tags`` are the raw, crowd-sourced OSM tags. They are echoed verbatim
  and are explicitly flagged as NOT independently verified; they are never
  promoted into a claim about opening status, emergency capability, beds,
  staffing or capacity (Rule 20).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

#: Straight-line (great-circle / Haversine) distance — the only measurement the
#: Overpass provider can produce. It is NOT a road-network distance.
DISTANCE_STRAIGHT_LINE = "straight_line_haversine"

#: Road-network distance, only ever set from a real routing provider response.
DISTANCE_ROAD = "road_network_routing_provider"

#: Standing wording used wherever OpenStreetMap attributes are presented.
OSM_ATTRIBUTES_NOTE = "as tagged in OpenStreetMap; not independently verified"

#: The standing wording used when no road travel time could be obtained.
ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE = (
    "Road travel time is unavailable: no supported routing request returned one "
    "for this facility."
)

#: Maximum number of raw OSM tags echoed back per facility (bounded payload).
MAX_OSM_TAGS = 12

#: Maximum length of a single echoed OSM tag value (bounded payload).
MAX_OSM_TAG_VALUE_CHARS = 200


class FacilityStatus(str, Enum):
    """Categorical outcome of a facilities lookup."""
    OK = "ok"
    UNAVAILABLE = "unavailable"          # No data / none found (honest, not fabricated)
    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_REQUEST = "invalid_request"


def bounded_osm_tags(tags: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Return a bounded, verbatim copy of the raw OSM tags.

    The tags are echoed exactly as OpenStreetMap has them (truncated only for
    payload safety) so the UI can present them as crowd-sourced tags rather
    than as verified facts.
    """
    if not tags:
        return {}
    out: Dict[str, str] = {}
    for key, value in list(tags.items())[:MAX_OSM_TAGS]:
        if value is None:
            continue
        out[str(key)] = str(value)[:MAX_OSM_TAG_VALUE_CHARS]
    return out


@dataclass(frozen=True)
class Facility:
    """A single nearby facility. Context only — never a safety input (Rule 11)."""
    facility_id: str
    category: str
    name: str
    latitude: float
    longitude: float
    distance_m: float
    source: str
    status: str = "ok"
    #: Granular OSM value (e.g. "hospital", "clinic", "pharmacy", "hotel").
    subtype: str = ""
    #: How ``distance_m`` was measured (straight-line vs road network).
    distance_kind: str = DISTANCE_STRAIGHT_LINE
    #: Road-network distance in meters — only set when a routing provider returned it.
    road_distance_m: Optional[float] = None
    #: Road travel time in seconds — only set when a routing provider returned it.
    road_travel_time_s: Optional[float] = None
    #: Which provider produced the road distance / travel time (provenance).
    road_access_source: Optional[str] = None
    #: Raw OpenStreetMap tags, verbatim. Never a verified fact.
    osm_tags: Dict[str, str] = field(default_factory=dict)
    #: Always False for crowd-sourced OSM data (Rule 20).
    attributes_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facility_id": self.facility_id,
            "category": self.category,
            "subtype": self.subtype,
            "name": self.name,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "distance_m": round(float(self.distance_m), 1),
            "distance_kind": self.distance_kind,
            "road_distance_m": (
                round(float(self.road_distance_m), 1)
                if self.road_distance_m is not None else None
            ),
            "road_travel_time_s": (
                round(float(self.road_travel_time_s), 1)
                if self.road_travel_time_s is not None else None
            ),
            "road_access_source": self.road_access_source,
            "source": self.source,
            "status": self.status,
            "osm_tags": dict(self.osm_tags),
            "attributes_verified": self.attributes_verified,
        }


@dataclass
class FacilityResult:
    """Standardized facilities lookup response.

    Provenance (provider, timestamp, radius, categories) is always recorded so
    every facility claim is auditable (Rule 17, Rule 20). Absence of facilities
    is reported as an explicit status, never invented (Rule 20).
    """
    status: FacilityStatus
    provider: str
    facilities: List[Facility] = field(default_factory=list)
    categories_requested: List[str] = field(default_factory=list)
    radius_m: float = 0.0
    origin_latitude: float = 0.0
    origin_longitude: float = 0.0
    retrieved_at: str = ""
    limitations: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    #: How the reported distances were measured (straight-line by default).
    distance_basis: str = DISTANCE_STRAIGHT_LINE
    #: Human-readable statement of the distance basis.
    distance_note: str = ""
    #: True only when at least one facility carries a real road travel time.
    road_access_available: bool = False
    #: Why road travel time is (or is not) available.
    road_access_note: str = ""
    #: Standing wording for the OpenStreetMap attributes.
    attributes_note: str = OSM_ATTRIBUTES_NOTE
    #: Attribution for the underlying data source (e.g. ODbL for OpenStreetMap).
    source_attribution: str = ""
    #: Short, human-readable, honest notes for the UI.
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "provider": self.provider,
            "facilities_count": len(self.facilities),
            "facilities": [f.to_dict() for f in self.facilities],
            "categories_requested": list(self.categories_requested),
            "radius_m": round(float(self.radius_m), 1),
            "origin": {
                "latitude": round(float(self.origin_latitude), 6),
                "longitude": round(float(self.origin_longitude), 6),
            },
            "retrieved_at": self.retrieved_at,
            "limitations": list(self.limitations),
            "error_message": self.error_message,
            "distance_basis": self.distance_basis,
            "distance_note": self.distance_note,
            "road_access_available": self.road_access_available,
            "road_access_note": self.road_access_note,
            "attributes_note": self.attributes_note,
            "source_attribution": self.source_attribution,
            "notes": list(self.notes),
        }
