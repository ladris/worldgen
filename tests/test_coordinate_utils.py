# tests/test_coordinate_utils.py
import unittest
from unittest import mock
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Assuming pyproj is installed, otherwise these tests will fail at import
from coordinate_utils import transform_bbox_to_crs, get_metric_dimensions
from pyproj.exceptions import CRSError

class TestCoordinateUtils(unittest.TestCase):

    # Basic test for a known transformation (WGS84 to a UTM zone)
    # Exact values depend on pyproj version and PROJ data, so check for plausibility / no errors.
    def test_transform_bbox_to_crs_valid(self):
        # Example: A small box in San Francisco (WGS84) to UTM Zone 10N (EPSG:32610)
        wgs84_bbox = (-122.42, 37.77, -122.40, 37.78) # lon_min, lat_min, lon_max, lat_max
        target_crs_epsg = "EPSG:32610" # UTM Zone 10N
        
        # This is a live call to pyproj, ensure it's installed and PROJ data is accessible
        transformed_bbox = transform_bbox_to_crs(wgs84_bbox, "EPSG:4326", target_crs_epsg)
        self.assertIsNotNone(transformed_bbox)
        self.assertEqual(len(transformed_bbox), 4)
        # Check if coordinates are plausible UTM values (e.g., positive, large numbers)
        # Example UTM Zone 10N for SF: X around 550000, Y around 4180000
        self.assertTrue(all(isinstance(coord, float) for coord in transformed_bbox))
        self.assertTrue(transformed_bbox[0] > 0 and transformed_bbox[1] > 0) # Basic check for UTM
        self.assertTrue(transformed_bbox[2] > transformed_bbox[0]) # max_x > min_x
        self.assertTrue(transformed_bbox[3] > transformed_bbox[1]) # max_y > min_y
        # print(f"Transformed San Francisco WGS84 {wgs84_bbox} to UTM10N {transformed_bbox}")


    @mock.patch('builtins.print') # Suppress logger/print messages for cleaner test output
    def test_transform_bbox_to_crs_invalid_epsg(self, mock_print):
        wgs84_bbox = (-122.42, 37.77, -122.40, 37.78)
        # Test with an invalid source CRS
        res_invalid_src = transform_bbox_to_crs(wgs84_bbox, "EPSG:INVALID_SRC", "EPSG:32610")
        self.assertIsNone(res_invalid_src)
        
        # Test with an invalid target CRS
        res_invalid_target = transform_bbox_to_crs(wgs84_bbox, "EPSG:4326", "EPSG:INVALID_TARGET")
        self.assertIsNone(res_invalid_target)

    @mock.patch('coordinate_utils.Transformer.from_crs')
    @mock.patch('builtins.print')
    def test_transform_bbox_to_crs_transformation_error(self, mock_print, mock_from_crs):
        # Simulate an error during the transformer.transform() call
        mock_transformer_instance = mock.Mock()
        mock_transformer_instance.transform.side_effect = Exception("Simulated pyproj transform error")
        mock_from_crs.return_value = mock_transformer_instance
        
        wgs84_bbox = (-122.42, 37.77, -122.40, 37.78)
        transformed_bbox = transform_bbox_to_crs(wgs84_bbox, "EPSG:4326", "EPSG:32610")
        self.assertIsNone(transformed_bbox)


    def test_get_metric_dimensions_valid(self):
        # Assuming a projected bounding box in meters
        # e.g., min_x, min_y, max_x, max_y
        projected_bbox = (500000.0, 4100000.0, 501000.0, 4102000.0) # 1km width, 2km height
        width, height = get_metric_dimensions(projected_bbox)
        self.assertIsNotNone(width)
        self.assertIsNotNone(height)
        self.assertAlmostEqual(width, 1000.0)
        self.assertAlmostEqual(height, 2000.0)

    @mock.patch('builtins.print')
    def test_get_metric_dimensions_non_numeric(self, mock_print):
        projected_bbox_non_numeric = ("a", 4100000.0, 501000.0, 4102000.0)
        result = get_metric_dimensions(projected_bbox_non_numeric) # type: ignore
        self.assertIsNone(result)

    @mock.patch('builtins.print')
    def test_get_metric_dimensions_min_greater_than_max(self, mock_print):
        # Should still return positive width/height due to abs()
        projected_bbox_inverted = (501000.0, 4102000.0, 500000.0, 4100000.0)
        width, height = get_metric_dimensions(projected_bbox_inverted) # type: ignore
        self.assertIsNotNone(width)
        self.assertIsNotNone(height)
        self.assertAlmostEqual(width, 1000.0)
        self.assertAlmostEqual(height, 2000.0)

    @mock.patch('builtins.print')
    def test_get_metric_dimensions_invalid_tuple_length(self, mock_print):
        projected_bbox_short = (500000.0, 4100000.0, 501000.0) # type: ignore
        result = get_metric_dimensions(projected_bbox_short)
        self.assertIsNone(result)

    @mock.patch('coordinate_utils.logger.warning') # More direct mock
    def test_get_metric_dimensions_crs_not_metric_warning(self, mock_logger_warning):
        projected_bbox = (500000.0, 4100000.0, 501000.0, 4102000.0)
        get_metric_dimensions(projected_bbox, crs_units_are_metric=False)
        
        # Check if the logger's warning method was called with the expected message
        called_with_expected_message = False
        for call in mock_logger_warning.call_args_list:
            if "CRS units are not confirmed metric" in call.args[0]:
                called_with_expected_message = True
                break
        self.assertTrue(called_with_expected_message,
                        "logger.warning was not called with the expected message about non-metric CRS units.")


if __name__ == '__main__':
    unittest.main()
