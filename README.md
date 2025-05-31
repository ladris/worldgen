# Real-World Terrain to Unreal Engine Importer

## 1. Introduction

This Python tool facilitates the recreation of real-world locations within virtual environments like Unreal Engine 5.5. It automates the process of fetching geospatial elevation data, processing it, and converting it into heightmap formats compatible with Unreal Engine, aiming for a 1:1 scale representation. This tool is designed for developers, artists, and researchers looking to build high-fidelity digital twins, realistic game levels, or accurate simulations.

## 2. Features

*   Fetches Digital Elevation Model (DEM) data from online sources (currently supports OpenTopography API).
*   Determines Area of Interest (AOI) via:
    *   Direct bounding box (latitude, longitude) input.
    *   Place name geocoding (e.g., "Mount Everest") and a specified distance to define the surrounding area.
*   Processes raw DEM data:
    *   Reads standard GeoTIFF files.
    *   Scales elevation values to the 16-bit unsigned integer range (0-65535) required by Unreal Engine.
*   Outputs heightmaps in formats compatible with Unreal Engine:
    *   Single 16-bit grayscale PNG (.png).
    *   Single 16-bit raw binary (.r16) with an accompanying JSON sidecar file.
    *   Supports tiling of large DEMs into smaller, manageable heightmap chunks (PNG or RAW+JSON) compatible with Unreal Engine's World Partition.
*   Calculates precise X, Y, and Z scale factors and Z location offset for Unreal Engine import, ensuring accurate 1:1 terrain scale (applies globally for tiled landscapes).
*   Generates a human-readable report detailing all parameters needed for manual import into Unreal Engine, including tiling information if used.
*   Modular design for extensibility (e.g., adding new APIs, processing steps).
*   Configurable logging for monitoring and debugging.
*   Unit tests for core components to ensure reliability.

## 3. Core Technologies and Libraries Used

*   **Python 3.9+**
*   **Requests**: For making HTTP calls to web APIs (e.g., OpenTopography).
*   **Rasterio**: For reading, writing, and manipulating raster geospatial data (GeoTIFFs).
*   **GDAL**: (As a dependency of Rasterio) For comprehensive geospatial data format translation and processing.
*   **PyProj**: For cartographic projections and Coordinate Reference System (CRS) transformations.
*   **NumPy**: For numerical computation, especially array manipulation for raster data.
*   **Pillow (PIL Fork)**: For image processing, particularly saving NumPy arrays as 16-bit PNG files.
*   **Shapely**: (As a dependency of Rasterio or used directly) For geometric operations.
*   **Geopy**: For geocoding place names (converting addresses/names to coordinates) and calculating distances on Earth's surface.
*   **unittest & unittest.mock**: For unit testing.

## 4. Project Structure Overview

