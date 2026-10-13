# SafeRoute AI — Provider-Independent Routing Module (`src.routing`)

> **Module Version:** `routing-v1`  
> **Primary Live Provider:** `osrm` (Open Source Routing Machine / OpenStreetMap)  
> **Mock / Test Provider:** `mock_routing` (Deterministic fixtures)  
> **Phase ID:** PHASE_13  
> **Governing Documents:** [`../../master_rules.md`](../../master_rules.md) (Rules 8, 10, 13, 14, 17), TRD §10, ARCHITECTURE §8.

---

## 1. Overview

The `src.routing` package provides a strictly decoupled, provider-independent routing adapter architecture. Upstream consumers (safety analysis, risk scoring, backend API) interact exclusively with abstract interfaces (`RoutingProvider`), insulating the system from specific vendor implementations.

### Invariants & Guardrails:
1. **Rule 10 (Routing Honesty):** Returns **only** the routes actually returned by the provider. The adapter strictly forbids synthesizing or padding routes to a fixed count. Fewer than four routes is an honest, valid result.
2. **Rule 8 (Imagery Guardrail):** The routing provider's API terms do **not** grant or imply rights to extract street-level imagery. Street imagery is strictly handled in Phase 14 via dedicated permitted sources.
3. **Rule 13 (Secrets Management):** Provider credentials (if any) are never stored in source code and are loaded exclusively from local, uncommitted `.env`.
4. **Stable Segment Identifiers (FR-R4):** Routes are decomposed into assessable units with deterministic identifiers matching `seg-{route_id}-{seq:04d}`.

---

## 2. Provider Evaluation & Decision Record

| Candidate Provider | License & Terms | Cost | Rate Limits | Imagery Rights | Selected? |
|---|---|:---:|:---:|:---:|:---:|
| **OSRM / OpenStreetMap** | Open Database License (ODbL) / BSD | **$0** (Free, Open Source) | Generous (Demo) / Unlimited (Self-hosted) | **None** (Guardrail noted) | **YES (Primary Live)** |
| **Recorded Mock Provider** | Internal MIT | **$0** | Unlimited (Offline) | N/A | **YES (Test / CI)** |
| **Mapbox Directions** | Proprietary | Paid tier ($0.50/1k) | 300 req/min | None | No (Vendor lock-in) |
| **Google Maps Directions** | Proprietary ToS §3.2.4 | Paid ($5.00/1k) | Quota-based | Strict prohibition on imagery extraction | No (Prohibits caching/storage) |

**Decision:** OSRM selected for live routing queries; `MockRoutingAdapter` selected for 100% reproducible, offline unit tests.

---

## 3. Interfaces & Data Contracts

```python
class RoutingProvider(ABC):
    @abstractmethod
    def get_routes(self, request: RouteRequest) -> RouteResponse: ...

    @abstractmethod
    def get_route_geometry(self, route_id: str) -> Optional[RouteGeometry]: ...

    @abstractmethod
    def get_segment_metadata(self, route_id: str) -> List[RouteSegment]: ...
```

### Stable Segment Scheme:
- Pattern: `seg-{route_id}-{sequence:04d}`
- Example: `seg-route_mock_alpha-0000`, `seg-route_mock_alpha-0001`
- Includes Haversine geodesic length ($L_i$ in meters), coordinates, and maneuver instructions.

---

## 4. Edge Case Handling

| Situation | Adapter Behavior | Limitation Code |
|---|---|---|
| Provider returns $< 4$ routes | Returns exactly those returned | `fewer_than_four_routes_returned` |
| Zero routes found | Returns empty list, status `NO_ROUTES_FOUND` | `zero_routes_returned` |
| Request timeout | Bounded retries (3) with exponential backoff; surfaces `PROVIDER_TIMEOUT` | `routing_request_timed_out_after_max_retries` |
| Provider error (5xx) | Bounded retries (3); surfaces `PROVIDER_ERROR` | `routing_provider_service_unreachable` |
| Rate limited (429) | Immediate backoff; surfaces `RATE_LIMITED` | `rate_limit_exceeded` |

---

## 5. Usage Example

```python
from src.routing import (
    Coordinate,
    RouteRequest,
    create_routing_adapter,
)

# Initialize adapter (mock or OSRM)
adapter = create_routing_adapter(provider_type="mock")

# Search routes
request = RouteRequest(
    origin=Coordinate(latitude=12.9716, longitude=77.5946),      # Bangalore Central
    destination=Coordinate(latitude=12.9352, longitude=77.6245), # Koramangala
    alternatives=True,
)

response = adapter.get_routes(request)
print(f"Status: {response.status.value}, Routes found: {len(response.routes)}")

for route in response.routes:
    print(f"Route: {route.summary} ({route.distance_m:.0f}m, {len(route.segments)} segments)")
    first_seg = route.segments[0]
    print(f"  First segment ID: {first_seg.segment_id} ({first_seg.length_m:.1f}m)")
```
