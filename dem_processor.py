# dem_processor.py
import os
import json
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.enums import Resampling # For potential future use, e.g. reproject
from shapely.geometry import box
from PIL import Image
import logging
from typing import Any # Import Any for type hinting

try:
    from logger_setup import setup_logger
    logger = setup_logger(__name__, level=logging.INFO)
except ImportError:
    print("Warning: logger_setup.py not found. Using basic logging for dem_processor.")
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s")

try:
    from coordinate_utils import transform_bbox_to_crs
except ImportError:
    logger.warning("coordinate_utils.py not found. CRS transformation capabilities will be limited.")
    transform_bbox_to_crs = None


def get_dem_info_and_data(dem_path: str) -> tuple[np.ndarray | None, dict | None, Any | None]:
    """
    Opens a DEM file, reads the first band into a NumPy array, and extracts metadata.

    Args:
        dem_path: Path to the DEM file (e.g., GeoTIFF).

    Returns:
        A tuple containing:
        - data_array (np.ndarray | None): NumPy array of the DEM data.
        - profile (dict | None): Rasterio profile (metadata) of the DEM.
        - nodata_value (Any | None): The NoData value defined in the DEM.
        Returns (None, None, None) if an error occurs.
    """
    if not os.path.exists(dem_path):
        logger.error(f"DEM file not found at path: {dem_path}")
        return None, None, None
        
    try:
        with rasterio.open(dem_path) as src:
            profile = src.profile
            data_array = src.read(1) # Read the first band
            nodata_value = src.nodata

            logger.info(f"Successfully read DEM: {dem_path}. Shape: {data_array.shape}, CRS: {profile.get('crs')}")
            logger.debug(f"Profile: {profile}")
            logger.debug(f"Nodata value from source: {nodata_value}")

            # Handle NoData values in the array
            # If data is float and nodata_value exists, convert nodata to np.nan for easier processing
            if np.issubdtype(data_array.dtype, np.floating) and nodata_value is not None:
                data_array[data_array == nodata_value] = np.nan
                logger.info(f"Converted nodata value {nodata_value} to np.nan in float array.")
            elif nodata_value is not None:
                logger.info(f"Integer array. Nodata value {nodata_value} retained. Use it for masking if needed.")
            
            return data_array, profile, nodata_value
    except rasterio.errors.RasterioIOError as e:
        logger.error(f"Rasterio I/O error opening or reading {dem_path}: {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"Unexpected error in get_dem_info_and_data for {dem_path}: {e}", exc_info=True)
        return None, None, None


def clip_raster_to_bbox(input_dem_path: str, 
                        output_clipped_path: str, 
                        clip_bounds: tuple[float, float, float, float],
                        crs_of_bounds: str | None = None) -> bool:
    """
    Clips a raster to a given bounding box and saves the result.

    Args:
        input_dem_path: Path to the input DEM file.
        output_clipped_path: Path to save the clipped DEM.
        clip_bounds: Tuple (west, south, east, north) for clipping.
                     Assumed to be in the SAME CRS as the input_dem_path for this iteration.
        crs_of_bounds: The CRS of `clip_bounds` (e.g., "EPSG:4326").
                       If provided and different from raster's CRS, transformation will be attempted.

    Returns:
        True if successful, False otherwise.
    """
    if not os.path.exists(input_dem_path):
        logger.error(f"Input DEM for clipping not found: {input_dem_path}")
        return False

    try:
        with rasterio.open(input_dem_path) as src:
            raster_crs = src.crs
            logger.info(f"Clipping {input_dem_path} (CRS: {raster_crs}) to bounds: {clip_bounds} (CRS: {crs_of_bounds or 'assumed same as raster'}).")

            transformed_bounds = clip_bounds
            if crs_of_bounds and raster_crs and str(raster_crs).upper() != crs_of_bounds.upper():
                if transform_bbox_to_crs:
                    logger.info(f"Attempting to transform clip_bounds from {crs_of_bounds} to raster CRS {raster_crs}.")
                    transformed_bounds_tuple = transform_bbox_to_crs(clip_bounds, crs_of_bounds, str(raster_crs))
                    if transformed_bounds_tuple is None:
                        logger.error("Failed to transform bounding box CRS. Cannot clip.")
                        return False
                    transformed_bounds = transformed_bounds_tuple # Use the Python tuple directly
                    logger.info(f"Transformed clip_bounds to raster CRS: {transformed_bounds}")
                else:
                    logger.warning("coordinate_utils.transform_bbox_to_crs not available. Assuming clip_bounds are in raster CRS.")
                    # TODO: Add robust handling or error if CRS transformation is critical and unavailable.
            
            # Create a GeoJSON-like feature for masking
            geom = box(*transformed_bounds) # west, south, east, north
            
            # Clip the raster using rasterio.mask
            # `crop=True` ensures the output extent is cut to the mask
            # `all_touched=True` can be useful depending on desired behavior for pixels partially covered
            out_image, out_transform = mask(src, [geom], crop=True)
            
            # Update metadata for the clipped raster
            out_meta = src.profile.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1], # Index 1 for height after mask
                "width": out_image.shape[2],  # Index 2 for width after mask
                "transform": out_transform
            })

            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_clipped_path)), exist_ok=True)

            with rasterio.open(output_clipped_path, "w", **out_meta) as dest:
                dest.write(out_image)
            
            logger.info(f"Successfully clipped raster to {output_clipped_path}")
            return True
            
    except rasterio.errors.RasterioIOError as e:
        logger.error(f"Rasterio I/O error during clipping of {input_dem_path}: {e}")
    except ImportError: # If shapely is missing, though installed
        logger.error("Shapely library not found, which is required for clipping. Please install it.")
    except Exception as e:
        logger.error(f"Unexpected error during raster clipping: {e}", exc_info=True)
    return False


