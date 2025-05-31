# unreal_preparer.py
import json
import os
import logging # Fallback logging

try:
    from logger_setup import setup_logger
    logger = setup_logger(__name__, level=logging.INFO)
except ImportError:
    print("Warning: logger_setup.py not found. Using basic logging for unreal_preparer.")
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s")

UE_INTERNAL_HEIGHT_SPAN = 511.992


def calculate_ue_scales(
    actual_min_elev_aoi_m: float,
    actual_max_elev_aoi_m: float,
    heightmap_pixel_resolution_m: float
) -> dict | None:
    """
    Calculates the X, Y, and Z scale factors and Z location for Unreal Engine import.
    """
    if not all(isinstance(val, (int, float)) for val in [actual_min_elev_aoi_m, actual_max_elev_aoi_m, heightmap_pixel_resolution_m]):
        logger.error("All input parameters must be numeric.")
        return None
    if heightmap_pixel_resolution_m <= 0:
        logger.error("Heightmap pixel resolution must be positive.")
        return None
    if actual_min_elev_aoi_m > actual_max_elev_aoi_m:
        logger.error(f"Min elevation ({actual_min_elev_aoi_m}m) cannot be greater than max elevation ({actual_max_elev_aoi_m}m).")
        return None
    elif actual_min_elev_aoi_m == actual_max_elev_aoi_m:
        logger.warning(
            f"Min elevation ({actual_min_elev_aoi_m}m) is equal to max elevation ({actual_max_elev_aoi_m}m). "
            "Terrain is flat."
        )
    scale_x_y_ue = heightmap_pixel_resolution_m * 100.0
    elevation_span_m = actual_max_elev_aoi_m - actual_min_elev_aoi_m
    if elevation_span_m == 0:
        scale_z_ue = 100.0
        logger.info("AOI elevation span is zero (flat terrain). Setting UE Z scale to 100.0 for convention.")
    else:
        if UE_INTERNAL_HEIGHT_SPAN == 0:
            logger.error("UE_INTERNAL_HEIGHT_SPAN is zero, division by zero for Z scale.")
            return None
        scale_z_ue = (elevation_span_m * 100.0) / UE_INTERNAL_HEIGHT_SPAN
    location_z_ue = (actual_min_elev_aoi_m * 100.0) + (256.0 * scale_z_ue)
    scales = {
        "scale_x_ue_cm": scale_x_y_ue,
        "scale_y_ue_cm": scale_x_y_ue,
        "scale_z_ue_cm": scale_z_ue,
        "location_z_ue_cm": location_z_ue,
        "note_on_location_z": "This Z location for the landscape actor ensures that areas corresponding to "
                              "actual_min_elev_aoi_m (0 in the 16-bit heightmap) are positioned at that elevation in UE.",
        "actual_min_elev_aoi_m": actual_min_elev_aoi_m,
        "actual_max_elev_aoi_m": actual_max_elev_aoi_m,
        "elevation_span_aoi_m": elevation_span_m,
        "heightmap_pixel_resolution_m": heightmap_pixel_resolution_m,
        "ue_internal_height_span_units": UE_INTERNAL_HEIGHT_SPAN
    }
    logger.info(f"Calculated Unreal Engine parameters: {scales}")
    return scales

