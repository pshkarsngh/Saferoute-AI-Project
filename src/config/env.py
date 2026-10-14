"""SafeRoute AI — minimal standard-library `.env` loader (Rule 13).

python-dotenv is intentionally NOT used: it is not installed, and installing a
package is gated by master_rules.md Rule 19. This loader covers the small subset
of `.env` syntax the project needs (KEY=VALUE, comments, optional quotes and an
optional leading ``export``), and never overrides variables that already exist
in the real environment.

Secrets live ONLY in the uncommitted `.env` (git-ignored). `.env.example`
documents the variable names with placeholder values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Union

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ENV_FILE = WORKSPACE_ROOT / ".env"

_ENV_LOADED = False


def parse_env_text(text: str) -> Dict[str, str]:
    """Parse `.env` text into a plain dict (no I/O, no side effects)."""
    values: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        # Strip a single pair of matching surrounding quotes.
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def load_env(
    path: Optional[Union[str, Path]] = None,
    override: bool = False,
) -> Dict[str, str]:
    """Load a `.env` file into ``os.environ``.

    Args:
        path: Path to the env file; defaults to ``<workspace>/.env``.
        override: When False (default) existing environment variables win.

    Returns:
        The parsed key/value pairs (empty dict if the file is absent).
    """
    global _ENV_LOADED
    env_path = Path(path) if path is not None else DEFAULT_ENV_FILE
    if not env_path.is_file():
        return {}

    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    values = parse_env_text(text)
    for key, val in values.items():
        if override or key not in os.environ:
            os.environ[key] = val
    _ENV_LOADED = True
    return values


def env_loaded() -> bool:
    """Whether a `.env` file has been loaded this process."""
    return _ENV_LOADED


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return an environment value, treating empty strings as unset."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val


def get_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable (1/true/yes/on)."""
    val = get_env(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def get_int(name: str, default: int = 0) -> int:
    """Parse an integer environment variable, falling back on error."""
    val = get_env(name)
    if val is None:
        return default
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


def get_float(name: str, default: float = 0.0) -> float:
    """Parse a float environment variable, falling back on error."""
    val = get_env(name)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