def scale_to_uint16(data_array_float: np.ndarray, 
                      nodata_val_input=np.nan,
                      output_nodata_val_uint16: int = 0
                      ) -> tuple[np.ndarray | None, float | None, float | None]:
    """
    Scales a float NumPy array (elevations) to uint16 (0-65535).
    NoData values in the input are mapped to `output_nodata_val_uint16` in the output.

    Args:
        data_array_float: Input float NumPy array.
        nodata_val_input: The NoData value present in data_array_float (e.g., np.nan or a specific float).
        output_nodata_val_uint16: The value to use for NoData in the output uint16 array (typically 0).

    Returns:
        Tuple of (scaled_array_uint16, min_elevation, max_elevation).
        Returns (None, None, None) on error or if array is all NoData.
    """
    try:
        if not isinstance(data_array_float, np.ndarray):
            logger.error("Input data_array_float must be a NumPy array.")
            return None, None, None

        # Create a mask for valid data points (not NoData)
        if np.isnan(nodata_val_input):
            valid_data_mask = ~np.isnan(data_array_float)
        else:
            valid_data_mask = (data_array_float != nodata_val_input)

        if not np.any(valid_data_mask):
            logger.warning("Input array contains only NoData values. Cannot scale.")
            # Return an array of nodata_val_uint16 with the same shape if needed by caller
            # scaled_array_uint16 = np.full(data_array_float.shape, output_nodata_val_uint16, dtype=np.uint16)
            # return scaled_array_uint16, None, None 
            return None, None, None # Or this, to indicate no valid min/max

        min_val = np.min(data_array_float[valid_data_mask])
        max_val = np.max(data_array_float[valid_data_mask])
        logger.info(f"Scaling data: Original min_val={min_val}, max_val={max_val} (excluding NoData).")

        if min_val == max_val: # Handle flat terrain (all valid data points have same elevation)
            logger.warning("All valid data points have the same value. Scaled array will be constant (mid-range).")
            # Scale to mid-value of uint16 range, or could be 0 or 65535.
            # Let's choose 32767 (middle of 0-65535) for non-nodata pixels.
            scaled_array_uint16 = np.full(data_array_float.shape, output_nodata_val_uint16, dtype=np.uint16)
            scaled_array_uint16[valid_data_mask] = 32767 
        else:
            # Perform linear scaling for valid data
            scaled_data = (data_array_float[valid_data_mask] - min_val) / (max_val - min_val) * 65535.0
            
            # Initialize uint16 array with the chosen NoData value
            scaled_array_uint16 = np.full(data_array_float.shape, output_nodata_val_uint16, dtype=np.uint16)
            # Place scaled valid data into the array
            scaled_array_uint16[valid_data_mask] = scaled_data.astype(np.uint16)

        logger.info(f"Data scaled to uint16. Output NoData value is {output_nodata_val_uint16}.")
        return scaled_array_uint16, float(min_val), float(max_val)

    except Exception as e:
        logger.error(f"Error scaling data to uint16: {e}", exc_info=True)
        return None, None, None


