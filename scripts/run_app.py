#!/usr/bin/env python3
"""SafeRoute AI — one-command launcher (API + UI).

Runs the stdlib HTTP server that serves both the JSON API and the static
frontend, and opens the UI in the default browser.

Usage:
    .\.venv\Scripts\python.exe scripts\run_app.py
    .\.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8010

No packages beyond the documented requirements are needed (Rule 19).
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.api.app import create_server  # noqa: E402
from src.config import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Run the SafeRoute AI API + UI.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    url = f"http://{args.host}:{args.port}/"
    print("SafeRoute AI running.")
    print(f"  UI + API : {url}")
    print(f"  routing={settings.routing_provider} imagery={settings.imagery_source} "
          f"facilities={settings.facilities_provider} geocoding={settings.geocoding_provider} "
          f"llm={'on' if settings.llm_enabled else 'off'} "
          f"mapillary_token={'yes' if settings.mapillary_token else 'no'}")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
