# 02 — Architecture and Data Flow

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21 · **Read-only analysis**
> **Related:** [`00-executive-summary.md`](00-executive-summary.md) ·
> [`01-repository-map.md`](01-repository-map.md) ·
> [`07-api-database-and-integrations.md`](07-api-database-and-integrations.md)

Every diagram below reflects the **actual implementation**. Node labels quote the real
module, class or function that performs the step. Where the implemented architecture
differs from `docs/ARCHITECTURE.md`, the implemented behaviour is shown and the divergence
is recorded as Finding **F-02**.

---

## 1. Architectural principles actually enforced in code

| Principle | Rule | Enforcement point |
|---|---|---|
| The backend is the **sole** owner of safety scores | 7 | `src/risk/engine.py` `DeterministicRiskEngine`; the frontend contains no score computation on any live path (`src/utils/safety.ts` is dead — F-07). |
| The LLM may only **explain** verified results | 12 | `src/llm/explainer.py` `GroundedExplanationService`; the prompt carries only verified backend records, and the reply is schema-validated and entity-grounded before use. |
| Facilities are **context only** | 11 | `config/facilities.yaml` `guardrails.facilities_in_hazard_score: false`; `src/facilities/schemas.py` has no score/risk field; `src/risk/*` never imports `src/facilities/*`. |
| Missing evidence is **unassessed**, never "safe" | 9 | `src/risk/engine.py` coverage suppression + `unassessed_score_placeholder: null` in `config/risk_engine.yaml`; `src/imagery/staleness.py` treats an unknown capture time as stale. |
| Only routes the provider **actually returned** are shown | 10 | `config/routing.yaml` `guardrails.enforce_rule_10: true`; `MockRoutingAdapter` marks synthetic routes as demo. |
| Only **permitted** imagery | 8 | `config/imagery.yaml` `sources` registry; `google_street_view` is explicitly `enabled: false` with a ToS reason. |
| Everything stays **inside the workspace** | 1 | `src/config/env.py` `WORKSPACE_ROOT`; `src/api/app.py` `_serve_static` resolves and rejects paths outside the static root. |

## 2. System context — component architecture

```mermaid
flowchart TD
    U["User in browser"] --> FE["React SPA<br/>frontend/Frontend/project frontend/src"]
    FE -->|"POST /api/analyze<br/>POST /api/routes"| API["SafeRoute API<br/>src/api/app.py<br/>http.server ThreadingHTTPServer"]
    API --> PIPE["SafetyAnalysisPipeline<br/>src/api/pipeline.py"]
    API --> STATIC["Static SPA serving<br/>_Handler._serve_static"]
    API --> DB[("SQLite<br/>data/saferoute.db<br/>src/api/store.py")]

    BOOT["bootstrap.py<br/>src/api/bootstrap.py"] -.->|"constructs live providers"| PIPE
    SET["Settings<br/>src/config/settings.py<br/>config/app.yaml + .env"] -.-> BOOT

    PIPE --> RT["OSRMRoutingAdapter<br/>src/routing/osrm_adapter.py"]
    PIPE --> IMG["PermittedImageryAdapter<br/>src/imagery/adapter.py"]
    PIPE --> DET["HazardDetector<br/>src/detection/detector.py"]
    PIPE --> AGG["HazardAggregator<br/>src/risk/aggregate.py"]
    PIPE --> RISK["DeterministicRiskEngine<br/>src/risk/engine.py"]
    PIPE --> CMP["RouteComparer<br/>src/risk/comparison.py"]
    PIPE --> LLM["GroundedExplanationService<br/>src/llm/explainer.py"]
    PIPE --> FAC["FacilitiesService<br/>src/facilities/service.py"]

    RT --> OSRM[("router.project-osrm.org")]
    IMG --> MAP[("graph.mapillary.com")]
    FAC --> OVR[("Overpass mirrors<br/>3 endpoints")]
    LLM --> OLL[("Ollama<br/>127.0.0.1:11434")]
    DET --> CKPT[("saferoute-yolo11-v2<br/>best.pt")]
    AGG --> RISK
    RISK --> CMP
    CMP --> LLM
    CMP --> DB
    LLM --> API

    classDef ext fill:#e6f0ff,stroke:#1a4f9c,color:#000
    classDef own fill:#e9f7ef,stroke:#1d7a45,color:#000
    classDef store fill:#fff3d6,stroke:#a67c00,color:#000
    class OSRM,MAP,OVR,OLL ext
    class CKPT store
    class DB store
```

