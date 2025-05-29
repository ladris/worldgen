# tests/test_unreal_preparer.py
import unittest
from unittest import mock
import os
import sys
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unreal_preparer import calculate_ue_scales, generate_ue_import_report, UE_INTERNAL_HEIGHT_SPAN

class TestUnrealPreparer(unittest.TestCase):

    def setUp(self):
        self.test_output_dir = "temp_ue_report_output"
        os.makedirs(self.test_output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_output_dir):
            for f in os.listdir(self.test_output_dir):
                os.remove(os.path.join(self.test_output_dir, f))
            os.rmdir(self.test_output_dir)

    def test_calculate_ue_scales_valid_inputs(self):
        min_elev = 100.0
        max_elev = 611.992 # Makes elevation_span_m * 100 / UE_INTERNAL_HEIGHT_SPAN = 100.0
        pixel_res = 2.0
        
        expected_scale_xy = pixel_res * 100.0  # 200.0
        expected_elevation_span_m = max_elev - min_elev # 511.992
        expected_scale_z = (expected_elevation_span_m * 100.0) / UE_INTERNAL_HEIGHT_SPAN # Should be 100.0
        expected_location_z = (min_elev * 100.0) + (256.0 * expected_scale_z) # 10000 + 25600 = 35600

        scales = calculate_ue_scales(min_elev, max_elev, pixel_res)
        self.assertIsNotNone(scales)
        self.assertAlmostEqual(scales["scale_x_ue_cm"], expected_scale_xy)
        self.assertAlmostEqual(scales["scale_y_ue_cm"], expected_scale_xy)
        self.assertAlmostEqual(scales["scale_z_ue_cm"], expected_scale_z)
        self.assertAlmostEqual(scales["location_z_ue_cm"], expected_location_z)
        self.assertEqual(scales["actual_min_elev_aoi_m"], min_elev)
        self.assertEqual(scales["actual_max_elev_aoi_m"], max_elev)
        self.assertEqual(scales["heightmap_pixel_resolution_m"], pixel_res)

    def test_calculate_ue_scales_flat_terrain(self):
        min_elev = 50.0
        max_elev = 50.0 # Flat
        pixel_res = 5.0

        expected_scale_xy = pixel_res * 100.0 # 500.0
        expected_scale_z = 100.0 # Default for flat terrain
        expected_location_z = (min_elev * 100.0) + (256.0 * expected_scale_z) # 5000 + 25600 = 30600


        scales = calculate_ue_scales(min_elev, max_elev, pixel_res)
        self.assertIsNotNone(scales)
        self.assertAlmostEqual(scales["scale_x_ue_cm"], expected_scale_xy)
        self.assertAlmostEqual(scales["scale_y_ue_cm"], expected_scale_xy)
        self.assertAlmostEqual(scales["scale_z_ue_cm"], expected_scale_z) # Default for flat
        self.assertAlmostEqual(scales["location_z_ue_cm"], expected_location_z)


    @mock.patch('builtins.print') # Suppress logger messages
    def test_calculate_ue_scales_invalid_pixel_resolution(self, mock_print):
        self.assertIsNone(calculate_ue_scales(100.0, 200.0, 0))
        self.assertIsNone(calculate_ue_scales(100.0, 200.0, -1.0))

    @mock.patch('builtins.print')
    def test_calculate_ue_scales_min_greater_than_max(self, mock_print):
        self.assertIsNone(calculate_ue_scales(200.0, 100.0, 10.0))
        
    @mock.patch('builtins.print')
    def test_calculate_ue_scales_non_numeric_input(self, mock_print):
        self.assertIsNone(calculate_ue_scales("abc", 200.0, 1.0)) # type: ignore
        self.assertIsNone(calculate_ue_scales(100.0, "xyz", 1.0)) # type: ignore
        self.assertIsNone(calculate_ue_scales(100.0, 200.0, "ghj"))# type: ignore


    def test_generate_ue_import_report_valid_params(self):
        ue_params = {
            "scale_x_ue_cm": 200.0, "scale_y_ue_cm": 200.0, "scale_z_ue_cm": 100.0,
            "location_z_ue_cm": 35600.0,
            "actual_min_elev_aoi_m": 100.0, "actual_max_elev_aoi_m": 611.992,
            "elevation_span_aoi_m": 511.992,
            "heightmap_pixel_resolution_m": 2.0,
            "note_on_location_z": "Test note."
        }
        report_path = os.path.join(self.test_output_dir, "test_report.txt")
        report_str = generate_ue_import_report(
            ue_params,
            heightmap_dims=(1024, 1024),
            heightmap_format="PNG16",
            report_path=report_path
        )
        self.assertIn("Unreal Engine Landscape Import Parameters Report", report_str)
        self.assertIn("Scale X: 200.000000", report_str)
        self.assertIn("Location Z: 35600.000", report_str)
        self.assertIn("Dimensions (Width x Height): 1024 x 1024 pixels", report_str)
        self.assertTrue(os.path.exists(report_path))

    @mock.patch('builtins.print') # Suppress logger messages
    def test_generate_ue_import_report_none_params(self, mock_print):
        report_path = os.path.join(self.test_output_dir, "test_report_none.txt")
        report_str = generate_ue_import_report(None, report_path=report_path)
        self.assertIn("No UE parameters calculated or provided", report_str)
        self.assertTrue(os.path.exists(report_path)) # Should still save minimal report

    @mock.patch('unreal_preparer.os.makedirs', side_effect=OSError("Simulated error creating dir"))
    @mock.patch('unreal_preparer.logger.error') # Mock the logger directly
    def test_generate_ue_import_report_save_io_error_makedirs(self, mock_logger_error, mock_makedirs):
        ue_params = {"scale_x_ue_cm": 100.0, 
                     "actual_min_elev_aoi_m": 0.0, # Add other keys to prevent ValueErrors from formatting N/A
                     "actual_max_elev_aoi_m": 0.0,
                     "elevation_span_aoi_m": 0.0,
                     "heightmap_pixel_resolution_m": 0.0,
                     "scale_y_ue_cm": 100.0,
                     "scale_z_ue_cm": 100.0,
                     "location_z_ue_cm": 0.0
                    } # Provide more complete ue_params to avoid ValueErrors during string formatting
        report_path = os.path.join(self.test_output_dir, "subdir", "test_report_fail.txt")
        
        report_str = generate_ue_import_report(ue_params, report_path=report_path)
        self.assertFalse(os.path.exists(report_path)) # File should not be created
        
        called_with_expected_message = False
        for call in mock_logger_error.call_args_list:
            if "Failed to save UE import report" in call.args[0]:
                called_with_expected_message = True
                break
        self.assertTrue(called_with_expected_message, 
                        "logger.error was not called with the expected 'Failed to save' message.")


if __name__ == '__main__':
    unittest.main()
