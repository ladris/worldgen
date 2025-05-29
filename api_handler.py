# api_handler.py
import requests
import os
import logging # Fallback logging

try:
    from config_manager import get_api_key, CONFIG_FILE_PATH # Import CONFIG_FILE_PATH for example
    from logger_setup import setup_logger
    logger = setup_logger(__name__, level=logging.INFO)
except ImportError:
    print("Warning: config_manager.py or logger_setup.py not found. Using basic logging and limited functionality.")
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s")
    
    # Define get_api_key locally if not importable, so __main__ example can run its checks
    def get_api_key(service_name: str) -> str | None:
        logger.warning(f"Using mock get_api_key for {service_name} as config_manager is unavailable.")
        return os.environ.get(f"{service_name.upper()}_API_KEY") # Simple fallback for example
    CONFIG_FILE_PATH = "config.json" # Define for example usage


OPENTOPOGRAPHY_API_URL = "https://portal.opentopography.org/API/globaldem"

def fetch_opentopography_data(dem_type: str, 
                              bbox: tuple[float, float, float, float], 
                              output_file: str,
                              api_key_override: str | None = None) -> bool:
    """
    Fetches elevation data from the OpenTopography API for a given bounding box.

    Args:
        dem_type: The type of DEM to request (e.g., "NASADEM", "SRTMGL1", "COP30").
        bbox: A tuple (west, south, east, north) defining the area of interest.
              Coordinates are in WGS84 decimal degrees.
        output_file: Path to save the downloaded GeoTIFF data.
        api_key_override: OpenTopography API key. If provided, this key is used. 
                          If None, tries to fetch from config_manager.

    Returns:
        True if download was successful, False otherwise.
    """
    if api_key_override is not None:
        api_key = api_key_override
        logger.debug("Using provided API key override.")
    else:
        try:
            api_key = get_api_key("OpenTopography")
        except NameError: # In case get_api_key was not even defined due to import error
             logger.error("config_manager's get_api_key is not available.")
             api_key = None


    if not api_key: # Checks if api_key is None or empty string
        logger.error("OpenTopography API key not found or is empty. Please set it in "
                     f"{CONFIG_FILE_PATH}, as an environment variable (OPENTOPOGRAPHY_API_KEY), "
                     "or pass it via api_key_override.")
        return False

    try:
        west, south, east, north = bbox
        if not all(isinstance(coord, (int, float)) for coord in bbox):
            logger.error(f"Invalid bounding box coordinates: {bbox}. All must be numbers.")
            return False
        # Basic validation for latitude and longitude ranges
        if not (-90 <= south <= 90 and -90 <= north <= 90 and -180 <= west <= 180 and -180 <= east <= 180):
            logger.error(f"Invalid coordinate values in bbox: {bbox}. Lat (-90 to 90), Lon (-180 to 180).")
            return False
        if west >= east or south >= north:
            logger.error(f"Invalid bbox order or zero area: west={west} >= east={east} or south={south} >= north={north}.")
            return False

    except ValueError:
        logger.error(f"Bounding box {bbox} is not a valid tuple of four numbers.")
        return False


    params = {
        "demtype": dem_type,
        "west": west,
        "south": south,
        "east": east,
        "north": north,
        "outputFormat": "GTiff", # Request GeoTIFF format
        "API_Key": api_key
    }

    logger.info(f"Requesting DEM '{dem_type}' for bbox: W={west},S={south},E={east},N={north} from OpenTopography.")
    
    try:
        response = requests.get(OPENTOPOGRAPHY_API_URL, params=params, stream=True, timeout=180) # Increased timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")

        with open(output_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192): # 8KB chunks
                f.write(chunk)
        logger.info(f"Successfully downloaded DEM data to {output_file}")
        # Basic check for file size, though API might return small error TIFs for some issues.
        if os.path.exists(output_file) and os.path.getsize(output_file) < 1024: # Check if file is very small (e.g. <1KB)
             # OpenTopography sometimes returns a small TIFF with an error message embedded
            with open(output_file, "rb") as f_check:
                # Read a small portion that might contain text if it's an error TIFF
                header = f_check.read(200).decode(errors='ignore') 
            if "Error" in header or "error" in header or "failed" in header or "Forbidden" in header:
                logger.warning(f"Downloaded file {output_file} is very small and may contain an API error message. Header snippet: {header[:100]}")
                # Potentially return False here if small error TIFFs should be treated as failure
                # For now, it's a warning, as the file *was* downloaded.
        return True

    except requests.exceptions.HTTPError as e:
        err_msg = f"HTTP error from OpenTopography API: {e.response.status_code}"
        try:
            # Try to get more detailed error from response body (often JSON or XML for OT)
            response_text = e.response.text
            if response_text:
                err_msg += f" - Body: {response_text[:500]}" # Log first 500 chars of error
        except Exception:
            pass # Ignore if can't read response body
        logger.error(err_msg, exc_info=False) # exc_info=False as we've extracted relevant info
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during OpenTopography API request: {e}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout (180s) during OpenTopography API request: {e}")
    except requests.exceptions.RequestException as e: # Catch other request-related errors
        logger.error(f"An unexpected error occurred with the OpenTopography API request: {e}", exc_info=True)
    except IOError as e:
        logger.error(f"File I/O error when saving DEM data to {output_file}: {e}", exc_info=True)
    except Exception as e: # Catch-all for any other unexpected errors
        logger.error(f"An unexpected error occurred in fetch_opentopography_data: {e}", exc_info=True)
        
    return False

