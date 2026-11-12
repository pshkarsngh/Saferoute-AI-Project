"""PHASE_44 helper: hash the frontend bundle assets before and after editing.

Records SHA-256 for every index-*.js bundle, index.html and model-status.js so
the pre-edit state of the shipped frontend is provable (the bundle is edited in
place because the frontend source project is not part of this repository).
"""

import hashlib
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2] if "scripts" in str(Path(__file__)) else Path.cwd()

TARGETS = [
    "frontend/index.html",
    "frontend/model-status.js",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def collect(root: Path) -> dict:
    entries = {}
    for rel in TARGETS:
        p = root / rel
        if p.is_file():
            entries[rel] = {
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
            }
    for p in sorted((root / "frontend" / "assets").glob("index-*.js")):
        rel = p.relative_to(root).as_posix()
        entries[rel] = {
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
        }
    return entries


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    stage = sys.argv[1] if len(sys.argv) > 1 else "pre_edit"
    out = root / "reports" / "phase44_bundle_manifest.json"
    manifest = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    manifest[stage] = {
        "files": collect(root),
        "backup": "frontend/backup/phase44_pre_edit" if stage == "pre_edit" else None,
    }
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} [{stage}] for {len(manifest[stage]['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
