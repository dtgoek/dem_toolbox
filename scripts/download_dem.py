#!/usr/bin/env python3
"""
download_dem.py — Entry point for the DEM download pipeline.

Usage:
    python scripts/download_dem.py --config configs/runs/alps_2026.yaml
"""

import argparse
from pathlib import Path

from dem_toolbox.utils.config import merge_configs, load_api_key
from dem_toolbox.utils.logger import get_logger
from dem_toolbox.etl.validator import validate_all
from dem_toolbox.etl.tiler import split_bbox
from dem_toolbox.etl.downloader import download_tile
from dem_toolbox.utils.io import move_to_raw, write_metadata


logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download DEM tiles from OpenTopography."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to run-specific YAML config (e.g. configs/runs/alps_2026.yaml)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info(f"Starting DEM download pipeline | config: {args.config}")

    # 1. Load config
    cfg = merge_configs(args.config)
    key = load_api_key()

    # 2. Validate
    validate_all(cfg, key)

    # 3. Tile bbox
    bbox     = cfg["aoi"]["bbox"]
    dataset  = cfg["download"]["dataset"]
    job_name = cfg["aoi"]["job_name"]
    out_dir  = Path(cfg["paths"]["temp_dir"])

    tiles = split_bbox(bbox, dataset=dataset, job_name=job_name)
    logger.info(f"Tiles to download: {len(tiles)}")

    # 4. Download, move, write metadata
    raw_dir = Path(cfg["paths"]["raw_dir"])
    for tile in tiles:
        temp_path = download_tile(tile, api_key=key, output_dir=out_dir)
        final_path = move_to_raw(temp_path, raw_dir)
        reproject_cfg = cfg.get("reproject")
        if cfg.get("reproject"):
            from dem_toolbox.processing.shadow import reproject_to_utm

            reproject_to_utm(
                dem_path=final_path,
                output_path=Path(cfg["reproject"]["output_path"]),
                target_crs=cfg["reproject"]["target_crs"],
            )
        write_metadata(final_path, tile, cfg)
        logger.info(f"  ✓ {final_path.name}  ({final_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()