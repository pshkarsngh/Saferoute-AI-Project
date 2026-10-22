"""SafeRoute AI — stdlib HTTP API server.

Implements the TRD §11 endpoints without third-party web frameworks (FastAPI is
not installed and installing it is gated by Rule 19). Uses http.server + sqlite3
from the standard library so the API runs with zero new dependencies.

Endpoints:
    GET  /api/health
    GET  /api/config          (non-secret provider/capability summary)
    POST /api/geocode         (place name -> coordinates; keyless Nominatim)
    POST /api/routes
    POST /api/analyze
    GET  /api/analyze/{id}
    GET  /api/analysis/{id}/hazards
    GET  /api/analysis/{id}/comparison
    GET  /api/analysis/{id}/explanation
    POST /api/facilities
    GET  /                    (serves the frontend/)

The server also statically serves the workspace `frontend/` directory so the UI
and API run from a single process (real-life single-command startup).
"""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.api.bootstrap import build_geocoder, build_pipeline
from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.config import Settings, load_settings
from src.geocoding.interfaces import GeocodingProvider
from src.routing.schemas import Coordinate

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def _parse_coord(value: Any) -> Optional[Coordinate]:
    if isinstance(value, dict) and "latitude" in value and "longitude" in value:
        return Coordinate(latitude=float(value["latitude"]), longitude=float(value["longitude"]))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return Coordinate(latitude=float(value[0]), longitude=float(value[1]))
    return None


def _error(code: str, message: str, detail: str = "") -> Dict[str, Any]:
    return {"status": "failed", "error": {"code": code, "message": message, "detail": detail}}


