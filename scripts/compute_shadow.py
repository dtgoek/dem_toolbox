# scripts/compute_shadow.py

import argparse
import yaml
import numpy as np
import rasterio
from pathlib import Path
from tqdm import tqdm

from dem_toolbox.processing.shadow import (
    generate_sun_positions,
    sun_position,
    compute_shadow,
    save_geotiff,
)


# ── Config helpers ────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins)."""
    for k, v in override.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(run_config_path: str) -> dict:
    with open("configs/defaults/shadow.yaml") as f:
        cfg = yaml.safe_load(f)
    with open(run_config_path) as f:
        run_cfg = yaml.safe_load(f)
    return _deep_merge(cfg, run_cfg)


# ── Main ──────────────────────────────────────────────────────────────────────

def main(config_path: str):
    cfg = load_config(config_path)

    # ── 1. Load DEM
    dem_path = Path(cfg["input"]["dem_path"])
    if not dem_path.exists():
        raise FileNotFoundError(f"DEM not found: {dem_path}")

    with rasterio.open(dem_path) as src:
        dem       = src.read(1).astype(float)
        crs       = src.crs
        transform = src.transform
        resolution = src.res[0]  # metres per pixel (after UTM reprojection)

    print(f"DEM loaded: {dem.shape[0]}×{dem.shape[1]} px  |  res={resolution:.1f} m")

    # ── 2. Output directory — derived from DEM stem
    shadow_dir = Path("data/processed/shadows") / dem_path.stem
    shadow_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {shadow_dir}")

    # ── 3. Build sun positions
    sun_cfg = cfg["sun"]
    if sun_cfg["mode"] == "timeseries":
        sun_positions = generate_sun_positions(
            date         = sun_cfg["date"],
            lat          = sun_cfg["lat"],
            lon          = sun_cfg["lon"],
            interval_min = sun_cfg["interval_minutes"],
        )
    elif sun_cfg["mode"] == "single":
        sun_positions = [
            sun_position(
                dt  = sun_cfg["date"],   # expects datetime or ISO string
                lat = sun_cfg["lat"],
                lon = sun_cfg["lon"],
            )
        ]
    else:
        raise ValueError(f"Unknown sun.mode: {sun_cfg['mode']}")

    # Filter: only timesteps where sun is above horizon
    sun_positions = [sp for sp in sun_positions if sp["elevation"] > 0]
    print(f"{len(sun_positions)} daylight timestep(s) to process")

    # ── 4. Loop — compute & optionally save each shadow mask
    out_cfg = cfg.get("output") or {}
    save_individual = out_cfg.get("save_individual", True)
    save_summary    = out_cfg.get("save_summary", True)
    shadow_stack = []

    for sp in tqdm(sun_positions, desc="Shadow sweep"):
        mask = compute_shadow(
            dem           = dem,
            resolution    = resolution,
            sun_azimuth   = sp["azimuth"],
            sun_elevation = sp["elevation"],
        )
        shadow_stack.append(mask.astype(np.uint8))

        if out_cfg["save_individual"]:
            fname = f"shadow_{sp['datetime'].strftime('%Y-%m-%d_%Hh%M')}.tif"
            save_geotiff(
                array     = mask.astype(np.uint8),
                path      = shadow_dir / fname,
                crs       = crs,
                transform = transform,
                dtype     = "uint8",
            )

    # ── 5. Shadow hours summary raster
    if out_cfg["save_summary"] and shadow_stack:
        interval_h    = sun_cfg["interval_minutes"] / 60.0
        shadow_hours  = np.sum(shadow_stack, axis=0) * interval_h
        fname         = f"shadow_hours_{sun_cfg['date']}.tif"
        save_geotiff(
            array     = shadow_hours.astype(np.float32),
            path      = shadow_dir / fname,
            crs       = crs,
            transform = transform,
            dtype     = "float32",
        )
        print(f"Summary raster saved: {fname}")
        print(f"Max shadow hours: {shadow_hours.max():.1f} h  |  "
              f"Mean: {shadow_hours.mean():.1f} h")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute DEM shadow masks")
    parser.add_argument("--config", required=True,
                        help="Path to run config YAML, e.g. configs/runs/shadow/oberaletsch_2026-07-15.yaml")
    args = parser.parse_args()
    main(args.config)