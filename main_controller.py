# main_controller.py
import os
import sys
import logging # Fallback for initial logger setup if logger_setup fails
import numpy as np # Added NumPy import

# Attempt to import all necessary modules.
# Assuming all .py files are in the same directory or PYTHONPATH is configured.
try:
    from logger_setup import setup_logger
    import config_manager
    import api_handler
    import dem_processor
    import coordinate_utils
    import unreal_preparer
except ImportError as e:
    # Use basic logging for this critical error as setup_logger might have failed
    logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.error(f"CRITICAL IMPORT ERROR: {e}. Ensure all required module files "
                  "(logger_setup.py, config_manager.py, api_handler.py, dem_processor.py, "
                  "coordinate_utils.py, unreal_preparer.py) are present in the "
                  "same directory or Python path.")
    sys.exit(1)

# --- Configuration ---
# TODO: Replace with argparse or a dedicated configuration file (e.g., YAML/JSON) for user input.

# --- Input Mode ---
INPUT_MODE = "BBOX"      # Use direct bounding box coordinates for tiling test
# INPUT_MODE = "PLACENAME" # Use place name geocoding and distance

# Parameters for PLACENAME mode (not used if INPUT_MODE is BBOX for this test)
PLACE_NAME_QUERY = "Mount Everest"
DISTANCE_KM_AROUND_PLACE = 15 # Kilometers around the geocoded center point

# Parameters for BBOX mode
# Using a generic extent for the dummy GeoTIFF created by _create_dummy_geotiff,
# which has its origin at (0,0) and y decreases downwards.
# Its extent is (0, -height, width, 0) in its own CRS (EPSG:4326 for the dummy).
# For a 600x400 dummy: (0.0, -400.0, 600.0, 0.0) - This was incorrect for WGS84 degrees.
# Using a small, valid WGS84 BBox for testing the flow.
# The dummy downloaded_dem.tif (600x400) will be used as the source data,
# but the georeferencing calculations will be based on this realistic BBox.
AOI_BBOX_WGS84_MANUAL = (-112.1100, 36.0550, -112.1000, 36.0600) # Small Grand Canyon area

# TARGET_UTM_EPSG: For Grand Canyon example area (approx 36.0N, 112.1W), UTM Zone 12N
TARGET_UTM_EPSG = "EPSG:32612"

DEM_TYPE_API = "SRTMGL1" # Not used if API call is skipped for this test (but kept for consistency)

OUTPUT_DIR = "./output_data_main_controller"
RAW_DEM_FILENAME = "downloaded_dem.tif" # This will be our dummy file
HEIGHTMAP_PNG_FILENAME = "heightmap_ue.png"
HEIGHTMAP_RAW_BASENAME = "heightmap_ue_raw"
UE_REPORT_FILENAME = "unreal_engine_import_guide.txt"

OUTPUT_HEIGHTMAP_FORMAT = "BOTH"

# --- Tiling Configuration ---
ENABLE_TILING = True # Set to True to enable tiling for this test
# Common Unreal Engine Landscape sizes (vertices, not components or quads)
# e.g., 64x64, 127x127, 253x253, 505x505, 1009x1009, 2017x2017, 4033x4033, 8129x8129
# Choose dimensions that are ((QuadsPerSection * SectionsPerComponent) * NumComponents) + 1
# For example, a 63x63 quad section, 1x1 sections/comp, 16x16 components = 1009x1009 vertices
TILE_SIZE_X_PX = 505  # Desired width of each tile in pixels (vertices)
TILE_SIZE_Y_PX = 505  # Desired height of each tile in pixels (vertices)
TILE_OUTPUT_DIR_NAME = "terrain_tiles" # Subdirectory within OUTPUT_DIR for tiles
TILE_NAMING_PREFIX = "tile"       # e.g., tile_X0_Y0.png

# DESIRED_PIXEL_RESOLUTION_M = 10.0 # Example: Uncomment to enable future resampling logic

# Setup main logger using the imported setup_logger
logger = setup_logger("MainController", level="INFO")
# --- End Configuration ---

