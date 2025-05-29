# coordinate_utils.py
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
import logging # Using logging directly for initial setup

# Attempt to import setup_logger, fall back to basic config if not found
try:
    from logger_setup import setup_logger
    logger = setup_logger(__name__, level=logging.INFO)
except ImportError:
    print("logger_setup.py not found or setup_logger could not be imported. Using basic logging.")
    logger = logging.getLogger(__name__)
    if not logger.handlers: # Avoid adding multiple handlers if already configured
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s")

def transform_bbox_to_crs(bbox: tuple[float, float, float, float], 
                          source_crs_str: str, 
                          target_crs_str: str) -> tuple[float, float, float, float] | None:
    """
    Transforms bounding box coordinates from a source CRS to a target CRS.

    Args:
        bbox: A tuple (min_lon, min_lat, max_lon, max_lat) or (min_x, min_y, max_x, max_y).
              The interpretation depends on the source_crs_str.
        source_crs_str: String identifier for the source CRS (e.g., "EPSG:4326").
        target_crs_str: String identifier for the target CRS (e.g., "EPSG:32610").

    Returns:
        A tuple (min_x_target, min_y_target, max_x_target, max_y_target) in the target CRS,
        or None if transformation fails.
    """
    try:
        source_crs = CRS.from_string(source_crs_str)
        target_crs = CRS.from_string(target_crs_str)
        # always_xy=True ensures (lon, lat) or (x, y) order for input and output
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        
        min_x_src, min_y_src, max_x_src, max_y_src = bbox

        # Transform the two defining points of the bounding box
        # (bottom-left and top-right corners usually, but depends on CRS axis order)
        transformed_corner1_x, transformed_corner1_y = transformer.transform(min_x_src, min_y_src)
        transformed_corner2_x, transformed_corner2_y = transformer.transform(max_x_src, max_y_src)
        
        # Ensure correct ordering for the output bounding box by taking min/max of transformed coords
        final_min_x = min(transformed_corner1_x, transformed_corner2_x)
        final_min_y = min(transformed_corner1_y, transformed_corner2_y)
        final_max_x = max(transformed_corner1_x, transformed_corner2_x)
        final_max_y = max(transformed_corner1_y, transformed_corner2_y)

        logger.info(f"Transformed bbox from {source_crs.name} (Source CRS: {source_crs_str}) "
                    f"to {target_crs.name} (Target CRS: {target_crs_str}): "
                    f"Original: ({min_x_src:.6f}, {min_y_src:.6f}, {max_x_src:.6f}, {max_y_src:.6f}) -> "
                    f"Transformed: ({final_min_x:.2f}, {final_min_y:.2f}, {final_max_x:.2f}, {final_max_y:.2f})")
        return (final_min_x, final_min_y, final_max_x, final_max_y)

    except CRSError as e:
        logger.error(f"CRS error during transformation from '{source_crs_str}' to '{target_crs_str}': {e}. "
                     f"Input bbox: {bbox}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during bounding box transformation: {e}", exc_info=True)
        return None

