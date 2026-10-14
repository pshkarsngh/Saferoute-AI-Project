"""SafeRoute AI — application configuration package.

Provides a dependency-free `.env` loader (Rule 13) and a typed application
settings layer that combines `config/app.yaml` with environment overrides.

No third-party packages are used (python-dotenv/FastAPI are not installed and
installing them is gated by Rule 19).
"""

from src.config.env import (
    WORKSPACE_ROOT,
    get_bool,
    get_env,
    get_float,
    get_int,
    load_env,
    parse_env_text,
)
from src.config.settings import Settings, load_settings
from src.config.thresholds import (
    ThresholdPolicy,
    assert_threshold_consistency,
    load_threshold_policy,
)

__version__ = "config-v1"

__all__ = [
    "WORKSPACE_ROOT",
    "parse_env_text",
    "load_env",
    "get_env",
    "get_bool",
    "get_int",
    "get_float",
    "Settings",
    "load_settings",
    "ThresholdPolicy",
    "load_threshold_policy",
    "assert_threshold_consistency",
    "__version__",
]