**Note on the facilities path.** `FacilitiesService` is reached from the API's
`POST /api/facilities` handler and is **not** part of the analysis pipeline's scoring
path. The arrow `PIPE --> FAC` in the diagram reflects that `SafetyAnalysisPipeline`
holds a facilities handle for the corridor lookup; it does **not** feed the risk engine —
see §4.

## 3. Backend module dependency graph

Arrows point from importer to imported module. Derived from the `import` statements in
`src/**`.

```mermaid
graph TD
    api_app["api/app.py"] --> api_pipeline["api/pipeline.py"]
    api_app --> api_store["api/store.py"]
    api_app --> cfg_settings["src/config/settings.py"]
    api_app --> src_config["src/config/__init__.py"]

    api_pipeline --> cfg_thresholds["src/config/thresholds.py"]
    api_pipeline --> fac_service["facilities/service.py"]
    api_pipeline --> img_adapter["imagery/adapter.py"]
    api_pipeline --> llm_explainer["llm/explainer.py"]
    api_pipeline --> risk_aggregate["risk/aggregate.py"]
    api_pipeline --> risk_comparison["risk/comparison.py"]
    api_pipeline --> risk_engine["risk/engine.py"]
    api_pipeline --> risk_schemas["risk/schemas.py"]
    api_pipeline --> routing_adapter["routing/adapter.py"]

    api_bootstrap["api/bootstrap.py"] --> api_pipeline
    api_bootstrap --> fac_service
    api_bootstrap --> geo_factory["geocoding/factory.py"]
    api_bootstrap --> img_adapter
    api_bootstrap --> img_mapillary["imagery/mapillary_provider.py"]
    api_bootstrap --> llm_explainer

    fac_service --> fac_geometry["facilities/geometry.py"]
    fac_service --> fac_interfaces["facilities/interfaces.py"]
    fac_service --> fac_overpass["facilities/overpass_provider.py"]
    fac_service --> fac_mock["facilities/mock_provider.py"]
    fac_service --> fac_schemas["facilities/schemas.py"]

    img_adapter --> img_matcher["imagery/matcher.py"]
    img_adapter --> img_staleness["imagery/staleness.py"]
    img_adapter --> img_schemas["imagery/schemas.py"]
    img_mapillary --> img_schemas

    det_detector["detection/detector.py"] --> pre_pipeline["preprocessing/pipeline.py"]
    det_detector --> det_schemas["detection/schemas.py"]

    risk_engine --> risk_aggregate
    risk_engine --> risk_schemas
    risk_aggregate --> risk_severity["risk/severity.py"]
    risk_aggregate --> det_schemas
    risk_comparison --> risk_schemas

    routing_adapter --> routing_osrm["routing/osrm_adapter.py"]
    routing_adapter --> routing_mock["routing/mock_adapter.py"]
    routing_adapter --> routing_seg["routing/segmentation.py"]
    routing_osrm --> routing_seg
    routing_osrm --> routing_schemas["routing/schemas.py"]

    img_matcher --> routing_seg
    img_matcher --> routing_schemas

    classDef warn fill:#ffe9b3,stroke:#a67c00,color:#000
    class risk_engine,llm_explainer warn
```

Two properties of this graph matter for Rule 7 and Rule 11:

1. **No path from `src/facilities/**` into `src/risk/**`.** The facilities package is
   imported by `api/pipeline.py` and `api/bootstrap.py` only. The risk engine cannot see
   a facility even by accident.
2. **No path from `src/llm/**` into `src/risk/**` or `src/detection/**`.** The LLM
   package depends on nothing upstream; it consumes already-computed results. The
   dependency arrow points *into* the explainer, not out of it.

