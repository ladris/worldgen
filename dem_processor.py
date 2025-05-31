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
import math # Added for math.ceil

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
    """
    if not os.path.exists(dem_path):
        logger.error(f"DEM file not found at path: {dem_path}")
        return None, None, None
    try:
        with rasterio.open(dem_path) as src:
            profile = src.profile
            data_array = src.read(1)
            nodata_value = src.nodata
            logger.info(f"Successfully read DEM: {dem_path}. Shape: {data_array.shape}, CRS: {profile.get('crs')}")
            logger.debug(f"Profile: {profile}")
            logger.debug(f"Nodata value from source: {nodata_value}")
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
                    transformed_bounds = transformed_bounds_tuple
                    logger.info(f"Transformed clip_bounds to raster CRS: {transformed_bounds}")
                else:
                    logger.warning("coordinate_utils.transform_bbox_to_crs not available. Assuming clip_bounds are in raster CRS.")
            geom = box(*transformed_bounds)
            out_image, out_transform = mask(src, [geom], crop=True)
            out_meta = src.profile.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            os.makedirs(os.path.dirname(os.path.abspath(output_clipped_path)), exist_ok=True)
            with rasterio.open(output_clipped_path, "w", **out_meta) as dest:
                dest.write(out_image)
            logger.info(f"Successfully clipped raster to {output_clipped_path}")
            return True
    except rasterio.errors.RasterioIOError as e:
        logger.error(f"Rasterio I/O error during clipping of {input_dem_path}: {e}")
    except ImportError:
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
    """
    try:
        if not isinstance(data_array_float, np.ndarray):
            logger.error("Input data_array_float must be a NumPy array.")
            return None, None, None
        if np.isnan(nodata_val_input):
            valid_data_mask = ~np.isnan(data_array_float)
        else:
            valid_data_mask = (data_array_float != nodata_val_input)
        if not np.any(valid_data_mask):
            logger.warning("Input array contains only NoData values. Cannot scale.")
            return None, None, None
        min_val = np.min(data_array_float[valid_data_mask])
        max_val = np.max(data_array_float[valid_data_mask])
        logger.info(f"Scaling data: Original min_val={min_val}, max_val={max_val} (excluding NoData).")
        scaled_array_uint16 = np.full(data_array_float.shape, output_nodata_val_uint16, dtype=np.uint16)
        if min_val == max_val:
            logger.warning("All valid data points have the same value. Scaled array will be constant (mid-range).")
            scaled_array_uint16[valid_data_mask] = 32767
        else:
            scaled_data = (data_array_float[valid_data_mask] - min_val) / (max_val - min_val) * 65535.0
            scaled_array_uint16[valid_data_mask] = scaled_data.astype(np.uint16)
        logger.info(f"Data scaled to uint16. Output NoData value is {output_nodata_val_uint16}.")
        return scaled_array_uint16, float(min_val), float(max_val)
    except Exception as e:
        logger.error(f"Error scaling data to uint16: {e}", exc_info=True)
        return None, None, None


def save_array_as_png16(array_uint16: np.ndarray, output_path: str) -> bool:
    """
    Saves a uint16 NumPy array as a 16-bit grayscale PNG.
    """
    if not isinstance(array_uint16, np.ndarray) or array_uint16.dtype != np.uint16:
        logger.error("Input array must be a NumPy array of type uint16.")
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        image = Image.fromarray(array_uint16, mode='I;16')
        image.save(output_path)
        logger.info(f"Successfully saved uint16 array as PNG: {output_path}")
        return True
    except ImportError:
        logger.error("Pillow (PIL) library not found. Please install it to save PNGs.")
        return False
    except Exception as e:
        logger.error(f"Error saving array as PNG: {e}", exc_info=True)
        return False


