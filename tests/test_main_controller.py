# tests/test_main_controller.py
import unittest
from unittest.mock import patch
import sys
import os
import argparse # For ArgumentParser.error which calls sys.exit

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the function to test.
try:
    from main_controller import parse_arguments
    MAIN_CONTROLLER_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"Could not import parse_arguments from main_controller: {e}")
    MAIN_CONTROLLER_PARSER_AVAILABLE = False
    def parse_arguments(): # Dummy for test collection if import fails
        raise unittest.SkipTest("parse_arguments could not be imported from main_controller")


@unittest.skipIf(not MAIN_CONTROLLER_PARSER_AVAILABLE, "parse_arguments from main_controller not available.")
class TestMainControllerArgs(unittest.TestCase):

    def _parse_cmd_args(self, cmd_args_list):
        # Helper to simulate command line arguments
        with patch.object(sys, 'argv', ['main_controller.py'] + cmd_args_list):
            return parse_arguments()

    def test_parse_arguments_placename_and_distance_valid(self):
        args = self._parse_cmd_args(['--placename', 'Test Place', '--distance', '10'])
        self.assertEqual(args.placename, "Test Place")
        self.assertEqual(args.distance, 10.0)
        self.assertIsNone(args.bbox)

    def test_parse_arguments_bbox_valid(self):
        args = self._parse_cmd_args(['--bbox', '1.0', '2.0', '3.0', '4.0', '--utm_epsg', 'EPSG:TEST'])
        self.assertEqual(args.bbox, [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(args.utm_epsg, 'EPSG:TEST')
        self.assertIsNone(args.placename)

    def test_parse_arguments_defaults(self):
        args = self._parse_cmd_args(['--placename', 'Somewhere', '--distance', '5'])
        self.assertEqual(args.dem_type, "SRTMGL1")
        self.assertEqual(args.output_dir, "./output_data_cli")
        self.assertEqual(args.output_format, "BOTH")
        self.assertFalse(args.enable_tiling)
        self.assertEqual(args.tile_size_x, 1009)
        self.assertEqual(args.tile_size_y, 1009)
        self.assertIsNone(args.utm_epsg)

    def test_parse_arguments_tiling_enabled(self):
        args = self._parse_cmd_args([
            '--placename', 'Tile Area', '--distance', '20',
            '--enable_tiling', '--tile_size_x', '505', '--tile_size_y', '253'
        ])
        self.assertTrue(args.enable_tiling)
        self.assertEqual(args.tile_size_x, 505)
        self.assertEqual(args.tile_size_y, 253)

    def test_parse_arguments_missing_distance_for_placename(self):
        with self.assertRaises(SystemExit):
            self._parse_cmd_args(['--placename', 'No Distance'])

    def test_parse_arguments_invalid_distance_value(self):
        with self.assertRaises(SystemExit):
            self._parse_cmd_args(['--placename', 'Place', '--distance', '0'])
        with self.assertRaises(SystemExit):
            self._parse_cmd_args(['--placename', 'Place', '--distance', '-5'])

    def test_parse_arguments_missing_utm_for_bbox(self):
        with self.assertRaises(SystemExit):
            self._parse_cmd_args(['--bbox', '1.0', '2.0', '3.0', '4.0'])

    def test_parse_arguments_mutually_exclusive_aoi(self):
        with self.assertRaises(SystemExit):
            self._parse_cmd_args(['--placename', 'Place', '--distance', '5',
                                  '--bbox', '1.0', '2.0', '3.0', '4.0',
                                  '--utm_epsg', 'EPSG:TEST']) # Need UTM for bbox part

    def test_parse_arguments_output_format_choices(self):
        args = self._parse_cmd_args(['--placename', 'Test', '--distance', '1', '--output_format', 'PNG'])
        self.assertEqual(args.output_format, "PNG")
        with self.assertRaises(SystemExit):
            self._parse_cmd_args(['--placename', 'Test', '--distance', '1', '--output_format', 'INVALID'])

    def test_parse_arguments_api_key_provided(self):
        args = self._parse_cmd_args(['--placename', 'Test', '--distance', '1', '--api_key', 'mysecretkey'])
        self.assertEqual(args.api_key, "mysecretkey")


if __name__ == '__main__':
    unittest.main()
