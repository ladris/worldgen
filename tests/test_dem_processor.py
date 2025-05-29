# tests/test_dem_processor.py
import unittest
from unittest import mock
import os
import sys
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from dem_processor import (
#     get_dem_info_and_data,
#     clip_raster_to_bbox,
#     scale_to_uint16,
#     save_array_as_png16,
#     save_array_as_raw16_with_json,
#     _create_dummy_geotiff # if testing this helper
# )

class TestDemProcessor(unittest.TestCase):

    def setUp(self):
        # Create a dummy output directory for test artifacts
        self.test_output_dir = "test_dem_proc_output_temp"
        os.makedirs(self.test_output_dir, exist_ok=True)
        # self.dummy_tif_path = os.path.join(self.test_output_dir, "dummy_test.tif")
        # _create_dummy_geotiff(self.dummy_tif_path, 10, 10) # Create a small dummy GeoTIFF

    def tearDown(self):
        # Clean up test artifacts
        # if os.path.exists(self.dummy_tif_path):
        #     os.remove(self.dummy_tif_path)
        if os.path.exists(self.test_output_dir):
            # Remove all files in test_output_dir then remove dir
            for f in os.listdir(self.test_output_dir):
                os.remove(os.path.join(self.test_output_dir, f))
            os.rmdir(self.test_output_dir)
    
    # --- Tests for get_dem_info_and_data ---
    # TODO: Mock rasterio.open
    # TODO: Test with a valid dummy GeoTIFF (requires creating one or mocking rasterio)
    # TODO: Test with non-existent file
    # TODO: Test with corrupted/invalid GeoTIFF (mock rasterio to raise error)

    # --- Tests for clip_raster_to_bbox ---
    # TODO: Mock rasterio.open, rasterio.mask.mask, shapely.geometry.box
    # TODO: Test successful clipping
    # TODO: Test with input file not found
    # TODO: Test with CRS transformation (mock coordinate_utils.transform_bbox_to_crs)

    # --- Tests for scale_to_uint16 ---
    # def test_scale_to_uint16_valid_data(self):
    #     data = np.array([[10.0, 20.0], [30.0, np.nan]], dtype=np.float32)
    #     scaled, min_val, max_val = scale_to_uint16(data, nodata_val_input=np.nan)
    #     self.assertIsNotNone(scaled)
    #     self.assertEqual(min_val, 10.0)
    #     self.assertEqual(max_val, 30.0)
    #     # Add more assertions about scaled values and nodata mapping
    
    # TODO: Test scale_to_uint16 with all NoData
    # TODO: Test scale_to_uint16 with flat terrain (min_val == max_val)
    # TODO: Test scale_to_uint16 with integer input array + integer nodata

    # --- Tests for save_array_as_png16 ---
    # TODO: Mock Image.fromarray and image.save from Pillow
    # TODO: Test successful save
    # TODO: Test with invalid array type

    # --- Tests for save_array_as_raw16_with_json ---
    # TODO: Mock open for file writing (tofile and json.dump)
    # TODO: Test successful save of .r16 and .json
    # TODO: Test metadata content in JSON

    pass

if __name__ == '__main__':
    unittest.main()
