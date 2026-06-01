# worldgen — Dynamic World Streaming

**Goal:** an Unreal Engine avatar walks in any direction, forever, across the
**real Earth**, and terrain materialises seamlessly ahead of them — no loading
screens, no visible seams, generated on the fly from real DEM data.

This repo has two halves that meet at one strict contract:

1. **Python terrain service** (`terrain_service/`) — turns real-world DEM data
   into a deterministic, seamlessly-tileable grid of heightmaps, served over
   HTTP. Fully built and tested.
2. **Unreal C++ plugin** (`unreal/DynamicWorldStreaming/`) — predictively
   streams those tiles into a seamless world at runtime
   (`UDynamicMeshComponent` tiles, stitching, LOD, async collision). Written to
   UE 5.5 APIs; compiled in-engine by you.

**Start here:**
- `docs/ARCHITECTURE.md` — the master blueprint.
- `docs/CONTRACT.md` — the WorldGrid + data contract both halves implement.
- `docs/ROADMAP.md` — phased status.
- `unreal/DynamicWorldStreaming/SETUP.md` — how to run it end to end.

**Quick start (Python service, no API key needed):**

```bash
pip install -r requirements-service.txt
python -m terrain_service.cli init --project-id demo \
    --lat 39.7392 --lon -104.9903 --provider synthetic -o demo.json
python -m terrain_service.cli serve -c demo.json --port 8000
# then point the Unreal plugin at http://127.0.0.1:8000
```

Run the test suite: `python -m pytest tests_service/`.

---

> The section below documents the **original single-shot importer tool**, which
> remains available and is the proof-of-concept the streaming service grew from.

# Real-World Terrain to Unreal Engine Importer

## 1. Introduction

This Python tool facilitates the recreation of real-world locations within virtual environments like Unreal Engine 5.5. It automates the process of fetching geospatial elevation data, processing it, and converting it into heightmap formats compatible with Unreal Engine, aiming for a 1:1 scale representation. This tool is designed for developers, artists, and researchers looking to build high-fidelity digital twins, realistic game levels, or accurate simulations.

## 2. Features

*   Fetches Digital Elevation Model (DEM) data from online sources (currently supports OpenTopography API).
*   Determines Area of Interest (AOI) via:
    *   Command-line input of direct bounding box (latitude, longitude).
    *   Command-line input of a place name (geocoded to a center point) and a specified distance to define the surrounding area.
*   Automatic UTM zone and EPSG code detection when AOI is defined by placename (can be overridden).
*   Processes raw DEM data:
    *   Reads standard GeoTIFF files.
    *   Scales elevation values to the 16-bit unsigned integer range (0-65535) required by Unreal Engine.
*   Outputs heightmaps in formats compatible with Unreal Engine:
    *   Single 16-bit grayscale PNG (.png).
    *   Single 16-bit raw binary (.r16) with an accompanying JSON sidecar file.
    *   Supports tiling of large DEMs into smaller, manageable heightmap chunks (PNG or RAW+JSON) compatible with Unreal Engine's World Partition.
*   Calculates precise X, Y, and Z scale factors and Z location offset for Unreal Engine import, ensuring accurate 1:1 terrain scale (applies globally for tiled landscapes).
*   Generates a human-readable report detailing all parameters needed for manual import into Unreal Engine, including tiling information if used.
*   Modular design for extensibility.
*   Configurable logging for monitoring and debugging.
*   Unit tests for core components.

## 3. Core Technologies and Libraries Used

*   **Python 3.9+**
*   **argparse**: For parsing command-line arguments.
*   **Requests**: For making HTTP calls to web APIs.
*   **Rasterio**: For reading, writing, and manipulating raster geospatial data.
*   **GDAL**: (As a dependency of Rasterio).
*   **PyProj**: For cartographic projections and CRS transformations.
*   **NumPy**: For numerical computation.
*   **Pillow (PIL Fork)**: For image processing (saving 16-bit PNGs).
*   **Shapely**: For geometric operations.
*   **Geopy**: For geocoding place names and calculating distances.
*   **utm**: For converting latitude/longitude to UTM zone numbers and determining EPSG codes.
*   **unittest & unittest.mock**: For unit testing.

## 4. Project Structure Overview

