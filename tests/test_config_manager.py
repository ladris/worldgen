# tests/test_config_manager.py
import unittest
from unittest import mock
import os
import json
import sys

# Add project root to sys.path to allow importing project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config_manager import get_api_key, get_setting, CONFIG_FILE_PATH

class TestConfigManager(unittest.TestCase):

    def setUp(self):
        # Store original environ and CONFIG_FILE_PATH to restore later if changed
        self.original_environ = os.environ.copy()
        self.original_config_file_path = CONFIG_FILE_PATH # Assuming CONFIG_FILE_PATH is constant
        
        # Ensure a clean slate for relevant env vars before each test
        self.env_vars_to_clear = ["TESTAPI_API_KEY", "OTHERAPI_API_KEY", "MYSERVICE_API_KEY"]
        for key in self.env_vars_to_clear:
            if key in os.environ:
                del os.environ[key]
        
        # Clean up dummy config file if it exists from a previous failed run
        if os.path.exists(self.original_config_file_path):
            try:
                os.remove(self.original_config_file_path)
            except OSError:
                pass


    def tearDown(self):
        # Clean up dummy config file if it exists
        if os.path.exists(self.original_config_file_path):
            try:
                os.remove(self.original_config_file_path)
            except OSError: 
                pass
        
        # Restore original environment variables that were modified or cleared
        os.environ.clear()
        os.environ.update(self.original_environ)


    @mock.patch.dict(os.environ, {"TESTAPI_API_KEY": "env_key_123"}, clear=True)
    def test_get_api_key_from_env_only(self):
        # Ensure no config file to interfere
        if os.path.exists(CONFIG_FILE_PATH): # Use module's CONFIG_FILE_PATH
            os.remove(CONFIG_FILE_PATH)
        self.assertEqual(get_api_key("TestAPI"), "env_key_123")

    def test_get_api_key_from_json_only(self):
        # Ensure env var is not set
        if "TESTAPI_API_KEY" in os.environ:
            del os.environ["TESTAPI_API_KEY"]
        
        dummy_config = {"api_keys": {"TestAPI": "json_key_456"}}
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            json.dump(dummy_config, f)
        self.assertEqual(get_api_key("TestAPI"), "json_key_456")

    @mock.patch.dict(os.environ, {"TESTAPI_API_KEY": "env_key_priority"}, clear=True)
    def test_get_api_key_env_takes_precedence(self):
        dummy_config = {"api_keys": {"TestAPI": "json_key_should_be_ignored"}}
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            json.dump(dummy_config, f)
        self.assertEqual(get_api_key("TestAPI"), "env_key_priority")

    def test_get_api_key_not_found(self):
        if "TESTAPI_API_KEY" in os.environ:
            del os.environ["TESTAPI_API_KEY"]
        if os.path.exists(CONFIG_FILE_PATH): # Use module's CONFIG_FILE_PATH
            os.remove(CONFIG_FILE_PATH)
        self.assertIsNone(get_api_key("TestAPI"))

    def test_get_api_key_json_exists_but_key_missing(self):
        if "TESTAPI_API_KEY" in os.environ:
            del os.environ["TESTAPI_API_KEY"]
        dummy_config = {"api_keys": {"OtherAPI": "other_key"}} 
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            json.dump(dummy_config, f)
        self.assertIsNone(get_api_key("TestAPI"))

    @mock.patch('builtins.print') # Suppress print output from function during test
    def test_get_api_key_malformed_json(self, mock_print):
        if "TESTAPI_API_KEY" in os.environ:
            del os.environ["TESTAPI_API_KEY"]
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            f.write("this is not json")
        self.assertIsNone(get_api_key("TestAPI"))
        mock_print.assert_any_call(f"Error: Could not decode {CONFIG_FILE_PATH}")


    def test_get_setting_from_json(self):
        dummy_config = {"settings": {"my_setting": "value123", "timeout": 30}}
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            json.dump(dummy_config, f)
        self.assertEqual(get_setting("my_setting"), "value123")
        self.assertEqual(get_setting("timeout"), 30)

    def test_get_setting_not_found_with_default(self):
        if os.path.exists(CONFIG_FILE_PATH): # Use module's CONFIG_FILE_PATH
            os.remove(CONFIG_FILE_PATH)
        self.assertEqual(get_setting("non_existent_setting", "default_val"), "default_val")

    def test_get_setting_not_found_no_default(self):
        if os.path.exists(CONFIG_FILE_PATH): # Use module's CONFIG_FILE_PATH
            os.remove(CONFIG_FILE_PATH)
        self.assertIsNone(get_setting("non_existent_setting"))

    def test_get_setting_json_exists_but_setting_missing(self):
        dummy_config = {"settings": {"known_setting": "known_value"}}
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            json.dump(dummy_config, f)
        self.assertIsNone(get_setting("missing_setting"))
        self.assertEqual(get_setting("missing_setting_with_default", "default1"), "default1")
        
    @mock.patch('builtins.print') # Suppress print output
    def test_get_setting_malformed_json(self, mock_print):
        with open(CONFIG_FILE_PATH, 'w') as f: # Use module's CONFIG_FILE_PATH
            f.write("this is not json either")
        self.assertEqual(get_setting("any_setting", "default_on_error"), "default_on_error")
        self.assertIsNone(get_setting("any_setting_no_default"))
        mock_print.assert_any_call(f"Error: Could not decode {CONFIG_FILE_PATH}. Using default for any_setting.")


if __name__ == '__main__':
    unittest.main()
