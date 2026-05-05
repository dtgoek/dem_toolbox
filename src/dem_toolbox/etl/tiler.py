import math
from dataclasses import dataclass
from dem_toolbox.utils.logger import get_logger
from dem_toolbox.etl.validator import DATASET_LIMITS

logger = get_logger(__name__)


@dataclass
class Tile:
    """Represents a single tile with its bbox and grid position."""
    row: int
    col: int
    west: float
    south: float
    east: float
    north: float
    dataset: str
    job_name: str

    @property
    def filename(self) -> str:
        """
        Generate meaningful, parseable filename for this tile.
        Format: {dataset}_{job_name}_tile_{row:02d}_{col:02d}_W{w}S{s}_E{e}N{n}.tif
        Uses 'p' instead of '.' in coordinates to avoid parsing issues.
        Example: GLO30_alps_tile_00_01_W7p9000S46p4000_E8p0200N46p4700.tif
        """
        def fmt(v: float) -> str:
            return f"{abs(v):.4f}".replace(".", "p")

        w_str = f"W{fmt(self.west)}" if self.west >= 0 else f"W-{fmt(self.west)}"
        s_str = f"S{fmt(self.south)}" if self.south >= 0 else f"S-{fmt(self.south)}"
        e_str = f"E{fmt(self.east)}" if self.east >= 0 else f"E-{fmt(self.east)}"
        n_str = f"N{fmt(self.north)}" if self.north >= 0 else f"N-{fmt(self.north)}"

        return (
            f"{self.dataset}_{self.job_name}_"
            f"tile_{self.row:02d}_{self.col:02d}_"
            f"{w_str}{s_str}_{e_str}{n_str}.tif"
        )


def _bbox_area_km2(west: float, south: float,
                   east: float, north: float) -> float:
    """Calculate bbox area in km² using equal-area projection."""
    import pyproj
    from shapely.geometry import box
    from shapely.ops import transform

    project = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:6933", always_xy=True
    ).transform
    return transform(project, box(west, south, east, north)).area / 1e6


def split_bbox(bbox: dict, dataset: str, job_name: str,
               safety_factor: float = 0.7) -> list[Tile]:
    """
    Split a bbox into area-safe tiles for the given dataset.
    - Single tile if bbox fits within safe limit
    - N×M grid of tiles if bbox exceeds safe limit

    Args:
        bbox: dict with west/south/east/north keys
        dataset: 'GLO30' or 'SRTM3'
        job_name: used in output filenames
        safety_factor: fraction of OT API limit to target per tile

    Returns:
        List of Tile objects sorted by row then col
    """
    w = bbox["west"]
    s = bbox["south"]
    e = bbox["east"]
    n = bbox["north"]

    total_area = _bbox_area_km2(w, s, e, n)
    safe_limit = DATASET_LIMITS[dataset]

    logger.info(
        f"Total AOI area: {total_area:,.0f} km² | "
        f"Safe limit per tile: {safe_limit:,.0f} km²"
    )

    if total_area <= safe_limit:
        logger.info("AOI fits within limit — no tiling required.")
        return [Tile(row=0, col=0, west=w, south=s, east=e,
                     north=n, dataset=dataset, job_name=job_name)]

    # Calculate grid dimensions
    n_tiles = math.ceil(total_area / safe_limit)
    n_cols = math.ceil(math.sqrt(n_tiles))
    n_rows = math.ceil(n_tiles / n_cols)

    lon_step = (e - w) / n_cols
    lat_step = (n - s) / n_rows

    logger.info(
        f"Splitting into {n_rows} rows × {n_cols} cols = "
        f"{n_rows * n_cols} tiles"
    )

    tiles = []
    for row in range(n_rows):
        for col in range(n_cols):
            tile_w = round(w + col * lon_step, 6)
            tile_e = round(w + (col + 1) * lon_step, 6)
            tile_s = round(s + row * lat_step, 6)
            tile_n = round(s + (row + 1) * lat_step, 6)

            tiles.append(Tile(
                row=row, col=col,
                west=tile_w, south=tile_s,
                east=tile_e, north=tile_n,
                dataset=dataset, job_name=job_name
            ))

    return tiles