def generate_ue_import_report(
    ue_params: dict | None,
    heightmap_overall_dims: tuple[int, int] | None = None,
    heightmap_format: str | None = None,
    tiling_info: dict | None = None, # New parameter
    report_path: str | None = None
) -> str:
    """
    Generates a human-readable report of parameters for Unreal Engine import.
    """
    report_lines = ["Unreal Engine Landscape Import Parameters Report"]
    report_lines.append("=" * 40)

    if not ue_params:
        report_lines.append("No UE parameters calculated or provided. Cannot generate full report.")
        report_str_early_exit = "\n".join(report_lines)
        if report_path:
            try:
                # Ensure output directory exists even for minimal report
                output_dir_min = os.path.dirname(os.path.abspath(report_path))
                if output_dir_min and not os.path.exists(output_dir_min):
                     os.makedirs(output_dir_min)
                with open(report_path, "w") as f: f.write(report_str_early_exit)
                logger.info(f"Minimal UE import report saved to: {report_path}")
            except IOError as e: logger.error(f"Failed to save minimal UE report to {report_path}: {e}")
        return report_str_early_exit

    report_lines.append("Source Data Overview (meters):")
    min_elev_str = f"{ue_params.get('actual_min_elev_aoi_m'):.3f}" if isinstance(ue_params.get('actual_min_elev_aoi_m'), (int, float)) else str(ue_params.get('actual_min_elev_aoi_m', 'N/A'))
    max_elev_str = f"{ue_params.get('actual_max_elev_aoi_m'):.3f}" if isinstance(ue_params.get('actual_max_elev_aoi_m'), (int, float)) else str(ue_params.get('actual_max_elev_aoi_m', 'N/A'))
    span_elev_str = f"{ue_params.get('elevation_span_aoi_m'):.3f}" if isinstance(ue_params.get('elevation_span_aoi_m'), (int, float)) else str(ue_params.get('elevation_span_aoi_m', 'N/A'))
    pixel_res_str = f"{ue_params.get('heightmap_pixel_resolution_m'):.3f}" if isinstance(ue_params.get('heightmap_pixel_resolution_m'), (int, float)) else str(ue_params.get('heightmap_pixel_resolution_m', 'N/A'))
    report_lines.append(f"  - Min Elevation of AOI (used for black in heightmap): {min_elev_str} m")
    report_lines.append(f"  - Max Elevation of AOI (used for white in heightmap): {max_elev_str} m")
    report_lines.append(f"  - Elevation Span of AOI: {span_elev_str} m")
    report_lines.append(f"  - Heightmap Pixel Ground Resolution: {pixel_res_str} m/pixel")
    report_lines.append("-" * 40)

    report_lines.append("Calculated Unreal Engine Import Settings (UE Units = cm):")
    scale_x_str = f"{ue_params.get('scale_x_ue_cm'):.6f}" if isinstance(ue_params.get('scale_x_ue_cm'), (int, float)) else str(ue_params.get('scale_x_ue_cm', 'N/A'))
    scale_y_str = f"{ue_params.get('scale_y_ue_cm'):.6f}" if isinstance(ue_params.get('scale_y_ue_cm'), (int, float)) else str(ue_params.get('scale_y_ue_cm', 'N/A'))
    scale_z_str = f"{ue_params.get('scale_z_ue_cm'):.6f}" if isinstance(ue_params.get('scale_z_ue_cm'), (int, float)) else str(ue_params.get('scale_z_ue_cm', 'N/A'))
    loc_z_str = f"{ue_params.get('location_z_ue_cm'):.3f}" if isinstance(ue_params.get('location_z_ue_cm'), (int, float)) else str(ue_params.get('location_z_ue_cm', 'N/A'))
    report_lines.append(f"  - Landscape Scale X: {scale_x_str}")
    report_lines.append(f"  - Landscape Scale Y: {scale_y_str}")
    report_lines.append(f"  - Landscape Scale Z: {scale_z_str}")
    report_lines.append(f"  - Landscape Actor Location Z: {loc_z_str}")
    report_lines.append(f"    (Note: {ue_params.get('note_on_location_z', '')})")
    report_lines.append("-" * 40)

    report_lines.append("Heightmap File Overview:") # Changed section title
    if heightmap_overall_dims:
        report_lines.append(f"  - Original DEM Dimensions (Overall): {heightmap_overall_dims[0]} x {heightmap_overall_dims[1]} pixels")
    if heightmap_format: # This is the OUTPUT_HEIGHTMAP_FORMAT from main_controller
        report_lines.append(f"  - Requested Output Format: {heightmap_format}")

    if tiling_info and tiling_info.get("is_tiled"):
        report_lines.append("-" * 40) # Separator before tiling info if it exists
        report_lines.append("Tiled Landscape Information:")
        report_lines.append("  - Output consists of multiple tiles.")
        tile_size_x = tiling_info.get('tile_size_x_px', 'N/A')
        tile_size_y = tiling_info.get('tile_size_y_px', 'N/A')
        report_lines.append(f"  - Individual Tile Dimensions: {tile_size_x} x {tile_size_y} pixels (vertices)")
        num_x = tiling_info.get('num_tiles_x', 'N/A')
        num_y = tiling_info.get('num_tiles_y', 'N/A')
        report_lines.append(f"  - Tile Grid Size: {num_x} x {num_y} tiles")

        example_tile_name = f"{tiling_info.get('tile_naming_prefix', 'tile')}_X0_Y0"
        # Determine example extension based on the original heightmap_format
        if heightmap_format:
            if "PNG" in heightmap_format.upper() or "BOTH" in heightmap_format.upper():
                example_tile_name += ".png"
            elif "RAW" in heightmap_format.upper(): # If only RAW, then .r16
                example_tile_name += ".r16 (and .json)"
        else: # Fallback if format not specified for some reason
            example_tile_name += ".*"

        report_lines.append(f"  - Tile Naming Convention: e.g., {example_tile_name}, ..._X0_Y1.*, etc.")
        report_lines.append(f"  - Tile Output Subdirectory: '{tiling_info.get('tile_output_dir_name', 'N/A')}'")
        report_lines.append(f"  - Note: The Scale X, Y, Z and Location Z values (above) apply globally to all tiles.")
    report_lines.append("-" * 40)

    report_lines.append("Notes for Unreal Engine Import:")
    report_lines.append("1. Ensure your 16-bit heightmap file(s) (e.g., Grayscale PNG or .r16) are ready.")
    report_lines.append("2. In UE Landscape mode, choose 'Import from File' and select your heightmap(s).")
    report_lines.append("3. Set 'Fit to Data' for heightmap resolution or manually input dimensions if importing a single file.")
    report_lines.append("4. Input the 'Landscape Scale X, Y, Z' values above into the UE import dialog.")
    report_lines.append("5. After the landscape is created, set its 'Location Z' in the Transform section to the 'Landscape Actor Location Z' value above.")

    current_note_index = 6
    if tiling_info and tiling_info.get("is_tiled"):
        report_lines.append(f"{current_note_index}. For tiled landscapes, import into a World Partition enabled level in Unreal Engine.")
        report_lines.append(f"   Unreal Engine can import tiles using the 'Import Tiled Landscape' feature.")
        report_lines.append(f"   Ensure tiles are named correctly (e.g., {tiling_info.get('tile_naming_prefix', 'tile')}_X0_Y0.*, _X1_Y0.*, etc.) and select the first tile in the set.")
        current_note_index +=1

    report_lines.append(f"{current_note_index}. Verify UE documentation for recommended landscape section sizes based on your heightmap dimensions.")


    report_str = "\n".join(report_lines)

    if report_path:
        try:
            output_dir = os.path.dirname(os.path.abspath(report_path))
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created report directory: {output_dir}")
            with open(report_path, "w") as f:
                f.write(report_str)
            logger.info(f"Unreal Engine import report saved to: {report_path}")
        except IOError as e:
            logger.error(f"Failed to save UE import report to {report_path}: {e}")

    logger.debug(f"Generated UE Report (length {len(report_str)} chars)")
    return report_str