class SafeRouteAPI:
    """Request router holding the pipeline, geocoder and persistence store."""

    def __init__(
        self,
        pipeline: Optional[SafetyAnalysisPipeline] = None,
        store: Optional[AnalysisStore] = None,
        settings: Optional[Settings] = None,
        geocoder: Optional[GeocodingProvider] = None,
    ):
        self.settings = settings or load_settings()
        self.pipeline = pipeline or build_pipeline(self.settings)
        self.store = store or AnalysisStore()
        self.geocoder = geocoder if geocoder is not None else build_geocoder(self.settings)

    # ------------------------------------------------------------------ #
    def health(self) -> Tuple[int, Dict[str, Any]]:
        return 200, {
            "status": "ok",
            "model_version": self.pipeline.model_version,
            "config_hash": self.pipeline.config_hash,
            "providers": {
                "routing": getattr(self.pipeline.routing, "provider_name", "unknown"),
                "imagery": getattr(self.pipeline.imagery, "provider_name", "unknown"),
                "facilities": getattr(self.pipeline.facilities.provider, "provider_name", "unknown"),
                "geocoding": getattr(self.geocoder, "provider_name", None) if self.geocoder else None,
                "llm": "ollama" if getattr(self.pipeline.explainer, "enabled", False) else "fallback",
            },
            "capabilities": {
                "geocoding": bool(self.settings.geocoding_enabled and self.geocoder),
                "live_imagery": getattr(self.pipeline.imagery, "provider_name", "") == "mapillary",
                "live_llm": bool(getattr(self.pipeline.explainer, "enabled", False)),
            },
        }

    def config(self) -> Tuple[int, Dict[str, Any]]:
        return 200, {"status": "ok", "settings": self.settings.to_safe_dict()}

    # ------------------------------------------------------------------ #
    def _geocode_coordinate(self, query: str) -> Tuple[Optional[Coordinate], Optional[str]]:
        """Resolve a place name through the live geocoder, or report why not."""
        if self.geocoder is None:
            return None, f"Could not resolve '{query}': no geocoding provider is configured."
        try:
            result = self.geocoder.geocode(query, limit=1)
        except Exception as exc:  # noqa: BLE001 - a provider failure is reported, never hidden
            return None, f"Could not resolve '{query}': {exc}"
        if result.status.value == "ok" and result.candidates:
            best = result.candidates[0]
            return Coordinate(best.latitude, best.longitude), None
        return None, f"Could not resolve '{query}': {result.error_message or result.status.value}"

    def _resolve_location(
        self,
        payload: Dict[str, Any],
        coord_key: str,
        query_key: str,
        required: bool = True,
        prefer_live_geocode: bool = False,
    ) -> Tuple[Optional[Coordinate], Optional[str], str]:
        """Resolve a location from coordinates or a place-name query.

        Returns ``(coordinate, error, source)``. ``source`` records WHICH input
        the point came from ("geocoder" or "coordinates") so the response can
        disclose it instead of silently swapping one for the other (Rule 9).

        When ``prefer_live_geocode`` is set and a place-name query is present,
        the live geocoder's own point for that name wins over the supplied
        coordinate: the routing provider is then asked about the real place
        instead of about an approximate table centroid. The supplied coordinate
        remains the fallback, so a geocoder outage never fails the request.
        """
        raw = payload.get(coord_key)
        coord = _parse_coord(raw)
        query = payload.get(query_key)
        if query is None and isinstance(raw, str):
            query = raw

        if (
            prefer_live_geocode
            and query
            and self.settings.geocoding_enabled
            and self.geocoder is not None
        ):
            resolved, _err = self._geocode_coordinate(str(query))
            if resolved is not None:
                return resolved, None, "geocoder"

        if coord is not None:
            return coord, None, "coordinates"

        if query:
            if not self.settings.geocoding_enabled or self.geocoder is None:
                return None, "Geocoding is disabled on this server; supply {latitude, longitude}.", ""
            resolved, err = self._geocode_coordinate(str(query))
            if resolved is not None:
                return resolved, None, "geocoder"
            return None, err, ""

        if required:
            return None, "location must be {latitude, longitude} or a place name (destination_query).", ""
        return None, None, ""

    def geocode(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        query = payload.get("query") or payload.get("q")
        if not query:
            return 400, _error("invalid_request", "Provide 'query' with a place name.", "")
        if not self.settings.geocoding_enabled or self.geocoder is None:
            return 503, _error("geocoding_disabled", "Geocoding is disabled on this server.", "")
        try:
            limit = int(payload.get("limit", 5))
        except (TypeError, ValueError):
            limit = 5
        result = self.geocoder.geocode(str(query), limit=limit)
        code = 200 if result.status.value in ("ok", "no_results") else 502
        return code, result.to_dict()

    def routes(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        prefer = bool(payload.get("resolve_place_names"))
        origin, err, origin_source = self._resolve_location(
            payload, "origin", "origin_query", required=False, prefer_live_geocode=prefer)
        if err:
            return 400, _error("invalid_request", err)
        if origin is None:
            origin = Coordinate(12.9716, 77.5946)
            origin_source = "default"
        destination, err, destination_source = self._resolve_location(
            payload, "destination", "destination_query", required=True, prefer_live_geocode=prefer)
        if err or destination is None:
            return 400, _error("invalid_request", err or "destination is required.",
                               "No geocoding provider resolved the destination.")
        result = self.pipeline.resolve_routes(origin, destination)
        result["origin_resolution"] = origin_source
        result["destination_resolution"] = destination_source
        return 200, result

    def analyze(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        prefer = bool(payload.get("resolve_place_names"))
        origin, err, origin_source = self._resolve_location(
            payload, "origin", "origin_query", required=False, prefer_live_geocode=prefer)
        if err:
            return 400, _error("invalid_request", err)
        if origin is None:
            origin = Coordinate(12.9716, 77.5946)
            origin_source = "default"
        destination, err, destination_source = self._resolve_location(
            payload, "destination", "destination_query", required=True, prefer_live_geocode=prefer)
        if err or destination is None:
            return 400, _error("invalid_request", err or "destination is required.",
                               "No geocoding provider resolved the destination.")
        record = self.pipeline.analyze(origin, destination)
        record["destination_query"] = payload.get("destination_query")
        record["origin_query"] = payload.get("origin_query")
        # Disclose WHICH input the routed points came from, so a geocoded
        # place is never presented as if the supplied coordinate was used
        # (Rule 9).
        record["origin_resolution"] = origin_source
        record["destination_resolution"] = destination_source
        self.store.save_analysis(record)
        return 200, record

    # ------------------------------------------------------------------ #
    def _load(self, analysis_id: str):
        return self.store.get_analysis(analysis_id)

    def get_analysis(self, analysis_id: str):
        rec = self._load(analysis_id)
        if rec is None:
            return 404, _error("not_found", f"Analysis '{analysis_id}' not found.")
        return 200, rec

    def hazards(self, analysis_id: str):
        rec = self._load(analysis_id)
        if rec is None:
            return 404, _error("not_found", f"Analysis '{analysis_id}' not found.")
        hazards = []
        for r in rec.get("routes", []):
            for h in r.get("hazards", []):
                hazards.append({"route_id": r["route_id"], **h})
        return 200, {"analysis_id": analysis_id, "hazards_count": len(hazards), "hazards": hazards}

    def comparison(self, analysis_id: str):
        rec = self._load(analysis_id)
        if rec is None:
            return 404, _error("not_found", f"Analysis '{analysis_id}' not found.")
        return 200, {"analysis_id": analysis_id, "status": rec.get("status"),
                     "comparison": rec.get("comparison"), "recommendation": rec.get("recommendation")}

    def explanation(self, analysis_id: str):
        rec = self._load(analysis_id)
        if rec is None:
            return 404, _error("not_found", f"Analysis '{analysis_id}' not found.")
        return 200, rec.get("explanation", {})

    def facilities(self, payload: Dict[str, Any]):
        """Nearby facilities — CONTEXT ONLY (Rule 11).

        Three request shapes are supported:

        * ``{"location": {...}}`` (or a place name) — a circle around one point.
        * ``{"route": {"polylines": [[[lon, lat], ...], ...]}}`` — the corridor
          around one or more route geometries, which is what the SafeRoute UI
          uses so the browser never has to query OpenStreetMap itself.

        The response always carries the provider's honest status. A provider
        failure is never rewritten into "no hospitals exist" (Rule 20).

        PHASE_32 adds a third shape:

        * ``{"routes": [{"route_id": "...", "polylines": [...]}, ...]}`` — one
          facility result PER ROUTE. Each result is measured against that
          route's own geometry, so alternative routes do not share one corridor
          list. The OpenStreetMap query is still a single shared request.
        """
        routes = payload.get("routes")
        if isinstance(routes, list):
            radius = self._optional_float(payload.get("radius_m"))
            cats = payload.get("categories")
            include_road_access = payload.get("include_road_access", True)
            if not isinstance(include_road_access, bool):
                include_road_access = True
            return 200, self.pipeline.facilities.get_facilities_for_routes(
                routes,
                radius,
                cats,
                include_road_access=include_road_access,
                routing_provider=self.pipeline.routing,
            )

        route = payload.get("route")
        if isinstance(route, dict):
            polylines = route.get("polylines")
            radius = self._optional_float(payload.get("radius_m"))
            cats = payload.get("categories")
            include_road_access = payload.get("include_road_access", True)
            if not isinstance(include_road_access, bool):
                include_road_access = True
            result = self.pipeline.facilities.get_facilities_near_route(
                polylines,
                radius,
                cats,
                include_road_access=include_road_access,
                routing_provider=self.pipeline.routing,
            )
            return 200, result.to_dict()

        loc, err, _source = self._resolve_location(
            payload, "location", "location_query", required=False)
        if loc is None:
            loc, err, _source = self._resolve_location(
                payload, "destination", "destination_query", required=True)
        if err or loc is None:
            return 400, _error("invalid_request", err or "location must be {latitude, longitude} or a place name.")
        radius = self._optional_float(payload.get("radius_m"))
        cats = payload.get("categories")
        result = self.pipeline.facilities.get_nearby_facilities(loc.latitude, loc.longitude, radius, cats)
        return 200, result.to_dict()

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        """Parse an optional numeric field; an unusable value falls back to the default."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class _Handler(BaseHTTPRequestHandler):
    api: Optional[SafeRouteAPI] = None
    static_dir: Path = WORKSPACE_ROOT / "frontend"

    def log_message(self, *args):  # keep logs quiet & secret-free
        return

    def _send(self, code: int, obj: Dict[str, Any]):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _serve_static(self, path: str) -> bool:
        """Serve a file from the frontend directory. Returns True if handled."""
        rel = path.lstrip("/")
        if rel == "" or rel == "/":
            rel = "index.html"
        candidate = (self.static_dir / rel).resolve()
        try:
            candidate.relative_to(self.static_dir.resolve())
        except ValueError:
            return False  # path traversal attempt
        if not candidate.is_file():
            return False
        ctype, _ = mimetypes.guess_type(str(candidate))
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def _serve_spa_index(self) -> bool:
        """Serve the SPA index.html for client-side routes. Returns True if handled."""
        if not self.static_dir:
            return False
        candidate = (self.static_dir / "index.html").resolve()
        try:
            candidate.relative_to(self.static_dir.resolve())
        except ValueError:
            return False  # path traversal attempt
        if not candidate.is_file():
            return False
        ctype, _ = mimetypes.guess_type(str(candidate))
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        parts = [p for p in path.split("/") if p]
        if not path.startswith("/api"):
            if self.static_dir and self._serve_static(path):
                return
            # SPA fallback for client-side routes (history API refresh/direct nav)
            if self.static_dir and self._serve_spa_index():
                return
            self._send(404, _error("not_found", f"Unknown path '{path}'."))
            return
        try:
            if path == "/api/health":
                code, obj = self.api.health()
            elif path == "/api/config":
                code, obj = self.api.config()
            elif len(parts) == 3 and parts[1] == "analyze":
                code, obj = self.api.get_analysis(parts[2])
            elif len(parts) == 4 and parts[1] == "analysis":
                sub = parts[3]
                if sub == "hazards":
                    code, obj = self.api.hazards(parts[2])
                elif sub == "comparison":
                    code, obj = self.api.comparison(parts[2])
                elif sub == "explanation":
                    code, obj = self.api.explanation(parts[2])
                else:
                    code, obj = 404, _error("not_found", f"Unknown path '{path}'.")
            else:
                code, obj = 404, _error("not_found", f"Unknown path '{path}'.")
        except Exception as e:
            code, obj = 500, _error("internal_error", "Unhandled server error.", f"{type(e).__name__}: {e}")
        self._send(code, obj)

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        payload = self._read_json()
        try:
            if path == "/api/routes":
                code, obj = self.api.routes(payload)
            elif path == "/api/analyze":
                code, obj = self.api.analyze(payload)
            elif path == "/api/geocode":
                code, obj = self.api.geocode(payload)
            elif path == "/api/facilities":
                code, obj = self.api.facilities(payload)
            else:
                code, obj = 404, _error("not_found", f"Unknown path '{path}'.")
        except Exception as e:
            code, obj = 500, _error("internal_error", "Unhandled server error.", f"{type(e).__name__}: {e}")
        self._send(code, obj)


def create_server(host: str = "127.0.0.1", port: int = 8000, api: SafeRouteAPI = None,
                  static_dir: Optional[Path] = None) -> ThreadingHTTPServer:
    api = api or SafeRouteAPI()
    _Handler.api = api
    if static_dir is not None:
        _Handler.static_dir = Path(static_dir)
    elif api is not None:
        from src.config.env import WORKSPACE_ROOT as _WS
        _Handler.static_dir = (_WS / api.settings.static_dir)
    return ThreadingHTTPServer((host, port), _Handler)


def main():
    settings = load_settings()
    host = settings.host
    port = settings.port
    server = create_server(host, port)
    print(f"SafeRoute AI API + UI listening on http://{host}:{port}")
    print(f"  routing={settings.routing_provider} imagery={settings.imagery_source} "
          f"facilities={settings.facilities_provider} geocoding={settings.geocoding_provider} "
          f"llm={'on' if settings.llm_enabled else 'off'} mapillary_token={'yes' if settings.mapillary_token else 'no'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