def main():
    logger.info("Starting Real-World Terrain to Unreal Engine Workflow.")
    logger.info(f"Input Mode: {INPUT_MODE}")

    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            logger.info(f"Created output directory: {OUTPUT_DIR}")
        except OSError as e:
            logger.error(f"Failed to create output directory {OUTPUT_DIR}: {e}")
            return

    aoi_bbox_wgs84_to_use = None
    if INPUT_MODE.upper() == "PLACENAME":
        logger.info(f"Attempting to determine AOI from place name: '{PLACE_NAME_QUERY}' with distance {DISTANCE_KM_AROUND_PLACE} km.")
        center_coords = coordinate_utils.geocode_place_name(PLACE_NAME_QUERY)
        if not center_coords:
            logger.error(f"Could not geocode place name '{PLACE_NAME_QUERY}'. Exiting workflow.")
            return
        lat, lon = center_coords
        aoi_bbox_wgs84_to_use = coordinate_utils.calculate_bbox_from_center_and_distance(
            lat, lon, DISTANCE_KM_AROUND_PLACE
        )
        if not aoi_bbox_wgs84_to_use:
            logger.error(f"Could not calculate bounding box for '{PLACE_NAME_QUERY}'. Exiting workflow.")
            return
        logger.info(f"Determined BBox for '{PLACE_NAME_QUERY}' ({DISTANCE_KM_AROUND_PLACE}km radius): {aoi_bbox_wgs84_to_use}")
    elif INPUT_MODE.upper() == "BBOX":
        logger.info(f"Using manually specified BBox: {AOI_BBOX_WGS84_MANUAL}")
        aoi_bbox_wgs84_to_use = AOI_BBOX_WGS84_MANUAL
    else:
        logger.error(f"Invalid INPUT_MODE: '{INPUT_MODE}'. Must be 'BBOX' or 'PLACENAME'. Exiting.")
        return

    if aoi_bbox_wgs84_to_use is None:
        logger.error("AOI Bounding Box could not be determined. Exiting.")
        return

    # --- 1. API Data Fetching (SKIPPED FOR TILING TEST WITH DUMMY FILE) ---
    raw_dem_path = os.path.join(OUTPUT_DIR, RAW_DEM_FILENAME)
    logger.info(f"Step 1: SKIPPED API Data Fetching. Using existing file: {raw_dem_path} for tiling test.")
    if not os.path.exists(raw_dem_path):
        logger.error(f"Dummy DEM file {raw_dem_path} not found. Create it first for this test.")
        # Attempt to create it if missing, for robustness of this test.
        logger.info(f"Attempting to create dummy DEM file: {raw_dem_path} for test...")
        try:
            from dem_processor import _create_dummy_geotiff as dummy_creator_func
            if not dummy_creator_func(raw_dem_path, width=600, height=400, crs='EPSG:4326'): # Match dummy created before
                 logger.error(f"Failed to create dummy DEM {raw_dem_path} on the fly. Exiting.")
                 return
            logger.info(f"Successfully created dummy DEM {raw_dem_path} on the fly.")
        except Exception as e_create:
            logger.error(f"Exception during on-the-fly dummy DEM creation: {e_create}. Exiting.")
            return
    # Original API call block - commented out for this test:
    # logger.info(f"Step 1: Fetching DEM data ({DEM_TYPE_API}) for BBOX {aoi_bbox_wgs84_to_use}...")
    # ot_api_key = config_manager.get_api_key("OpenTopography")
    # if not ot_api_key:
    #     logger.warning("OpenTopography API key not found. API calls may fail or be rate-limited.")
    # else:
    #     logger.info("OpenTopography API key retrieved successfully.")

    # if not api_handler.fetch_opentopography_data(
    #     dem_type=DEM_TYPE_API, bbox=aoi_bbox_wgs84_to_use,
    #     output_file=raw_dem_path, api_key_override=ot_api_key
    # ):
    #     logger.error(f"Failed to download DEM data to {raw_dem_path}. Exiting workflow.")
    #     return
    # logger.info(f"Raw DEM data saved to: {raw_dem_path}")

    logger.info(f"Step 2: Reading and getting info from downloaded DEM: {raw_dem_path}...")
    dem_array, dem_profile, dem_nodata_val = dem_processor.get_dem_info_and_data(raw_dem_path)
    if dem_array is None or dem_profile is None:
        logger.error("Failed to read or process the downloaded DEM. Exiting workflow.")
        return
    dem_pixel_width, dem_pixel_height = dem_profile.get('width'), dem_profile.get('height')
    source_crs_str = str(dem_profile.get('crs', 'Unknown'))
    if not dem_pixel_width or not dem_pixel_height:
        logger.error(f"DEM profile missing width/height. Profile: {dem_profile}")
        return
    logger.info(f"DEM properties: {dem_pixel_width}x{dem_pixel_height}px, CRS: {source_crs_str}, NoData: {dem_nodata_val}")

    logger.info(f"Step 3: Transforming AOI BBox ({aoi_bbox_wgs84_to_use}) to target CRS ({TARGET_UTM_EPSG}) for metric sizing...")
    projected_aoi_bbox = coordinate_utils.transform_bbox_to_crs(
        aoi_bbox_wgs84_to_use, "EPSG:4326", TARGET_UTM_EPSG
    )
    if not projected_aoi_bbox:
        logger.error("Failed to project AOI bounding box. Exiting workflow.")
        return
    metric_width_aoi_m, metric_height_aoi_m = coordinate_utils.get_metric_dimensions(projected_aoi_bbox)
    if metric_width_aoi_m is None or metric_height_aoi_m is None:
        logger.error("Failed to calculate metric dimensions of projected AOI. Exiting.")
        return
    logger.info(f"Projected AOI ({TARGET_UTM_EPSG}) BBox: {projected_aoi_bbox}")
    logger.info(f"Projected AOI metric dimensions: W={metric_width_aoi_m:.3f}m, H={metric_height_aoi_m:.3f}m")

    logger.info("Step 4: Determining effective heightmap pixel resolution...")
    heightmap_pixel_resolution_m = metric_width_aoi_m / dem_pixel_width
    logger.info(f"Effective pixel resolution (width-based): {heightmap_pixel_resolution_m:.3f} m/pixel")

    logger.info("Step 5: Scaling elevation data to uint16 (0-65535)...")
    nodata_input_for_scaling = np.nan if np.issubdtype(dem_array.dtype, np.floating) else dem_nodata_val
    scaled_array_uint16, actual_min_elev, actual_max_elev = dem_processor.scale_to_uint16(
        dem_array, nodata_val_input=nodata_input_for_scaling
    )
    if scaled_array_uint16 is None or actual_min_elev is None or actual_max_elev is None:
        logger.error("Failed to scale DEM data to uint16. Exiting workflow.")
        return
    logger.info(f"Elevation data scaled. Actual Min/Max Elev (AOI): {actual_min_elev:.3f}m, {actual_max_elev:.3f}m")

    # --- 6. Tiling or Saving Processed Heightmap ---
    heightmap_saved_as_tiles = False
    generated_tile_paths = []

    if ENABLE_TILING:
        logger.info(f"Step 6a: Tiling enabled. Outputting to {TILE_SIZE_X_PX}x{TILE_SIZE_Y_PX} tiles...")
        tile_output_fulldir = os.path.join(OUTPUT_DIR, TILE_OUTPUT_DIR_NAME)

        generated_tile_paths = dem_processor.tile_scaled_dem_array(
            scaled_dem_array_uint16=scaled_array_uint16,
            tile_size_x=TILE_SIZE_X_PX,
            tile_size_y=TILE_SIZE_Y_PX,
            output_tile_dir=tile_output_fulldir,
            tile_naming_prefix=TILE_NAMING_PREFIX,
            output_format=OUTPUT_HEIGHTMAP_FORMAT,
            actual_min_elev=actual_min_elev,
            actual_max_elev=actual_max_elev
        )
        if generated_tile_paths: # Check if list is not None and not empty
            logger.info(f"Successfully generated {len(generated_tile_paths)} tile file(s) in {tile_output_fulldir}")
            heightmap_saved_as_tiles = True
            for p_idx, p_path in enumerate(generated_tile_paths):
                if p_idx < 5: logger.info(f"  - {p_path}")
            if len(generated_tile_paths) > 5: logger.info(f"  ... and {len(generated_tile_paths) - 5} more tiles.")
        else:
            logger.error("Tiling was enabled, but failed to generate tiles or no tiles were produced.")
            # Depending on desired robustness, might choose to exit or fall back to single file.
            # For now, we'll let it proceed to parameter calculation, but report will be affected.

    if not heightmap_saved_as_tiles:
        logger.info("Step 6b: Saving processed heightmap as a single file (tiling not enabled or failed)...")
        saved_at_least_one_single_format = False
        if OUTPUT_HEIGHTMAP_FORMAT.upper() in ["PNG", "BOTH"]:
            png_path = os.path.join(OUTPUT_DIR, HEIGHTMAP_PNG_FILENAME)
            if dem_processor.save_array_as_png16(scaled_array_uint16, png_path):
                logger.info(f"Single heightmap saved as PNG: {png_path}")
                saved_at_least_one_single_format = True
            else:
                logger.error(f"Failed to save single heightmap as PNG.")

        if OUTPUT_HEIGHTMAP_FORMAT.upper() in ["RAW", "BOTH"]:
            raw_base_path = os.path.join(OUTPUT_DIR, HEIGHTMAP_RAW_BASENAME)
            if dem_processor.save_array_as_raw16_with_json(
                scaled_array_uint16, raw_base_path,
                min_elev=actual_min_elev, max_elev=actual_max_elev
            ):
                logger.info(f"Single heightmap saved as RAW+JSON: {raw_base_path}.r16")
                saved_at_least_one_single_format = True
            else:
                logger.error(f"Failed to save single heightmap as RAW+JSON.")

        if not saved_at_least_one_single_format and not ENABLE_TILING:
             logger.error("No heightmap was saved for single file output. Check format or errors. Exiting.")
             return

    logger.info("Step 7: Calculating Unreal Engine import parameters...")
    ue_params = unreal_preparer.calculate_ue_scales(
        actual_min_elev_aoi_m=actual_min_elev,
        actual_max_elev_aoi_m=actual_max_elev,
        heightmap_pixel_resolution_m=heightmap_pixel_resolution_m
    )
    if not ue_params:
        logger.error("Failed to calculate Unreal Engine parameters. Exiting workflow.")
        return

    logger.info("Step 8: Generating Unreal Engine import report...")
    report_path = os.path.join(OUTPUT_DIR, UE_REPORT_FILENAME)

    report_details_tiling_info = None
    if heightmap_saved_as_tiles:
        # Calculate number of tiles based on the full DEM dimensions and tile sizes
        # This needs math.ceil, ensure it's imported if not already (it is via dem_processor import)
        num_tiles_x = int(np.ceil(dem_pixel_width / TILE_SIZE_X_PX)) # Use np.ceil and cast to int
        num_tiles_y = int(np.ceil(dem_pixel_height / TILE_SIZE_Y_PX)) # Use np.ceil and cast to int
        report_details_tiling_info = {
            "is_tiled": True,
            "tile_size_x_px": TILE_SIZE_X_PX,
            "tile_size_y_px": TILE_SIZE_Y_PX,
            "num_tiles_x": num_tiles_x,
            "num_tiles_y": num_tiles_y,
            "tile_naming_prefix": TILE_NAMING_PREFIX,
            "tile_output_dir_name": TILE_OUTPUT_DIR_NAME
        }

    unreal_preparer.generate_ue_import_report(
        ue_params=ue_params,
        heightmap_overall_dims=(dem_pixel_width, dem_pixel_height),
        heightmap_format=OUTPUT_HEIGHTMAP_FORMAT, # Pass original format
        tiling_info=report_details_tiling_info, # Pass the new dict
        report_path=report_path
    )
    logger.info(f"Unreal Engine import guide saved to: {report_path}")

    logger.info("Workflow completed successfully!")

if __name__ == '__main__':
    main()
