# logger_setup.py
import logging
import sys
import os # Added to potentially create log directory

DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"

def setup_logger(name="terrain_tool_logger", level=DEFAULT_LOG_LEVEL, log_file=None, log_to_console=True):
    """
    Configures and returns a logger.

    Args:
        name (str): Name of the logger.
        level (int): Logging level (e.g., logging.DEBUG, logging.INFO).
        log_file (str, optional): Path to the log file. If None, no file logging.
        log_to_console (bool): Whether to output logs to the console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Prevent messages from propagating to the root logger, which might have its own handlers
    logger.propagate = False

    # Clear existing handlers to avoid duplicate messages if setup_logger is called multiple times
    # or if other parts of the application configure the same logger.
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    if log_to_console:
        # Console Handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # File Handler (optional)
    if log_file:
        try:
            # Ensure directory for log file exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            fh = logging.FileHandler(log_file, mode='a') # 'a' for append
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as e:
            # If file handler setup fails, log an error to console (if enabled)
            # or to a temporary emergency logger.
            emergency_logger = logging.getLogger("logger_setup_emergency")
            if not emergency_logger.hasHandlers(): # Avoid duplicate handlers for emergency logger
                emergency_ch = logging.StreamHandler(sys.stderr)
                emergency_ch.setFormatter(formatter)
                emergency_logger.addHandler(emergency_ch)
                emergency_logger.setLevel(logging.ERROR)
            emergency_logger.error(f"Failed to set up file handler for {log_file}: {e}", exc_info=True)
            if logger.hasHandlers() and ch in logger.handlers: # If console handler exists, use it
                 logger.error(f"Failed to set up file handler for {log_file}: {e}", exc_info=True)


    # If no handlers are configured (e.g. log_to_console=False and log_file=None or failed)
    # add a NullHandler to prevent "No handlers could be found for logger..." messages
    if not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())

    return logger

if __name__ == '__main__':
    # Example Usage

    print("--- Example 1: Console Logger (DEBUG level) ---")
    logger_console_debug = setup_logger("ConsoleOnlyDebug", level=logging.DEBUG)
    logger_console_debug.debug("This is a DEBUG message for the console-only logger.")
    logger_console_debug.info("This is an INFO message for the console-only logger.")

    print("\n--- Example 2: Console Logger (INFO level, default) ---")
    logger_console_info = setup_logger("ConsoleOnlyInfo") # Default level is INFO
    logger_console_info.debug("This DEBUG message will NOT be shown for ConsoleOnlyInfo.")
    logger_console_info.info("This is an INFO message for ConsoleOnlyInfo.")
    logger_console_info.warning("This is a WARNING message for ConsoleOnlyInfo.")
    logger_console_info.error("This is an ERROR message for ConsoleOnlyInfo.")
    logger_console_info.critical("This is a CRITICAL message for ConsoleOnlyInfo.")

    print("\n--- Example 3: File Logger (INFO level) ---")
    # Create a logs directory if it doesn't exist for the example
    log_dir_example = "logs_example"
    if not os.path.exists(log_dir_example):
        os.makedirs(log_dir_example)
    app_log_file = os.path.join(log_dir_example, "app.log")

    # Clean up old log file for fresh test run
    if os.path.exists(app_log_file):
        os.remove(app_log_file)

    logger_file = setup_logger("FileLoggerDemo", level=logging.INFO, log_file=app_log_file)
    logger_file.info("This INFO message will go to console (if enabled by default) and to " + app_log_file)
    logger_file.warning("This WARNING message will also go to console and " + app_log_file)
    print(f"Check {app_log_file} for file logger messages from FileLoggerDemo.")

    print("\n--- Example 4: File Logger Only (DEBUG level) ---")
    file_only_log_path = os.path.join(log_dir_example, "file_only.log")
    if os.path.exists(file_only_log_path):
        os.remove(file_only_log_path)

    logger_file_only = setup_logger("FileOnlyDemo", level=logging.DEBUG, log_file=file_only_log_path, log_to_console=False)
    logger_file_only.debug("This DEBUG message goes only to " + file_only_log_path)
    logger_file_only.info("This INFO message goes only to " + file_only_log_path)
    print(f"Check {file_only_log_path} for messages. Nothing should have printed to console from FileOnlyDemo.")

    print("\n--- Example 5: Logger with same name (reconfiguration) ---")
    # First configuration
    logger_reconfig = setup_logger("ReconfigTest", level=logging.WARNING, log_file=os.path.join(log_dir_example, "reconfig.log"))
    logger_reconfig.info("This INFO should not appear (due to WARNING level).")
    logger_reconfig.warning("First warning for ReconfigTest.")

    # Reconfigure (e.g. change level or add another handler, this tests handler clearing)
    # For simplicity, we'll just change the level and log file.
    # The previous file handler for reconfig.log should be removed.
    reconfig_log_2 = os.path.join(log_dir_example, "reconfig_new.log")
    if os.path.exists(reconfig_log_2):
        os.remove(reconfig_log_2)
    logger_reconfig_updated = setup_logger("ReconfigTest", level=logging.INFO, log_file=reconfig_log_2)
    logger_reconfig_updated.info("This INFO should appear in console and " + reconfig_log_2)
    logger_reconfig_updated.warning("Second warning for ReconfigTest, now to " + reconfig_log_2)
    print(f"Check {os.path.join(log_dir_example, 'reconfig.log')} and {reconfig_log_2}.")

    print("\n--- Example 6: No handlers (should not produce errors) ---")
    logger_no_handlers = setup_logger("NoHandlersDemo", log_to_console=False, log_file=None)
    logger_no_handlers.info("This message will go nowhere, but should not cause an error.")
    print("Completed NoHandlersDemo test.")

    print("\n--- Logger setup tests complete. ---")
    print(f"Please check the '{log_dir_example}' directory for log files.")
    # To clean up example logs directory:
    # import shutil
    # if os.path.exists(log_dir_example):
    # shutil.rmtree(log_dir_example)
    # print(f"Cleaned up {log_dir_example} directory.")
