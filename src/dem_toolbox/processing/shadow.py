# src/dem_toolbox/processing/shadow.py

import math
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from datetime import datetime, timedelta
from pathlib import Path
from numba import njit


# ── Sun Position ──────────────────────────────────────────────────────────────

def sun_position(dt: datetime, lat: float, lon: float) -> dict:
    """
    Compute solar azimuth and elevation for a given datetime and location.
    No external astronomy libraries — pure geometry.
    Returns dict with keys: datetime, azimuth, elevation (degrees).
    """
    # Day of year
    doy = dt.timetuple().tm_yday
    hour_utc = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

    # Solar declination (degrees)
    declination = -23.45 * math.cos(math.radians(360 / 365 * (doy + 10)))

    # Hour angle
    solar_time  = hour_utc + lon / 15.0
    hour_angle  = (solar_time - 12.0) * 15.0  # degrees

    # Convert to radians
    lat_r  = math.radians(lat)
    dec_r  = math.radians(declination)
    ha_r   = math.radians(hour_angle)

    # Solar elevation
    sin_elev = (math.sin(lat_r) * math.sin(dec_r) +
                math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r))
    elevation = math.degrees(math.asin(sin_elev))

    # Solar azimuth
    cos_az = ((math.sin(dec_r) - math.sin(lat_r) * sin_elev) /
              (math.cos(lat_r) * math.cos(math.asin(sin_elev)) + 1e-10))
    cos_az = max(-1.0, min(1.0, cos_az))  # clamp for numerical safety
    azimuth = math.degrees(math.acos(cos_az))
    if hour_angle > 0:
        azimuth = 360.0 - azimuth

    return {"datetime": dt, "azimuth": azimuth, "elevation": elevation}


def generate_sun_positions(date: str, lat: float, lon: float,
                           interval_min: int = 60) -> list:
    """
    Return list of sun_position dicts for a full day at given interval.
    Only returns timesteps where sun is above horizon (elevation > 0).
    """
    d = datetime.fromisoformat(date)
    positions = []
    for minutes in range(0, 1440, interval_min):
        dt = d + timedelta(minutes=minutes)
        sp = sun_position(dt, lat, lon)
        if sp["elevation"] > 0:
            positions.append(sp)
    return positions


# ── DEM Reprojection ──────────────────────────────────────────────────────────

def reproject_to_utm(dem_path: Path, output_path: Path,
                     target_crs: str = "EPSG:32632") -> None:
    """Reproject DEM to a metric CRS (UTM) and save as GeoTIFF."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(dem_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        meta = src.meta.copy()
        meta.update({
            "crs":       target_crs,
            "transform": transform,
            "width":     width,
            "height":    height,
        })
        with rasterio.open(output_path, "w", **meta) as dst:
            reproject(
                source      = rasterio.band(src, 1),
                destination = rasterio.band(dst, 1),
                src_crs     = src.crs,
                dst_crs     = target_crs,
                resampling  = Resampling.bilinear,
            )


# ── DEM Rotation ─────────────────────────────────────────────────────────────

def rotate_dem(dem: np.ndarray, sun_azimuth: float) -> np.ndarray:
    """
    Rotate DEM so that sun always shines from the top (north).
    Rotation angle is -azimuth so columns run parallel to sun rays.
    Uses scipy to avoid border artefacts with reshape=True.
    """
    from scipy.ndimage import rotate
    angle = -(sun_azimuth - 180.0)   # rotate so sun comes from top
    return rotate(dem, angle=angle, reshape=True, order=1, cval=np.nan)


def unrotate_mask(shadow_rotated: np.ndarray, sun_azimuth: float,
                  original_shape: tuple) -> np.ndarray:
    """
    Rotate shadow mask back to original DEM orientation and crop to
    original shape.
    """
    from scipy.ndimage import rotate
    angle = sun_azimuth - 180.0
    unrotated = rotate(shadow_rotated.astype(float), angle=angle,
                       reshape=True, order=1, cval=0)

    # Centre-crop to original shape
    ch, cw  = original_shape
    rh, rw  = unrotated.shape
    r0 = (rh - ch) // 2
    c0 = (rw - cw) // 2
    cropped = unrotated[r0:r0 + ch, c0:c0 + cw]
    return cropped > 0.5   # back to bool


# ── Shadow Sweep (Numba) ──────────────────────────────────────────────────────
@njit
def _sweep_column(col: np.ndarray, resolution: float,
                  sun_elev_rad: float) -> np.ndarray:
    n        = len(col)
    shadow   = np.zeros(n, dtype=np.uint8)
    sun_tan  = math.tan(sun_elev_rad)   # compute once, not inside loop

    # baseline: first valid elevation (sun-side edge of rotated DEM)
    baseline = col[0]
    for k in range(n):
        if not np.isnan(col[k]):
            baseline = col[k]
            break

    max_tan = -1e9   # max terrain horizon angle seen so far

    for i in range(n):
        if np.isnan(col[i]):
            continue
        dist_m = i * resolution
        if dist_m == 0:
            terrain_tan = -1e9
        else:
            terrain_tan = (col[i] - baseline) / dist_m

        # Shadow if sun is below the max terrain horizon seen so far
        if sun_tan < max_tan:
            shadow[i] = 1

        # Always update horizon — shadowed peaks still cast shadows further
        if terrain_tan > max_tan:
            max_tan = terrain_tan

    return shadow


def _sweep_all_columns(dem_rotated: np.ndarray, resolution: float,
                       sun_elev_rad: float) -> np.ndarray:
    """Apply _sweep_column to every column of the rotated DEM."""
    rows, cols = dem_rotated.shape
    shadow = np.zeros((rows, cols), dtype=np.uint8)
    for c in range(cols):
        shadow[:, c] = _sweep_column(dem_rotated[:, c], resolution, sun_elev_rad)
    return shadow


# ── Full Shadow Computation ───────────────────────────────────────────────────

def compute_shadow(dem: np.ndarray, resolution: float,
                   sun_azimuth: float, sun_elevation: float) -> np.ndarray:
    """
    Compute binary shadow mask for a single sun position.

    Parameters
    ----------
    dem           : 2D elevation array in metres
    resolution    : pixel size in metres
    sun_azimuth   : solar azimuth in degrees (0° = N, clockwise)
    sun_elevation : solar elevation in degrees above horizon

    Returns
    -------
    shadow : bool array, True = pixel is in shadow
    """
    original_shape = dem.shape
    sun_elev_rad   = math.radians(sun_elevation)

    # 1. Rotate DEM so sun shines from top
    dem_rot = rotate_dem(dem, sun_azimuth)

    # 2. Column-wise shadow sweep
    shadow_rot = _sweep_all_columns(dem_rot, resolution, sun_elev_rad)

    # 3. Rotate mask back and crop to original shape
    shadow = unrotate_mask(shadow_rot, sun_azimuth, original_shape)

    return shadow


# ── GeoTIFF Output ────────────────────────────────────────────────────────────

def save_geotiff(array: np.ndarray, path: Path,
                 crs, transform, dtype: str = "uint8") -> None:
    """Save a 2D numpy array as a single-band GeoTIFF."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w",
        driver    = "GTiff",
        height    = array.shape[0],
        width     = array.shape[1],
        count     = 1,
        dtype     = dtype,
        crs       = crs,
        transform = transform,
    ) as dst:
        dst.write(array.astype(dtype), 1)