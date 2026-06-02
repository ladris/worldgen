# coordinate_utils.py
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
import logging # Using logging directly for initial setup

# Attempt to import setup_logger, fall back to basic config if not found
try:
    from logger_setup import setup_logger
    logger = setup_logger(__name__, level=logging.INFO)
except ImportError:
    # This print is for the case where logger_setup itself is missing
    print("Warning: logger_setup.py not found or setup_logger could not be imported. Using basic Python logging.")
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s")

# Geopy imports
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError
    from geopy.distance import geodesic, great_circle
    GEOPY_AVAILABLE = True
except ImportError:
    # Warning logged here if logger is already configured by logger_setup
    if 'logger' in globals() and logger.handlers: # Check if our main logger is available
        logger.warning("Geopy library not found. Geocoding and distance functions may not be available.")
    else: # Fallback print if logger isn't ready
        print("Warning: Geopy library not found. Geocoding and distance functions may not be available.")
    Nominatim = None
    geodesic = None
    great_circle = None
    GEOPY_AVAILABLE = False # Explicitly set

# UTM library import
try:
    import utm
    UTM_AVAILABLE = True # If geopy was false, this makes it true if utm is found
except ImportError:
    UTM_AVAILABLE = False # Stays false if geopy was also false, or becomes false if geopy was true but utm is not
    # Warning logged here if logger is available
    if 'logger' in globals() and logger.handlers:
        logger.warning("utm library not found. Automatic UTM EPSG detection will not be available.")
    else:
        print("Warning: utm library not found. Automatic UTM EPSG detection will not be available.")


