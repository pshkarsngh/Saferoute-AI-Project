"""SafeRoute AI — stdlib HTTP API server (PHASE_16).

Implements the TRD §11 endpoints without third-party web frameworks (FastAPI is
not installed and installing it is gated by Rule 19). Uses http.server + sqlite3
from the standard library so the API runs with zero new dependencies.

Endpoints:
    GET  /api/health
    POST /api/routes
    POST /api/analyze
    GET  /api/analyze/{id}
    GET  /api/analysis/{id}/hazards
    GET  /api/analysis/{id}/comparison
    GET  /api/analysis/{id}/explanation
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple

from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.routing.schemas import Coordinate


def _parse_coord(value: Any) -> Optional[Coordinate]:
    if isinstance(value, dict) and "latitude" in value and "longitude" in value:
        return Coordinate(latitude=float(value["latitude"]), longitude=float(value["longitude"]))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return Coordinate(latitude=float(value[0]), longitude=float(value[1]))
    return None


def _error(code: str, message: str, detail: str = "") -> Dict[str, Any]:
    return {"status": "failed", "error": {"code": code, "message": message, "detail": detail}}


class SafeRouteAPI:
    """Request router holding the pipeline and persistence store."""

    def __init__(self, pipeline: Optional[SafetyAnalysisPipeline] = None, store: Optional[AnalysisStore] = None):
        self.pipeline = pipeline or SafetyAnalysisPipeline()
        self.store = store or AnalysisStore()

    def health(self) -> Tuple[int, Dict[str, Any]]:
        return 200, {"status": "ok", "model_version": self.pipeline.model_version,
                     "config_hash": self.pipeline.config_hash}

    def routes(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        origin = _parse_coord(payload.get("origin")) if payload.get("origin") else Coordinate(12.9716, 77.5946)
        destination = _parse_coord(payload.get("destination"))
        if origin is None or destination is None:
            return 400, _error("invalid_request", "origin/destination must be {latitude, longitude} or [lat, lon].",
                               "No geocoding provider is configured; supply coordinates.")
        return 200, self.pipeline.resolve_routes(origin, destination)

    def analyze(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        origin = _parse_coord(payload.get("origin")) if payload.get("origin") else Coordinate(12.9716, 77.5946)
        destination = _parse_coord(payload.get("destination"))
        if origin is None or destination is None:
            return 400, _error("invalid_request", "origin/destination must be {latitude, longitude} or [lat, lon].",
                               "No geocoding provider is configured; supply coordinates.")
        record = self.pipeline.analyze(origin, destination)
        self.store.save_analysis(record)
        return 200, record

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
        loc = _parse_coord(payload.get("location")) or _parse_coord(payload.get("destination"))
        if loc is None:
            return 400, _error("invalid_request", "location must be {latitude, longitude} or [lat, lon].")
        radius = payload.get("radius_m")
        cats = payload.get("categories")
        result = self.pipeline.facilities.get_nearby_facilities(loc.latitude, loc.longitude, radius, cats)
        return 200, result.to_dict()


class _Handler(BaseHTTPRequestHandler):
    api: SafeRouteAPI = None  # type: ignore

    def log_message(self, *args):  # keep logs quiet & secret-free
        return

    def _send(self, code: int, obj: Dict[str, Any]):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
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

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        parts = [p for p in path.split("/") if p]
        try:
            if path == "/api/health":
                code, obj = self.api.health()
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
            elif path == "/api/facilities":
                code, obj = self.api.facilities(payload)
            else:
                code, obj = 404, _error("not_found", f"Unknown path '{path}'.")
        except Exception as e:
            code, obj = 500, _error("internal_error", "Unhandled server error.", f"{type(e).__name__}: {e}")
        self._send(code, obj)


def create_server(host: str = "127.0.0.1", port: int = 8000, api: SafeRouteAPI = None) -> HTTPServer:
    _Handler.api = api or SafeRouteAPI()
    return HTTPServer((host, port), _Handler)


def main():
    import os
    host = os.environ.get("SAFEROUTE_HOST", "127.0.0.1")
    port = int(os.environ.get("SAFEROUTE_PORT", "8000"))
    server = create_server(host, port)
    print(f"SafeRoute AI API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
