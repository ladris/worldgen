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
# INPUT_MODE = "BBOX"      # Use direct bounding box coordinates
INPUT_MODE = "PLACENAME" # Use place name geocoding and distance

# Parameters for PLACENAME mode
PLACE_NAME_QUERY = "Mount Everest" 
# PLACE_NAME_QUERY = "Eiffel Tower, Paris"
# PLACE_NAME_QUERY = "Denver, Colorado"
DISTANCE_KM_AROUND_PLACE = 15 # Kilometers around the geocoded center point

# Parameters for BBOX mode (still used if INPUT_MODE is "BBOX")
AOI_BBOX_WGS84_MANUAL = (86.85, 27.90, 87.00, 28.05) # Around Everest for comparison if BBOX mode
# AOI_BBOX_WGS84_MANUAL = (-112.1100, 36.0550, -112.1000, 36.0600) # Small Grand Canyon

# TARGET_UTM_EPSG still needs to be set appropriately for the AOI
# For Mount Everest (approx 27.9N, 86.9E), UTM Zone 45N
TARGET_UTM_EPSG = "EPSG:32645" 
# For Denver (approx 39.7N, 104.9W), UTM Zone 13N
# TARGET_UTM_EPSG = "EPSG:32613" 
# For Paris (approx 48.8N, 2.3E), UTM Zone 31N
# TARGET_UTM_EPSG = "EPSG:32631"
# For Grand Canyon example area (approx 36.0N, 112.1W), UTM Zone 12N (or 11N on edge)
# TARGET_UTM_EPSG = "EPSG:32612" # More accurate for -112.1W
# TARGET_UTM_EPSG = "EPSG:32611" # As used before for -112.1W

DEM_TYPE_API = "SRTMGL1" # For OpenTopography: SRTMGL1, NASADEM, COP30, etc.

OUTPUT_DIR = "./output_data_main_controller" # Specific output for this controller
RAW_DEM_FILENAME = "downloaded_dem.tif"
HEIGHTMAP_PNG_FILENAME = "heightmap_ue.png"
HEIGHTMAP_RAW_BASENAME = "heightmap_ue_raw" # Becomes .r16 and .json
UE_REPORT_FILENAME = "unreal_engine_import_guide.txt"

OUTPUT_HEIGHTMAP_FORMAT = "BOTH" # Options: "PNG", "RAW", "BOTH"
# DESIRED_PIXEL_RESOLUTION_M = 10.0 # Example: Uncomment to enable future resampling logic

# Setup main logger using the imported setup_logger
logger = setup_logger("MainController", level="INFO")
# --- End Configuration ---