def transform_bbox_to_crs(bbox: tuple[float, float, float, float],
                          source_crs_str: str,
                          target_crs_str: str) -> tuple[float, float, float, float] | None:
    """
    Transforms bounding box coordinates from a source CRS to a target CRS.
    """
    try:
        source_crs = CRS.from_string(source_crs_str)
        target_crs = CRS.from_string(target_crs_str)
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        min_x_src, min_y_src, max_x_src, max_y_src = bbox
        transformed_corner1_x, transformed_corner1_y = transformer.transform(min_x_src, min_y_src)
        transformed_corner2_x, transformed_corner2_y = transformer.transform(max_x_src, max_y_src)
        final_min_x = min(transformed_corner1_x, transformed_corner2_x)
        final_min_y = min(transformed_corner1_y, transformed_corner2_y)
        final_max_x = max(transformed_corner1_x, transformed_corner2_x)
        final_max_y = max(transformed_corner1_y, transformed_corner2_y)
        logger.info(f"Transformed bbox from {source_crs.name} ({source_crs_str}) to {target_crs.name} ({target_crs_str}): "
                    f"Original: ({min_x_src:.6f}, {min_y_src:.6f}, {max_x_src:.6f}, {max_y_src:.6f}) -> "
                    f"Transformed: ({final_min_x:.2f}, {final_min_y:.2f}, {final_max_x:.2f}, {final_max_y:.2f})")
        return final_min_x, final_min_y, final_max_x, final_max_y
    except CRSError as e:
        logger.error(f"CRS error during transformation from '{source_crs_str}' to '{target_crs_str}': {e}. Input bbox: {bbox}")
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
            logger.warning(f"Calculating dimensions for bbox {projected_bbox}, but CRS units are not confirmed metric.")
        if min_x > max_x: logger.warning(f"min_x ({min_x}) > max_x ({max_x}) in projected_bbox. Using abs diff.")
        if min_y > max_y: logger.warning(f"min_y ({min_y}) > max_y ({max_y}) in projected_bbox. Using abs diff.")
        width = abs(max_x - min_x)
        height = abs(max_y - min_y)
        logger.info(f"Calculated dimensions for bbox {projected_bbox}: W={width:.2f}, H={height:.2f} (CRS units)")
        return width, height
    except TypeError:
        logger.error(f"Invalid input type for projected_bbox: {projected_bbox}.", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error calculating metric dimensions for {projected_bbox}: {e}", exc_info=True)
        return None

def geocode_place_name(place_name_query: str, user_agent_app_name: str = "TerrainToolGeocoder") -> tuple[float, float] | None:
    """
    Geocodes a place name query to latitude and longitude using Nominatim.
    """
    if not GEOPY_AVAILABLE or Nominatim is None: # Check GEOPY_AVAILABLE as well
        logger.error("Geopy library (Nominatim) not available. Cannot geocode.")
        return None
    logger.info(f"Geocoding place name: '{place_name_query}' with user_agent: '{user_agent_app_name}'")
    try:
        geolocator = Nominatim(user_agent=user_agent_app_name)
        location = geolocator.geocode(place_name_query, timeout=10)
        if location:
            logger.info(f"Successfully geocoded '{place_name_query}' to: Lat={location.latitude:.6f}, Lon={location.longitude:.6f}")
            return location.latitude, location.longitude
        else:
            logger.warning(f"Could not geocode '{place_name_query}'. Place not found or no results by Nominatim.")
            return None
    except GeocoderTimedOut: logger.error(f"Geocoder (Nominatim) timed out for: '{place_name_query}'."); return None
    except GeocoderUnavailable: logger.error(f"Geocoder (Nominatim) unavailable for: '{place_name_query}'."); return None
    except GeocoderServiceError as e: logger.error(f"Geocoder (Nominatim) error for: '{place_name_query}': {e}"); return None
    except Exception as e: logger.error(f"Unexpected error during geocoding for '{place_name_query}': {e}", exc_info=True); return None

def calculate_bbox_from_center_and_distance(
    center_lat: float, center_lon: float, distance_km: float, use_great_circle: bool = False
) -> tuple[float, float, float, float] | None:
    """
    Calculates a bounding box (west, south, east, north) given a center point and distance.
    """
    if not GEOPY_AVAILABLE or geodesic is None or great_circle is None:
        logger.error("Geopy library (distance functions) not available. Cannot calculate bounding box.")
        return None
    if not (-90 <= center_lat <= 90): logger.error(f"Invalid center_lat: {center_lat}."); return None
    if not (-180 <= center_lon <= 180): logger.error(f"Invalid center_lon: {center_lon}."); return None
    if distance_km <= 0: logger.error(f"Invalid distance_km: {distance_km}. Must be positive."); return None
    logger.info(f"Calculating bbox from center ({center_lat:.4f}, {center_lon:.4f}), dist {distance_km} km.")
    center_point = (center_lat, center_lon); dist_calc_method = great_circle if use_great_circle else geodesic
    try:
        north_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=0)
        south_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=180)
        east_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=90)
        west_point = dist_calc_method(kilometers=distance_km).destination(point=center_point, bearing=270)
        min_lat, max_lat = south_point.latitude, north_point.latitude
        min_lon, max_lon = west_point.longitude, east_point.longitude
        if min_lat > max_lat: logger.warning("Calculated min_lat > max_lat, swapping."); min_lat, max_lat = max_lat, min_lat
        bbox = (min_lon, min_lat, max_lon, max_lat)
        logger.info(f"Calculated BBox: W={bbox[0]:.4f}, S={bbox[1]:.4f}, E={bbox[2]:.4f}, N={bbox[3]:.4f}")
        return bbox
    except Exception as e: logger.error(f"Unexpected error during bbox calculation: {e}", exc_info=True); return None

