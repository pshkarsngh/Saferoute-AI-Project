"""SafeRoute AI — SQLite persistence for analyses (PHASE_16).

Implements the TRD §12 entities (analyses, routes, segments, imagery refs,
detections, model versions, scores) with model_version + config_hash recorded
for auditability (Rule 17). No personal data is stored (Rule 13).

SQLite is used instead of MySQL: it is a stdlib module, so no server or package
install is required (Rule 19). The schema mirrors TRD §12 and can be ported.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_REL = Path("data/saferoute.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_versions (
  id TEXT PRIMARY KEY,
  name TEXT,
  checkpoint_path TEXT,
  trained_at TEXT,
  metrics_json TEXT
);
CREATE TABLE IF NOT EXISTS searches (
  id TEXT PRIMARY KEY,
  origin TEXT,
  destination TEXT,
  provider TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY,
  search_id TEXT,
  status TEXT,
  model_version TEXT,
  config_hash TEXT,
  result_json TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS scores (
  id TEXT PRIMARY KEY,
  analysis_id TEXT,
  route_id TEXT,
  model_version TEXT,
  config_hash TEXT,
  route_score REAL,
  coverage_fraction REAL,
  status TEXT,
  computed_at TEXT
);
CREATE TABLE IF NOT EXISTS hazard_detections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id TEXT,
  route_id TEXT,
  segment_id TEXT,
  image_id TEXT,
  hazard_class TEXT,
  confidence REAL,
  severity REAL,
  bbox_json TEXT,
  status TEXT
);
"""


class AnalysisStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else (WORKSPACE_ROOT / DEFAULT_DB_REL)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def save_analysis(self, analysis: Dict[str, Any]) -> str:
        analysis_id = analysis["analysis_id"]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO searches (id, origin, destination, provider, created_at) VALUES (?,?,?,?,?)",
                (analysis.get("search_id", analysis_id), json.dumps(analysis.get("origin")),
                 json.dumps(analysis.get("destination")), analysis.get("provider", ""), now),
            )
            conn.execute(
                "INSERT OR REPLACE INTO analyses (id, search_id, status, model_version, config_hash, result_json, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (analysis_id, analysis.get("search_id", analysis_id), analysis.get("status", ""),
                 analysis.get("model_version", ""), analysis.get("config_hash", ""),
                 json.dumps(analysis), now),
            )
            for r in analysis.get("routes", []):
                conn.execute(
                    "INSERT OR REPLACE INTO scores (id, analysis_id, route_id, model_version, config_hash, "
                    "route_score, coverage_fraction, status, computed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"{analysis_id}:{r['route_id']}", analysis_id, r["route_id"],
                     analysis.get("model_version", ""), analysis.get("config_hash", ""),
                     r.get("route_score"), r.get("coverage", {}).get("fraction"),
                     r.get("status", ""), now),
                )
            # PHASE_25: persist the supported hazard detections the schema already
            # declares (TRD §12), so the audit trail is queryable and the module
            # docstring is accurate (Rule 17). Re-saving an analysis first clears
            # its previous rows so persistence stays idempotent, mirroring the
            # INSERT OR REPLACE behaviour used above.
            conn.execute("DELETE FROM hazard_detections WHERE analysis_id=?", (analysis_id,))
            for r in analysis.get("routes", []):
                for h in (r.get("hazards") or []):
                    conn.execute(
                        "INSERT INTO hazard_detections (analysis_id, route_id, segment_id, image_id, "
                        "hazard_class, confidence, severity, bbox_json, status) VALUES (?,?,?,?,?,?,?,?,?)",
                        (analysis_id, h.get("route_id") or r.get("route_id"),
                         h.get("segment_id"), h.get("image_id"),
                         h.get("hazard_class"), h.get("confidence"), h.get("severity"),
                         json.dumps({"bbox_xyxy": h.get("bbox_xyxy"),
                                     "bbox_norm": h.get("bbox_norm")}),
                         h.get("status", "")),
                    )
            conn.commit()
        finally:
            conn.close()
        return analysis_id

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT result_json FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        finally:
            conn.close()
        return json.loads(row["result_json"]) if row else None