if __name__ == '__main__':
    try:
        from logger_setup import setup_logger as main_setup_logger
        logger_ue_test = main_setup_logger("UEPrepTestMain", level="DEBUG")
    except ImportError:
        logger_ue_test = logger
        logger_ue_test.setLevel(logging.DEBUG)
        logger_ue_test.warning("Running UEPrepTestMain with fallback logger configuration.")

    test_output_dir = "output_data_test"
    if not os.path.exists(test_output_dir):
        try:
            os.makedirs(test_output_dir)
            logger_ue_test.info(f"Created '{test_output_dir}' directory for reports.")
        except OSError as e:
            logger_ue_test.error(f"Could not create '{test_output_dir}' directory: {e}")

    logger_ue_test.info("--- Testing UE Scale Calculation (Standard Case) ---")
    min_elev_m = 100.0
    max_elev_m = 611.992
    pixel_res_m = 2.0
    ue_scales = calculate_ue_scales(min_elev_m, max_elev_m, pixel_res_m)
    expected_z_scale = (max_elev_m - min_elev_m) * 100.0 / UE_INTERNAL_HEIGHT_SPAN
    logger_ue_test.debug(f"Expected Z scale for standard case: {expected_z_scale}")

    if ue_scales:
        logger_ue_test.info(f"Calculated scales: {ue_scales}")
        logger_ue_test.info("\n--- Testing UE Import Report Generation (Standard Case - Single File) ---")
        report_file_path = os.path.join(test_output_dir, "ue_import_report_standard_single.txt")
        report_content = generate_ue_import_report(
            ue_scales,
            heightmap_overall_dims=(1009, 1009),
            heightmap_format="PNG16 (Grayscale)",
            tiling_info={"is_tiled": False}, # Explicitly not tiled
            report_path=report_file_path
        )
        if os.path.exists(report_file_path):
             logger_ue_test.info(f"Report saved to {report_file_path}")

        logger_ue_test.info("\n--- Testing UE Import Report Generation (Standard Case - Tiled) ---")
        report_file_path_tiled = os.path.join(test_output_dir, "ue_import_report_standard_tiled.txt")
        tiling_data_example = {
            "is_tiled": True, "tile_size_x_px": 505, "tile_size_y_px": 505,
            "num_tiles_x": 2, "num_tiles_y": 2, "tile_naming_prefix": "mytile",
            "tile_output_dir_name": "terrain_tiles_example"
        }
        report_content_tiled = generate_ue_import_report(
            ue_scales,
            heightmap_overall_dims=(1009, 1009),
            heightmap_format="PNG", # Example format
            tiling_info=tiling_data_example,
            report_path=report_file_path_tiled
        )
        if os.path.exists(report_file_path_tiled):
             logger_ue_test.info(f"Tiled report saved to {report_file_path_tiled}")
    else:
        logger_ue_test.error("Failed to calculate UE scales for standard case.")

    logger_ue_test.info("\n--- Testing with Flat Terrain ---")
    flat_scales = calculate_ue_scales(50.0, 50.0, 5.0)
    if flat_scales:
        logger_ue_test.info(f"Calculated scales for flat terrain: {flat_scales}")
        generate_ue_import_report(flat_scales, heightmap_overall_dims=(512,512), heightmap_format="R16", report_path=os.path.join(test_output_dir, "ue_import_report_flat.txt"))
    else:
        logger_ue_test.error("Failed to calculate UE scales for flat terrain.")

    logger_ue_test.info("\n--- Testing with Invalid Pixel Resolution (<=0) ---")
    if not calculate_ue_scales(100.0, 200.0, 0): logger_ue_test.info("Correctly handled invalid pixel resolution (0).")
    if not calculate_ue_scales(100.0, 200.0, -1.0): logger_ue_test.info("Correctly handled invalid pixel resolution (<0).")

    logger_ue_test.info("\n--- Testing with Min Elevation > Max Elevation ---")
    if not calculate_ue_scales(200.0, 100.0, 10.0): logger_ue_test.info("Correctly handled inverted elevation range (min > max).")

    logger_ue_test.info("\n--- Testing with Non-Numeric Inputs ---")
    if not calculate_ue_scales("100.0", 200.0, 10.0): logger_ue_test.info("Correctly handled non-numeric input for min_elev.") # type: ignore
    if not calculate_ue_scales(100.0, "200.0", 10.0): logger_ue_test.info("Correctly handled non-numeric input for max_elev.") # type: ignore
    if not calculate_ue_scales(100.0, 200.0, "10.0"): logger_ue_test.info("Correctly handled non-numeric input for pixel_resolution.") # type: ignore

    logger_ue_test.info("\n--- Testing Report Generation with None ue_params ---")
    report_for_none_params = generate_ue_import_report(None, report_path=os.path.join(test_output_dir, "ue_import_report_none_params.txt"))
    logger_ue_test.info(f"Report for None ue_params: \n{report_for_none_params[:100]}...")

    logger_ue_test.info("\n--- Unreal Preparer Tests Finished ---")
    logger_ue_test.info(f"Test reports (if any) are in '{test_output_dir}'.")