def save_array_as_raw16_with_json(array_uint16: np.ndarray, base_output_path: str,
                                   min_elev: float | None = None, max_elev: float | None = None) -> bool:
    """
    Saves a uint16 NumPy array as a raw binary file (.r16) and a JSON sidecar.
    """
    if not isinstance(array_uint16, np.ndarray) or array_uint16.dtype != np.uint16:
        logger.error("Input array must be a NumPy array of type uint16 for RAW16 saving.")
        return False
    raw_output_path = base_output_path + ".r16"
    json_output_path = base_output_path + ".json"
    try:
        output_dir = os.path.dirname(os.path.abspath(base_output_path))
        if output_dir : os.makedirs(output_dir, exist_ok=True)
        array_uint16.tofile(raw_output_path)
        logger.info(f"Successfully saved uint16 array as RAW: {raw_output_path}")
        metadata = {
            "width": array_uint16.shape[1],
            "height": array_uint16.shape[0],
            "bbp": 16,
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

def tile_scaled_dem_array(
    scaled_dem_array_uint16: np.ndarray,
    tile_size_x: int,
    tile_size_y: int,
    output_tile_dir: str,
    tile_naming_prefix: str,
    output_format: str,
    actual_min_elev: float | None = None,
    actual_max_elev: float | None = None
) -> list[str] | None:
    """
    Tiles a large, already scaled UInt16 DEM NumPy array into smaller chunks and saves them.
    """
    if scaled_dem_array_uint16 is None or scaled_dem_array_uint16.ndim != 2:
        logger.error("Invalid input DEM array for tiling. Must be a 2D NumPy array.")
        return None
    if tile_size_x <= 0 or tile_size_y <= 0:
        logger.error("Tile dimensions (tile_size_x, tile_size_y) must be positive.")
        return None

    full_height, full_width = scaled_dem_array_uint16.shape
    logger.info(f"Starting tiling of DEM ({full_width}x{full_height}) into {tile_size_x}x{tile_size_y} tiles.")

    if not os.path.exists(output_tile_dir):
        try:
            os.makedirs(output_tile_dir)
            logger.info(f"Created tile output directory: {output_tile_dir}")
        except OSError as e:
            logger.error(f"Failed to create tile output directory {output_tile_dir}: {e}")
            return None

    num_tiles_x = math.ceil(full_width / tile_size_x)
    num_tiles_y = math.ceil(full_height / tile_size_y)
    logger.info(f"Grid size: {num_tiles_x} tiles wide, {num_tiles_y} tiles high.")

    generated_tile_paths = []
    success = True

    for y_idx in range(num_tiles_y):
        for x_idx in range(num_tiles_x):
            start_x = x_idx * tile_size_x
            start_y = y_idx * tile_size_y
            end_x = min(start_x + tile_size_x, full_width)
            end_y = min(start_y + tile_size_y, full_height)
            tile_array = scaled_dem_array_uint16[start_y:end_y, start_x:end_x]
            tile_array_to_save = tile_array

            tile_base_name = f"{tile_naming_prefix}_X{x_idx}_Y{y_idx}"
            logger.debug(f"Processing tile {tile_base_name} ({start_x},{start_y} to {end_x},{end_y})")

            if output_format.upper() in ["PNG", "BOTH"]:
                png_path = os.path.join(output_tile_dir, f"{tile_base_name}.png")
                if save_array_as_png16(tile_array_to_save, png_path):
                    generated_tile_paths.append(png_path)
                    logger.info(f"Saved PNG tile: {png_path}")
                else:
                    logger.error(f"Failed to save PNG tile: {png_path}")
                    success = False

            if output_format.upper() in ["RAW", "BOTH"]:
                raw_base_path_for_tile = os.path.join(output_tile_dir, tile_base_name)
                if save_array_as_raw16_with_json(
                    tile_array_to_save,
                    raw_base_path_for_tile,
                    min_elev=actual_min_elev,
                    max_elev=actual_max_elev
                ):
                    generated_tile_paths.append(f"{raw_base_path_for_tile}.r16")
                    logger.info(f"Saved RAW+JSON tile: {raw_base_path_for_tile}.r16")
                else:
                    logger.error(f"Failed to save RAW+JSON tile: {raw_base_path_for_tile}")
                    success = False

    if not success and not generated_tile_paths:
        logger.error("All tile saving operations failed.")
        return None
    if not generated_tile_paths:
        logger.warning("No tiles were generated, possibly due to zero-sized input DEM.")
        return []

    logger.info(f"Successfully generated {len(generated_tile_paths)} tile file(s) in {output_tile_dir}")
    return generated_tile_paths

# --- Helper function for creating a dummy GeoTIFF for testing ---
def _create_dummy_geotiff(file_path: str, width: int, height: int, num_bands: int = 1,
                         crs: str = "EPSG:4326", dtype:str = 'float32',
                         nodata_val: float | None = -9999.0) -> bool:
    """Creates a dummy GeoTIFF file for testing purposes."""
    try:
        transform = rasterio.Affine(1.0, 0, 0, 0, -1.0, 0)
        profile = {
            'driver': 'GTiff', 'width': width, 'height': height, 'count': num_bands,
            'dtype': dtype, 'crs': rasterio.CRS.from_string(crs),
            'transform': transform, 'nodata': nodata_val if nodata_val is not None else None
        }
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with rasterio.open(file_path, 'w', **profile) as dst:
            for i in range(1, num_bands + 1):
                data = np.arange(width * height, dtype=profile['dtype']).reshape((height, width))
                if nodata_val is not None and width > 4 and height > 4 :
                    data[height//4:height//2, width//4:width//2] = nodata_val
                dst.write(data.astype(profile['dtype']), i)
        logger.info(f"Created dummy GeoTIFF: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create dummy GeoTIFF {file_path}: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    try:
        from logger_setup import setup_logger as main_setup_logger
        main_logger = main_setup_logger("DEMProcessorMain", level="DEBUG")
    except ImportError:
        main_logger = logger
        main_logger.setLevel(logging.DEBUG)
        main_logger.warning("Running DEMProcessorMain with fallback logger configuration.")

    main_logger.info("--- DEM Processor Tests ---")
    test_output_dir = "test_dem_processing_output" # Renamed from TEST_OUTPUT_DIR for consistency
    if not os.path.exists(test_output_dir):
        os.makedirs(test_output_dir)
        main_logger.info(f"Created test output directory: {test_output_dir}")

    dummy_tif_path = os.path.join(test_output_dir, "dummy_dem.tif")
    clipped_tif_path = os.path.join(test_output_dir, "dummy_dem_clipped.tif")
    scaled_png_path = os.path.join(test_output_dir, "scaled_dem.png")
    scaled_raw_basepath = os.path.join(test_output_dir, "scaled_dem_raw")

    created_dummy = _create_dummy_geotiff(dummy_tif_path, width=100, height=80, nodata_val=-9999.0, dtype='float32')
    if not created_dummy:
        main_logger.error("Failed to create dummy GeoTIFF. Aborting some tests.")
        data_array, profile, nodata, array_uint16 = None, None, None, None # Ensure these are defined for later checks
    else:
        main_logger.info("\n--- Testing get_dem_info_and_data ---")
        data_array, profile, nodata = get_dem_info_and_data(dummy_tif_path)
        if data_array is not None and profile is not None:
            main_logger.info(f"DEM Info: Shape={data_array.shape}, Profile CRS={profile.get('crs')}, Nodata={nodata}")
            main_logger.info(f"Nans in data: {np.sum(np.isnan(data_array)) if np.issubdtype(data_array.dtype, np.floating) else 'N/A (int array)'}")
        else:
            main_logger.error("Failed to get DEM info and data.")
            data_array = None # Ensure it's None for subsequent checks

        if data_array is not None:
            main_logger.info("\n--- Testing clip_raster_to_bbox ---")
            clip_b = (10.0, -70.0, 50.0, -30.0)
            success_clip = clip_raster_to_bbox(dummy_tif_path, clipped_tif_path, clip_b, crs_of_bounds="EPSG:4326")
            if success_clip:
                main_logger.info(f"Clipping successful. Output: {clipped_tif_path}")
                clipped_data, clipped_profile, _ = get_dem_info_and_data(clipped_tif_path)
                if clipped_data is not None:
                    main_logger.info(f"Clipped DEM Info: Shape={clipped_data.shape}, Profile CRS={clipped_profile.get('crs')}")
                    if clipped_data.shape == (40,40): main_logger.info("Clipped shape is as expected (40x40).")
                    else: main_logger.warning(f"Clipped shape is {clipped_data.shape}, expected (40,40).")
                    data_array = clipped_data
                else:
                    main_logger.error("Failed to read clipped DEM data.")
            else:
                main_logger.error("Clipping failed.")

        if data_array is not None:
            main_logger.info("\n--- Testing scale_to_uint16 ---")
            array_uint16, min_elev, max_elev = scale_to_uint16(data_array, nodata_val_input=np.nan, output_nodata_val_uint16=0)
            if array_uint16 is not None:
                main_logger.info(f"Scaling to uint16 successful. Min/Max elevation: {min_elev}, {max_elev}")
                main_logger.info(f"Scaled array data type: {array_uint16.dtype}, shape: {array_uint16.shape}")
                if np.issubdtype(data_array.dtype, np.floating):
                    original_nan_mask = np.isnan(data_array)
                    output_nodata_mask = (array_uint16 == 0)
                    if np.all(original_nan_mask == output_nodata_mask): main_logger.info("NoData values correctly mapped to 0.")
                    else: main_logger.warning("Potential mismatch in NoData mapping during scaling.")

                main_logger.info("\n--- Testing save_array_as_png16 ---")
                if save_array_as_png16(array_uint16, scaled_png_path): main_logger.info(f"Saving PNG successful: {scaled_png_path}")
                else: main_logger.error("Saving PNG failed.")

                main_logger.info("\n--- Testing save_array_as_raw16_with_json ---")
                if save_array_as_raw16_with_json(array_uint16, scaled_raw_basepath, min_elev, max_elev):
                    main_logger.info(f"Saving RAW16+JSON successful. Base: {scaled_raw_basepath}")
                else: main_logger.error("Saving RAW16+JSON failed.")
            else:
                main_logger.error("Scaling to uint16 failed.")
                array_uint16 = None # Ensure it's None
        else:
            main_logger.error("data_array is None after get_info/clipping. Skipping scaling/saving tests.")
            array_uint16 = None # Ensure it's None

    main_logger.info("\n--- Testing scale_to_uint16 with all NoData array ---")
    all_nodata_float_array = np.full((10, 10), np.nan, dtype=np.float32)
    scaled_all_nodata, _, _ = scale_to_uint16(all_nodata_float_array, nodata_val_input=np.nan)
    if scaled_all_nodata is None: main_logger.info("scale_to_uint16 correctly handled all-NoData array.")
    else: main_logger.error("scale_to_uint16 did not correctly handle all-NoData array.")

    main_logger.info("\n--- Tiling Tests ---")
    dummy_full_scaled_height = 250
    dummy_full_scaled_width = 150
    test_scaled_full_array = np.zeros((dummy_full_scaled_height, dummy_full_scaled_width), dtype=np.uint16)
    for r_idx in range(dummy_full_scaled_height): # Renamed r to r_idx to avoid conflict
        for c_idx in range(dummy_full_scaled_width): # Renamed c to c_idx
            test_scaled_full_array[r_idx, c_idx] = (r_idx + c_idx) % 65536

    tile_test_dir_actual = os.path.join(test_output_dir, "tiled_output_actual") # Changed name
    tile_size = 100

    main_logger.info(f"Test tiling to PNG format (tile size {tile_size}x{tile_size})...")
    png_tile_paths = tile_scaled_dem_array(
        test_scaled_full_array, tile_size_x=tile_size, tile_size_y=tile_size,
        output_tile_dir=tile_test_dir_actual, tile_naming_prefix="test_tile_png", output_format="PNG"
    )
    if png_tile_paths:
        main_logger.info(f"PNG tiles generated: {len(png_tile_paths)}")
        if len(png_tile_paths) == 6: main_logger.info("Correct number of PNG tiles generated.")
        else: main_logger.error(f"Incorrect number of PNG tiles: {len(png_tile_paths)}, expected 6.")
    else: main_logger.error("Failed to generate PNG tiles.")

    main_logger.info(f"Test tiling to RAW+JSON format (tile size {tile_size}x{tile_size})...")
    overall_min_elev_test = 100.0
    overall_max_elev_test = 2000.0
    raw_tile_paths = tile_scaled_dem_array(
        test_scaled_full_array, tile_size_x=tile_size, tile_size_y=tile_size,
        output_tile_dir=tile_test_dir_actual, tile_naming_prefix="test_tile_raw", output_format="RAW",
        actual_min_elev=overall_min_elev_test, actual_max_elev=overall_max_elev_test
    )
    if raw_tile_paths:
        main_logger.info(f"RAW tiles generated: {len(raw_tile_paths)}")
        if len(raw_tile_paths) == 6:
            main_logger.info("Correct number of RAW tiles generated.")
            try:
                first_raw_tile_base = os.path.join(tile_test_dir_actual, "test_tile_raw_X0_Y0")
                with open(f"{first_raw_tile_base}.json", 'r') as f_json: # Renamed f to f_json
                    json_data = json.load(f_json)
                    if json_data.get("min_elevation_original") == overall_min_elev_test:
                        main_logger.info("RAW JSON metadata correctly contains overall min/max elevation.")
                    else: main_logger.error("RAW JSON metadata missing or incorrect overall min/max elev.")
            except Exception as e: main_logger.error(f"Error checking RAW JSON metadata: {e}")
        else: main_logger.error(f"Incorrect number of RAW tiles: {len(raw_tile_paths)}, expected 6.")
    else: main_logger.error("Failed to generate RAW tiles.")

    main_logger.info(f"Test tiling with tile size larger than array...")
    large_tile_paths = tile_scaled_dem_array(
        test_scaled_full_array, tile_size_x=dummy_full_scaled_width + 10,
        tile_size_y=dummy_full_scaled_height + 10, output_tile_dir=tile_test_dir_actual,
        tile_naming_prefix="large_tile", output_format="PNG"
    )
    if large_tile_paths and len(large_tile_paths) == 1:
        main_logger.info(f"Correctly generated 1 tile when tile size > array size.")
    else: main_logger.error(f"Incorrect tile count for oversized tile: {large_tile_paths}")

    main_logger.info("\n--- DEM Processor Tests Finished ---")
    main_logger.info(f"Test outputs are in: {test_output_dir}")
    # Cleanup can be added here if desired
    # import shutil
    # if os.path.exists(test_output_dir): shutil.rmtree(test_output_dir)