## 4. Analysis data flow — one `POST /api/analyze`

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend<br/>useSafeRoute.ts
    participant API as SafeRouteAPI.analyze
    participant PIPE as SafetyAnalysisPipeline
    participant RT as OSRMRoutingAdapter
    participant IMG as PermittedImageryAdapter
    participant DET as HazardDetector
    participant AGG as HazardAggregator
    participant RISK as DeterministicRiskEngine
    participant CMP as RouteComparer
    participant LLM as GroundedExplanationService
    participant ST as AnalysisStore

    FE->>API: POST /api/analyze {origin, destination, route_ids?}
    API->>PIPE: analyse(request)
    PIPE->>RT: get_routes(origin, destination, alternatives=true)
    RT-->>PIPE: RouteResponse(routes actually returned)
    Note over RT: Rule 10 - routes are never padded or synthesised
    RT->>RT: RouteSegmenter.segment(<br/>target 200 m, 50-500 m bounds)

    par Parallel imagery prefetch across segments
        PIPE->>IMG: get_imagery(segment)
        IMG->>IMG: SegmentImageryMatcher<br/>(25 m buffer)
        IMG->>IMG: StalenessEvaluator<br/>(180 days; unknown=stale)
        IMG-->>PIPE: ImageryResult(images | unavailable)
    end

    PIPE->>DET: detect(image)
    DET->>DET: PreprocessingPipeline<br/>validate - letterbox - prepare
    DET->>DET: YOLO11 predict<br/>conf 0.25, iou 0.45, imgsz 640
    DET-->>PIPE: ImageDetectionResult(detections)
    PIPE->>AGG: assess_segment(segment, detections)
    AGG->>AGG: SeverityPolicy<br/>dedup IoU 0.45
    AGG-->>PIPE: HazardRecord list
    PIPE->>RISK: score_route(segments, hazards)
    RISK->>RISK: H = severity per km<br/>S = 100 * exp(-0.10 * H)
    RISK->>RISK: coverage suppression<br/>min 0.50, full 0.90
    RISK-->>PIPE: RouteSafetyResult[]
    PIPE->>CMP: RouteComparer.build(results)
    CMP-->>PIPE: ranking + recommendation<br/>(null when evidence insufficient)
    PIPE->>LLM: explain(verified results only)
    LLM-->>PIPE: ExplanationResult<br/>(source ollama or fallback)
    PIPE->>ST: save_analysis(...)
    PIPE-->>API: analysis record
    API-->>FE: 200 {analysis_id, routes, comparison,<br/>recommendation, explanation}
```

### 4.1 The two honest-failure branches

```mermaid
flowchart LR
    IMG_OK["Imagery acquired<br/>and fresh"] --> DET_OK["Detection runs"]
    DET_OK --> AGG_OK["Hazard records"]

    IMG_MISS["No image in 25 m buffer"] --> UNASS["status = unassessed"]
    IMG_STALE["Capture date unknown or > 180 d"] --> UNASS
    IMG_401["Mapillary 401/403"] --> INACC["status = inaccessible"]
    IMG_404["Mapillary no candidates"] --> UNASS
    DET_ERR["Inference error"] --> FAILED["status = failed"]
    DET_NONE["Zero detections<br/>on a valid image"] --> CLEAN["zero hazards on<br/>the assessed part"]

    UNASS --> RISK["Risk engine:<br/>score may be null;<br/>coverage reduced"]
    INACC --> RISK
    FAILED --> RISK
    CLEAN --> RISK
    AGG_OK --> RISK

    RISK --> SUP["coverage < 0.50 =><br/>safe verdict suppressed"]
    RISK --> OK["coverage >= 0.50 =><br/>score reported with coverage"]
    SUP --> CMP["RouteComparer:<br/>no recommendation if<br/>insufficiently assessed"]
    OK --> CMP
```

The critical distinction, implemented in `src/risk/engine.py` and asserted by
`tests/unit/test_risk_engine.py` and `tests/unit/test_route_recommendation_correctness.py`:
**"zero detections on an image we successfully assessed"** and **"no image, therefore
unassessed"** produce different statuses and different coverage figures. Only the first
may contribute a low hazard value.

## 5. Facilities flow — a separate request path (Rule 11)

```mermaid
flowchart TD
    FE["Frontend<br/>src/services/facilities.ts"] -->|"POST /api/facilities<br/>{route: {polylines}}"| API["SafeRouteAPI.facilities"]
    API --> FS["FacilitiesService<br/>get_facilities_near_route"]
    FS --> GEO["geometry.py<br/>polylines_bbox +<br/>distance_to_polylines_m"]
    FS --> OP["OverpassProvider<br/>get_facilities_in_bbox"]
    OP --> Q1["category: hospital"]
    OP --> Q2["category: medical"]
    OP --> Q3["category: police"]
    OP --> Q4["category: fuel"]
    OP --> Q5["category: hotel"]
    OP --> Q6["category: restaurant"]
    Q1 --> MIR["3-mirror failover<br/>gap 0.7 s, deadline 45 s"]
    Q2 --> MIR
    Q3 --> MIR
    Q4 --> MIR
    Q5 --> MIR
    Q6 --> MIR
    MIR --> RES["FacilityResult<br/>distance_kind + subtype +<br/>osm_tags (unverified) + notes"]
    RES --> FE
    FS -.->|"road_access: only when a real<br/>routing provider returned a road route"| RA["nearest facility per category<br/>max 6 requests"]
    RA --> RES

    classDef sep fill:#fff3d6,stroke:#a67c00,color:#000
    class RES sep
