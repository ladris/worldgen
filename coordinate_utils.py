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

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError
    from geopy.distance import geodesic, great_circle 
except ImportError:
    logger.warning("Geopy library not found. Geocoding and distance functions may not be available.")
    Nominatim = None 
    geodesic = None
    great_circle = None

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
        transformed_corner1_x, transformed_corner1_y = transformer.transform(min_x_src, min_y_src)
        transformed_corner2_x, transformed_corner2_y = transformer.transform(max_x_src, max_y_src)
        
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
        if min_x > max_x:
            logger.warning(f"min_x ({min_x}) is greater than max_x ({max_x}) in projected_bbox. Using absolute difference for width.")
        if min_y > max_y:
            logger.warning(f"min_y ({min_y}) is greater than max_y ({max_y}) in projected_bbox. Using absolute difference for height.")
        width = abs(max_x - min_x)
        height = abs(max_y - min_y)
        logger.info(f"Calculated dimensions for bbox {projected_bbox}: Width={width:.2f}, Height={height:.2f} (units of input CRS)")
        return width, height
    except TypeError: 
        logger.error(f"Invalid input type for projected_bbox or its elements: {projected_bbox}.", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error calculating metric dimensions for {projected_bbox}: {e}", exc_info=True)
        return None

def geocode_place_name(place_name_query: str, user_agent_app_name: str = "TerrainToolGeocoder") -> tuple[float, float] | None:
    """
    Geocodes a place name query to latitude and longitude using Nominatim.
    """
    if Nominatim is None:
        logger.error("Geopy library (Nominatim) not available. Cannot geocode.")
        return None
    logger.info(f"Geocoding place name: '{place_name_query}' with user_agent: '{user_agent_app_name}'")
    try:
        geolocator = Nominatim(user_agent=user_agent_app_name)
        location = geolocator.geocode(place_name_query, timeout=10)
        if location:
            logger.info(f"Successfully geocoded '{place_name_query}' to: Latitude={location.latitude:.6f}, Longitude={location.longitude:.6f}")
            return location.latitude, location.longitude
        else:
            logger.warning(f"Could not geocode '{place_name_query}'. Place not found or no results returned by Nominatim.")
            return None
    except GeocoderTimedOut:
        logger.error(f"Geocoder service (Nominatim) timed out for query: '{place_name_query}'.")
        return None
    except GeocoderUnavailable:
        logger.error(f"Geocoder service (Nominatim) unavailable for query: '{place_name_query}'. Check internet connection or service status.")
        return None
    except GeocoderServiceError as e:
        logger.error(f"Geocoder service (Nominatim) error for query: '{place_name_query}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during geocoding for '{place_name_query}': {e}", exc_info=True)
        return None

def calculate_bbox_from_center_and_distance(
    center_lat: float, 
    center_lon: float, 
    distance_km: float,
    use_great_circle: bool = False
) -> tuple[float, float, float, float] | None:
    """
    Calculates a bounding box (west, south, east, north) given a center point
    and a distance to extend in each cardinal direction.
    """
    if geodesic is None or great_circle is None: # Check if geopy.distance was imported
        logger.error("Geopy library (distance functions) not available. Cannot calculate bounding box from center.")
        return None
        
    if not (-90 <= center_lat <= 90):
        logger.error(f"Invalid center_lat: {center_lat}. Must be between -90 and 90.")
        return None
    if not (-180 <= center_lon <= 180):
        logger.error(f"Invalid center_lon: {center_lon}. Must be between -180 and 180.")
        return None
    if distance_km <= 0:
        logger.error(f"Invalid distance_km: {distance_km}. Must be positive.")
        return None

    logger.info(f"Calculating bounding box from center ({center_lat:.4f}, {center_lon:.4f}) with distance {distance_km} km.")

    center_point = (center_lat, center_lon)
    dist_calc_method = great_circle if use_great_circle else geodesic

    try:
        north_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=0)
        south_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=180)
        east_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=90)
        west_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=270)

        min_lat = south_point.latitude
        max_lat = north_point.latitude
        min_lon = west_point.longitude
        max_lon = east_point.longitude
        
        if min_lat > max_lat: 
             logger.warning("Calculated min_lat > max_lat, swapping.")
             min_lat, max_lat = max_lat, min_lat
        
        bbox = (min_lon, min_lat, max_lon, max_lat) 
        logger.info(f"Calculated BBox: West={bbox[0]:.4f}, South={bbox[1]:.4f}, East={bbox[2]:.4f}, North={bbox[3]:.4f}")
        return bbox

    except Exception as e:
        logger.error(f"An unexpected error occurred during bounding box calculation: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    try:
        from logger_setup import setup_logger 
        logger_utils_demo = setup_logger("CoordinateUtilsDemo", level=logging.DEBUG)
    except ImportError:
        logger.setLevel(logging.DEBUG) 
        logger_utils_demo = logger 

    logger_utils_demo.info("--- Starting CoordinateUtilsDemo ---")

    wgs84_bbox_berlin = (13.0, 52.3, 13.7, 52.6) 
    source_epsg_4326 = "EPSG:4326"
    utm32n_epsg = "EPSG:32632" 
    logger_utils_demo.info(f"Attempting to transform Berlin bbox: {wgs84_bbox_berlin} from {source_epsg_4326} to {utm32n_epsg}")
    projected_bbox_berlin = transform_bbox_to_crs(wgs84_bbox_berlin, source_epsg_4326, utm32n_epsg)
    if projected_bbox_berlin:
        logger_utils_demo.info(f"Projected Berlin bbox ({utm32n_epsg}): {projected_bbox_berlin}")
        dimensions_berlin = get_metric_dimensions(projected_bbox_berlin, crs_units_are_metric=True)
        if dimensions_berlin:
            logger_utils_demo.info(f"Metric dimensions of Berlin bbox: Width={dimensions_berlin[0]:.2f}m, Height={dimensions_berlin[1]:.2f}m")
    else:
        logger_utils_demo.error("Failed to transform Berlin bbox.")

    logger_utils_demo.info("\nAttempting transformation with an invalid source CRS:")
    invalid_src_crs_bbox = transform_bbox_to_crs(wgs84_bbox_berlin, "EPSG:INVALID_SRC", utm32n_epsg)
    if not invalid_src_crs_bbox:
        logger_utils_demo.info("Transformation with invalid source CRS correctly failed.")

    logger_utils_demo.info("\nAttempting transformation with an invalid target CRS:")
    invalid_target_crs_bbox = transform_bbox_to_crs(wgs84_bbox_berlin, source_epsg_4326, "EPSG:INVALID_TARGET")
    if not invalid_target_crs_bbox:
        logger_utils_demo.info("Transformation with invalid target CRS correctly failed.")

    logger_utils_demo.info("\nTesting get_metric_dimensions with invalid input types:")
    invalid_dims_type = get_metric_dimensions(("a", "b", "c", "d")) # type: ignore
    if not invalid_dims_type:
        logger_utils_demo.info("get_metric_dimensions with non-numeric tuple elements correctly failed.")
    invalid_dims_format = get_metric_dimensions((10, 20, 30)) # type: ignore
    if not invalid_dims_format:
        logger_utils_demo.info("get_metric_dimensions with incorrect tuple length correctly failed.")
        
    logger_utils_demo.info("\nTesting get_metric_dimensions with out-of-order coords (should use abs diff):")
    unordered_bbox = (500000.0, 6000000.0, 400000.0, 5900000.0) 
    dims_unordered = get_metric_dimensions(unordered_bbox)
    if dims_unordered:
        logger_utils_demo.info(f"Dimensions of unordered bbox: Width={dims_unordered[0]:.2f}, Height={dims_unordered[1]:.2f} (abs values used)")

    wgs84_bbox_la = (-118.5, 33.7, -117.8, 34.2)
    utm11n_epsg = "EPSG:32611"
    logger_utils_demo.info(f"\nAttempting to transform LA bbox: {wgs84_bbox_la} from {source_epsg_4326} to {utm11n_epsg}")
    projected_bbox_la = transform_bbox_to_crs(wgs84_bbox_la, source_epsg_4326, utm11n_epsg)
    if projected_bbox_la:
        logger_utils_demo.info(f"Projected LA bbox ({utm11n_epsg}): {projected_bbox_la}")
        dimensions_la = get_metric_dimensions(projected_bbox_la)
        if dimensions_la:
            logger_utils_demo.info(f"Metric dimensions of LA bbox: Width={dimensions_la[0]:.2f}m, Height={dimensions_la[1]:.2f}m")
    else:
        logger_utils_demo.error("Failed to transform LA bbox.")
        
    logger_utils_demo.info("\n--- Geocoding Tests ---")
    if Nominatim is not None: # Check if geopy was imported
        place = "Mount Everest"
        coords = geocode_place_name(place)
        if coords:
            logger_utils_demo.info(f"Coordinates for {place}: Latitude={coords[0]:.4f}, Longitude={coords[1]:.4f}")
        else:
            logger_utils_demo.warning(f"Could not geocode {place}. This might be due to no internet or Nominatim policy/availability.")
        place_fail = "HopefullyThisPlaceDoesNotExist12345XYZAndReturnsNoResults"
        coords_fail = geocode_place_name(place_fail)
        if not coords_fail:
            logger_utils_demo.info(f"Correctly failed to geocode non-existent place: '{place_fail}'")
        specific_place = "Eiffel Tower, Paris"
        specific_coords = geocode_place_name(specific_place)
        if specific_coords:
            logger_utils_demo.info(f"Coordinates for {specific_place}: Latitude={specific_coords[0]:.4f}, Longitude={specific_coords[1]:.4f}")
        else:
            logger_utils_demo.warning(f"Could not geocode {specific_place}. This might be due to no internet or Nominatim policy/availability.")
    else:
        logger_utils_demo.warning("Skipping geocoding tests as Geopy/Nominatim is not available.")

    logger_utils_demo.info("\n--- Bounding Box Calculation Tests ---")
    if geodesic is not None and great_circle is not None: # Check if geopy.distance was imported
        denver_coords_direct = (39.7392, -104.9903) # Denver, CO approx coords
        distance = 50 
        logger_utils_demo.info(f"Calculating {distance}km bbox around Denver ({denver_coords_direct[0]:.4f}, {denver_coords_direct[1]:.4f}) using geodesic")
        bbox_denver = calculate_bbox_from_center_and_distance(denver_coords_direct[0], denver_coords_direct[1], distance)
        if bbox_denver:
            logger_utils_demo.info(f"Denver {distance}km BBox (W,S,E,N): ({bbox_denver[0]:.4f}, {bbox_denver[1]:.4f}, {bbox_denver[2]:.4f}, {bbox_denver[3]:.4f})")
            # Optional: Verify dimensions (approximate)
            # projected_bbox_denver_val = transform_bbox_to_crs(bbox_denver, "EPSG:4326", "EPSG:32613") # UTM Zone 13N for Denver
            # if projected_bbox_denver_val:
            #     dims = get_metric_dimensions(projected_bbox_denver_val)
            #     if dims: logger_utils_demo.info(f"Approx. metric dimensions: W={dims[0]/1000:.1f}km, H={dims[1]/1000:.1f}km (Geodesic)")

        logger_utils_demo.info(f"Calculating {distance}km bbox around Denver ({denver_coords_direct[0]:.4f}, {denver_coords_direct[1]:.4f}) using great_circle")
        bbox_denver_gc = calculate_bbox_from_center_and_distance(denver_coords_direct[0], denver_coords_direct[1], distance, use_great_circle=True)
        if bbox_denver_gc:
             logger_utils_demo.info(f"Denver {distance}km BBox (Great Circle) (W,S,E,N): ({bbox_denver_gc[0]:.4f}, {bbox_denver_gc[1]:.4f}, {bbox_denver_gc[2]:.4f}, {bbox_denver_gc[3]:.4f})")

        invalid_bbox_calc = calculate_bbox_from_center_and_distance(95, 0, 10) 
        if not invalid_bbox_calc: logger_utils_demo.info("Correctly handled invalid latitude for bbox calculation.")
        invalid_bbox_calc_dist = calculate_bbox_from_center_and_distance(0, 0, -10) 
        if not invalid_bbox_calc_dist: logger_utils_demo.info("Correctly handled invalid distance for bbox calculation.")

        north_pole_lat, north_pole_lon = 89.95, 0.0 # Closer to pole
        distance_pole = 10 
        logger_utils_demo.info(f"Calculating {distance_pole}km bbox around North Pole area ({north_pole_lat:.2f}, {north_pole_lon})")
        bbox_pole = calculate_bbox_from_center_and_distance(north_pole_lat, north_pole_lon, distance_pole)
        if bbox_pole:
             logger_utils_demo.info(f"North Pole area {distance_pole}km BBox (W,S,E,N): ({bbox_pole[0]:.4f}, {bbox_pole[1]:.4f}, {bbox_pole[2]:.4f}, {bbox_pole[3]:.4f})")
        
        # Test near anti-meridian (e.g., Fiji, direct coords to avoid geocoding dependency here)
        # Using direct coordinates for Suva, Fiji for robustness if geocoding fails
        lat_fiji, lon_fiji = -18.1416, 178.4419 
        distance_fiji = 200 # km, larger distance to potentially cross anti-meridian more clearly
        logger_utils_demo.info(f"Calculating {distance_fiji}km bbox around Fiji test coords ({lat_fiji:.4f}, {lon_fiji:.4f})")
        bbox_fiji = calculate_bbox_from_center_and_distance(lat_fiji, lon_fiji, distance_fiji)
        if bbox_fiji:
            logger_utils_demo.info(f"Fiji test {distance_fiji}km BBox (W,S,E,N): ({bbox_fiji[0]:.4f}, {bbox_fiji[1]:.4f}, {bbox_fiji[2]:.4f}, {bbox_fiji[3]:.4f})")
    else:
        logger_utils_demo.warning("Skipping BBox calculation tests as Geopy distance functions are not available.")

    logger_utils_demo.info("\n--- CoordinateUtilsDemo finished ---")
