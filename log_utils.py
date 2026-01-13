import logging
from settings import LOG_FILE, LOG_FILE_MODE

# Configure logging
logging.basicConfig(
    filename= LOG_FILE,
    filemode= LOG_FILE_MODE,
    level= logging.INFO,
    format='%(asctime)s - %(levelname)s [%(filename)s]: %(message)s',
    # datefmt='%Y-%m-%d %H:%M:%S',
    # handlers=[
    #     logging.FileHandler("app.log"),    # Log to file
    #     logging.StreamHandler()             # Log to console (stdout)
    # ]
)


def log_info(
        msg: str,
        logger: logging.Logger | None = None,
    ) -> None:
    """
    Logs an informational message and prints it to the console.

    Args:
        msg (str): The message to log.
        logger (logging.Logger | None): Optional logger instance. Defaults to root logger.
    """
    if logger is None:
        logger = logging.getLogger()
    
    logger.info(msg)
    print(msg)

def log_warning(
        msg: str,
        logger: logging.Logger | None = None,
    ) -> None:
    """
    Logs a warning message and prints it to the console with a 'WARNING:' prefix.

    Args:
        msg (str): The warning message to log.
        logger (logging.Logger | None): Optional logger instance. Defaults to root logger.
    """
    if logger is None:
        logger = logging.getLogger()
    
    logger.warning(msg)
    print(f"WARNING: {msg}")

def log_debug(msg: str, logger: logging.Logger | None = None) -> None:
    """
    Logs a debug message and prints it to the console with a 'DEBUG:' prefix.

    Args:
        msg (str): The debug message to log.
        logger (logging.Logger | None): Optional logger instance. Defaults to root logger.
    """
    if logger is None:
        logger = logging.getLogger()
    logger.debug(msg)
    print(f"DEBUG: {msg}")