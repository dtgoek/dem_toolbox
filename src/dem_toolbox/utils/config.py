from pathlib import Path
import yaml
from dotenv import load_dotenv
import os
from dem_toolbox.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path("configs/default_config.yaml")


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Config loaded from {config_path}")
    return config


def load_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("OT_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OT_API_KEY not found. Add it to your .env file."
        )
    logger.info("API key loaded successfully.")
    return api_key