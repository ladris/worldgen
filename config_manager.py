# config_manager.py
import os
import json

# IMPORTANT: Do not hardcode API keys directly in this file if it's version controlled.
# It's recommended to use environment variables or a separate, gitignored config file.

CONFIG_FILE_PATH = "config.json" # This file should be in .gitignore

def get_api_key(api_name: str) -> str | None:
    """
    Retrieves an API key.
    Priority:
    1. Environment variable (e.g., OPENTOPOGRAPHY_API_KEY)
    2. config.json file
    """
    # Check environment variables first
    env_var_name = f"{api_name.upper()}_API_KEY"
    api_key = os.environ.get(env_var_name)
    if api_key:
        print(f"Found API key for {api_name} in environment variable.")
        return api_key

    # Check config file
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)
            key = config.get("api_keys", {}).get(api_name)
            if key:
                print(f"Found API key for {api_name} in {CONFIG_FILE_PATH}.")
                return key
        except json.JSONDecodeError:
            print(f"Error: Could not decode {CONFIG_FILE_PATH}")
            return None
    print(f"API key for {api_name} not found in environment variables or {CONFIG_FILE_PATH}.")
    return None

def get_setting(setting_name: str, default: any = None) -> any:
    """
    Retrieves a general setting from the config file or returns a default.
    Settings are read from the "settings" dictionary in config.json.
    """
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)
            return config.get("settings", {}).get(setting_name, default)
        except json.JSONDecodeError:
            print(f"Error: Could not decode {CONFIG_FILE_PATH}. Using default for {setting_name}.")
            return default
    return default

# Example of how to structure a config.json (this file should be gitignored)
# {
# "api_keys": {
# "OpenTopography": "YOUR_OPENTOPOGRAPHY_API_KEY_HERE",
# "AnotherAPI": "YOUR_OTHER_API_KEY_HERE"
# },
# "settings": {
# "default_output_path": "./output_data",
# "default_dem_resolution": 30,
# "max_download_retries": 3
# }
# }

if __name__ == '__main__':
    # Example usage (primarily for testing the module directly)
    # To test, you would need to set an environment variable or create a config.json
    
    # Test case 1: API key from environment variable
    print("\n--- Test Case 1: API Key from Environment Variable ---")
    os.environ["TESTAPI_API_KEY"] = "env_key_123"
    print(f"TestAPI API Key: {get_api_key('TestAPI')}")
    del os.environ["TESTAPI_API_KEY"] # Clean up env var

    # Test case 2: API key from config.json
    print("\n--- Test Case 2: API Key from config.json ---")
    example_config_content = {
        "api_keys": {
            "OpenTopography": "json_key_456",
            "AnotherAPI": "another_json_key_789"
        },
        "settings": {
            "default_output_path": "./output_from_config",
            "max_download_retries": 5
        }
    }
    with open(CONFIG_FILE_PATH, 'w') as f_temp:
        json.dump(example_config_content, f_temp, indent=4)
    
    print(f"OpenTopography API Key: {get_api_key('OpenTopography')}")
    print(f"NonExistent API Key: {get_api_key('NonExistentAPI')}")

    # Test case 3: Settings from config.json
    print("\n--- Test Case 3: Settings from config.json ---")
    print(f"Default output path: {get_setting('default_output_path', './default_out')}")
    print(f"Max download retries: {get_setting('max_download_retries', 3)}")
    print(f"Non-existent setting: {get_setting('some_other_setting', 'default_value')}")

    # Test case 4: Config file not found
    print("\n--- Test Case 4: Config File Not Found ---")
    os.remove(CONFIG_FILE_PATH) # Remove config file for this test
    print(f"OpenTopography API Key (no config): {get_api_key('OpenTopography')}")
    print(f"Default output path (no config): {get_setting('default_output_path', './default_out_no_config')}")

    # Test case 5: Malformed config.json
    print("\n--- Test Case 5: Malformed config.json ---")
    with open(CONFIG_FILE_PATH, 'w') as f_temp:
        f_temp.write("this is not json")
    print(f"OpenTopography API Key (malformed config): {get_api_key('OpenTopography')}")
    print(f"Default output path (malformed config): {get_setting('default_output_path', './default_out_malformed')}")
    if os.path.exists(CONFIG_FILE_PATH):
        os.remove(CONFIG_FILE_PATH) # Clean up
    
    print("\n--- End of Tests ---")
