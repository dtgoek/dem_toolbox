from pathlib import Path
import yaml
from dotenv import load_dotenv
import os
from dem_toolbox.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path("configs/defaults/download.yaml")


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load a single YAML config file and return as dictionary."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Config loaded from {config_path}")
    return config


def load_api_key() -> str:
    """Load OpenTopography API key from .env file."""
    load_dotenv()
    api_key = os.getenv("OT_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OT_API_KEY not found. Add it to your .env file."
        )
    logger.info("API key loaded successfully.")
    return api_key


def merge_configs(run_config_path: Path) -> dict:
    """
    Load default config and merge with a run-specific YAML.
    Run YAML values override defaults — only specify what changes.

    Args:
        run_config_path: path to run-specific YAML (e.g. configs/runs/alps_2026.yaml)

    Returns:
        Merged config dict
    """
    # Start with defaults as base
    base = load_config(DEFAULT_CONFIG_PATH)

    # Load run-specific overrides
    run = load_config(run_config_path)

    # Deep merge: run values override base values at each nested level
    merged = _deep_merge(base, run)
    logger.info(f"Config merged: defaults + {run_config_path}")
    return merged


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recurse into nested dicts
            result[key] = _deep_merge(result[key], value)
        else:
            # Override scalar values directly
            result[key] = value
    return result