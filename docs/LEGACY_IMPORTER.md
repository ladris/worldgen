# Legacy: Real-World Terrain → Unreal Importer (single-shot CLI)

> This is the **original tool** the project grew from: a one-shot command-line
> importer that fetches a DEM for an area and writes Unreal-ready heightmaps. It
> still works and is maintained, but new work happens in the **terrain service**
> (`terrain_service/`) and **Unreal plugin** (`unreal/`). For the streaming,
> editable, VR system, start at the repo [README](../README.md) and
> [QUICKSTART](QUICKSTART.md).

## What it does

Fetches Digital Elevation Model (DEM) data, processes it, and converts it into
16-bit heightmaps for Unreal Engine at 1:1 scale — as a single file or tiled.

- Fetches DEMs from OpenTopography.
- AOI by **place name + distance** (geocoded) or explicit **bounding box**.
- Automatic UTM zone / EPSG detection for placename mode (overridable).
- Scales elevation to 16-bit (0–65535); outputs PNG and/or RAW (`.r16` + JSON).
- Optional tiling for World Partition.
- Computes UE X/Y/Z scale + Z-location and writes a human-readable import guide.

## Install

```bash
pip install -r requirements.txt   # legacy deps (GDAL via rasterio, geopy, etc.)
```

## Configure (API key)

Sign up for a free [OpenTopography key](https://portal.opentopography.org/myopentopo).
Provide it via `config.json` (gitignored), the `OPENTOPOGRAPHY_API_KEY`
environment variable, or `--api_key`.

```json
{ "api_keys": { "OpenTopography": "YOUR_KEY_HERE" },
  "settings": { "default_output_path": "./output_data" } }
```

## Usage

```bash
python main_controller.py [AOI_OPTIONS] [OTHER_OPTIONS]
```

**AOI (choose one):**
- `--placename "Eiffel Tower, Paris" --distance 10` (km radius), or
- `--bbox WEST SOUTH EAST NORTH` (WGS84 degrees).

**Projection:** `--utm_epsg EPSG:32613` (required with `--bbox`; auto-detected
with `--placename`).

**Data:** `--dem_type SRTMGL1` (default), `--api_key …`.

**Output:** `--output_dir ./out`, `--output_format {PNG|RAW|BOTH}` (default BOTH).

**Tiling:** `--enable_tiling --tile_size_x 1009 --tile_size_y 1009` (tiles saved
under `terrain_tiles/`).

### Examples

```bash
# Eiffel Tower, 10 km, PNG tiles, auto UTM
python main_controller.py --placename "Eiffel Tower, Paris" --distance 10 \
    --enable_tiling --tile_size_x 505 --tile_size_y 505 --output_format PNG

# Colorado bbox, single RAW file, explicit UTM zone
python main_controller.py --bbox -105.0 39.7 -104.9 39.8 \
    --utm_epsg EPSG:32613 --output_format RAW --output_dir ./denver_terrain
```

## Output

- `downloaded_dem.tif` — raw fetched DEM.
- Single mode: `heightmap_ue.png`, `heightmap_ue_raw.r16` + `.json`.
- Tiled mode: `terrain_tiles/tile_Xn_Ym.{png,r16,json}` (JSON carries overall
  AOI min/max elevation).
- `unreal_engine_import_guide.txt` — scales and steps for manual UE import.

## Tests

```bash
python -m unittest discover tests
```

## Modules

`main_controller` · `api_handler` · `dem_processor` · `coordinate_utils` ·
`unreal_preparer` · `config_manager` · `logger_setup`.

## Relationship to the new system

The legacy tool validated the core idea (real DEM → correct-scale UE heightmap).
The terrain service generalises it into a deterministic, tile-grid-aligned,
cacheable, **editable** service with a strict client contract — see
[ARCHITECTURE](ARCHITECTURE.md). Notably, the service fixes the legacy tool's
per-tile elevation scaling (which would seam between tiles) with project-wide
**absolute encoding**, and adds reprojection/resampling onto an exact grid.