def get_utm_epsg_from_latlon(latitude: float, longitude: float) -> str | None:
    """
    Determines the UTM EPSG code from latitude and longitude.
    """
    global_logger_available = 'logger' in globals() and logger is not None and hasattr(logger, "error")

    if not UTM_AVAILABLE:
        log_msg = "The 'utm' library is not installed. Cannot perform automatic UTM EPSG detection."
        if global_logger_available: logger.error(log_msg)
        else: print(f"ERROR: {log_msg}")
        return None
    if not (-90 <= latitude <= 90):
        log_msg = f"Invalid latitude: {latitude}. Must be between -90 and 90."
        if global_logger_available: logger.error(log_msg)
        else: print(f"ERROR: {log_msg}")
        return None
    if not (-180 <= longitude <= 180):
        log_msg = f"Invalid longitude: {longitude}. Must be between -180 and 180."
        if global_logger_available: logger.error(log_msg)
        else: print(f"ERROR: {log_msg}")
        return None
    try:
        utm_info = utm.from_latlon(latitude, longitude)
        zone_number = utm_info[2]
        is_northern_hemisphere = latitude >= 0
        epsg_base = 32600 if is_northern_hemisphere else 32700
        epsg_code_val = epsg_base + zone_number
        epsg_code_str = f"EPSG:{epsg_code_val}"
        if global_logger_available:
            logger.info(f"Determined UTM EPSG for ({latitude:.4f}, {longitude:.4f}) as: {epsg_code_str} (Zone {zone_number}{utm_info[3]})")
        return epsg_code_str
    except utm.error.OutOfRangeError: # type: ignore
        log_msg = (f"Coords ({latitude:.4f}, {longitude:.4f}) are out of standard UTM range. "
                   "Consider Polar Stereographic (e.g., EPSG:32661 Arctic, EPSG:32761 Antarctic).")
        if global_logger_available: logger.warning(log_msg)
        else: print(f"WARNING: {log_msg}")
        return None
    except Exception as e:
        log_msg = f"Unexpected error in UTM EPSG detection for ({latitude:.4f}, {longitude:.4f}): {e}"
        if global_logger_available: logger.error(log_msg, exc_info=True)
        else: print(f"ERROR: {log_msg}")
        return None

