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

# Unreal Engine's internal height representation range for a heightmap scaled from 0-65535
# This corresponds to a span from -256 to +255.992 in UE's internal units when a 16-bit heightmap is imported.
# The total range of values a 16-bit heightmap can represent is 65536.
# UE remaps this 0-65535 range. The effective span used for scaling is 511.9921875 (which is 65535 / 128)
# but often simplified to 512 or 511.992 for practical purposes.
# Let's use a more precise value if possible, or the commonly cited one.
# Using 65535 / 128.0 which is exactly 511.9921875 for the span of the 0-FFFF height data.
# Or, more simply, the range from -256 to almost +256 is about 512 units.
# The value 255.992 comes from (65535/256) - 256. This is (MaxHeight - MinHeight) / ZScale from UE docs.
# The key is that a value of 32768 in the heightmap corresponds to Z=0 in UE landscape.
# 0 corresponds to -256 * ZScale_UE_units.
# 65535 corresponds to (256 * (65535/32768 - 1) - 0.0078125 * ZScale_UE_units) approx 255.992 * ZScale_UE_units
# The total Z difference represented by the full 16-bit range is (255.9921875 - (-256.0)) = 511.9921875
UE_INTERNAL_HEIGHT_SPAN_UNITS = 511.9921875 
# A common simplification is 512.0 or the ((Max - Min) * 100) / Z-Scale = 51200 / 100 = 512 formula.
# Let's stick to the more precise version if it helps, or simplify to 512.0 if that's more standard in tools.
# Given the prompt used 511.992, we'll use that for consistency with the prompt's example.
UE_INTERNAL_HEIGHT_SPAN = 511.992 


