# SafeRoute AI — Permitted Imagery Acquisition Module (`src.imagery`)

> **Module Version:** `imagery-v1`  
> **Primary Sources:** `workspace_dashcam_v1` (CC-BY 4.0), `mapillary` (CC-BY-SA 4.0)  
> **Phase ID:** PHASE_14  
> **Governing Documents:** [`../../master_rules.md`](../../master_rules.md) (Rules 1, 8, 9, 14, 19), TRD §10, ARCHITECTURE §8.

---

## 1. Overview

The `src.imagery` module manages the retrieval, validation, provenance tracking, and spatial matching of road imagery to route segments. It operates under strict legal and ethical guardrails to guarantee that only authorized, open-licensed imagery is ingested into the computer vision assessment pipeline.

### Core Invariants & Guardrails:
1. **Rule 8 (Permitted Sources Only):** The adapter enforces a strict registry of allowed sources. It forbids ingesting images from unauthorized, proprietary, or terms-violating endpoints (such as Google Street View scraping).
2. **Routing Provider Separation (Rule 8):** The routing provider (OSRM/OSM) terms do **not** grant or imply rights to download street-level imagery.
3. **Rule 9 (Evidence Honesty):** Missing, stale, or unmatched imagery yields an explicit `ImageryUnavailable` result. **Unavailable imagery is NEVER treated as safe road evidence.**
4. **Workspace Isolation (Rule 1):** All cached or stored imagery resides strictly within the workspace directory (`data/imagery/`).

---

## 2. Permitted Sources Registry

Configured in [`config/imagery.yaml`](../../config/imagery.yaml):

| Source Identifier | License | Status | Permitted Uses | Attribution Required |
|---|---|:---:|---|:---:|
| `workspace_dashcam_v1` | **CC-BY 4.0** | **ENABLED** | Local storage, computer vision model inference, evaluation. | Yes (Roboflow Universe) |
| `mapillary` | **CC-BY-SA 4.0** | **ENABLED** | Open street-level imagery via public Graph API. | Yes (Mapillary) |
| `google_street_view` | Commercial Proprietary | **BLOCKED** | Prohibited under Terms §3.2.3 (no automated downloading/offline ML). | N/A |

---

## 3. Spatial Matching & Buffer Specification

- **Algorithm:** Minimum geodesic distance calculation between candidate imagery coordinates `(lon, lat)` and segment LineString vertices using Haversine formula.
- **Search Radius:** Default $25.0\text{ meters}$.
- **Accuracy Limits & Documented Assumptions:**
  - Mobile dashcams typically experience $\pm 5-15\text{ m}$ GPS position drift.
  - Images beyond the 25m buffer are strictly classified as `UNMATCHED`.
  - Camera azimuth/heading is not guaranteed to align with vehicle travel direction.

---

## 4. Timeliness & Staleness Policy (Rule 9)

- **Freshness Window:** 180 days (6 months).
- **Staleness Handling:**
  - Images older than 180 days are flagged with `is_stale = True` and status `stale`.
  - A mandatory limitation disclosure is attached: *"Imagery is stale (> 180 days old); condition may not reflect current road state."*

---

## 5. Usage Example

```python
from src.imagery import PermittedImageryAdapter
from src.routing.schemas import RouteSegment, Coordinate, RouteGeometry

# 1. Initialize adapter
adapter = PermittedImageryAdapter()

# 2. Define route segment
segment = RouteSegment(
    segment_id="seg-rt01-0000",
    route_id="rt01",
    sequence=0,
    length_m=200.0,
    duration_s=15.0,
    start_coord=Coordinate(latitude=12.9716, longitude=77.5946),
    end_coord=Coordinate(latitude=12.9726, longitude=77.5956),
    geometry=RouteGeometry(coordinates=[(77.5946, 12.9716), (77.5956, 12.9726)]),
)

# 3. Retrieve permitted imagery
result = adapter.get_imagery_for_segment(segment, permitted_source="workspace_dashcam_v1")

if result.is_available:
    print(f"Acquired {len(result.images)} images under {result.licence}")
    for img in result.images:
        print(f"  Frame {img.image_id}: {img.file_path} (stale={img.is_stale})")
else:
    print(f"Imagery unavailable: {result.unavailable_detail.message}")
    # Downstream hazard aggregator will mark this segment as UNASSESSED (Rule 9)
```
