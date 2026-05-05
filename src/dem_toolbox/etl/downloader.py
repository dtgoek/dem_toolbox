import time
import requests
from pathlib import Path
from dem_toolbox.etl.tiler import Tile
from dem_toolbox.utils.logger import get_logger

logger = get_logger(__name__)

# OpenTopography API endpoint for global raster DEMs
OT_API_URL = "https://portal.opentopography.org/API/globaldem"

# Dataset name mapping: our internal names → OT API parameter values
DATASET_MAP = {
    "GLO30": "COP30",
    "SRTM3": "SRTM GL3",
}

# Polling settings for async responses
POLL_INTERVAL_SEC = 10   # seconds between status checks
MAX_POLL_ATTEMPTS = 30   # max ~5 minutes total wait time


def download_tile(tile: Tile, api_key: str, output_dir: Path) -> Path:
    """
    Download a single DEM tile from OpenTopography API.

    Handles both:
    - Synchronous response: file returned directly in response body
    - Async response: OT returns a job URL → we poll until ready

    Args:
        tile: Tile object with bbox and filename info
        api_key: OpenTopography API key
        output_dir: directory to save the downloaded tile (data/temp/)

    Returns:
        Path to the saved .tif file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / tile.filename

    # Skip download if tile already exists (basic cache check)
    if output_path.exists():
        logger.info(f"Tile already exists, skipping: {tile.filename}")
        return output_path

    # Build API request parameters
    params = {
        "demtype": DATASET_MAP[tile.dataset],
        "west": tile.west,
        "south": tile.south,
        "east": tile.east,
        "north": tile.north,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }

    logger.info(f"Requesting tile: {tile.filename}")

    try:
        response = requests.get(OT_API_URL, params=params, timeout=120)
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API request failed for {tile.filename}: {e}")

    # Handle async job (OT returns a URL to poll instead of the file)
    if response.status_code == 202:
        job_url = response.headers.get("Location") or response.json().get("url")
        logger.info(f"Async job started, polling: {job_url}")
        return _poll_and_download(job_url, output_path, api_key)

    # Handle direct file response
    if response.status_code == 200:
        _save_response(response, output_path)
        logger.info(f"Tile saved: {output_path}")
        return output_path

    # Handle API errors with clear messages
    raise RuntimeError(
        f"API error {response.status_code} for {tile.filename}: {response.text[:200]}"
    )


def _poll_and_download(job_url: str, output_path: Path, api_key: str) -> Path:
    """
    Poll an async OT job URL until the file is ready, then download it.
    Raises TimeoutError if max polling attempts are exceeded.
    """
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        logger.info(f"Polling attempt {attempt}/{MAX_POLL_ATTEMPTS}...")
        time.sleep(POLL_INTERVAL_SEC)

        try:
            response = requests.get(
                job_url, params={"API_Key": api_key}, timeout=60
            )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Polling request failed: {e} — retrying...")
            continue

        if response.status_code == 200:
            _save_response(response, output_path)
            logger.info(f"Tile ready and saved: {output_path}")
            return output_path

        if response.status_code == 202:
            logger.info("Job still processing...")
            continue

        raise RuntimeError(
            f"Unexpected status {response.status_code} while polling: {response.text[:200]}"
        )

    raise TimeoutError(
        f"Tile {output_path.name} not ready after "
        f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SEC}s. Try again later."
    )


def _save_response(response: requests.Response, output_path: Path) -> None:
    """Write response binary content to file in chunks (memory efficient)."""
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)