def get_metric_dimensions(projected_bbox: tuple[float, float, float, float], 
                          crs_units_are_metric: bool = True) -> tuple[float, float] | None:
    """
    Calculates the width and height of a bounding box, assuming its CRS uses metric units.

    Args:
        projected_bbox: A tuple (min_x, min_y, max_x, max_y) in a projected CRS.
        crs_units_are_metric: Boolean indicating if the CRS units are meters. If False,
                              a warning is logged as the result might not be in meters.

    Returns:
        A tuple (width, height) in the units of the CRS (assumed meters), 
        or None if input is invalid.
    """
    try:
        if not isinstance(projected_bbox, tuple) or len(projected_bbox) != 4:
            logger.error("Invalid projected_bbox format. Expected a tuple of 4 numbers.")
            return None
            
        min_x, min_y, max_x, max_y = projected_bbox
        
        if not all(isinstance(coord, (int, float)) for coord in projected_bbox):
            logger.error(f"Invalid coordinate types in projected_bbox: {projected_bbox}. Must be numeric.")
            return None
            
        if not crs_units_are_metric:
            logger.warning(f"Calculating dimensions for bbox {projected_bbox}, but CRS units are not confirmed metric. "
                           "Resulting width/height will be in CRS units.")

        # Check for inverted coordinates, which can happen if points were not correctly ordered
        # or if a transformation resulted in an unexpected configuration.
        if min_x > max_x:
            logger.warning(f"min_x ({min_x}) is greater than max_x ({max_x}) in projected_bbox. Using absolute difference for width.")
        if min_y > max_y:
            logger.warning(f"min_y ({min_y}) is greater than max_y ({max_y}) in projected_bbox. Using absolute difference for height.")

        width = abs(max_x - min_x)
        height = abs(max_y - min_y)
        
        logger.info(f"Calculated dimensions for bbox {projected_bbox}: Width={width:.2f}, Height={height:.2f} (units of input CRS)")
        return width, height
        
    except TypeError: # Catches errors if projected_bbox is not subscriptable or elements are wrong type for abs()
        logger.error(f"Invalid input type for projected_bbox or its elements: {projected_bbox}.", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error calculating metric dimensions for {projected_bbox}: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # Ensure logger is specifically configured for demo if logger_setup was available
    try:
        from logger_setup import setup_logger # Re-import for __main__ scope if needed
        logger_utils_demo = setup_logger("CoordinateUtilsDemo", level=logging.DEBUG)
    except ImportError:
        # If logger_setup is not found, the logger configured at the top of the file will be used.
        # We might want to ensure its level is appropriate for the demo.
        logger.setLevel(logging.DEBUG) # Ensure demo output is visible
        logger_utils_demo = logger # Use the globally configured logger

    logger_utils_demo.info("--- Starting CoordinateUtilsDemo ---")

    # 1. Test BBox Transformation (WGS84 to UTM Zone 32N - Germany example)
    wgs84_bbox_berlin = (13.0, 52.3, 13.7, 52.6) # (lon_min, lat_min, lon_max, lat_max)
    source_epsg_4326 = "EPSG:4326"
    utm32n_epsg = "EPSG:32632" # UTM Zone 32N, WGS84 datum

    logger_utils_demo.info(f"Attempting to transform Berlin bbox: {wgs84_bbox_berlin} "
                           f"from {source_epsg_4326} to {utm32n_epsg}")
    projected_bbox_berlin = transform_bbox_to_crs(wgs84_bbox_berlin, source_epsg_4326, utm32n_epsg)

    if projected_bbox_berlin:
        logger_utils_demo.info(f"Projected Berlin bbox ({utm32n_epsg}): {projected_bbox_berlin}")

        # 2. Test Metric Dimensions Calculation (assuming UTM is metric)
        # CRS("EPSG:32632").axis_info will confirm units are 'metre'
        dimensions_berlin = get_metric_dimensions(projected_bbox_berlin, crs_units_are_metric=True)
        if dimensions_berlin:
            logger_utils_demo.info(f"Metric dimensions of Berlin bbox: Width={dimensions_berlin[0]:.2f}m, "
                                   f"Height={dimensions_berlin[1]:.2f}m")
    else:
        logger_utils_demo.error("Failed to transform Berlin bbox.")

    # Example with an invalid source CRS string
    logger_utils_demo.info("\nAttempting transformation with an invalid source CRS:")
    invalid_src_crs_bbox = transform_bbox_to_crs(wgs84_bbox_berlin, "EPSG:INVALID_SRC", utm32n_epsg)
    if not invalid_src_crs_bbox:
        logger_utils_demo.info("Transformation with invalid source CRS correctly failed.")

    # Example with an invalid target CRS string
    logger_utils_demo.info("\nAttempting transformation with an invalid target CRS:")
    invalid_target_crs_bbox = transform_bbox_to_crs(wgs84_bbox_berlin, source_epsg_4326, "EPSG:INVALID_TARGET")
    if not invalid_target_crs_bbox:
        logger_utils_demo.info("Transformation with invalid target CRS correctly failed.")

    # Test get_metric_dimensions with various inputs
    logger_utils_demo.info("\nTesting get_metric_dimensions with invalid input types:")
    invalid_dims_type = get_metric_dimensions(("a", "b", "c", "d")) # type: ignore
    if not invalid_dims_type:
        logger_utils_demo.info("get_metric_dimensions with non-numeric tuple elements correctly failed.")

    invalid_dims_format = get_metric_dimensions((10, 20, 30)) # type: ignore
    if not invalid_dims_format:
        logger_utils_demo.info("get_metric_dimensions with incorrect tuple length correctly failed.")
        
    logger_utils_demo.info("\nTesting get_metric_dimensions with out-of-order coords (should use abs diff):")
    # min_x > max_x, min_y > max_y. Width/Height should still be positive.
    unordered_bbox = (500000.0, 6000000.0, 400000.0, 5900000.0) 
    dims_unordered = get_metric_dimensions(unordered_bbox)
    if dims_unordered:
        # Expected: Width = 100000.0, Height = 100000.0
        logger_utils_demo.info(f"Dimensions of unordered bbox: Width={dims_unordered[0]:.2f}, Height={dims_unordered[1]:.2f} (abs values used)")


    # Example: Los Angeles (lon_min, lat_min, lon_max, lat_max) -> (-118.5, 33.7, -117.8, 34.2)
    # Target: UTM Zone 11N (EPSG:32611)
    wgs84_bbox_la = (-118.5, 33.7, -117.8, 34.2)
    utm11n_epsg = "EPSG:32611"
    logger_utils_demo.info(f"\nAttempting to transform LA bbox: {wgs84_bbox_la} "
                           f"from {source_epsg_4326} to {utm11n_epsg}")
    projected_bbox_la = transform_bbox_to_crs(wgs84_bbox_la, source_epsg_4326, utm11n_epsg)
    if projected_bbox_la:
        logger_utils_demo.info(f"Projected LA bbox ({utm11n_epsg}): {projected_bbox_la}")
        dimensions_la = get_metric_dimensions(projected_bbox_la)
        if dimensions_la:
            logger_utils_demo.info(f"Metric dimensions of LA bbox: Width={dimensions_la[0]:.2f}m, "
                                   f"Height={dimensions_la[1]:.2f}m")
    else:
        logger_utils_demo.error("Failed to transform LA bbox.")
        
    logger_utils_demo.info("\n--- CoordinateUtilsDemo finished ---")