def calculate_ue_scales(
    actual_min_elev_aoi_m: float,
    actual_max_elev_aoi_m: float,
    heightmap_pixel_resolution_m: float
) -> dict | None:
    """
    Calculates the X, Y, and Z scale factors and Z location for Unreal Engine import.

    Args:
        actual_min_elev_aoi_m: Minimum elevation of the AOI in meters. This is the
                               real-world elevation that will correspond to the value 0
                               in the 16-bit heightmap after it's scaled.
        actual_max_elev_aoi_m: Maximum elevation of the AOI in meters. This is the
                               real-world elevation that will correspond to the value 65535
                               in the 16-bit heightmap.
        heightmap_pixel_resolution_m: Ground resolution of one pixel in the heightmap (meters).

    Returns:
        A dictionary with 'scale_x', 'scale_y', 'scale_z', 'location_z' in UE units (cm),
        and the input parameters for context, or None if inputs are invalid.
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

    # Scale X and Y: 1 UE unit = 1 cm.
    # If heightmap pixel is 10m, then that square is 1000cm x 1000cm.
    # The scale factor for the landscape component is applied to its unit grid.
    # A 1x1 quad section by default is 1m x 1m if scale is 100.
    # So, scale_x_y_ue should be heightmap_pixel_resolution_m * 100.
    scale_x_y_ue = heightmap_pixel_resolution_m * 100.0

    elevation_span_m = actual_max_elev_aoi_m - actual_min_elev_aoi_m
    
    # Z Scale: The full 0-65535 range of the 16-bit heightmap is mapped by UE
    # across UE_INTERNAL_HEIGHT_SPAN internal units (e.g., -256 to +255.992).
    # So, scale_z_ue determines how many cm in world height this internal span represents.
    # scale_z_ue = (elevation_span_m * 100.0 cm/m) / UE_INTERNAL_HEIGHT_SPAN
    if elevation_span_m == 0:
        # For flat terrain, the Z scale doesn't change geometry but might affect Z location interpretation slightly.
        # Defaulting to 100.0 (like X/Y if pixel res was 1m) is a common UE default.
        # This means the -256 to +255.992 internal range would map to a large potential Z variation
        # if the heightmap wasn't flat. Since it IS flat, only one value from the heightmap is used,
        # and its Z position is determined by location_z_ue + (heightmap_value_scaled_to_internal_range * scale_z_ue).
        # If the heightmap is truly flat (e.g. all pixels are 0 post-scaling, representing min_elev),
        # then Z will be location_z_ue + (-256.0 * scale_z_ue / 100.0) if scale_z_ue is thought of as %
        # Or more simply, location_z_ue is the height of the value 0 in the heightmap.
        scale_z_ue = 100.0 
        logger.info("AOI elevation span is zero (flat terrain). Setting UE Z scale to 100.0 for convention.")
    else:
        if UE_INTERNAL_HEIGHT_SPAN == 0: # Should not happen with defined constant
            logger.error("UE_INTERNAL_HEIGHT_SPAN is zero, division by zero for Z scale.")
            return None
        scale_z_ue = (elevation_span_m * 100.0) / UE_INTERNAL_HEIGHT_SPAN
    
    # Location Z: This is the world Z coordinate in UE (cm) that corresponds to the
    # *bottom* of the imported height range (actual_min_elev_aoi_m).
    # When a heightmap value of 0 (representing actual_min_elev_aoi_m) is encountered,
    # UE maps it to -256 internal units. The landscape's final Z position for that point will be:
    # LandscapeActor.Z + (-256 * Landscape.Scale.Z).
    # We want this to be actual_min_elev_aoi_m * 100.
    # So, LandscapeActor.Z = (actual_min_elev_aoi_m * 100) + (256 * scale_z_ue)
    # This is often a point of confusion. A simpler interpretation for users is:
    # If location_z_ue is set to actual_min_elev_aoi_m * 100, this means that a pixel in the
    # heightmap that *represents* actual_min_elev_aoi_m (i.e., has value 0 in the 0-65535 scaled image)
    # will be placed at Z = location_z_ue - (256/UE_INTERNAL_HEIGHT_SPAN_UNITS) * (elevation_span_m * 100)
    # For UE 5.1+ with "Independent Z Scale" often it's simpler:
    # The "Z Offset" in UE import dialog would effectively be actual_min_elev_aoi_m * 100
    # And the Z scale is applied to the 0-1 normalized height.
    # Let's provide the Z that makes the lowest point (0 in heightmap) sit at actual_min_elev_aoi_m.
    # The heightmap value 0 (black) is mapped to -256 in UE's internal representation.
    # The heightmap value 65535 (white) is mapped to +255.992...
    # Vertex Z = ActorLocation.Z + MappedHeightValue(-256 to 256) * ActorScale.Z
    # We want Vertex Z for black pixels to be actual_min_elev_aoi_m * 100.
    # actual_min_elev_aoi_m * 100 = location_z_ue + (-256.0 * scale_z_ue)
    # So, location_z_ue = (actual_min_elev_aoi_m * 100.0) + (256.0 * scale_z_ue)
    # This makes the actor's pivot higher, so the "bottom" of its range lands at the desired min elevation.
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
    ue_params: dict | None, # Made dict optional
    heightmap_dims: tuple[int, int] | None = None, # (width, height) in pixels
    heightmap_format: str | None = None, # e.g., "PNG16" or "R16"
    report_path: str | None = None
) -> str:
    """
    Generates a human-readable report of parameters for Unreal Engine import.

    Args:
        ue_params: Dictionary of UE scale and location parameters from calculate_ue_scales.
        heightmap_dims: Optional tuple (width, height) of the heightmap in pixels.
        heightmap_format: Optional string indicating heightmap format (e.g., "PNG", "R16").
        report_path: Optional path to save the report as a text file.

    Returns:
        A string containing the formatted report.
    """
    report_lines = ["Unreal Engine Landscape Import Parameters Report"]
    report_lines.append("=" * 40)

    if not ue_params: # Check if ue_params is None or empty
        report_lines.append("No UE parameters calculated or provided. Cannot generate full report.")
        report_str_early_exit = "\n".join(report_lines)
        if report_path: # Still try to save this minimal report if path is given
            try:
                os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
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

    if heightmap_dims:
        report_lines.append("Heightmap File Information:")
        report_lines.append(f"  - Dimensions (Width x Height): {heightmap_dims[0]} x {heightmap_dims[1]} pixels")
    if heightmap_format:
        report_lines.append(f"  - Format: {heightmap_format}")
    if heightmap_dims or heightmap_format : report_lines.append("-" * 40) # Add separator if section has content
    
    report_lines.append("Notes for Unreal Engine Import:")
    report_lines.append("1. Ensure your 16-bit heightmap file (e.g., Grayscale PNG or .r16) is ready.")
    report_lines.append("2. In UE Landscape mode, choose 'Import from File' and select your heightmap.")
    report_lines.append("3. Set 'Fit to Data' for heightmap resolution or manually input dimensions.")
    report_lines.append("4. Input the 'Landscape Scale X, Y, Z' values above into the UE import dialog.")
    report_lines.append("5. After the landscape is created, set its 'Location Z' in the Transform section to the 'Landscape Actor Location Z' value above.")
    report_lines.append("6. Verify UE documentation for recommended landscape section sizes based on your heightmap dimensions (e.g., 1x1 components, 127x127 quads per section).")

    report_str = "\n".join(report_lines)

    if report_path:
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(os.path.abspath(report_path)) # Use abspath for safety
            if output_dir and not os.path.exists(output_dir): # Check if output_dir is not empty string
                os.makedirs(output_dir)
                logger.info(f"Created report directory: {output_dir}")
            
            with open(report_path, "w") as f:
                f.write(report_str)
            logger.info(f"Unreal Engine import report saved to: {report_path}")
        except IOError as e:
            logger.error(f"Failed to save UE import report to {report_path}: {e}")
            
    logger.debug(f"Generated UE Report:\n{report_str}")
    return report_str

if __name__ == '__main__':
    # Ensure logger_setup provides a logger named UEPrepTest or use the module's logger
    try:
        from logger_setup import setup_logger as main_setup_logger # Re-import to ensure it's the intended one
        logger_ue_test = main_setup_logger("UEPrepTestMain", level="DEBUG")
    except ImportError:
        logger_ue_test = logger # Use the module-level logger already configured
        logger_ue_test.setLevel(logging.DEBUG) # Ensure verbosity for test
        logger_ue_test.warning("Running UEPrepTestMain with fallback logger configuration.")

    test_output_dir = "output_data_test" # Consistent with other modules
    if not os.path.exists(test_output_dir):
        try:
            os.makedirs(test_output_dir)
            logger_ue_test.info(f"Created '{test_output_dir}' directory for reports.")
        except OSError as e:
            logger_ue_test.error(f"Could not create '{test_output_dir}' directory: {e}")
            # Potentially exit or handle so report saving doesn't fail silently later if dir is crucial

    logger_ue_test.info("--- Testing UE Scale Calculation (Standard Case) ---")
    min_elev_m = 100.0
    max_elev_m = 611.992 # Chosen so elevation_span_m * 100 / UE_INTERNAL_HEIGHT_SPAN = 100.0
    pixel_res_m = 2.0   # 2 meters per pixel -> XY Scale = 200 cm

    ue_scales = calculate_ue_scales(min_elev_m, max_elev_m, pixel_res_m)
    
    expected_z_scale = (max_elev_m - min_elev_m) * 100.0 / UE_INTERNAL_HEIGHT_SPAN
    logger_ue_test.debug(f"Expected Z scale for standard case: {expected_z_scale}")


    if ue_scales:
        logger_ue_test.info(f"Calculated scales: {ue_scales}")

        logger_ue_test.info("\n--- Testing UE Import Report Generation (Standard Case) ---")
        report_file_path = os.path.join(test_output_dir, "ue_import_report_standard.txt")
        report_content = generate_ue_import_report(
            ue_scales,
            heightmap_dims=(1009, 1009), 
            heightmap_format="PNG16 (Grayscale)",
            report_path=report_file_path
        )
        if os.path.exists(report_file_path):
             logger_ue_test.info(f"Report saved to {report_file_path}")
        # print(f"--- Report ---\n{report_content}\n--- End Report ---") # For debugging if needed
    else:
        logger_ue_test.error("Failed to calculate UE scales for standard case.")

    logger_ue_test.info("\n--- Testing with Flat Terrain ---")
    flat_scales = calculate_ue_scales(50.0, 50.0, 5.0)
    if flat_scales:
        logger_ue_test.info(f"Calculated scales for flat terrain: {flat_scales}")
        generate_ue_import_report(flat_scales, heightmap_dims=(512,512), heightmap_format="R16", report_path=os.path.join(test_output_dir, "ue_import_report_flat.txt"))
    else:
        logger_ue_test.error("Failed to calculate UE scales for flat terrain.")
    
    logger_ue_test.info("\n--- Testing with Invalid Pixel Resolution (<=0) ---")
    invalid_scales_res = calculate_ue_scales(100.0, 200.0, 0)
    if not invalid_scales_res:
        logger_ue_test.info("Correctly handled invalid pixel resolution (0).")
    invalid_scales_res_neg = calculate_ue_scales(100.0, 200.0, -1.0)
    if not invalid_scales_res_neg:
        logger_ue_test.info("Correctly handled invalid pixel resolution (<0).")


    logger_ue_test.info("\n--- Testing with Min Elevation > Max Elevation ---")
    inverted_scales = calculate_ue_scales(200.0, 100.0, 10.0)
    if not inverted_scales:
        logger_ue_test.info("Correctly handled inverted elevation range (min > max).")
    
    logger_ue_test.info("\n--- Testing with Non-Numeric Inputs ---")
    non_numeric_scales = calculate_ue_scales("100.0", 200.0, 10.0) # type: ignore
    if not non_numeric_scales:
        logger_ue_test.info("Correctly handled non-numeric input for min_elev.")
    non_numeric_scales_2 = calculate_ue_scales(100.0, "200.0", 10.0) # type: ignore
    if not non_numeric_scales_2:
        logger_ue_test.info("Correctly handled non-numeric input for max_elev.")
    non_numeric_scales_3 = calculate_ue_scales(100.0, 200.0, "10.0") # type: ignore
    if not non_numeric_scales_3:
        logger_ue_test.info("Correctly handled non-numeric input for pixel_resolution.")

    logger_ue_test.info("\n--- Testing Report Generation with None ue_params ---")
    report_for_none_params = generate_ue_import_report(None, report_path=os.path.join(test_output_dir, "ue_import_report_none_params.txt"))
    logger_ue_test.info(f"Report for None ue_params: \n{report_for_none_params[:100]}...") # Print start of report


    logger_ue_test.info("\n--- Unreal Preparer Tests Finished ---")
    logger_ue_test.info(f"Test reports (if any) are in '{test_output_dir}'.")

