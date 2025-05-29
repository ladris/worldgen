# Real-World Terrain to Unreal Engine Importer

## 1. Introduction

This Python tool facilitates the recreation of real-world locations within virtual environments like Unreal Engine 5.5. It automates the process of fetching geospatial elevation data, processing it, and converting it into heightmap formats compatible with Unreal Engine, aiming for a 1:1 scale representation. This tool is designed for developers, artists, and researchers looking to build high-fidelity digital twins, realistic game levels, or accurate simulations.

## 2. Features

*   Fetches Digital Elevation Model (DEM) data from online sources (currently supports OpenTopography API).
*   Processes raw DEM data:
    *   Reads standard GeoTIFF files.
    *   Scales elevation values to the 16-bit unsigned integer range (0-65535) required by Unreal Engine.
*   Outputs heightmaps in formats compatible with Unreal Engine:
    *   16-bit grayscale PNG (.png)
    *   16-bit raw binary (.r16) with an accompanying JSON sidecar file.
*   Calculates precise X, Y, and Z scale factors and Z location offset for Unreal Engine import, ensuring accurate 1:1 terrain scale.
*   Generates a human-readable report detailing all parameters needed for manual import into Unreal Engine.
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
*   **unittest & unittest.mock**: For unit testing.

## 4. Project Structure Overview

