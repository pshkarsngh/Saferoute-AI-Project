# SafeRoute AI — Facilities Lookup Service (`src.facilities`)

> **Module Version:** `facilities-v1`
> **Phase ID:** PHASE_15
> **Live Provider:** OpenStreetMap Overpass API (ODbL, $0, no key) — used only on demand
> **Offline/Test Provider:** `mock_facilities` (deterministic fixtures)
> **Governing rules:** master_rules.md Rule 11 (separation), 13 (secrets), 14 (testing), 20 (honesty)

---

## 1. Purpose

Provide **nearby facilities** (hospitals, pharmacies, police stations, petrol pumps,
hotels, restaurants) as **context only**. Facilities are **never** an input to the
deterministic hazard score or route ranking (Rule 11).

## 2. Interface

```python
class FacilitiesProvider(ABC):
    @property
    def provider_name(self) -> str: ...
    def get_nearby_facilities(latitude, longitude, radius_m=None, categories=None) -> FacilityResult: ...
```

`FacilitiesService` wraps a provider and applies configured radius/category defaults.

## 3. Record contract

Each facility carries: `facility_id, category, name, latitude, longitude, distance_m,
source, status`. `FacilityResult` records provenance: `provider, categories_requested,
radius_m, origin, retrieved_at, limitations, error_message`.

## 4. Status handling (Rule 20)

| Status | Meaning |
|---|---|
| `ok` | Facilities found and returned. |
| `unavailable` | None found / no data — reported honestly, never fabricated. |
| `provider_error` | Upstream failure (bounded retries with backoff). |
| `provider_timeout` | Request timed out. |
| `rate_limited` | Provider rate limit (e.g. HTTP 429). |
| `invalid_request` | Invalid coordinates/params. |

## 5. Rule 11 guardrail (enforced & tested)

- The risk engine's inputs never include facility data.
- `tests/unit/test_facilities_service.py::TestFacilitiesSeparationGuardrail` proves the
  route score is byte-identical with and without a facilities lookup, and that the
  facility payload contains no score/severity fields.

## 6. Usage

```python
from src.facilities.service import FacilitiesService
svc = FacilitiesService()                      # default provider from config (mock)
res = svc.get_nearby_facilities(12.9716, 77.5946, radius_m=1000, categories=["hospital"])
print(res.status.value, len(res.facilities))
```

## 7. Configuration

`config/facilities.yaml` — providers, categories/OSM tags, search limits, and the
`guardrails.facilities_in_hazard_score: false` invariant (must never be changed without an
approved requirements change, Rule 11). Any credentials would load only from `.env` (Rule 13).

## 8. Limitations

- Overpass data completeness/recency depends on OpenStreetMap contributors.
- Distances are straight-line (Haversine), not road-network distances.
- Facilities are context; they do not imply a road is safer or riskier.
