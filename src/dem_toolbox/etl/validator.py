from pathlib import Path
from shapely.geometry import box
import pyproj
from shapely.ops import transform
from dem_toolbox.utils.logger import get_logger

logger = get_logger(__name__)

# --- Constants ---
# OT API max area per dataset (km²), reduced to 70% for safety
DATASET_LIMITS = {
    "GLO30": 450_000 * 0.7,    # Copernicus 30m → ~315,000 km²
    "SRTM3": 4_050_000 * 0.7,  # SRTM 90m     → ~2,835,000 km²
}


def validate_dataset(dataset: str) -> None:
    """Reject unknown dataset names early."""
    if dataset not in DATASET_LIMITS:
        raise ValueError(f"Unknown dataset '{dataset}'. Choose from: {list(DATASET_LIMITS)}")
    logger.info(f"Dataset OK: {dataset}")


def validate_bbox(bbox: dict) -> None:
    """Check bbox keys exist and coordinates are geographically valid."""
    for key in ["west", "south", "east", "north"]:
        if key not in bbox:
            raise ValueError(f"bbox missing key: '{key}'")

    w, s, e, n = bbox["west"], bbox["south"], bbox["east"], bbox["north"]

    if not (-180 <= w < e <= 180):
        raise ValueError(f"Longitude invalid: west={w}, east={e} (west must be < east)")
    if not (-90 <= s < n <= 90):
        raise ValueError(f"Latitude invalid: south={s}, north={n} (south must be < north)")

    logger.info(f"bbox OK: W{w} S{s} E{e} N{n}")


def validate_bbox_area(bbox: dict, dataset: str) -> None:
    """Check bbox area stays within OT API safe limit for the given dataset."""
    w, s, e, n = bbox["west"], bbox["south"], bbox["east"], bbox["north"]

    # Project to equal-area CRS (EPSG:6933) for accurate km² calculation
    project = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:6933", always_xy=True
    ).transform
    area_km2 = transform(project, box(w, s, e, n)).area / 1e6

    limit_km2 = DATASET_LIMITS[dataset]
    if area_km2 > limit_km2:
        raise ValueError(
            f"AOI too large: {area_km2:,.0f} km² exceeds safe limit "
            f"of {limit_km2:,.0f} km² for {dataset}. Consider tiling."
        )
    logger.info(f"bbox area OK: {area_km2:,.0f} km² (limit: {limit_km2:,.0f} km²)")


def validate_geojson(path: str) -> None:
    """Check GeoJSON file exists and has correct extension (batch mode)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"GeoJSON not found: {path}")
    if p.suffix.lower() != ".geojson":
        raise ValueError(f"Expected .geojson file, got: {p.suffix}")
    logger.info(f"GeoJSON OK: {path}")


def validate_all(config: dict, api_key: str) -> None:
    """Master validation — runs all checks before any download starts."""
    # 1. Check dataset name
    validate_dataset(config["download"]["dataset"])

    # 2. Check API key exists
    if not api_key:
        raise EnvironmentError("API key missing. Check your .env file.")

    aoi = config["aoi"]

    # 3a. Batch mode: validate GeoJSON path
    if aoi.get("geojson_path"):
        validate_geojson(aoi["geojson_path"])

    # 3b. Single mode: validate bbox coordinates and area
    else:
        validate_bbox(aoi["bbox"])
        validate_bbox_area(aoi["bbox"], config["download"]["dataset"])

    logger.info("✓ All validations passed.")