```

Note the deliberate absence of any arrow from `RES` into the risk engine or the route
comparison. The facilities response is returned to the UI as a separate panel.

## 6. Frontend ↔ backend contract

```mermaid
flowchart LR
    subgraph Browser
        HOOK["useSafeRoute.ts"]
        APICL["src/lib/api.ts<br/>only fetch module"]
        TYPES["src/lib/analyzeTypes.ts"]
        ROUTES["src/utils/backendRoutes.ts"]
        PRES["src/utils/facilityPresentation.ts"]
        PAGE["src/pages/RouteResults.tsx"]
        MAP["MapLibre map"]
    end

    HOOK --> APICL
    APICL --> TYPES
    APICL --> ROUTES
    ROUTES --> PAGE
    PRES --> PAGE
    PAGE --> MAP

    APICL -->|"VITE_API_URL"| S1["/api/routes"]
    APICL -->|"VITE_API_URL"| S2["/api/analyze"]
    APICL -->|"VITE_API_URL"| S3["/api/geocode"]
    APICL -->|"VITE_API_URL"| S4["/api/facilities"]
    APICL -->|"VITE_API_URL"| S5["/api/analyze/{id}"]
    APICL -->|"VITE_API_URL"| S6["/api/analysis/{id}/comparison"]
    APICL -->|"VITE_API_URL"| S7["/api/analysis/{id}/explanation"]
    APICL -->|"VITE_API_URL"| S8["/api/health"]

    S1 --> BE["SafeRoute API"]
    S2 --> BE
    S3 --> BE
    S4 --> BE
    S5 --> BE
    S6 --> BE
    S7 --> BE
    S8 --> BE
```

The frontend performs **no** third-party network calls of its own. In particular, after
the Phase 2 change, the browser no longer queries Overpass directly — `POST /api/facilities`
is the single source of truth for facilities.

### 6.1 Client-side timeouts

Configured in `src/lib/api.ts` from `VITE_ANALYZE_TIMEOUT_MS` and defaults read from
the same module:

| Call | Timeout (ms) |
|---|---:|
| `/api/analyze` | 900 000 (15 min) |
| `/api/routes` | 60 000 |
| `/api/facilities` | 90 000 |
| `/api/geocode` | 60 000 |

Error kinds surfaced by `ApiError`: `network`, `timeout`, `http`, `invalid`, `aborted`.

## 7. ML pipeline — training (offline) versus serving (online)

```mermaid
flowchart TD
    subgraph Offline["Offline path - scripts/"]
        RAW["DATA-YOLO/<br/>raw source, licence unresolved"]
        PREP["prepare_datayolo_2class.py<br/>group-aware, 2-class, leakage-checked"]
        DER["build_derived_dataset_v2.py<br/>date-atomic split"]
        TRAIN["train_baseline.py<br/>Ultralytics YOLO11n"]
        EVAL["evaluate_baseline.py"]
        REC["logs/evaluation/<br/>evaluation_record.json"]
        RAW --> PREP --> DER --> TRAIN --> EVAL --> REC
    end

    subgraph Online["Online path - src/"]
        ACQ["Mapillary frames"] --> PRE["PreprocessingPipeline<br/>preprocess-v1"]
        PRE --> INF["HazardDetector<br/>detect-v2"]
        INF --> SEV["SeverityPolicy<br/>severity-v1"]
        SEV --> RK["DeterministicRiskEngine<br/>risk-v1"]
    end

    CKPT["models/training/<br/>saferoute-yolo11-v2/weights/best.pt"]
    TRAIN --> CKPT
    CKPT --> INF
    DETCFG["config/detection.yaml<br/>imgsz 640, conf 0.25, iou 0.45"] -.-> INF
    SEVCFG["config/hazard_severity.yaml<br/>threshold 0.25"] -.-> SEV
    RKCFG["config/risk_engine.yaml<br/>lambda 0.10, coverage 0.50/0.90"] -.-> RK