def save_array_as_png16(array_uint16: np.ndarray, output_path: str) -> bool:
    """
    Saves a uint16 NumPy array as a 16-bit grayscale PNG.

    Args:
        array_uint16: Input uint16 NumPy array.
        output_path: Path to save the PNG file.

    Returns:
        True if successful, False otherwise.
    """
    if not isinstance(array_uint16, np.ndarray) or array_uint16.dtype != np.uint16:
        logger.error("Input array must be a NumPy array of type uint16.")
        return False
    
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        image = Image.fromarray(array_uint16, mode='I;16') # I;16 for 16-bit integer pixels
        image.save(output_path)
        logger.info(f"Successfully saved uint16 array as PNG: {output_path}")
        return True
    except ImportError: # If Pillow is missing
        logger.error("Pillow (PIL) library not found. Please install it to save PNGs.")
        return False
    except Exception as e:
        logger.error(f"Error saving array as PNG: {e}", exc_info=True)
        return False


def save_array_as_raw16_with_json(array_uint16: np.ndarray, base_output_path: str,
                                   min_elev: float | None = None, max_elev: float | None = None) -> bool:
    """
    Saves a uint16 NumPy array as a raw binary file (.raw or .r16) and a JSON sidecar.

    Args:
        array_uint16: Input uint16 NumPy array.
        base_output_path: Base path for output (e.g., "heightmap" -> "heightmap.raw", "heightmap.json").
        min_elev: Original minimum elevation before scaling (optional, for metadata).
        max_elev: Original maximum elevation before scaling (optional, for metadata).

    Returns:
        True if successful, False otherwise.
    """
    if not isinstance(array_uint16, np.ndarray) or array_uint16.dtype != np.uint16:
        logger.error("Input array must be a NumPy array of type uint16 for RAW16 saving.")
        return False

    raw_output_path = base_output_path + ".r16" # Common extension for 16-bit raw heightmaps
    json_output_path = base_output_path + ".json"

    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(os.path.abspath(base_output_path))
        if output_dir : os.makedirs(output_dir, exist_ok=True)

        # Save raw binary file (little-endian by default with tofile if array is native)
        array_uint16.tofile(raw_output_path)
        logger.info(f"Successfully saved uint16 array as RAW: {raw_output_path}")

        # Create JSON metadata
        metadata = {
            "width": array_uint16.shape[1],
            "height": array_uint16.shape[0],
            "bbp": 16, # bits per pixel
            "format": "uint16",
            "byte_order": array_uint16.dtype.byteorder.replace('=', 'native').replace('<','little').replace('>','big'),
        }
        if min_elev is not None: metadata["min_elevation_original"] = min_elev
        if max_elev is not None: metadata["max_elevation_original"] = max_elev
        
        with open(json_output_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        logger.info(f"Successfully saved metadata JSON: {json_output_path}")
        
        return True
    except Exception as e:
        logger.error(f"Error saving array as RAW16 with JSON: {e}", exc_info=True)
        return False

# --- Helper function for creating a dummy GeoTIFF for testing ---
def _create_dummy_geotiff(file_path: str, width: int, height: int, num_bands: int = 1, 
                         crs: str = "EPSG:4326", dtype:str = 'float32', 
                         nodata_val: float | None = -9999.0) -> bool:
    """Creates a dummy GeoTIFF file for testing purposes."""
    try:
        # Define the transformation (affine matrix)
        # This example sets top-left corner at (0,0) with 1-degree cells
        transform = rasterio.Affine(1.0, 0, 0, 0, -1.0, 0) 

        profile = {
            'driver': 'GTiff',
            'width': width,
            'height': height,
            'count': num_bands,
            'dtype': dtype,
            'crs': rasterio.CRS.from_string(crs),
            'transform': transform,
            'nodata': nodata_val if nodata_val is not None else None
        }
        
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        with rasterio.open(file_path, 'w', **profile) as dst:
            for i in range(1, num_bands + 1):
                # Create some dummy data (e.g., a gradient)
                data = np.arange(width * height, dtype=profile['dtype']).reshape((height, width))
                # Introduce some NoData values if nodata_val is set
                if nodata_val is not None and width > 4 and height > 4 :
                    data[height//4:height//2, width//4:width//2] = nodata_val
                dst.write(data.astype(profile['dtype']), i)
        logger.info(f"Created dummy GeoTIFF: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create dummy GeoTIFF {file_path}: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    # Setup a specific logger for the __main__ block if logger_setup was available
    try:
        from logger_setup import setup_logger as main_setup_logger
        main_logger = main_setup_logger("DEMProcessorMain", level="DEBUG")
    except ImportError:
        main_logger = logger # Use the module-level logger
        main_logger.setLevel(logging.DEBUG)
        main_logger.warning("Running DEMProcessorMain with fallback logger configuration.")

    main_logger.info("--- DEM Processor Tests ---")
    
    test_output_dir = "test_dem_processing_output"
    if not os.path.exists(test_output_dir):
        os.makedirs(test_output_dir)
        main_logger.info(f"Created test output directory: {test_output_dir}")

    dummy_tif_path = os.path.join(test_output_dir, "dummy_dem.tif")
    clipped_tif_path = os.path.join(test_output_dir, "dummy_dem_clipped.tif")
    scaled_png_path = os.path.join(test_output_dir, "scaled_dem.png")
    scaled_raw_basepath = os.path.join(test_output_dir, "scaled_dem_raw") # for .r16 and .json

    # 1. Create a dummy GeoTIFF for testing
    created_dummy = _create_dummy_geotiff(dummy_tif_path, width=100, height=80, nodata_val=-9999.0, dtype='float32')
    if not created_dummy:
        main_logger.error("Failed to create dummy GeoTIFF. Aborting tests.")
        exit()

    # 2. Test get_dem_info_and_data
    main_logger.info("\n--- Testing get_dem_info_and_data ---")
    data_array, profile, nodata = get_dem_info_and_data(dummy_tif_path)
    if data_array is not None and profile is not None:
        main_logger.info(f"DEM Info: Shape={data_array.shape}, Profile CRS={profile.get('crs')}, Nodata={nodata}")
        main_logger.info(f"Nans in data: {np.sum(np.isnan(data_array)) if np.issubdtype(data_array.dtype, np.floating) else 'N/A (int array)'}")
    else:
        main_logger.error("Failed to get DEM info and data.")
        # exit() # Continue to test other functions if possible

    # 3. Test clip_raster_to_bbox
    # Define clip bounds (min_x, min_y, max_x, max_y) in the CRS of the dummy GeoTIFF (EPSG:4326)
    # Dummy GeoTIFF spans (0, -height) to (width, 0) due to transform
    # So, (0, -80) to (100, 0) if height=80, width=100.
    # Let's clip a smaller portion, e.g., x from 10 to 50, y from -70 to -30
    main_logger.info("\n--- Testing clip_raster_to_bbox ---")
    clip_b = (10.0, -70.0, 50.0, -30.0) 
    # Clip bounds are (west, south, east, north)
    # Rasterio transform: (1.0, 0, 0, 0, -1.0, 0) means (0,0) is top-left pixel's top-left corner.
    # y decreases downwards. So south should be less than north for geographic sense,
    # but for pixel space, it means y_bottom_coord < y_top_coord.
    # With transform Affine(1.0, 0.0, 0.0, 0.0, -1.0, 0.0)
    # (0,0) is top-left. (width, -height) is bottom-right.
    # So, west=10, east=50. south=-70 (more negative, so "lower" on map), north=-30 ("higher" on map).
    # This corresponds to rows from 30 to 70, cols from 10 to 50.
    
    success_clip = clip_raster_to_bbox(dummy_tif_path, clipped_tif_path, clip_b, crs_of_bounds="EPSG:4326")
    if success_clip:
        main_logger.info(f"Clipping successful. Output: {clipped_tif_path}")
        # Further test: read the clipped raster
        clipped_data, clipped_profile, _ = get_dem_info_and_data(clipped_tif_path)
        if clipped_data is not None:
            main_logger.info(f"Clipped DEM Info: Shape={clipped_data.shape}, Profile CRS={clipped_profile.get('crs')}")
            # Expected width: 50-10 = 40. Expected height: -30 - (-70) = 40.
            if clipped_data.shape == (40,40):
                 main_logger.info("Clipped shape is as expected (40x40).")
            else:
                 main_logger.warning(f"Clipped shape is {clipped_data.shape}, expected (40,40). Check clip_bounds and transform.")
            data_array = clipped_data # Use clipped data for subsequent tests
        else:
            main_logger.error("Failed to read clipped DEM data. Subsequent tests might fail or use unclipped data.")
    else:
        main_logger.error("Clipping failed.")
        # data_array for subsequent tests will be the original unclipped one if clipping failed but get_dem_info succeeded.

    # Ensure data_array is not None before proceeding
    if data_array is None:
        main_logger.error("data_array is None after get_info/clipping attempts. Cannot proceed with scaling/saving.")
        exit()

    # 4. Test scale_to_uint16
    main_logger.info("\n--- Testing scale_to_uint16 ---")
    # Use `nodata` which was np.nan if original was float, or the original nodata value if int.
    # The dummy is float32, so `nodata` from get_dem_info_and_data is the original float nodata value.
    # `get_dem_info_and_data` already converts nodata to np.nan in the float array.
    array_uint16, min_elev, max_elev = scale_to_uint16(data_array, nodata_val_input=np.nan, output_nodata_val_uint16=0)
    if array_uint16 is not None:
        main_logger.info(f"Scaling to uint16 successful. Min/Max elevation: {min_elev}, {max_elev}")
        main_logger.info(f"Scaled array data type: {array_uint16.dtype}, shape: {array_uint16.shape}")
        # Check if nodata values (0) are present where they should be (where original was nan)
        if np.issubdtype(data_array.dtype, np.floating): # Original was float
            original_nan_mask = np.isnan(data_array)
            output_nodata_mask = (array_uint16 == 0)
            if np.all(original_nan_mask == output_nodata_mask):
                 main_logger.info("NoData values correctly mapped to 0 in uint16 array.")
            else:
                 main_logger.warning("Potential mismatch in NoData mapping during scaling.")
    else:
        main_logger.error("Scaling to uint16 failed.")
        exit() # Cannot proceed without uint16 array

    # 5. Test save_array_as_png16
    main_logger.info("\n--- Testing save_array_as_png16 ---")
    success_png = save_array_as_png16(array_uint16, scaled_png_path)
    if success_png:
        main_logger.info(f"Saving as PNG successful: {scaled_png_path}")
    else:
        main_logger.error("Saving as PNG failed.")

    # 6. Test save_array_as_raw16_with_json
    main_logger.info("\n--- Testing save_array_as_raw16_with_json ---")
    success_raw = save_array_as_raw16_with_json(array_uint16, scaled_raw_basepath, min_elev, max_elev)
    if success_raw:
        main_logger.info(f"Saving as RAW16+JSON successful. Base: {scaled_raw_basepath}")
    else:
        main_logger.error("Saving as RAW16+JSON failed.")
        
    # 7. Test with all NoData array for scaling
    main_logger.info("\n--- Testing scale_to_uint16 with all NoData array ---")
    all_nodata_float_array = np.full((10, 10), np.nan, dtype=np.float32)
    scaled_all_nodata, _, _ = scale_to_uint16(all_nodata_float_array, nodata_val_input=np.nan)
    if scaled_all_nodata is None:
        main_logger.info("scale_to_uint16 correctly handled all-NoData array by returning None.")
    else:
        main_logger.error("scale_to_uint16 did not correctly handle all-NoData array.")

    main_logger.info("\n--- DEM Processor Tests Finished ---")
    main_logger.info(f"Test outputs are in: {test_output_dir}")
    # Clean up dummy files:
    # for f_path in [dummy_tif_path, clipped_tif_path, scaled_png_path, scaled_raw_basepath + ".r16", scaled_raw_basepath + ".json"]:
    #     if os.path.exists(f_path):
    #         os.remove(f_path)
    # if os.path.exists(test_output_dir):
    #     if not os.listdir(test_output_dir): # Check if empty
    #         os.rmdir(test_output_dir)
    #     else: # Or remove all contents
    #         import shutil
    #         shutil.rmtree(test_output_dir)

