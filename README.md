# DEM Toolbox

A lightweight Python toolbox for reproducible DEM acquisition from [OpenTopography](https://opentopography.org/).
Given a bounding box and dataset, it validates, tiles, downloads, and archives elevation data with full provenance.

---

```text
dem_toolbox/
├── configs/
│   ├── default_config.yaml        ← shared defaults
│   └── runs/
│       └── alps_2026.yaml         ← one YAML per download run
├── data/
│   ├── raw/                       ← downloaded tiles + JSON sidecars
│   ├── temp/                      ← intermediate files
│   └── processed/                 ← merged, reprojected, clipped DEMs
├── scripts/
│   └── download_dem.py            ← pipeline entry point
└── src/dem_toolbox/
    ├── etl/
    │   ├── validator.py           ← bbox + dataset checks
    │   ├── tiler.py               ← splits large AOIs into tiles
    │   ├── downloader.py          ← OpenTopography API requests
    │   └── processor.py           ← merge, reproject, clip
    └── utils/
        ├── config.py              ← YAML loading + config merger
        ├── io.py                  ← file management + metadata sidecars
        └── logger.py              ← structured logging
```

---

## Quickstart

**1. Install**
```bash
git clone https://github.com/yourname/dem_toolbox.git
cd dem_toolbox
pip install -e .
```

**2. Add API key**
```bash
echo "OT_API_KEY=your_key_here" > .env
```
Get a free key at [opentopography.org](https://opentopography.org/developers).

**3. Create a run config**
```yaml
# configs/runs/my_area.yaml
aoi:
  job_name: my_area
  bbox:
    west: 7.9
    south: 46.4
    east: 8.02
    north: 46.47

download:
  dataset: GLO30
```

**4. Run**
```bash
python scripts/download_dem.py --config configs/runs/my_area.yaml
```

---

## Supported Datasets

| Dataset | Resolution | Coverage |
|---------|-----------|----------|
| GLO30   | ~30 m     | Global   |
| GLO90   | ~90 m     | Global   |
| SRTMGL1 | ~30 m     | ±60° lat |
| SRTMGL3 | ~90 m     | ±60° lat |

---

## Output

Each run produces a GeoTIFF tile and a JSON provenance sidecar in `data/raw/`:

```json
{
  "file": "GLO30_my_area_tile_00_00_....tif",
  "job_name": "my_area",
  "dataset": "GLO30",
  "bbox": { "west": 7.9, "south": 46.4, "east": 8.02, "north": 46.47 },
  "downloaded_at": "2026-05-05T13:58:59Z",
  "source": "OpenTopography"
}
```

---

## Requirements

- Python ≥ 3.10
- `rasterio`, `shapely`, `requests`, `pyyaml`, `python-dotenv`

---

## Data Sources

Elevation data provided by [OpenTopography](https://opentopography.org).
Copernicus DEM © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018.
SRTM data courtesy of NASA/USGS — public domain.

---

## License

This project is licensed under the [MIT License](LICENSE).