```
.
├── terrain_tool/                 # Main application package (if structured as such)
│   ├── main_controller.py        # Orchestrates the entire workflow
│   ├── api_handler.py            # Handles interactions with elevation data APIs
│   ├── dem_processor.py          # GIS and raster processing tasks (including tiling)
│   ├── coordinate_utils.py       # Coordinate transformation and geocoding functions
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
├── output_data_main_controller/  # Default directory for generated output files from main_controller
│   └── terrain_tiles/            # Default subdirectory for tiled output
├── output_data_test/             # Directory for test output files from individual module tests
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── LICENSE                       # Project license file
└── .gitignore                    # Specifies intentionally untracked files
```
*(Note: The `terrain_tool/` subdirectory is conceptual if you're running scripts directly from the root. If run as a package, imports would be relative like `from . import api_handler`)*

## 5. Setup and Installation

1.  **Prerequisites**:
    *   Python 3.9 or higher.
    *   `pip` (Python package installer).
    *   Git (for cloning the repository).
    *   GDAL: Rasterio depends on GDAL. Installation varies by OS:
        *   **Windows**: Consider using `pip install GDAL` after installing a precompiled binary (e.g., from [GISInternals](https://www.gisinternals.com/release.php) or via OSGeo4W). Alternatively, using Conda can simplify this: `conda install gdal`.
        *   **macOS**: `brew install gdal` or `conda install gdal`.
        *   **Linux**: `sudo apt-get install libgdal-dev gdal-bin` (Debian/Ubuntu) or equivalent for your distribution. `conda install gdal` is also an option.

2.  **Clone the Repository (if applicable)**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

3.  **Create a Virtual Environment (Recommended)**:
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

4.  **Install Dependencies**:
    A `requirements.txt` file is provided. Install using:
    ```bash
    pip install -r requirements.txt
    ```

## 6. Configuration

1.  **API Keys**:
    This tool requires API keys for some data sources. Currently, OpenTopography is supported.
    *   Sign up for an [OpenTopography API Key](https://portal.opentopography.org/myopentopo).
2.  **`config.json`**:
    *   Rename `config.json.example` to `config.json` in the root directory (or the same directory as `config_manager.py`).
    *   Edit `config.json` to add your API keys:
        ```json
        {
            "api_keys": {
                "OpenTopography": "YOUR_OPENTOPOGRAPHY_API_KEY_HERE"
            },
            "settings": {
                "default_output_path": "./output_data",
                "default_dem_resolution": 30
            }
        }
        ```
    *   Alternatively, API keys can be set as environment variables (e.g., `OPENTOPOGRAPHY_API_KEY="YOUR_KEY_HERE"`). Environment variables take precedence.
    *   **Important**: `config.json` is included in `.gitignore` and should **not** be committed to version control if it contains sensitive API keys.

## 7. Usage Guidelines

The primary entry point for the tool is `main_controller.py`.

1.  **Configure Input Parameters in `main_controller.py`**:
    Open `main_controller.py` and adjust parameters in the `# --- Configuration ---`, `# --- Input Mode ---`, and `# --- Tiling Configuration ---` sections:

    *   **`INPUT_MODE`**: Set to either `"BBOX"` or `"PLACENAME"`.
        *   `"BBOX"`: Uses manually defined bounding box coordinates via `AOI_BBOX_WGS84_MANUAL`.
        *   `"PLACENAME"`: Uses a place name (`PLACE_NAME_QUERY`), geocodes it to a center point, and calculates a bounding box based on `DISTANCE_KM_AROUND_PLACE`.

    *   **If `INPUT_MODE = "PLACENAME"`**:
        *   `PLACE_NAME_QUERY`: The place name string to geocode (e.g., `"Mount Everest"`, `"Denver, Colorado"`).
        *   `DISTANCE_KM_AROUND_PLACE`: The distance in kilometers to extend the bounding box around the geocoded center point (e.g., `15`).

    *   **If `INPUT_MODE = "BBOX"`**:
        *   `AOI_BBOX_WGS84_MANUAL`: The Area of Interest as a tuple `(west_longitude, south_latitude, east_longitude, north_latitude)` in WGS84 decimal degrees (e.g., `(86.85, 27.90, 87.00, 28.05)`).

    *   **Required for all modes**:
        *   `TARGET_UTM_EPSG`: The EPSG code for the target UTM zone corresponding to your AOI (e.g., `"EPSG:32645"` for UTM Zone 45N which covers Mount Everest). This is crucial for correct scaling in Unreal Engine and **must be set accurately by the user based on the final AOI's location.** You can find appropriate EPSG codes from sites like [epsg.io](https://epsg.io/).
        *   `DEM_TYPE_API`: The DEM type for the API (e.g., for OpenTopography: `"SRTMGL1"`).
        *   `OUTPUT_DIR`: Directory for output files (default: `./output_data_main_controller`).
        *   `OUTPUT_HEIGHTMAP_FORMAT`: Choose `"PNG"`, `"RAW"`, or `"BOTH"`.

    *   **Tiling Configuration (Optional)**:
        *   `ENABLE_TILING`: Set to `True` to enable tiling for large terrains, or `False` (default) for a single output heightmap.
        *   `TILE_SIZE_X_PX`, `TILE_SIZE_Y_PX`: Desired dimensions (width, height) of each tile in pixels (vertices). Common Unreal Engine landscape sizes like 505 (505x505), 1009 (1009x1009), 2017 (2017x2017) are recommended. These sizes are typically calculated as `((QuadsPerSection * SectionsPerComponent * NumComponents) + 1)`.
        *   `TILE_OUTPUT_DIR_NAME`: Name of the subdirectory (within `OUTPUT_DIR`) where tiles will be saved (e.g., `"terrain_tiles"`).
        *   `TILE_NAMING_PREFIX`: Prefix for tile filenames (e.g., `"tile"` resulting in `tile_X0_Y0.png`).

2.  **Run the Script**:
    ```bash
    python main_controller.py
    ```
    *(Or `python terrain_tool/main_controller.py` if you have it in a subdirectory and are running from the project root).*

## 8. Workflow Overview

The `main_controller.py` script performs the following steps:
1.  **Determines AOI**: Based on `INPUT_MODE`, either uses a predefined bounding box or geocodes a place name and calculates a bounding box.
2.  **Fetches DEM Data**: Downloads raw DEM data (usually GeoTIFF) for the determined AOI from the configured API.
3.  **Reads DEM Info**: Loads the downloaded DEM, extracting its properties (dimensions, CRS, NoData values).
4.  **Calculates Metric Size**: Transforms the AOI's WGS84 bounding box to the target UTM CRS to determine its precise width and height in meters.
5.  **Determines Pixel Resolution**: Calculates the effective ground resolution (meters/pixel) of the downloaded DEM based on its pixel dimensions and the AOI's metric size.
6.  **Scales Elevation Data**: Converts the DEM's elevation values (which are typically floats representing meters) into a 0-65535 unsigned 16-bit integer range. This step also captures the actual minimum and maximum elevation values of the AOI.
7.  **Saves Heightmap(s)**:
    *   If tiling is enabled (`ENABLE_TILING = True`), the scaled DEM is sliced into multiple tile files and saved in the specified format(s) (PNG and/or RAW+JSON) within a subdirectory.
    *   Otherwise, the single, full-size scaled DEM is saved in the specified format(s).
8.  **Calculates UE Parameters**: Determines the exact Scale X, Y, Z, and Location Z values needed for Unreal Engine import. These apply globally, even for tiled landscapes.
9.  **Generates Report**: Creates a text file summarizing the input parameters, processed data characteristics (including tiling details if applicable), and the calculated Unreal Engine import settings.

## 9. Output Explanation

After a successful run, you will find files in your specified `OUTPUT_DIR` (e.g., `./output_data_main_controller`):
*   `downloaded_dem.tif`: The original DEM file downloaded from the API.
*   **If Tiling is Disabled (`ENABLE_TILING = False`)**:
    *   `heightmap_ue.png` (if PNG format selected): The processed 16-bit grayscale heightmap.
    *   `heightmap_ue_raw.r16` (if RAW format selected): The raw 16-bit heightmap data.
    *   `heightmap_ue_raw.json` (if RAW format selected): JSON sidecar for the single `.r16` file.
*   **If Tiling is Enabled (`ENABLE_TILING = True`)**:
    *   A subdirectory named by `TILE_OUTPUT_DIR_NAME` (e.g., `terrain_tiles/`) containing:
        *   Multiple tile files, e.g., `tile_X0_Y0.png`, `tile_X0_Y1.png`, ... (if PNG format selected).
        *   And/or `tile_X0_Y0.r16`, `tile_X0_Y0.json`, ... (if RAW format selected).
    *   The JSON sidecar for each RAW tile (`.r16`) will contain metadata such as:
        *   `width`, `height`: Dimensions of that specific tile in pixels.
        *   `bbp`: Bits per pixel (typically 16).
        *   `format`: Data type ("uint16").
        *   `byte_order`: Byte order (e.g., "little", "big", "native").
        *   `min_elevation_original`, `max_elevation_original`: These refer to the original minimum and maximum elevation (in meters) of the **entire AOI** before tiling, ensuring consistent Z-scaling across all tiles.
*   `unreal_engine_import_guide.txt`: A text file with calculated parameters and import notes. If tiling was used, this report will include details about the tile dimensions, grid size, and naming.

## 10. Unreal Engine Import Steps

Refer to the `unreal_engine_import_guide.txt` generated by the tool. The general steps are:
1.  In Unreal Engine, open your project and go to **Landscape Mode** (Shift+2).
2.  Choose **Manage** mode, then click **New**.
3.  Select **Import from File**.
4.  Browse to and select your generated heightmap file(s).
    *   **For a single heightmap**: Select the `.png` or `.r16` file.
    *   **For Tiled Landscapes**:
        *   It is highly recommended to use Unreal Engine's **World Partition** system (enabled by default in new UE5 projects).
        *   Click the "Import Tiled Landscape" button in the Landscape panel.
        *   Select all your generated heightmap tiles (e.g., select all `tile_X*_Y*.png` or `tile_X*_Y*.r16` files). Unreal Engine will arrange them based on their filenames.
5.  Enter the **Scale X, Y, and Z** values provided in the report. These scales are global and apply to the entire landscape or all tiles.
6.  Set the **Landscape Actor's Z Location** (under its Transform details after creation) to the `Location Z` value from the report.
7.  Adjust **Section Size**, **Sections Per Component**, and **Number of Components** according to your heightmap's resolution (for single files) or tile dimensions (for tiled landscapes) and Unreal Engine's recommended landscape sizes. The report will indicate the dimensions of your generated heightmap(s).
8.  Click **Import**.

## 11. Running Tests

To run the unit tests:
1.  Ensure you are in the root directory of the project.
2.  Make sure your virtual environment is activated and dependencies are installed.
3.  Run the following command:
    ```bash
    python -m unittest discover tests
    ```
    This will automatically find and run all tests within the `tests` directory.

## 12. Future Enhancements/TODOs

*   **Graphical User Interface (GUI)**: Develop a GUI for easier parameter input.
*   **Command-Line Interface (CLI)**: Implement a proper CLI using `argparse`.
*   **More API Support**: Add integration for other elevation data sources.
*   **Automatic UTM Zone Detection**.
*   **Advanced DEM Processing**: Clipping, reprojection, resampling options.
*   **Unreal Engine Python Scripting**: Automate import into UE.
*   **Error Handling and Validation**: Enhance input validation.
*   **Packaging**: Package the tool for easier distribution.

## 13. Extra Resources

*   [OpenTopography API Documentation](https://opentopography.org/developers)
*   [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/): If using the place name geocoding feature, please be aware of Nominatim's usage policy.
*   [Unreal Engine Landscape Technical Guide](https://docs.unrealengine.com/en-US/BuildingWorlds/Landscape/TechnicalGuide/index.html)
*   [Unreal Engine World Partition](https://docs.unrealengine.com/en-US/BuildingWorlds/WorldPartition/)
*   [Unreal Engine Georeferencing Plugin](https://docs.unrealengine.com/en-US/BuildingWorlds/Georeferencing/index.html)
*   [Rasterio Documentation](https://rasterio.readthedocs.io/en/stable/)
*   [PyProj Documentation](https://pyproj4.github.io/pyproj/stable/)
*   [NumPy Documentation](https://numpy.org/doc/stable/)
*   [Pillow Documentation](https://pillow.readthedocs.io/en/stable/)
*   [EPSG.io](https://epsg.io/) - For finding EPSG codes.

## 14. Version History / Changelog

**v1.0.1 - 2023-10-28**
*   Added tiling functionality:
    *   DEMs can be split into multiple smaller heightmap tiles.
    *   Configuration options for enabling tiling and tile parameters in `main_controller.py`.
    *   UE import report updated to include tiling information.
*   Enhanced `coordinate_utils` with geocoding and bounding box calculation from center point.
*   Updated `main_controller` to support AOI definition by place name + distance or by manual BBox.

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
