# tests/test_coordinate_utils.py
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from coordinate_utils import (
    transform_bbox_to_crs,
    get_metric_dimensions,
    geocode_place_name,
    calculate_bbox_from_center_and_distance,
    get_utm_epsg_from_latlon # Added
)
from pyproj.exceptions import CRSError

# Attempt to import geopy exceptions, handle if geopy is not installed
try:
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError
    from geopy.location import Location
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    class GeocoderTimedOut(Exception): pass
    class GeocoderUnavailable(Exception): pass
    class GeocoderServiceError(Exception): pass
    class Location: pass

# Attempt to import utm, handle if not installed
try:
    import utm # For testing get_utm_epsg_from_latlon
    UTM_AVAILABLE = True
except ImportError:
    UTM_AVAILABLE = False
    # Define dummy utm.error if utm is not available so tests can be defined
    class utm: # type: ignore
        class error: # type: ignore
            class OutOfRangeError(Exception): pass


class TestCoordinateUtils(unittest.TestCase):

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

    @patch('coordinate_utils.logger.error')
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
        self.assertIsNotNone(width); self.assertIsNotNone(height)
        self.assertAlmostEqual(width, 1000.0); self.assertAlmostEqual(height, 2000.0)

    @patch('coordinate_utils.logger.error')
    def test_get_metric_dimensions_non_numeric(self, mock_logger_error):
        self.assertIsNone(get_metric_dimensions(("a", 4100000.0, 501000.0, 4102000.0))) # type: ignore

    @patch('coordinate_utils.logger.warning')
    def test_get_metric_dimensions_min_greater_than_max(self, mock_logger_warning):
        width, height = get_metric_dimensions((501000.0, 4102000.0, 500000.0, 4100000.0)) # type: ignore
        self.assertIsNotNone(width); self.assertIsNotNone(height)
        self.assertAlmostEqual(width, 1000.0); self.assertAlmostEqual(height, 2000.0)

    @patch('coordinate_utils.logger.error')
    def test_get_metric_dimensions_invalid_tuple_length(self, mock_logger_error):
        self.assertIsNone(get_metric_dimensions((500000.0, 4100000.0, 501000.0))) # type: ignore

    @patch('coordinate_utils.logger.warning')
    def test_get_metric_dimensions_crs_not_metric_warning(self, mock_logger_warning):
        get_metric_dimensions((500000.0,4100000.0,501000.0,4102000.0), crs_units_are_metric=False)
        self.assertTrue(any("CRS units are not confirmed metric" in call.args[0] for call in mock_logger_warning.call_args_list))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy library not installed, skipping geocoding tests")
    @patch('coordinate_utils.Nominatim')
    def test_geocode_place_name_success(self, mock_nominatim):
        mock_geo_inst = MagicMock(); mock_loc_obj = MagicMock()
        mock_loc_obj.latitude = 48.8584; mock_loc_obj.longitude = 2.2945
        mock_geo_inst.geocode.return_value = mock_loc_obj; mock_nominatim.return_value = mock_geo_inst
        self.assertEqual(geocode_place_name("Eiffel Tower"), (48.8584, 2.2945))
        mock_nominatim.assert_called_once_with(user_agent="TerrainToolGeocoder")
        mock_geo_inst.geocode.assert_called_once_with("Eiffel Tower", timeout=10)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.warning') # Outer decorator
    @patch('coordinate_utils.Nominatim')   # Inner decorator
    def test_geocode_place_name_not_found(self, mock_nominatim, mock_logger_warning): # Inner mock (mock_nominatim) first
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.return_value = None
        mock_nominatim.return_value = mock_geolocator_instance
        result = geocode_place_name("NonExistentPlace123")
        self.assertIsNone(result)

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.error') # Outer decorator
    @patch('coordinate_utils.Nominatim')   # Inner decorator
    def test_geocode_place_name_timeout(self, mock_nominatim, mock_logger_error):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.side_effect = GeocoderTimedOut("Timeout")
        mock_nominatim.return_value = mock_geolocator_instance
        self.assertIsNone(geocode_place_name("QueryTimesOut"))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.error') # Outer decorator
    @patch('coordinate_utils.Nominatim')   # Inner decorator
    def test_geocode_place_name_service_unavailable(self, mock_nominatim, mock_logger_error):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.side_effect = GeocoderUnavailable("Unavailable")
        mock_nominatim.return_value = mock_geolocator_instance
        self.assertIsNone(geocode_place_name("QueryToUnavailable"))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.error') # Outer decorator
    @patch('coordinate_utils.Nominatim')   # Inner decorator
    def test_geocode_place_name_service_error(self, mock_nominatim, mock_logger_error):
        mock_geolocator_instance = MagicMock()
        mock_geolocator_instance.geocode.side_effect = GeocoderServiceError("Error")
        mock_nominatim.return_value = mock_geolocator_instance
        self.assertIsNone(geocode_place_name("QueryCausesError"))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    def test_calculate_bbox_valid_inputs(self):
        bbox = calculate_bbox_from_center_and_distance(48.8566, 2.3522, 10)
        self.assertIsNotNone(bbox); self.assertEqual(len(bbox), 4)
        self.assertLess(bbox[1], bbox[3])
        self.assertTrue(all(isinstance(c, float) for c in bbox))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.error')
    def test_calculate_bbox_invalid_latitude(self, mock_log_err):
        self.assertIsNone(calculate_bbox_from_center_and_distance(95.0,0.0,10.0))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.error')
    def test_calculate_bbox_invalid_longitude(self, mock_log_err):
        self.assertIsNone(calculate_bbox_from_center_and_distance(0.0,185.0,10.0))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    @patch('coordinate_utils.logger.error')
    def test_calculate_bbox_invalid_distance(self, mock_log_err):
        self.assertIsNone(calculate_bbox_from_center_and_distance(0.0,0.0,-5.0))
        self.assertIsNone(calculate_bbox_from_center_and_distance(0.0,0.0,0.0))

    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    def test_calculate_bbox_pole_crossing(self):
        bbox = calculate_bbox_from_center_and_distance(89.9,0.0,10.0)
        self.assertIsNotNone(bbox); self.assertEqual(len(bbox),4)
    @unittest.skipIf(not GEOPY_AVAILABLE, "geopy skip")
    def test_calculate_bbox_antimeridian_crossing(self):
        bbox = calculate_bbox_from_center_and_distance(-18.1,178.4,300.0)
        self.assertIsNotNone(bbox); self.assertEqual(len(bbox),4)

    # --- Tests for get_utm_epsg_from_latlon ---
    @unittest.skipIf(not UTM_AVAILABLE, "utm library not installed, skipping UTM EPSG tests")
    def test_get_utm_epsg_from_latlon_valid_cases(self):
        self.assertEqual(get_utm_epsg_from_latlon(39.7392, -104.9903), "EPSG:32613") # Denver
        self.assertEqual(get_utm_epsg_from_latlon(48.8566, 2.3522), "EPSG:32631")   # Paris
        self.assertEqual(get_utm_epsg_from_latlon(-33.8688, 151.2093), "EPSG:32756") # Sydney
        self.assertEqual(get_utm_epsg_from_latlon(0, 0), "EPSG:32631") # Equator, Prime Meridian
        self.assertEqual(get_utm_epsg_from_latlon(0, 179.5), "EPSG:32660")# Equator, near dateline (Zone 60N)

    @unittest.skipIf(not UTM_AVAILABLE, "utm library not installed, skipping UTM EPSG tests")
    @patch('coordinate_utils.logger.error')
    def test_get_utm_epsg_from_latlon_invalid_coords(self, mock_logger_error):
        self.assertIsNone(get_utm_epsg_from_latlon(95.0, 0.0))
        self.assertIsNone(get_utm_epsg_from_latlon(0.0, 185.0))

    @unittest.skipIf(not UTM_AVAILABLE, "utm library not installed, skipping UTM EPSG tests")
    @patch('coordinate_utils.logger.warning') # Outer decorator
    @patch('coordinate_utils.utm.from_latlon', side_effect=utm.error.OutOfRangeError("Test OutOfRange")) # type: ignore # Inner decorator
    def test_get_utm_epsg_from_latlon_polar_oor(self, mock_utm_from_latlon, mock_logger_warning): # Inner mock first
        self.assertIsNone(get_utm_epsg_from_latlon(85.0, 0.0))
        mock_utm_from_latlon.assert_called_once_with(85.0, 0.0)

    @unittest.skipIf(not UTM_AVAILABLE, "utm library not installed, skipping UTM EPSG tests")
    @patch('coordinate_utils.logger.error') # Outer decorator
    @patch('coordinate_utils.utm.from_latlon', side_effect=Exception("Generic UTM Error")) # Inner decorator
    def test_get_utm_epsg_from_latlon_generic_utm_exception(self, mock_utm_from_latlon, mock_logger_error): # Inner mock first
        self.assertIsNone(get_utm_epsg_from_latlon(30.0, 30.0))
        mock_utm_from_latlon.assert_called_once_with(30.0, 30.0)

if __name__ == '__main__':
    unittest.main()