if __name__ == '__main__':
    try: from logger_setup import setup_logger; logger_utils_demo = setup_logger("CoordinateUtilsDemo", level=logging.DEBUG)
    except ImportError: logger.setLevel(logging.DEBUG); logger_utils_demo = logger
    logger_utils_demo.info("--- Starting CoordinateUtilsDemo ---")
    # ... (Existing tests for transform_bbox_to_crs, get_metric_dimensions) ...
    wgs84_bbox_berlin=(13.0,52.3,13.7,52.6); src_epsg="EPSG:4326"; utm32n="EPSG:32632"
    logger_utils_demo.info(f"Transform Berlin bbox: {wgs84_bbox_berlin} from {src_epsg} to {utm32n}")
    pbb = transform_bbox_to_crs(wgs84_bbox_berlin,src_epsg,utm32n)
    if pbb: logger_utils_demo.info(f"Projected: {pbb}"); dims=get_metric_dimensions(pbb); print(dims) # Shortened
    else: logger_utils_demo.error("Berlin transform failed.")
    if not transform_bbox_to_crs(wgs84_bbox_berlin,"EPSG:INVALID",utm32n): logger_utils_demo.info("Invalid src CRS handled.")
    if not transform_bbox_to_crs(wgs84_bbox_berlin,src_epsg,"EPSG:INVALID"): logger_utils_demo.info("Invalid target CRS handled.")
    if not get_metric_dimensions(("a","b","c","d")):logger_utils_demo.info("Invalid types for get_metric_dimensions handled.") # type: ignore
    if not get_metric_dimensions((1,2,3)):logger_utils_demo.info("Invalid tuple length for get_metric_dimensions handled.") # type: ignore
    udims=get_metric_dimensions((5,6,4,5)); logger_utils_demo.info(f"Unordered get_metric_dimensions: {udims}")

    logger_utils_demo.info("\n--- Geocoding Tests ---")
    if GEOPY_AVAILABLE and Nominatim is not None:
        for p in ["Mount Everest", "HopefullyThisPlaceDoesNotExist12345XYZ", "Eiffel Tower, Paris"]:
            coords = geocode_place_name(p)
            if coords: logger_utils_demo.info(f"Coords for {p}: Lat={coords[0]:.4f}, Lon={coords[1]:.4f}")
            else: logger_utils_demo.warning(f"Could not geocode {p} (or correctly failed).")
    else: logger_utils_demo.warning("Skipping geocoding tests: Geopy/Nominatim unavailable.")

    logger_utils_demo.info("\n--- Bounding Box Calculation Tests ---")
    if GEOPY_AVAILABLE and geodesic is not None:
        d_lat,d_lon,dist_km = 39.7392,-104.9903,50
        logger_utils_demo.info(f"Calc {dist_km}km bbox around Denver ({d_lat:.4f},{d_lon:.4f})")
        for gc_opt in [False, True]:
            bbox_d = calculate_bbox_from_center_and_distance(d_lat,d_lon,dist_km,use_great_circle=gc_opt)
            if bbox_d: logger_utils_demo.info(f"Denver {dist_km}km BBox (GC={gc_opt}): (W={bbox_d[0]:.4f},S={bbox_d[1]:.4f},E={bbox_d[2]:.4f},N={bbox_d[3]:.4f})")
        if not calculate_bbox_from_center_and_distance(95,0,10): logger_utils_demo.info("Invalid lat for bbox calc handled.")
        if not calculate_bbox_from_center_and_distance(0,0,-10): logger_utils_demo.info("Invalid dist for bbox calc handled.")
        np_lat,np_lon,np_dist = 89.95,0.0,10
        logger_utils_demo.info(f"Calc {np_dist}km bbox around N Pole ({np_lat:.2f},{np_lon})")
        bbox_p = calculate_bbox_from_center_and_distance(np_lat,np_lon,np_dist)
        if bbox_p: logger_utils_demo.info(f"N Pole {np_dist}km BBox: (W={bbox_p[0]:.4f},S={bbox_p[1]:.4f},E={bbox_p[2]:.4f},N={bbox_p[3]:.4f})")
        fj_lat,fj_lon,fj_dist = -18.1416,178.4419,200
        logger_utils_demo.info(f"Calc {fj_dist}km bbox around Fiji ({fj_lat:.4f},{fj_lon})")
        bbox_fj = calculate_bbox_from_center_and_distance(fj_lat,fj_lon,fj_dist)
        if bbox_fj: logger_utils_demo.info(f"Fiji {fj_dist}km BBox: (W={bbox_fj[0]:.4f},S={bbox_fj[1]:.4f},E={bbox_fj[2]:.4f},N={bbox_fj[3]:.4f})")
    else: logger_utils_demo.warning("Skipping BBox calc tests: Geopy distance unavailable.")

    logger_utils_demo.info("\n--- UTM EPSG Detection Tests ---")
    if UTM_AVAILABLE:
        test_locs = {"Denver":(39.7392,-104.9903,"EPSG:32613"), "Paris":(48.8566,2.3522,"EPSG:32631"), "Sydney":(-33.8688,151.2093,"EPSG:32756")}
        for name,(lat,lon,expected_epsg) in test_locs.items():
            epsg = get_utm_epsg_from_latlon(lat,lon)
            logger_utils_demo.info(f"UTM EPSG for {name} ({lat},{lon}): {epsg}")
            if epsg != expected_epsg: logger_utils_demo.error(f"Expected {expected_epsg} for {name}, got {epsg}")
        if not get_utm_epsg_from_latlon(95.0,0.0): logger_utils_demo.info("Invalid lat for UTM EPSG handled.")
        if not get_utm_epsg_from_latlon(85.0,0.0): logger_utils_demo.info("Polar region for UTM EPSG handled (returned None).")
    else: logger_utils_demo.warning("UTM library not available, skipping UTM EPSG detection tests.")

    logger_utils_demo.info("\n--- CoordinateUtilsDemo finished ---")