```
.
├── terrain_tool/                 # Main application package (if structured as such)
│   ├── main_controller.py        # Orchestrates the entire workflow via CLI
│   ├── api_handler.py            # Handles interactions with elevation data APIs
│   ├── dem_processor.py          # GIS and raster processing tasks (including tiling)
│   ├── coordinate_utils.py       # Coordinate transformation, geocoding, UTM functions
│   ├── unreal_preparer.py        # Calculates UE specific parameters and generates reports
│   ├── config_manager.py         # Manages configuration (API keys, paths)
│   ├── logger_setup.py           # Configures logging
│   ├── config.json.example       # Example configuration file structure
│   └── ... (other modules)
├── tests/                        # Unit tests
│   ├── __init__.py
│   ├── test_config_manager.py
│   ├── test_coordinate_utils.py
│   ├── ... (other test files)
├── output_data_cli/              # Default directory for generated output files when using CLI
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── LICENSE                       # Project license file
└── .gitignore                    # Specifies intentionally untracked files
```
*(Note: The `terrain_tool/` subdirectory is conceptual if you're running scripts directly from the root.)*

## 5. Setup and Installation

1.  **Prerequisites**:
    *   Python 3.9 or higher.
    *   `pip` (Python package installer).
    *   Git (for cloning the repository).
    *   GDAL: Rasterio depends on GDAL. Installation varies by OS (see README section in project for details, or use Conda: `conda install gdal`).

2.  **Clone the Repository (if applicable)**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

3.  **Create a Virtual Environment (Recommended)**:
    ```bash
    python -m venv venv
    # On Windows: venv\Scripts\activate
    # On macOS/Linux: source venv/bin/activate
    ```

4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 6. Configuration

1.  **API Keys (Optional - Can be passed via CLI)**:
    *   For OpenTopography: Sign up at [OpenTopography API Key](https://portal.opentopography.org/myopentopo).
    *   Keys can be stored in `config.json` (renamed from `config.json.example`) or as environment variables (e.g., `OPENTOPOGRAPHY_API_KEY`). CLI `--api_key` argument overrides these.
    *   **Important**: `config.json` is in `.gitignore`; do not commit sensitive keys.
        ```json
        {
            "api_keys": { "OpenTopography": "YOUR_KEY_HERE" },
            "settings": { "default_output_path": "./output_data" }
        }
        ```

## 7. Usage Guidelines

The tool is operated via the command line using `main_controller.py`.

**Command Structure:**
```bash
python main_controller.py [AOI_OPTIONS] [OTHER_OPTIONS]
```

**Area of Interest (AOI) Options (Required - Choose one method):**

*   **Method 1: By Place Name & Distance:**
    *   `--placename "Your Place Name"`: Specify the name of the location (e.g., "Mount Everest", "Denver, Colorado").
    *   `--distance KILOMETERS`: Specify the distance in kilometers to extend the bounding box around the geocoded center of the placename. *Required if `--placename` is used.*

*   **Method 2: By Bounding Box:**
    *   `--bbox WEST SOUTH EAST NORTH`: Specify the exact bounding box coordinates in WGS84 decimal degrees (e.g., `--bbox 2.25 48.8 2.35 48.9`).

**Projection Options:**

*   `--utm_epsg EPSG_CODE`: Specify the target UTM EPSG code (e.g., `"EPSG:32611"`).
    *   If using `--placename` and this is **not** provided, the tool will attempt to auto-detect the UTM zone and corresponding EPSG code.
    *   If using `--bbox`, this argument is **required** for accurate projection calculations. Look up codes on [epsg.io](https://epsg.io/).

**API & Data Source Options:**

*   `--dem_type DEM_TYPE_NAME`: Specify the DEM type for the API (e.g., `"SRTMGL1"`, `"NASADEM"` for OpenTopography).
    *   Default: `"SRTMGL1"`
*   `--api_key YOUR_API_KEY`: Optionally provide your API key directly. This overrides keys from `config.json` or environment variables.

**Output Options:**

*   `--output_dir PATH_TO_DIRECTORY`: Specify the directory where all output files will be saved.
    *   Default: `"./output_data_cli"`
*   `--output_format {PNG|RAW|BOTH}`: Choose the output format for the heightmap(s).
    *   Default: `"BOTH"`

**Tiling Options (Optional):**

*   `--enable_tiling`: Enable this flag to process the terrain as multiple tiles. If omitted, a single heightmap file is generated.
*   `--tile_size_x PIXELS`: Desired width of each tile in pixels (vertices).
    *   Default: `1009`
*   `--tile_size_y PIXELS`: Desired height of each tile in pixels (vertices).
    *   Default: `1009`
    *(Note: Tiles are saved in a subdirectory named "terrain_tiles" within your specified `--output_dir`, using a prefix "tile".)*


**Examples:**

1.  **Get terrain for Eiffel Tower, 10km radius, output as PNG tiles (UTM auto-detected):**
    ```bash
    python main_controller.py --placename "Eiffel Tower, Paris" --distance 10 --enable_tiling --tile_size_x 505 --tile_size_y 505 --output_format PNG
    ```

2.  **Get terrain for a specific bounding box in Colorado, output as single RAW file, specifying UTM zone:**
    ```bash
    python main_controller.py --bbox -105.0 39.7 -104.9 39.8 --utm_epsg EPSG:32613 --output_format RAW --output_dir ./denver_terrain
    ```

## 8. Workflow Overview

The `main_controller.py` script, driven by command-line arguments, performs the following:
1.  **Parses CLI Arguments**: Determines all operational parameters.
2.  **Determines AOI**: Based on chosen mode (`--placename` or `--bbox`).
3.  **Determines UTM EPSG**: Uses provided `--utm_epsg` or auto-detects if using placename mode.
4.  **Fetches DEM Data**: Downloads raw DEM for the AOI.
5.  **Reads DEM Info**: Extracts properties (dimensions, CRS).
6.  **Calculates Metric Size**: Transforms AOI BBox to determined UTM for metric sizing.
7.  **Determines Pixel Resolution**: Based on DEM dimensions and AOI metric size.
8.  **Scales Elevation Data**: Converts to uint16 range, capturing min/max elevations.
9.  **Saves Heightmap(s)**: Either as a single file or as multiple tiles if `--enable_tiling` is used.
10. **Calculates UE Parameters**: For Unreal Engine import scales and location.
11. **Generates Report**: Summarizing all inputs, data, and UE parameters.

## 9. Output Explanation
(This section remains largely the same as before, but it's understood that the output directory is now specified by `--output_dir`)
*   `downloaded_dem.tif`
*   If Tiling Disabled: `heightmap_ue.png`, `heightmap_ue_raw.r16`, `heightmap_ue_raw.json`
*   If Tiling Enabled: A subdirectory `terrain_tiles/` with `tile_Xn_Ym.png`, `tile_Xn_Ym.r16`, `tile_Xn_Ym.json`. JSONs contain overall AOI min/max elevation.
*   `unreal_engine_import_guide.txt`

## 10. Unreal Engine Import Steps
(This section remains largely the same, with the addition for tiled landscapes)
*   ...
*   **For Tiled Landscapes**:
    *   Use Unreal Engine's **World Partition** system.
    *   Use the "Import Tiled Landscape" feature.
    *   Global Scale X, Y, Z and Location Z from report apply to all tiles.

## 11. Running Tests
```bash
python -m unittest discover tests
```

## 12. Future Enhancements/TODOs
*   GUI.
*   More API Support.
*   Advanced DEM Processing (clipping, reprojection, resampling).
*   UE Python Scripting for import.
*   Packaging.

## 13. Extra Resources
*   [OpenTopography API Documentation](https://opentopography.org/developers)
*   [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/): Be mindful of this for geocoding.
*   [Unreal Engine Landscape Technical Guide](https://docs.unrealengine.com/en-US/BuildingWorlds/Landscape/TechnicalGuide/index.html)
*   [Unreal Engine World Partition](https://docs.unrealengine.com/en-US/BuildingWorlds/WorldPartition/)
*   ... (other library links) ...
*   [utm library documentation](https://github.com/Turbo87/utm) (or PyPI)

## 14. Version History / Changelog

**v1.0.2 - 2023-10-29**
*   Implemented Command-Line Interface (CLI) using `argparse` for all major inputs.
*   Added automatic UTM zone and EPSG code detection (using `utm` library) when AOI is defined by placename and `--utm_epsg` is not provided.
*   Removed hardcoded AOI and most output parameters from `main_controller.py` in favor of CLI arguments.

**v1.0.1 - 2023-10-28**
*   Added tiling functionality:
    *   DEMs can be split into multiple smaller heightmap tiles.
    *   Configuration options for enabling tiling and tile parameters.
    *   UE import report updated to include tiling information.
*   Enhanced `coordinate_utils` with geocoding and bounding box calculation from center point.
*   Updated `main_controller` to support AOI definition by place name + distance or by manual BBox (via hardcoded variables).

**v1.0.0 - 2023-10-27**
*   Initial release.
*   Core functionality:
    *   Fetch DEM from OpenTopography based on BBox.
    *   Process DEM to 16-bit heightmap (single PNG & RAW+JSON).
    *   Calculate UE scale and location parameters.
    *   Generate import report.
*   Modules: `main_controller`, `api_handler`, `dem_processor`, `coordinate_utils`, `unreal_preparer`, `config_manager`, `logger_setup`.
*   Basic unit tests for `config_manager`, `coordinate_utils`, `unreal_preparer`.

## 15. License

This project is licensed under the MIT License. See the `LICENSE` file for details.
