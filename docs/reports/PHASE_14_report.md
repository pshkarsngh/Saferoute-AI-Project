# PHASE_14 — Imagery Adapter Report

=================================
**Date (actual):** 2026-10-13  
**Phase ID:** PHASE_14  
**Governing Documents:** TRD §10, ARCHITECTURE §8, master_rules.md Rules 1, 8, 9, 14, 19  

---

## 1. Permitted Source Selection & Guardrail (Rule 8)

- **Permitted Sources Approved:**
  - `workspace_dashcam_v1`: Curated workspace dashcam archive (`data/pothole_crack_manhole/` & `logs/evaluation/qualitative_samples/`) under **Creative Commons Attribution 4.0 International (CC-BY 4.0)** from Roboflow Universe.
  - `mapillary`: Open street-level imagery platform under **Creative Commons Attribution-ShareAlike 4.0 International (CC-BY-SA 4.0)**.
- **Licence & Permitted Uses:**
  - Both licences explicitly permit computer vision processing, feature extraction, model inference, and local cached storage with attribution.
- **Attribution Required:** Yes (Attribution to Roboflow Universe and Mapillary included in metadata).
- **Disallowed Sources (Strictly Rejected):**
  - `google_street_view`: Prohibited under Google Maps Platform Terms of Service §3.2.3 (forbids scraping, automated downloading, and offline model ingestion). Rejected and disabled in config.
- **Guardrail Noted (Rule 8):** **YES.** Routing providers (OSRM/OSM/Mapbox) do **NOT** grant street-level imagery rights. Imagery acquisition is strictly decoupled and handled exclusively via approved permitted sources.

---

## 2. Interface Implemented

Implemented abstract interface `ImageryProvider` in [`src/imagery/interfaces.py`](file:///d:/New%20folder%20(3)/src/imagery/interfaces.py) with concrete adapter in [`src/imagery/adapter.py`](file:///d:/New%20folder%20(3)/src/imagery/adapter.py):
- `get_imagery_for_segment(segment: RouteSegment, permitted_source: Optional[str] = None) -> ImageryResult`
- Returns structured `ImageryResult` containing `List[ImageRef]` when available, or `ImageryUnavailable` with explicit categorical reason (`missing`, `stale`, `inaccessible`, `disallowed_source`, `unmatched`).

---

## 3. Provenance Record Contract

Every acquired frame records full provenance matching TRD §10.1 & ARCHITECTURE §8:
- `image_id`: Unique image frame identifier.
- `file_path`: Workspace-local file path.
- `source`: Registered source name (`workspace_dashcam_v1` or `mapillary`).
- `licence`: Applicable open license string (`CC-BY 4.0` or `CC-BY-SA 4.0`).
- `captured_at`: ISO-8601 capture timestamp.
- `retrieved_at`: ISO-8601 acquisition timestamp.
- `coordinates`: Geographic `(lon, lat)` where frame was captured.
- `distance_to_segment_m`: Geodesic offset from segment line.
- `is_stale`: Boolean timeliness flag.
- `status`: Categorical status (`available` or `stale`).

---

## 4. Staleness & Timeliness Policy (Rule 9)

- **Definition:** Standard freshness window is **180 days** (6 months).
- **Flagged Behaviour:**
  - Capture timestamps older than 180 days set `is_stale = True` and status `stale`.
  - A mandatory disclosure is attached to limitations: *"Imagery is stale (> 180 days old); condition may not reflect current road state."*
  - Stale evidence is never misrepresented as current (Rule 9).

---

## 5. Segment Matching

- **Method:** Minimum Haversine geodesic distance from candidate image coordinate to the segment LineString vertices.
- **Search Buffer:** $25.0\text{ meters}$ radius buffer along the segment.
- **Accuracy Limits:**
  - Dashcam GPS drift of $\pm 5-15\text{ m}$ is accommodated by the 25m buffer.
  - Camera azimuth/heading is noted as uncalibrated.
- **Unmatched Behaviour:** Candidates outside 25m are excluded. Segments with no candidate frames within 25m return `ImageryStatus.UNMATCHED` $\to$ downstream hazard aggregator receives 0 images and marks segment as `UNASSESSED` (Rule 9).

---

## 6. Workspace Storage (Rule 1)

- **Storage Path:** [`data/imagery/`](file:///d:/New%20folder%20(3)/data/imagery/)
- **Workspace Isolation:** Confirmed. All stored imagery and image paths reside strictly within `D:\New folder (3)`.

---

## 7. Test Results (Empirical & Reproducible)

- **Edge Cases Tested & Observed:**
  - *Available:* Matched within 25m buffer $\to$ returns `ImageRef` with CC-BY 4.0 licence, distance $< 5\text{m}$, unflagged fresh status.
  - *Disallowed:* Requesting `google_street_view` $\to$ returns `DISALLOWED_SOURCE`, `ImageryUnavailable`, and disclosure limitation.
  - *Unmatched:* Querying segment far outside buffer (e.g. London coordinates) $\to$ returns `UNMATCHED`, `ImageryUnavailable`, and `missing_imagery_not_safe`.
  - *Stale:* Timestamps $> 180$ days $\to$ `is_stale = True`, limitation note attached.
  - *Workspace isolation:* Confirmed storage directory path starts with workspace root.
- **Test Command:** `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
- **Passed / Total:** **67 / 67 passed (100%) in 11.35s** (including 8 dedicated `test_imagery_adapter.py` tests).

---

## 8. Validation Checklist

| # | Check | Status | Empirical Evidence |
|---|---|:---:|---|
| V1 | Source permitted | PASS | `workspace_dashcam_v1` (CC-BY 4.0) and `mapillary` (CC-BY-SA 4.0) documented and verified. |
| V2 | No forbidden source | PASS | `google_street_view` and unauthorized sources strictly rejected (`test_rule_8_rejection_of_disallowed_source_query`). |
| V3 | Provenance recorded | PASS | `image_id`, `path`, `source`, `licence`, `captured_at`, `retrieved_at` emitted in `ImageRef`. |
| V4 | Staleness flagged | PASS | Imagery $> 180$ days flagged as stale in `test_staleness_evaluator_flagging`. |
| V5 | Unavailable handled | PASS | Missing, stale, and unmatched return explicit `ImageryUnavailable` (`test_rule_9_unmatched_segment_yields_unavailable`). |
| V6 | Matching documented | PASS | 25m buffer proximity matching implemented in `SegmentImageryMatcher` and tested. |
| V7 | No fabrication | PASS | Adapter never invents image references. |
| V8 | Workspace storage | PASS | Verified in `test_workspace_isolation_storage_path`. |
| V9 | Tests pass | PASS | 67/67 unit and integration tests passing. |

---

## 9. Limitations & Honesty Note

1. **Absence is NOT Safety (Rule 9):** Unmatched, missing, or corrupt imagery produces an explicit `unassessed` status in the risk engine. The system never claims or implies that an unobserved road segment is hazard-free or safe.
2. **Camera Perspective:** Dashcam and street-level imagery provides forward-facing monocular viewpoints. Pavement hidden behind preceding vehicles or outside the field of view remains unobserved and is acknowledged as an operational limitation.

---

## 10. Result & Next Phase

- **Result:** **COMPLETE**
- **Next Phase:** **PHASE_15 — Facilities Lookup Service**
- **Status:** Complete; awaiting user authorization for Phase 15.
