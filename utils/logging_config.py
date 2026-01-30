"""
Centralized logging configuration for ISROBOT.
Provides color-coded console output and configurable log levels.
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()


# ANSI color codes for console output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.DIM + Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD + Colors.BRIGHT_RED,
    }

    LEVEL_ICONS = {
        logging.DEBUG: "🔍",
        logging.INFO: "ℹ️ ",
        logging.WARNING: "⚠️ ",
        logging.ERROR: "❌",
        logging.CRITICAL: "💀",
    }

    def __init__(self, fmt=None, datefmt=None, use_colors=True, use_icons=True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()
        self.use_icons = use_icons

    def format(self, record):
        # Save original values
        original_levelname = record.levelname
        original_msg = record.msg

        # Add icon prefix
        if self.use_icons:
            icon = self.LEVEL_ICONS.get(record.levelno, "")
            record.levelname = f"{icon} {record.levelname}"

        # Add colors
        if self.use_colors:
            color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
            record.levelname = f"{color}{record.levelname}{Colors.RESET}"
            record.msg = f"{color}{record.msg}{Colors.RESET}"

        # Format the message
        result = super().format(record)

        # Restore original values
        record.levelname = original_levelname
        record.msg = original_msg

        return result


def get_log_level_from_env():
    """Get log level from environment variable.

    Supports:
    - 'verbose' or 'debug' -> DEBUG
    - 'normal' or 'info' -> INFO
    - 'warning' or 'warn' -> WARNING
    - 'error' -> ERROR
    - 'critical' -> CRITICAL
    - 'quiet' or 'silent' -> WARNING (only show warnings and above)

    Default is INFO.
    """
    level_str = os.getenv("LOG_LEVEL", "info").lower().strip()

    level_mapping = {
        "verbose": logging.DEBUG,
        "debug": logging.DEBUG,
        "normal": logging.INFO,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
        "quiet": logging.WARNING,
        "silent": logging.WARNING,
    }

    return level_mapping.get(level_str, logging.INFO)


def setup_logging(
    log_file="discord.log",
    console_level=None,
    file_level=logging.DEBUG,
    use_colors=True,
    use_icons=True,
):
    """
    Configure logging for the application.

    Args:
        log_file: Path to the log file
        console_level: Log level for console (default: from LOG_LEVEL env)
        file_level: Log level for file (default: DEBUG to capture everything)
        use_colors: Whether to use colored output in console
        use_icons: Whether to use emoji icons in console output

    Returns:
        The root logger
    """
    if console_level is None:
        console_level = get_log_level_from_env()

    # Create formatters
    console_format = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s"
    file_format = "%(asctime)s:%(levelname)s:%(name)s: %(message)s"
    date_format = "%H:%M:%S"
    file_date_format = "%Y-%m-%d %H:%M:%S"

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(
        ColoredFormatter(console_format, date_format, use_colors, use_icons)
    )

    # File handler (captures everything)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(file_format, file_date_format))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Allow all levels, handlers filter

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger


def get_logger(name):
    """Get a logger for a specific module.

    Args:
        name: Usually __name__ from the calling module

    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)


# Print startup banner with log level info
def print_startup_banner(logger):
    """Print a startup banner showing current log configuration."""
    level = get_log_level_from_env()
    level_name = logging.getLevelName(level)

    logger.info("=" * 50)
    logger.info("ISROBOT - Discord Bot Starting")
    logger.info(f"Log Level: {level_name}")
    if level == logging.DEBUG:
        logger.info("Verbose mode enabled - all messages will be shown")
    logger.info("=" * 50)