```
.
├── terrain_tool/                 # Main application package (if structured as such)
│   ├── main_controller.py        # Orchestrates the entire workflow
│   ├── api_handler.py            # Handles interactions with elevation data APIs
│   ├── dem_processor.py          # GIS and raster processing tasks
│   ├── coordinate_utils.py       # Coordinate transformation functions
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
├── output_data_main/             # Default directory for generated output files
├── output_data_test/             # Directory for test output files
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

1.  **Modify Parameters in `main_controller.py`**:
    Open `main_controller.py` and adjust the following parameters in the `# --- Configuration ---` section:
    *   `AOI_BBOX_WGS84`: The Area of Interest as a tuple `(west_longitude, south_latitude, east_longitude, north_latitude)` in WGS84 decimal degrees.
    *   `TARGET_UTM_EPSG`: The EPSG code for the target UTM zone corresponding to your AOI (e.g., `"EPSG:32611"` for UTM Zone 11N). You can find appropriate EPSG codes from sites like [epsg.io](https://epsg.io/).
    *   `DEM_TYPE_API`: The DEM type to request from the API (e.g., for OpenTopography: `"SRTMGL1"`, `"NASADEM"`, `"COP30"`). Check API documentation for available types.
    *   `OUTPUT_DIR`: Directory where all output files will be saved.
    *   `OUTPUT_HEIGHTMAP_FORMAT`: Choose `"PNG"`, `"RAW"`, or `"BOTH"`.

2.  **Run the Script**:
    ```bash
    python main_controller.py
    ```
    *(Or `python terrain_tool/main_controller.py` if you have it in a subdirectory and are running from the project root).*

## 8. Workflow Overview

The `main_controller.py` script performs the following steps:
1.  **Fetches DEM Data**: Downloads raw DEM data (usually GeoTIFF) for the specified AOI from the configured API.
2.  **Reads DEM Info**: Loads the downloaded DEM, extracting its properties (dimensions, CRS, NoData values).
3.  **Calculates Metric Size**: Transforms the AOI's WGS84 bounding box to the target UTM CRS to determine its precise width and height in meters.
4.  **Determines Pixel Resolution**: Calculates the effective ground resolution (meters/pixel) of the downloaded DEM based on its pixel dimensions and the AOI's metric size.
5.  **Scales Elevation Data**: Converts the DEM's elevation values (which are typically floats representing meters) into a 0-65535 unsigned 16-bit integer range. This step also captures the actual minimum and maximum elevation values of the AOI.
6.  **Saves Heightmap**: Saves the scaled 16-bit data as:
    *   A 16-bit grayscale PNG file.
    *   And/or a 16-bit raw binary file (`.r16`) with an accompanying JSON sidecar file (e.g., `heightmap_ue_raw.json`) detailing its dimensions, bit depth, and original elevation range.
7.  **Calculates UE Parameters**: Determines the exact Scale X, Y, Z, and Location Z values needed for Unreal Engine import.
8.  **Generates Report**: Creates a text file summarizing the input parameters, processed data characteristics, and the calculated Unreal Engine import settings.

## 9. Output Explanation

After a successful run, you will find the following files in your specified `OUTPUT_DIR`:
*   `downloaded_dem.tif`: The original DEM file downloaded from the API.
*   `heightmap_ue.png` (if PNG format selected): The processed 16-bit grayscale heightmap ready for Unreal Engine.
*   `heightmap_ue_raw.r16` (if RAW format selected): The raw 16-bit heightmap data.
*   `heightmap_ue_raw.json` (if RAW format selected): The JSON sidecar file for the `.r16` heightmap, containing metadata such as:
    *   `width`: Width of the heightmap in pixels.
    *   `height`: Height of the heightmap in pixels.
    *   `bbp`: Bits per pixel (typically 16).
    *   `format`: Data type of the raw pixels (e.g., "uint16").
    *   `byte_order`: Byte order of the raw data (e.g., "little" for little-endian, "big" for big-endian, or "native").
    *   `min_elevation_original`: The original minimum elevation (in meters) of the Area of Interest that corresponds to the value 0 in the scaled heightmap.
    *   `max_elevation_original`: The original maximum elevation (in meters) of the Area of Interest that corresponds to the value 65535 in the scaled heightmap.
*   `unreal_engine_import_guide.txt`: A text file with all the calculated parameters (Scale X, Y, Z; Location Z) and notes for importing the landscape into Unreal Engine.

## 10. Unreal Engine Import Steps

Refer to the `unreal_engine_import_guide.txt` generated by the tool. The general steps are:
1.  In Unreal Engine, open your project and go to **Landscape Mode** (Shift+2).
2.  Choose **Manage** mode, then click **New**.
3.  Select **Import from File**.
4.  Browse to and select your generated heightmap file (either the `.png` or the `.r16` file – UE will use the `.json` sidecar for the `.r16`).
5.  Enter the **Scale X, Y, and Z** values provided in the report.
6.  Set the **Landscape Actor's Z Location** (under its Transform details after creation, or sometimes available during import) to the `Location Z` value from the report. This ensures the landscape is positioned correctly relative to sea level (if your min elevation was sea level).
7.  Adjust **Section Size**, **Sections Per Component**, and **Number of Components** according to your heightmap's resolution and Unreal Engine's recommended landscape sizes (see Unreal Engine Landscape Technical Guide). The report will indicate the dimensions of your generated heightmap.
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

*   **Graphical User Interface (GUI)**: Develop a GUI (e.g., using Tkinter, PyQt, or a web framework like Flask/Django) for easier parameter input and workflow management.
*   **Command-Line Interface (CLI)**: Implement a proper CLI using `argparse` for more flexible script execution.
*   **More API Support**: Add integration for other elevation data sources (e.g., USGS 3DEP via `seamless-3dep`, NASA AppEEARS, OpenTopoData).
*   **Automatic UTM Zone Detection**: Implement logic to automatically determine the correct UTM zone for the AOI.
*   **Advanced DEM Processing**:
    *   Implement optional clipping of the downloaded DEM if it's larger than the AOI.
    *   Implement reprojection of the DEM to different CRSs if needed.
    *   Implement resampling to user-defined output resolutions.
*   **Tiling for Large Terrains**: Add support for tiling large DEMs into smaller, manageable heightmap chunks compatible with Unreal Engine's World Partition system.
*   **Unreal Engine Python Scripting**: Explore generating a Python script to automate the import process directly within Unreal Engine.
*   **Error Handling and Validation**: Enhance input validation and error reporting.
*   **Packaging**: Package the tool for easier distribution (e.g., using PyInstaller or as a pip-installable package).

## 13. Extra Resources

*   [OpenTopography API Documentation](https://opentopography.org/developers)
*   [Unreal Engine Landscape Technical Guide](https://docs.unrealengine.com/en-US/BuildingWorlds/Landscape/TechnicalGuide/index.html)
*   [Unreal Engine Georeferencing Plugin](https://docs.unrealengine.com/en-US/BuildingWorlds/Georeferencing/index.html)
*   [Rasterio Documentation](https://rasterio.readthedocs.io/en/stable/)
*   [PyProj Documentation](https://pyproj4.github.io/pyproj/stable/)
*   [NumPy Documentation](https://numpy.org/doc/stable/)
*   [Pillow Documentation](https://pillow.readthedocs.io/en/stable/)
*   [EPSG.io](https://epsg.io/) - For finding EPSG codes.

## 14. Version History / Changelog

**v1.0.0 (Current Version) - 2023-10-27**
*   Initial release.
*   Core functionality:
    *   Fetch DEM from OpenTopography.
    *   Process DEM to 16-bit heightmap (PNG & RAW+JSON).
    *   Calculate UE scale and location parameters.
    *   Generate import report.
*   Modules: `main_controller`, `api_handler`, `dem_processor`, `coordinate_utils`, `unreal_preparer`, `config_manager`, `logger_setup`.
*   Basic unit tests for `config_manager`, `coordinate_utils`, `unreal_preparer`.

## 15. License

This project is licensed under the MIT License. See the `LICENSE` file for details.