```

The inference path shares the same `PreprocessingPipeline` module used for validation and
visualisation, satisfying Rule 6's "consistent, documented preprocessing" requirement.
The training path uses Ultralytics' own augmentation pipeline; this is a **documented
divergence**, not an unnoticed one, and is discussed in
[`05-preprocessing-and-feature-engineering.md`](05-preprocessing-and-feature-engineering.md) §5.

## 8. Runtime and deployment topology (as implemented)

```mermaid
flowchart LR
    subgraph Host["Single Windows host"]
        subgraph Proc1["Process A - scripts/run_app.py"]
            SRV["SafeRoute API<br/>ThreadingHTTPServer<br/>127.0.0.1:8000"]
        end
        subgraph Proc2["Process B - vite preview (dev)"]
            VITE["Vite preview server<br/>127.0.0.1:8123<br/>serves frontend/Frontend/project frontend/dist"]
        end
        subgraph Proc3["Process C - Ollama"]
            OL["Ollama 0.40.6<br/>127.0.0.1:11434<br/>model llama3:latest"]
        end
        VENV[".venv<br/>Python 3.12.10"]
        DBD[("data/saferoute.db")]
        VENV --> SRV
        VENV --> VITE
        SRV --> DBD
    end

    SRV --> OSRM[("router.project-osrm.org")]
    SRV --> MAP[("graph.mapillary.com")]
    SRV --> OVR[("overpass-api.de + 2 mirrors")]
    SRV -->|"localhost"| OL
    BROWSER["Browser"] --> VITE
    BROWSER -->|"direct /api calls"| SRV
```

In the documented single-command mode (`scripts/run_app.py`), the API process also serves
the prebuilt `frontend/` directory, so one process covers API + UI. The two-process split
above is the configuration used for the Phase 2 browser verification (Vite preview on
8123, API on 8000).

## 9. State and configuration flow

```mermaid
flowchart TD
    ENV[".env<br/>gitignored, secrets only"] --> ES["src/config/env.py<br/>load_env, get_env"]
    APPY["config/app.yaml<br/>non-secret provider policy"] --> SS["src/config/settings.py<br/>Settings dataclass"]
    ES --> SS
    SS --> BOOT["src/api/bootstrap.py<br/>provider construction"]
    SS --> API["src/api/app.py<br/>health, config summary"]

    C1["config/detection.yaml"] --> TH["src/config/thresholds.py<br/>assert_threshold_consistency"]
    C2["config/hazard_severity.yaml"] --> TH
    TH -->|"raises on divergence"| BOOT

    C3["config/risk_engine.yaml"] --> HASH["compute_config_hash()<br/>SHA-256 of the file"]
    HASH --> DB[("scores.config_hash<br/>analyses.config_hash")]

    C4["config/routing.yaml"] --> RT["routing/adapter.py"]
    C5["config/imagery.yaml"] --> IMG["imagery/adapter.py"]
    C6["config/facilities.yaml"] --> FS["facilities/service.py"]
    C7["config/geocoding.yaml"] --> GF["geocoding/factory.py"]
    C8["config/app.yaml<br/>app.llm section"] --> LL["llm/explainer.py"]
```

`Settings.to_safe_dict()` is the only method that exposes configuration outward, and it
**never emits secrets** — `/api/config` returns a capability summary only.

## 10. Persistence flow

```mermaid
flowchart LR
    PIPE["SafetyAnalysisPipeline"] --> SAVE["AnalysisStore.save_analysis"]
    SAVE --> T1[("analyses<br/>result_json")]
    SAVE --> T2[("scores<br/>route_score, coverage_fraction")]
    SAVE --> T3[("hazard_detections<br/>class, confidence, severity, bbox")]
    SAVE --> T4[("searches<br/>origin, destination, provider")]
    SAVE --> T5[("model_versions<br/>checkpoint_path, metrics_json")]
    T1 --> READ["get_analysis"]
    READ --> ENDPOINTS["GET /api/analyze/{id}<br/>/analysis/{id}/hazards<br/>/comparison<br/>/explanation"]
```

`save_analysis` is idempotent for `analyses`, `searches` and `scores`
(`INSERT OR REPLACE`), and explicitly deletes prior `hazard_detections` rows for the
analysis before re-inserting, so repeated saves do not duplicate detections.

---

*Diagram source: the `src/**` import graph, the `src/api/app.py` handler dispatch table,
`src/api/pipeline.py` orchestration order, `src/api/store.py` `_SCHEMA`, and the frontend
`src/lib/api.ts` call sites. Every function name quoted above exists in the repository at
the paths shown.*