if __name__ == '__main__':
    # This block is for example usage and basic testing.
    # Ensure 'requests' is installed: pip install requests
    # For live tests, configure OpenTopography API key in config.json or env var.

    # Use a specific logger for this test section
    try:
        # Re-setup logger if main logger_setup is available
        from logger_setup import setup_logger as main_setup_logger
        logger_api_test = main_setup_logger("APITestMain", level="DEBUG")
    except ImportError:
        logger_api_test = logger # Use the fallback logger already configured
        logger_api_test.setLevel(logging.DEBUG) # Ensure it's verbose enough for test
        logger_api_test.warning("Running APITestMain with fallback logger configuration.")

    logger_api_test.info("--- OpenTopography API Fetch Test ---")

    # Attempt to get API key to determine if a live test can be run
    configured_api_key = None
    try:
        configured_api_key = get_api_key("OpenTopography")
    except NameError: # get_api_key might not be defined if imports failed
        pass

    output_dir_example = "output_data_test" # Use a specific test output directory
    if not os.path.exists(output_dir_example):
        os.makedirs(output_dir_example)
        logger_api_test.info(f"Created example output directory: {output_dir_example}")

    # Test Case 1: Attempt live API call if key is found
    if configured_api_key:
        logger_api_test.info("OpenTopography API key found. Attempting a small, live API call.")
        # Small, valid bounding box (e.g., part of Golden Gate Park, San Francisco)
        # Using a different bbox than previous examples to avoid large downloads.
        # ggp_bbox = (-122.49, 37.765, -122.48, 37.770) # West, South, East, North
        # Even smaller test area:
        small_test_bbox = (-122.485, 37.768, -122.480, 37.770) 
        dem_type_to_fetch = "SRTMGL1" # Common, usually available, relatively small
        output_filename_live = os.path.join(output_dir_example, f"test_{dem_type_to_fetch}_live.tif")
        
        # Clean up previous test file if it exists
        if os.path.exists(output_filename_live):
            os.remove(output_filename_live)

        success = fetch_opentopography_data(dem_type_to_fetch, small_test_bbox, output_filename_live)

        if success:
            logger_api_test.info(f"Live test download successful. Check '{output_filename_live}'.")
            if os.path.exists(output_filename_live) and os.path.getsize(output_filename_live) > 100: # Check if not empty/tiny
                logger_api_test.info(f"File '{output_filename_live}' exists and has size {os.path.getsize(output_filename_live)} bytes.")
            else:
                logger_api_test.warning(f"File '{output_filename_live}' was created but is very small or empty. This might indicate an API-side issue or an error TIFF.")
        else:
            logger_api_test.error("Live test download failed. Check logs for details.")
    else:
        logger_api_test.warning("OpenTopography API key not found or config_manager not available. Skipping live API test.")
        logger_api_test.info(f"To run a live test, set your API key for 'OpenTopography' in '{CONFIG_FILE_PATH}' or as an environment variable.")

    # Test Case 2: API key explicitly provided as empty string (should fail)
    logger_api_test.info("\n--- Test Case: API call with empty string API key ---")
    # BBox for a known area, e.g., Mount Everest
    everest_bbox = (86.90, 27.97, 86.95, 28.00) 
    output_filename_empty_key = os.path.join(output_dir_example, "test_everest_empty_key.tif")
    if os.path.exists(output_filename_empty_key): # Cleanup
        os.remove(output_filename_empty_key)

    success_empty_key = fetch_opentopography_data("NASADEM", everest_bbox, output_filename_empty_key, api_key_override="") 
    if not success_empty_key:
        logger_api_test.info("API call with empty string API key correctly failed as expected.")
    else:
        logger_api_test.error("API call with empty string API key unexpectedly succeeded.")
        if os.path.exists(output_filename_empty_key): os.remove(output_filename_empty_key) # Clean up if it somehow got created

    # Test Case 3: Invalid DEM type (should fail with HTTP error if API is reached)
    logger_api_test.info("\n--- Test Case: API call with invalid DEM type ---")
    invalid_dem_type = "INVALID_DEM_TYPE_XYZ"
    output_filename_invalid_dem = os.path.join(output_dir_example, f"test_{invalid_dem_type}.tif")
    if os.path.exists(output_filename_invalid_dem): os.remove(output_filename_invalid_dem)

    # This test requires a valid key to actually reach the API and get a DEM type error
    if configured_api_key:
        success_invalid_dem = fetch_opentopography_data(invalid_dem_type, small_test_bbox, output_filename_invalid_dem, api_key_override=configured_api_key)
        if not success_invalid_dem:
            logger_api_test.info(f"API call with invalid DEM type ('{invalid_dem_type}') correctly failed.")
        else:
            logger_api_test.error(f"API call with invalid DEM type ('{invalid_dem_type}') unexpectedly succeeded.")
            if os.path.exists(output_filename_invalid_dem): os.remove(output_filename_invalid_dem)
    else:
        logger_api_test.warning("Skipping invalid DEM type test as no API key is configured (would fail due to missing key first).")

    # Test Case 4: Invalid Bbox (e.g. west > east)
    logger_api_test.info("\n--- Test Case: API call with invalid bbox ---")
    invalid_bbox = (10.0, 20.0, 5.0, 25.0) # west > east
    output_filename_invalid_bbox = os.path.join(output_dir_example, "test_invalid_bbox.tif")
    success_invalid_bbox = fetch_opentopography_data("SRTMGL1", invalid_bbox, output_filename_invalid_bbox, api_key_override="dummy_key_for_logic_test")
    if not success_invalid_bbox:
        logger_api_test.info("API call with invalid bbox correctly failed before making API request.")
    else:
        logger_api_test.error("API call with invalid bbox unexpectedly succeeded.")

    logger_api_test.info("\n--- OpenTopography API Fetch Test Suite Finished ---")
    logger_api_test.info(f"Test artifacts (if any) are in '{output_dir_example}'. Consider cleaning it up if necessary.")
    # Example cleanup:
    # import shutil
    # if os.path.exists(output_dir_example):
    #     logger_api_test.info(f"Cleaning up test directory: {output_dir_example}")
    #     shutil.rmtree(output_dir_example)