def main():
    logger.info("Starting Real-World Terrain to Unreal Engine Workflow.")
    logger.info(f"Input Mode: {INPUT_MODE}")

    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            logger.info(f"Created output directory: {OUTPUT_DIR}")
        except OSError as e:
            logger.error(f"Failed to create output directory {OUTPUT_DIR}: {e}")
            return 

    # --- Determine AOI Bounding Box ---
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

    if aoi_bbox_wgs84_to_use is None: # Should be caught by earlier returns, but as a safeguard
        logger.error("AOI Bounding Box could not be determined. Exiting.")
        return
            
    # --- 1. API Data Fetching ---
    logger.info(f"Step 1: Fetching DEM data ({DEM_TYPE_API}) for BBOX {aoi_bbox_wgs84_to_use}...") # Use determined BBOX
    raw_dem_path = os.path.join(OUTPUT_DIR, RAW_DEM_FILENAME)
    
    ot_api_key = None
    try:
        ot_api_key = config_manager.get_api_key("OpenTopography")
        if not ot_api_key:
            logger.warning("OpenTopography API key not found in config.json or environment variables. "
                           "API calls may fail or be rate-limited.")
        else:
            logger.info("OpenTopography API key retrieved successfully.")
    except Exception as e:
        logger.error(f"Error retrieving OpenTopography API key via config_manager: {e}")

    if not api_handler.fetch_opentopography_data(
        dem_type=DEM_TYPE_API,
        bbox=aoi_bbox_wgs84_to_use, # USE THE DETERMINED BBOX HERE
        output_file=raw_dem_path,
        api_key_override=ot_api_key 
    ):
        logger.error(f"Failed to download DEM data to {raw_dem_path}. Exiting workflow.")
        return
    logger.info(f"Raw DEM data saved to: {raw_dem_path}")

    # --- 2. DEM Processing (Initial Read & Info) ---
    logger.info(f"Step 2: Reading and getting info from downloaded DEM: {raw_dem_path}...")
    dem_array, dem_profile, dem_nodata_val = dem_processor.get_dem_info_and_data(raw_dem_path)
    if dem_array is None or dem_profile is None: 
        logger.error("Failed to read or process the downloaded DEM. Exiting workflow.")
        return
    
    dem_pixel_width = dem_profile.get('width')
    dem_pixel_height = dem_profile.get('height')
    source_crs_str = str(dem_profile.get('crs', 'Unknown')) 
    
    if not dem_pixel_width or not dem_pixel_height:
        logger.error(f"DEM profile missing width/height information. Profile: {dem_profile}")
        return

    logger.info(f"DEM properties: {dem_pixel_width}x{dem_pixel_height} pixels, CRS: {source_crs_str}, NoData Raw: {dem_nodata_val}")
    logger.debug(f"DEM Affine Transform: {dem_profile.get('transform')}")

    # --- 3. Coordinate Transformation & Metric Size of AOI ---
    logger.info(f"Step 3: Transforming AOI BBox ({aoi_bbox_wgs84_to_use}) to target CRS ({TARGET_UTM_EPSG}) for metric sizing...")
    projected_aoi_bbox = coordinate_utils.transform_bbox_to_crs(
        aoi_bbox_wgs84_to_use, "EPSG:4326", TARGET_UTM_EPSG # USE THE DETERMINED BBOX
    )
    if not projected_aoi_bbox:
        logger.error("Failed to project AOI bounding box. Exiting workflow.")
        return
    
    metric_width_aoi_m, metric_height_aoi_m = coordinate_utils.get_metric_dimensions(projected_aoi_bbox)
    if metric_width_aoi_m is None or metric_height_aoi_m is None:
        logger.error("Failed to calculate metric dimensions of the projected AOI. Exiting workflow.")
        return
    logger.info(f"Projected AOI ({TARGET_UTM_EPSG}) BBox: {projected_aoi_bbox}")
    logger.info(f"Projected AOI metric dimensions: Width={metric_width_aoi_m:.3f}m, Height={metric_height_aoi_m:.3f}m")

    # --- 4. Determine Effective Heightmap Pixel Resolution ---
    logger.info("Step 4: Determining effective heightmap pixel resolution from downloaded DEM...")
    if dem_pixel_width == 0 or dem_pixel_height == 0: 
        logger.error("DEM pixel width or height is zero. Cannot calculate resolution.")
        return

    heightmap_pixel_resolution_m = metric_width_aoi_m / dem_pixel_width
    height_pixel_resolution_m_check = metric_height_aoi_m / dem_pixel_height 
    logger.info(f"Calculated effective heightmap pixel resolution (width-based): {heightmap_pixel_resolution_m:.3f} m/pixel")
    logger.info(f"Calculated effective heightmap pixel resolution (height-based): {height_pixel_resolution_m_check:.3f} m/pixel")
    
    # --- 5. Scaling Elevation Data ---
    logger.info("Step 5: Scaling elevation data to uint16 (0-65535)...")
    nodata_input_for_scaling = np.nan if np.issubdtype(dem_array.dtype, np.floating) else dem_nodata_val
    scaled_array_uint16, actual_min_elev, actual_max_elev = dem_processor.scale_to_uint16(
        dem_array, nodata_val_input=nodata_input_for_scaling 
    )
    if scaled_array_uint16 is None or actual_min_elev is None or actual_max_elev is None:
        logger.error("Failed to scale DEM data to uint16. Exiting workflow.")
        return
    logger.info(f"Elevation data scaled. Actual Min Elevation (AOI): {actual_min_elev:.3f}m, Actual Max Elevation (AOI): {actual_max_elev:.3f}m")

    # --- 6. Saving Processed Heightmap ---
    logger.info(f"Step 6: Saving processed heightmap (Format: {OUTPUT_HEIGHTMAP_FORMAT})...")
    saved_at_least_one_format = False
    if OUTPUT_HEIGHTMAP_FORMAT.upper() in ["PNG", "BOTH"]:
        png_path = os.path.join(OUTPUT_DIR, HEIGHTMAP_PNG_FILENAME)
        if dem_processor.save_array_as_png16(scaled_array_uint16, png_path):
            logger.info(f"Heightmap saved as 16-bit PNG: {png_path}")
            saved_at_least_one_format = True
        else:
            logger.error(f"Failed to save heightmap as PNG.")

    if OUTPUT_HEIGHTMAP_FORMAT.upper() in ["RAW", "BOTH"]:
        raw_base_path = os.path.join(OUTPUT_DIR, HEIGHTMAP_RAW_BASENAME)
        if dem_processor.save_array_as_raw16_with_json(
            scaled_array_uint16, 
            raw_base_path,
            min_elev=actual_min_elev, 
            max_elev=actual_max_elev
            ):
            logger.info(f"Heightmap saved as RAW (.r16) with JSON metadata: {raw_base_path}.r16/.json")
            saved_at_least_one_format = True
        else:
            logger.error(f"Failed to save heightmap as RAW+JSON.")
    
    if not saved_at_least_one_format:
        logger.error("No heightmap was saved due to previous errors or invalid format string. Exiting.")
        return

    # --- 7. Unreal Engine Parameter Calculation ---
    logger.info("Step 7: Calculating Unreal Engine import parameters...")
    ue_params = unreal_preparer.calculate_ue_scales(
        actual_min_elev_aoi_m=actual_min_elev,
        actual_max_elev_aoi_m=actual_max_elev,
        heightmap_pixel_resolution_m=heightmap_pixel_resolution_m
    )
    if not ue_params:
        logger.error("Failed to calculate Unreal Engine parameters. Exiting workflow.")
        return
    
    # --- 8. Report Generation ---
    logger.info("Step 8: Generating Unreal Engine import report...")
    report_path = os.path.join(OUTPUT_DIR, UE_REPORT_FILENAME)
    final_heightmap_dims = (scaled_array_uint16.shape[1], scaled_array_uint16.shape[0]) 
    unreal_preparer.generate_ue_import_report(
        ue_params=ue_params,
        heightmap_dims=final_heightmap_dims, 
        heightmap_format=OUTPUT_HEIGHTMAP_FORMAT, 
        report_path=report_path
    )
    logger.info(f"Unreal Engine import guide saved to: {report_path}")

    logger.info("Workflow completed successfully!")

if __name__ == '__main__':
    main()
