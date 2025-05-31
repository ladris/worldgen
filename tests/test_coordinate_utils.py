# tests/test_coordinate_utils.py
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock # Added MagicMock
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Assuming pyproj is installed, otherwise these tests will fail at import
from coordinate_utils import (
    transform_bbox_to_crs,
    get_metric_dimensions,
    geocode_place_name,              # Added
    calculate_bbox_from_center_and_distance # Added
)
from pyproj.exceptions import CRSError

# Attempt to import geopy exceptions, handle if geopy is not installed
try:
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError
    from geopy.location import Location
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    # Define dummy exceptions if geopy is not available so tests can be defined
    class GeocoderTimedOut(Exception): pass
    class GeocoderUnavailable(Exception): pass
    class GeocoderServiceError(Exception): pass
    class Location: pass # Dummy class


class TestCoordinateUtils(unittest.TestCase):

    # Basic test for a known transformation (WGS84 to a UTM zone)
    def test_transform_bbox_to_crs_valid(self):
        wgs84_bbox = (-122.42, 37.77, -122.40, 37.78)
        target_crs_epsg = "EPSG:32610"
        transformed_bbox = transform_bbox_to_crs(wgs84_bbox, "EPSG:4326", target_crs_epsg)
        self.assertIsNotNone(transformed_bbox)
        self.assertEqual(len(transformed_bbox), 4)
        self.assertTrue(all(isinstance(coord, float) for coord in transformed_bbox))
        self.assertTrue(transformed_bbox[0] > 0 and transformed_bbox[1] > 0)
        self.assertTrue(transformed_bbox[2] > transformed_bbox[0])
        self.assertTrue(transformed_bbox[3] > transformed_bbox[1])

    @patch('coordinate_utils.logger.error') # Patch logger to suppress error messages during test
    def test_transform_bbox_to_crs_invalid_epsg(self, mock_logger_error):
        wgs84_bbox = (-122.42, 37.77, -122.40, 37.78)
        res_invalid_src = transform_bbox_to_crs(wgs84_bbox, "EPSG:INVALID_SRC", "EPSG:32610")
        self.assertIsNone(res_invalid_src)
        res_invalid_target = transform_bbox_to_crs(wgs84_bbox, "EPSG:4326", "EPSG:INVALID_TARGET")
        self.assertIsNone(res_invalid_target)

    @patch('coordinate_utils.Transformer.from_crs')
    @patch('coordinate_utils.logger.error')
    def test_transform_bbox_to_crs_transformation_error(self, mock_logger_error, mock_from_crs):
        mock_transformer_instance = MagicMock()
        mock_transformer_instance.transform.side_effect = Exception("Simulated pyproj transform error")
        mock_from_crs.return_value = mock_transformer_instance
        wgs84_bbox = (-122.42, 37.77, -122.40, 37.78)
        transformed_bbox = transform_bbox_to_crs(wgs84_bbox, "EPSG:4326", "EPSG:32610")
        self.assertIsNone(transformed_bbox)

    def test_get_metric_dimensions_valid(self):
        projected_bbox = (500000.0, 4100000.0, 501000.0, 4102000.0)
        width, height = get_metric_dimensions(projected_bbox) # type: ignore
        self.assertIsNotNone(width)
        self.assertIsNotNone(height)
        self.assertAlmostEqual(width, 1000.0)
        self.assertAlmostEqual(height, 2000.0)

    @patch('coordinate_utils.logger.error')
    def test_get_metric_dimensions_non_numeric(self, mock_logger_error):
        projected_bbox_non_numeric = ("a", 4100000.0, 501000.0, 4102000.0)
        result = get_metric_dimensions(projected_bbox_non_numeric) # type: ignore
        self.assertIsNone(result)

    @patch('coordinate_utils.logger.warning')
    def test_get_metric_dimensions_min_greater_than_max(self, mock_logger_warning):
        projected_bbox_inverted = (501000.0, 4102000.0, 500000.0, 4100000.0)
        width, height = get_metric_dimensions(projected_bbox_inverted) # type: ignore
        self.assertIsNotNone(width)
        self.assertIsNotNone(height)
        self.assertAlmostEqual(width, 1000.0)
        self.assertAlmostEqual(height, 2000.0)

    @patch('coordinate_utils.logger.error')
    def test_get_metric_dimensions_invalid_tuple_length(self, mock_logger_error):
        projected_bbox_short = (500000.0, 4100000.0, 501000.0)
        result = get_metric_dimensions(projected_bbox_short) # type: ignore
        self.assertIsNone(result)

    @patch('coordinate_utils.logger.warning')
    def test_get_metric_dimensions_crs_not_metric_warning(self, mock_logger_warning):
        projected_bbox = (500000.0, 4100000.0, 501000.0, 4102000.0)
        get_metric_dimensions(projected_bbox, crs_units_are_metric=False)
        called_with_expected_message = False
        for call in mock_logger_warning.call_args_list:
            if "CRS units are not confirmed metric" in call.args[0]:
                called_with_expected_message = True
                break
        self.assertTrue(called_with_expected_message,
                        "logger.warning was not called with the expected message about non-metric CRS units.")

    # --- Tests for geocode_place_name ---
    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping geocoding tests")
    @patch('coordinate_utils.Nominatim')
    def test_geocode_place_name_success(self, mock_nominatim):
        mock_geolocator_instance = MagicMock()
        # Use a plain MagicMock first to ensure truthiness, then re-evaluate spec if needed
        mock_location_obj = MagicMock()
        mock_location_obj.latitude = 48.8584
        mock_location_obj.longitude = 2.2945

        mock_geolocator_instance.geocode.return_value = mock_location_obj
        mock_nominatim.return_value = mock_geolocator_instance

        result = geocode_place_name("Eiffel Tower")
        self.assertEqual(result, (48.8584, 2.2945))
        mock_nominatim.assert_called_once_with(user_agent="TerrainToolGeocoder")
        mock_geolocator_instance.geocode.assert_called_once_with("Eiffel Tower", timeout=10)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping geocoding tests")
    @patch('coordinate_utils.Nominatim')
    @patch('coordinate_utils.logger.warning')
    def test_geocode_place_name_not_found(self, mock_logger_warning, mock_nominatim):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.return_value = None
        mock_nominatim.return_value = mock_geolocator_instance
        result = geocode_place_name("NonExistentPlace123")
        self.assertIsNone(result)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping geocoding tests")
    @patch('coordinate_utils.Nominatim')
    @patch('coordinate_utils.logger.error')
    def test_geocode_place_name_timeout(self, mock_logger_error, mock_nominatim):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.side_effect = GeocoderTimedOut("Service timed out")
        mock_nominatim.return_value = mock_geolocator_instance
        result = geocode_place_name("QueryThatTimesOut")
        self.assertIsNone(result)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping geocoding tests")
    @patch('coordinate_utils.Nominatim')
    @patch('coordinate_utils.logger.error')
    def test_geocode_place_name_service_unavailable(self, mock_logger_error, mock_nominatim):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.side_effect = GeocoderUnavailable("Service unavailable")
        mock_nominatim.return_value = mock_geolocator_instance
        result = geocode_place_name("QueryToUnavailableService")
        self.assertIsNone(result)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping geocoding tests")
    @patch('coordinate_utils.Nominatim')
    @patch('coordinate_utils.logger.error')
    def test_geocode_place_name_service_error(self, mock_logger_error, mock_nominatim):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.side_effect = GeocoderServiceError("Service error")
        mock_nominatim.return_value = mock_geolocator_instance
        result = geocode_place_name("QueryCausingServiceError")
        self.assertIsNone(result)

    # --- Tests for calculate_bbox_from_center_and_distance ---
    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping distance tests")
    def test_calculate_bbox_valid_inputs(self):
        lat, lon = 48.8566, 2.3522
        distance = 10
        bbox = calculate_bbox_from_center_and_distance(lat, lon, distance)
        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)
        self.assertLess(bbox[1], bbox[3])
        self.assertTrue(all(isinstance(coord, float) for coord in bbox))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping distance tests")
    @patch('coordinate_utils.logger.error')
    def test_calculate_bbox_invalid_latitude(self, mock_logger_error):
        bbox = calculate_bbox_from_center_and_distance(95.0, 0.0, 10.0)
        self.assertIsNone(bbox)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping distance tests")
    @patch('coordinate_utils.logger.error')
    def test_calculate_bbox_invalid_longitude(self, mock_logger_error):
        bbox = calculate_bbox_from_center_and_distance(0.0, 185.0, 10.0)
        self.assertIsNone(bbox)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping distance tests")
    @patch('coordinate_utils.logger.error')
    def test_calculate_bbox_invalid_distance(self, mock_logger_error):
        bbox = calculate_bbox_from_center_and_distance(0.0, 0.0, -5.0)
        self.assertIsNone(bbox)
        bbox_zero = calculate_bbox_from_center_and_distance(0.0, 0.0, 0.0)
        self.assertIsNone(bbox_zero)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping distance tests")
    def test_calculate_bbox_pole_crossing_longitude_behavior(self):
        bbox = calculate_bbox_from_center_and_distance(89.9, 0.0, 10.0)
        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping distance tests")
    def test_calculate_bbox_antimeridian_crossing_behavior(self):
        bbox = calculate_bbox_from_center_and_distance(-18.1, 178.4, 300.0) # 300km
        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)


if __name__ == '__main__':
    unittest.main()
