# tests/test_dem_processor.py
import unittest
from unittest import mock
from unittest.mock import patch, call, MagicMock # Ensure all are imported
import os
import sys
import numpy as np
import math # Added math

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import functions to test directly
from dem_processor import (
    get_dem_info_and_data,
    clip_raster_to_bbox,
    scale_to_uint16,
    save_array_as_png16,
    save_array_as_raw16_with_json,
    tile_scaled_dem_array, # Added new function
    _create_dummy_geotiff # if testing this helper, but prefer mocking for unit tests
)
# Also import the module itself if needed for patching its internal components
import dem_processor

class TestDemProcessor(unittest.TestCase):

    def setUp(self):
        self.test_output_dir = "test_dem_proc_output_temp"
        # Create directory if it doesn't exist, clean if it does
        if os.path.exists(self.test_output_dir):
            for f in os.listdir(self.test_output_dir):
                os.remove(os.path.join(self.test_output_dir, f))
        else:
            os.makedirs(self.test_output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_output_dir):
            for f in os.listdir(self.test_output_dir):
                try:
                    os.remove(os.path.join(self.test_output_dir, f))
                except OSError: # Handle cases where a subdir might have been created by a faulty test
                    pass
            try:
                os.rmdir(self.test_output_dir)
            except OSError: # If subdirs were created and not cleaned by file loop
                pass

    # --- Placeholder Tests for existing functions (from original file) ---
    # TODO: Mock rasterio.open for get_dem_info_and_data
    # TODO: Mock rasterio.open, rasterio.mask.mask, shapely.geometry.box for clip_raster_to_bbox
    # TODO: Add more tests for scale_to_uint16 (all NoData, flat, int array)
    # TODO: Mock Image.fromarray for save_array_as_png16
    # TODO: Mock open for save_array_as_raw16_with_json

    # --- Tests for tile_scaled_dem_array ---

    def _create_dummy_tiling_input_array(self, height, width, fill_pattern=True):
        arr = np.zeros((height, width), dtype=np.uint16)
        if fill_pattern:
            for r_idx in range(height): # Renamed r to r_idx
                for c_idx in range(width): # Renamed c to c_idx
                    arr[r_idx, c_idx] = (r_idx * width + c_idx) % 65536
        return arr

    @patch('dem_processor.save_array_as_raw16_with_json')
    @patch('dem_processor.save_array_as_png16')
    @patch('os.makedirs')
    def test_tile_scaled_dem_array_perfect_fit_png(self, mock_makedirs, mock_save_png, mock_save_raw):
        height, width = 200, 300
        tile_h, tile_w = 100, 150
        input_array = self._create_dummy_tiling_input_array(height, width)

        mock_save_png.return_value = True # Simulate successful save

        tile_paths = tile_scaled_dem_array( # Direct call
            input_array, tile_w, tile_h,
            "/fake/tile_dir", "test_tile", "PNG", 100.0, 200.0
        )

        self.assertIsNotNone(tile_paths)
        expected_num_tiles = (height // tile_h) * (width // tile_w) # 2 * 2 = 4
        self.assertEqual(len(tile_paths), expected_num_tiles)
        self.assertEqual(mock_save_png.call_count, expected_num_tiles)
        mock_save_raw.assert_not_called()
        # Check if makedirs was called if dir doesn't exist (mocked by default to not raise error)
        # os.makedirs in the function has exist_ok=True, so it might not be called if dir exists
        # For this test, let's assume it might be called:
        # mock_makedirs.assert_called_with("/fake/tile_dir", exist_ok=True) # This path is tricky with mock

        args_list = mock_save_png.call_args_list
        # Tile Y0_X0 (row 0, col 0)
        call_args_tile00 = args_list[0].args # .args gives the tuple of positional args
        np.testing.assert_array_equal(call_args_tile00[0], input_array[0:tile_h, 0:tile_w])
        self.assertEqual(call_args_tile00[1], os.path.join("/fake/tile_dir", "test_tile_X0_Y0.png"))
        # Tile Y0_X1 (row 0, col 1)
        call_args_tile01 = args_list[1].args
        np.testing.assert_array_equal(call_args_tile01[0], input_array[0:tile_h, tile_w:tile_w*2])
        self.assertEqual(call_args_tile01[1], os.path.join("/fake/tile_dir", "test_tile_X1_Y0.png"))

    @patch('dem_processor.save_array_as_raw16_with_json')
    @patch('dem_processor.save_array_as_png16')
    @patch('os.makedirs')
    def test_tile_scaled_dem_array_imperfect_fit_raw(self, mock_makedirs, mock_save_png, mock_save_raw):
        height, width = 250, 180
        tile_h, tile_w = 100, 100
        input_array = self._create_dummy_tiling_input_array(height, width)
        min_elev, max_elev = 50.0, 250.0
        mock_save_raw.return_value = True # Simulate successful save

        tile_paths = tile_scaled_dem_array( # Direct call
            input_array, tile_w, tile_h,
            "/fake/tile_dir_raw", "raw_tile", "RAW", min_elev, max_elev
        )

        expected_num_tiles_y = math.ceil(height / tile_h) # 3
        expected_num_tiles_x = math.ceil(width / tile_w)   # 2
        expected_total_tiles = expected_num_tiles_x * expected_num_tiles_y # 6

        self.assertIsNotNone(tile_paths)
        self.assertEqual(len(tile_paths), expected_total_tiles)
        self.assertEqual(mock_save_raw.call_count, expected_total_tiles)
        mock_save_png.assert_not_called()

        last_tile_array_expected = input_array[200:250, 100:180]
        last_call_args_tuple = mock_save_raw.call_args_list[-1]

        np.testing.assert_array_equal(last_call_args_tuple.args[0], last_tile_array_expected)
        self.assertEqual(last_call_args_tuple.args[1], os.path.join("/fake/tile_dir_raw", f"raw_tile_X{expected_num_tiles_x-1}_Y{expected_num_tiles_y-1}"))
        self.assertEqual(last_call_args_tuple.kwargs['min_elev'], min_elev)
        self.assertEqual(last_call_args_tuple.kwargs['max_elev'], max_elev)

    @patch('dem_processor.save_array_as_raw16_with_json')
    @patch('dem_processor.save_array_as_png16')
    @patch('os.makedirs')
    def test_tile_scaled_dem_array_tile_larger_than_dem_both_formats(self, mock_makedirs, mock_save_png, mock_save_raw):
        height, width = 50, 50
        tile_h, tile_w = 100, 100
        input_array = self._create_dummy_tiling_input_array(height, width)
        min_elev, max_elev = 0.0, 10.0
        mock_save_png.return_value = True
        mock_save_raw.return_value = True

        tile_paths = tile_scaled_dem_array( # Direct call
            input_array, tile_w, tile_h,
            "/fake/tile_dir_both", "large_tile", "BOTH", min_elev, max_elev
        )

        self.assertIsNotNone(tile_paths)
        self.assertEqual(len(tile_paths), 2)
        mock_save_png.assert_called_once()
        mock_save_raw.assert_called_once()

        np.testing.assert_array_equal(mock_save_png.call_args.args[0], input_array)
        self.assertEqual(mock_save_png.call_args.args[1], os.path.join("/fake/tile_dir_both", "large_tile_X0_Y0.png"))

        # For save_array_as_raw16_with_json, min_elev and max_elev are kwargs
        self.assertIsInstance(mock_save_raw.call_args.args[0], np.ndarray) # Check array first
        np.testing.assert_array_equal(mock_save_raw.call_args.args[0], input_array)
        self.assertEqual(mock_save_raw.call_args.args[1], os.path.join("/fake/tile_dir_both", "large_tile_X0_Y0"))
        self.assertEqual(mock_save_raw.call_args.kwargs['min_elev'], min_elev)
        self.assertEqual(mock_save_raw.call_args.kwargs['max_elev'], max_elev)

    @patch('dem_processor.logger.error') # Mock logger to check error messages
    def test_tile_scaled_dem_array_invalid_inputs(self, mock_logger_error):
        self.assertIsNone(tile_scaled_dem_array(None, 100, 100, "dir", "p", "PNG")) # type: ignore
        arr_1d = np.array([1,2,3], dtype=np.uint16)
        self.assertIsNone(tile_scaled_dem_array(arr_1d, 100, 100, "dir", "p", "PNG"))
        arr_2d = self._create_dummy_tiling_input_array(10,10)
        self.assertIsNone(tile_scaled_dem_array(arr_2d, 0, 100, "dir", "p", "PNG"))
        self.assertIsNone(tile_scaled_dem_array(arr_2d, 100, -1, "dir", "p", "PNG"))

    @patch('os.makedirs', side_effect=OSError("Test OS Error creating directory"))
    @patch('os.path.exists', return_value=False) # Ensure makedirs is called
    @patch('dem_processor.logger.error')
    def test_tile_scaled_dem_array_makedirs_oserror(self, mock_logger_error, mock_path_exists, mock_makedirs):
        input_array = self._create_dummy_tiling_input_array(10, 10)
        tile_paths = tile_scaled_dem_array(
            input_array, 5, 5, "/test_os_error_dir", "tile", "PNG", actual_min_elev=0.0, actual_max_elev=1.0 # Pass min/max elev
        )
        self.assertIsNone(tile_paths)
        # In tile_scaled_dem_array, os.makedirs is called without exist_ok=True when path.exists is false
        mock_makedirs.assert_called_once_with("/test_os_error_dir")
        self.assertTrue(any("Failed to create tile output directory" in call.args[0] for call in mock_logger_error.call_args_list))


if __name__ == '__main__':
    unittest.main()
