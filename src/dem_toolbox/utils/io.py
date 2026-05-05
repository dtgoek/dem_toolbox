"""
io.py — File I/O and metadata utilities for the DEM toolbox.

Responsibilities:
- Move tiles from temp → raw after successful download
- Write a metadata JSON sidecar file next to each tile
- Load existing metadata
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dem_toolbox.utils.logger import get_logger

logger = get_logger(__name__)


def move_to_raw(temp_path: Path, raw_dir: Path) -> Path:
    """
    Move a downloaded tile from temp/ to raw/.

    Args:
        temp_path: path of downloaded tile in data/temp/
        raw_dir:   target directory (data/raw/)

    Returns:
        Final path in raw_dir
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / temp_path.name
    shutil.move(str(temp_path), dest)
    logger.info(f"Moved {temp_path.name} → {dest}")
    return dest


def write_metadata(tile_path: Path, tile, cfg: dict) -> Path:
    meta = {
        "file":          tile_path.name,
        "job_name":      tile.job_name,
        "dataset":       tile.dataset,
        "bbox": {
            "west":  tile.west,
            "south": tile.south,
            "east":  tile.east,
            "north": tile.north,
        },
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "source":        "OpenTopography",
        "config": {
            "safety_factor": cfg["download"]["tile_safety_factor"],
            "aoi_bbox":      cfg["aoi"]["bbox"],
        },
    }
    meta_path = tile_path.with_suffix(".json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"Metadata written → {meta_path.name}")
    return meta_path


def load_metadata(tile_path: Path) -> dict:
    """Load the JSON sidecar for a given tile."""
    meta_path = tile_path.with_suffix(".json")
    if not meta_path.exists():
        raise FileNotFoundError(f"No metadata found for {tile_path.name}")
    with open(meta_path, "r") as f:
        return json.load(f)