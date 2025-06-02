# main_controller.py
import os
import sys
import logging # Fallback for initial logger setup if logger_setup fails
import numpy as np
import argparse # Added argparse
import textwrap # For better help formatting

# Attempt to import all necessary modules.
try:
    from logger_setup import setup_logger
    import config_manager
    import api_handler
    import dem_processor
    import coordinate_utils
    import unreal_preparer
except ImportError as e:
    logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.error(f"CRITICAL IMPORT ERROR: {e}. Ensure all required module files are present.")
    sys.exit(1)

# --- Global constants for filenames (can be overridden by future CLI args if needed) ---
RAW_DEM_FILENAME = "downloaded_dem.tif"
HEIGHTMAP_PNG_FILENAME = "heightmap_ue.png"
HEIGHTMAP_RAW_BASENAME = "heightmap_ue_raw"
UE_REPORT_FILENAME = "unreal_engine_import_guide.txt"
TILE_OUTPUT_DIR_NAME = "terrain_tiles" # Default name for the subdirectory for tiles
TILE_NAMING_PREFIX = "tile"       # Default prefix for tile filenames

# Setup main logger before parse_arguments, in case parsing itself needs logging
# Or, can be configured after parsing if log level is a CLI arg. For now, fixed.
logger = setup_logger("MainController", level="INFO")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Real-World Terrain to Unreal Engine Importer.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=textwrap.dedent('''        Examples:
          - Get terrain for Eiffel Tower, 10km radius, output as PNG tiles:
            python main_controller.py --placename "Eiffel Tower, Paris" --distance 10 --enable_tiling --tile_size_x 505 --tile_size_y 505 --output_format PNG

          - Get terrain for a specific bounding box, output as single RAW file:
            python main_controller.py --bbox 2.25 48.8 2.35 48.9 --utm_epsg EPSG:32631 --output_format RAW
        ''')
    )

    aoi_group = parser.add_mutually_exclusive_group(required=True)
    aoi_group.add_argument(
        '--bbox', nargs=4, type=float, metavar=('WEST', 'SOUTH', 'EAST', 'NORTH'),
        help='Bounding box: west_lon south_lat east_lon north_lat (WGS84 decimal degrees).'
    )
    aoi_group.add_argument(
        '--placename', type=str,
        help='Place name to geocode for the center of the AOI (e.g., "Mount Everest"). Requires --distance.'
    )
    parser.add_argument(
        '--distance', type=float, metavar='KM',
        help='Distance in kilometers around the geocoded placename to define the AOI. Required if --placename is used.'
    )
    parser.add_argument(
        '--utm_epsg', type=str,
        help='Target UTM EPSG code (e.g., "EPSG:32611"). If using --placename and not provided, auto-detection is attempted. Required if using --bbox.'
    )
    parser.add_argument(
        '--dem_type', type=str, default="SRTMGL1",
        help='DEM type for the API (e.g., "SRTMGL1", "NASADEM", "COP30"). Default: SRTMGL1.'
    )
    parser.add_argument(
        '--api_key', type=str, default=None,
        help='Optional API key for data source. Overrides config file / env vars.'
    )
    parser.add_argument(
        '--output_dir', type=str, default="./output_data_cli", # Changed default for CLI test
        help='Directory to save all output files. Default: ./output_data_cli'
    )
    parser.add_argument(
        '--output_format', type=str, default="BOTH", choices=["PNG", "RAW", "BOTH"],
        help='Output format for the heightmap(s). Default: BOTH.'
    )
    parser.add_argument(
        '--enable_tiling', action='store_true',
        help='Enable tiling. If not set, a single heightmap file is generated.'
    )
    parser.add_argument(
        '--tile_size_x', type=int, default=1009, metavar='PX',
        help='Desired width of each tile in pixels (vertices). Default: 1009.'
    )
    parser.add_argument(
        '--tile_size_y', type=int, default=1009, metavar='PX',
        help='Desired height of each tile in pixels (vertices). Default: 1009.'
    )

    args = parser.parse_args()

    if args.placename and args.distance is None:
        parser.error("--placename requires --distance to be specified.")
    if args.distance is not None and args.distance <= 0:
        parser.error("--distance must be a positive value.")
    if args.bbox and args.utm_epsg is None:
        parser.error("--bbox input mode requires --utm_epsg to be specified for accurate projection.")

    return args

def main():
    args = parse_arguments()

    logger.info("Starting Real-World Terrain to Unreal Engine Workflow with CLI arguments.")
    logger.debug(f"Parsed arguments: {args}")

    # Use parsed arguments for configuration
    output_dir = args.output_dir # Use this instead of global OUTPUT_DIR

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        except OSError as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            return

    aoi_bbox_wgs84_to_use = None
    target_utm_epsg_to_use = args.utm_epsg
    center_coords_for_utm_detection = None # For placename mode if UTM needs detection

    if args.placename:
        logger.info(f"Input Mode: PLACENAME ('{args.placename}', {args.distance} km)")
        center_coords = coordinate_utils.geocode_place_name(args.placename)
        if not center_coords:
            logger.error(f"Could not geocode place name '{args.placename}'. Exiting workflow.")
            return
        center_coords_for_utm_detection = center_coords # Save for UTM detection
        lat, lon = center_coords
        aoi_bbox_wgs84_to_use = coordinate_utils.calculate_bbox_from_center_and_distance(
            lat, lon, args.distance
        )
        if not aoi_bbox_wgs84_to_use:
            logger.error(f"Could not calculate bounding box for '{args.placename}'. Exiting workflow.")
            return
        logger.info(f"Determined BBox for '{args.placename}' ({args.distance}km radius): {aoi_bbox_wgs84_to_use}")

        if not target_utm_epsg_to_use and center_coords_for_utm_detection:
            logger.info("Attempting to auto-detect UTM EPSG code...")
            target_utm_epsg_to_use = coordinate_utils.get_utm_epsg_from_latlon(
                center_coords_for_utm_detection[0], center_coords_for_utm_detection[1]
            )
            if target_utm_epsg_to_use:
                logger.info(f"Auto-detected UTM EPSG: {target_utm_epsg_to_use}")
            else:
                logger.error("Failed to auto-detect UTM EPSG. Please provide it using --utm_epsg. Exiting.")
                return
        elif not target_utm_epsg_to_use: # Should be caught if geocoding failed, but defensive
             logger.error("UTM EPSG could not be determined. Please provide it using --utm_epsg. Exiting.")
             return

    elif args.bbox:
        logger.info(f"Input Mode: BBOX ({args.bbox})")
        aoi_bbox_wgs84_to_use = tuple(args.bbox)
        if not target_utm_epsg_to_use: # Caught by argparse validation, but good to double check
             logger.error("Critical: --utm_epsg was not provided for --bbox mode. Exiting.")
             return

    if aoi_bbox_wgs84_to_use is None:
        logger.error("AOI Bounding Box could not be determined. Exiting.")
        return

    raw_dem_path = os.path.join(output_dir, RAW_DEM_FILENAME) # Use args.output_dir

    # API Key: CLI arg > config_manager
    ot_api_key_to_use = args.api_key if args.api_key is not None else config_manager.get_api_key("OpenTopography")
    if not ot_api_key_to_use:
        logger.warning("OpenTopography API key not found from CLI, config.json or env vars. API calls may fail.")
    else:
        logger.info("OpenTopography API key will be used.")

    logger.info(f"Step 1: Fetching DEM data ({args.dem_type}) for BBOX {aoi_bbox_wgs84_to_use}...")
    if not api_handler.fetch_opentopography_data(
        dem_type=args.dem_type, bbox=aoi_bbox_wgs84_to_use,
        output_file=raw_dem_path, api_key_override=ot_api_key_to_use
    ):
        logger.error(f"Failed to download DEM data to {raw_dem_path}. Exiting workflow.")
        return
    logger.info(f"Raw DEM data saved to: {raw_dem_path}")

    logger.info(f"Step 2: Reading DEM: {raw_dem_path}...")
    dem_array, dem_profile, dem_nodata_val = dem_processor.get_dem_info_and_data(raw_dem_path)
    if dem_array is None or dem_profile is None:
        logger.error("Failed to read/process downloaded DEM. Exiting."); return
    dem_pixel_width, dem_pixel_height = dem_profile.get('width'), dem_profile.get('height')
    source_crs_str = str(dem_profile.get('crs', 'Unknown'))
    if not dem_pixel_width or not dem_pixel_height:
        logger.error(f"DEM profile missing width/height. Profile: {dem_profile}"); return
    logger.info(f"DEM: {dem_pixel_width}x{dem_pixel_height}px, CRS: {source_crs_str}, NoData: {dem_nodata_val}")

    logger.info(f"Step 3: Transforming AOI BBox to target CRS ({target_utm_epsg_to_use}) for metric sizing...")
    projected_aoi_bbox = coordinate_utils.transform_bbox_to_crs(
        aoi_bbox_wgs84_to_use, "EPSG:4326", target_utm_epsg_to_use
    )
    if not projected_aoi_bbox: logger.error("Failed to project AOI BBox. Exiting."); return
    metric_width_aoi_m, metric_height_aoi_m = coordinate_utils.get_metric_dimensions(projected_aoi_bbox)
    if metric_width_aoi_m is None or metric_height_aoi_m is None:
        logger.error("Failed to calculate metric dimensions of projected AOI. Exiting."); return
    logger.info(f"Projected AOI ({target_utm_epsg_to_use}) BBox: {projected_aoi_bbox}")
    logger.info(f"Projected AOI metric dimensions: W={metric_width_aoi_m:.3f}m, H={metric_height_aoi_m:.3f}m")

    logger.info("Step 4: Determining effective heightmap pixel resolution...")
    heightmap_pixel_resolution_m = metric_width_aoi_m / dem_pixel_width
    logger.info(f"Effective pixel resolution (width-based): {heightmap_pixel_resolution_m:.3f} m/pixel")

    logger.info("Step 5: Scaling elevation data to uint16...")
    nodata_input_for_scaling = np.nan if np.issubdtype(dem_array.dtype, np.floating) else dem_nodata_val
    scaled_array_uint16, actual_min_elev, actual_max_elev = dem_processor.scale_to_uint16(
        dem_array, nodata_val_input=nodata_input_for_scaling
    )
    if scaled_array_uint16 is None or actual_min_elev is None or actual_max_elev is None:
        logger.error("Failed to scale DEM data to uint16. Exiting."); return
    logger.info(f"Elevation data scaled. Actual Min/Max Elev (AOI): {actual_min_elev:.3f}m, {actual_max_elev:.3f}m")

    heightmap_saved_as_tiles = False; generated_tile_paths = []
    if args.enable_tiling:
        logger.info(f"Step 6a: Tiling enabled. Outputting to {args.tile_size_x}x{args.tile_size_y} tiles...")
        tile_output_fulldir = os.path.join(output_dir, TILE_OUTPUT_DIR_NAME)
        generated_tile_paths = dem_processor.tile_scaled_dem_array(
            scaled_dem_array_uint16, args.tile_size_x, args.tile_size_y,
            tile_output_fulldir, TILE_NAMING_PREFIX, args.output_format,
            actual_min_elev, actual_max_elev
        )
        if generated_tile_paths:
            logger.info(f"Successfully generated {len(generated_tile_paths)} tile file(s) in {tile_output_fulldir}")
            heightmap_saved_as_tiles = True
            for p_idx, p_path in enumerate(generated_tile_paths):
                if p_idx < 5: logger.info(f"  - {p_path}")
            if len(generated_tile_paths) > 5: logger.info(f"  ... and {len(generated_tile_paths) - 5} more tiles.")
        else: logger.error("Tiling enabled, but failed to generate tiles.")

    if not heightmap_saved_as_tiles:
        logger.info("Step 6b: Saving as single file (tiling not enabled or failed)...")
        saved_single = False
        if args.output_format.upper() in ["PNG", "BOTH"]:
            png_path = os.path.join(output_dir, HEIGHTMAP_PNG_FILENAME)
            if dem_processor.save_array_as_png16(scaled_array_uint16, png_path):
                logger.info(f"Single heightmap PNG: {png_path}"); saved_single = True
            else: logger.error("Failed to save single PNG.")
        if args.output_format.upper() in ["RAW", "BOTH"]:
            raw_base = os.path.join(output_dir, HEIGHTMAP_RAW_BASENAME)
            if dem_processor.save_array_as_raw16_with_json(
                scaled_array_uint16, raw_base, actual_min_elev, actual_max_elev
            ): logger.info(f"Single heightmap RAW+JSON: {raw_base}.r16"); saved_single = True
            else: logger.error("Failed to save single RAW+JSON.")
        if not saved_single and not args.enable_tiling: logger.error("No heightmap saved. Exiting."); return

    logger.info("Step 7: Calculating Unreal Engine import parameters...")
    ue_params = unreal_preparer.calculate_ue_scales(
        actual_min_elev, actual_max_elev, heightmap_pixel_resolution_m
    )
    if not ue_params: logger.error("Failed to calculate UE params. Exiting."); return

    logger.info("Step 8: Generating Unreal Engine import report...")
    report_path = os.path.join(output_dir, UE_REPORT_FILENAME)
    tiling_info_for_report = None
    if heightmap_saved_as_tiles:
        num_tiles_x = int(np.ceil(dem_pixel_width / args.tile_size_x))
        num_tiles_y = int(np.ceil(dem_pixel_height / args.tile_size_y))
        tiling_info_for_report = {
            "is_tiled": True, "tile_size_x_px": args.tile_size_x, "tile_size_y_px": args.tile_size_y,
            "num_tiles_x": num_tiles_x, "num_tiles_y": num_tiles_y,
            "tile_naming_prefix": TILE_NAMING_PREFIX, "tile_output_dir_name": TILE_OUTPUT_DIR_NAME
        }
    unreal_preparer.generate_ue_import_report(
        ue_params, (dem_pixel_width, dem_pixel_height),
        args.output_format, tiling_info_for_report, report_path
    )
    logger.info(f"UE import guide: {report_path}")
    logger.info("Workflow completed successfully!")

if __name__ == '__main__':
    main()
