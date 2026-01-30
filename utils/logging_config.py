"""
Advanced logging configuration for ISROBOT.

Features:
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, VERBOSE) via .env
- Automatic log file rotation to prevent oversized log files
- Structured logging format for easier analysis and debugging
- Colorized console output for improved readability
- Different log level icons for quick visual identification
"""

import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Default configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "discord.log"
DEFAULT_MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 5

# Custom VERBOSE level (between DEBUG and INFO)
VERBOSE = 15
logging.addLevelName(VERBOSE, "VERBOSE")

# Valid log levels with aliases
VALID_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "VERBOSE": VERBOSE,
    "INFO": logging.INFO,
    "NORMAL": logging.INFO,  # Alias for INFO
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ANSI color codes for terminal output
COLORS = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    # Log level colors
    "DEBUG": "\033[36m",      # Cyan
    "VERBOSE": "\033[96m",    # Light Cyan
    "INFO": "\033[32m",       # Green
    "WARNING": "\033[33m",    # Yellow
    "ERROR": "\033[31m",      # Red
    "CRITICAL": "\033[41m",   # Red background
    # Component colors
    "TIME": "\033[90m",       # Gray
    "MODULE": "\033[35m",     # Magenta
}

# Log level icons for visual identification (all without trailing space - handled in formatter)
LEVEL_ICONS = {
    "DEBUG": "🔍",
    "VERBOSE": "📝",
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "ERROR": "❌",
    "CRITICAL": "🚨",
}


def _supports_color() -> bool:
    """Check if the terminal supports color output."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    # Check for common environment variables that indicate color support
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    # Most modern terminals support color
    return True


class StructuredFormatter(logging.Formatter):
    """
    Structured log formatter for file logging with easier parsing and analysis.
    
    Format: [TIMESTAMP] [LEVEL] [MODULE:LINE] MESSAGE
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Add structured fields using timezone-aware datetime
        record.structured_time = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]
        record.module_line = f"{record.module}:{record.lineno}"
        
        return super().format(record)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Colorized console formatter for improved readability.
    
    Features:
    - Color-coded log levels
    - Icons for quick visual identification
    - Compact, readable format
    """
    
    def __init__(self, use_colors: bool = True, use_icons: bool = True):
        super().__init__()
        self.use_colors = use_colors and _supports_color()
        self.use_icons = use_icons
    
    def format(self, record: logging.LogRecord) -> str:
        # Get timestamp
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        
        # Get level name and normalize it
        level_name = record.levelname
        if record.levelno == VERBOSE:
            level_name = "VERBOSE"
        
        # Build the formatted message
        if self.use_colors:
            # Get colors
            level_color = COLORS.get(level_name, COLORS["INFO"])
            time_color = COLORS["TIME"]
            module_color = COLORS["MODULE"]
            reset = COLORS["RESET"]
            
            # Get icon (add space after if icon is present)
            icon = LEVEL_ICONS.get(level_name, "")
            icon_str = f"{icon} " if self.use_icons and icon else ""
            
            # Format with colors
            formatted = (
                f"{time_color}{timestamp}{reset} "
                f"{level_color}{icon_str}{level_name:<8}{reset} "
                f"{module_color}{record.name}{reset}: "
                f"{record.getMessage()}"
            )
        else:
            # Format without colors
            icon = LEVEL_ICONS.get(level_name, "")
            icon_str = f"{icon} " if self.use_icons and icon else ""
            formatted = (
                f"{timestamp} {icon_str}{level_name:<8} {record.name}: "
                f"{record.getMessage()}"
            )
        
        # Add exception info if present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                if self.use_colors:
                    formatted += f"\n{COLORS['ERROR']}{record.exc_text}{COLORS['RESET']}"
                else:
                    formatted += f"\n{record.exc_text}"
        
        return formatted


def get_log_level() -> int:
    """Get the configured log level from environment variables."""
    level_str = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    
    if level_str not in VALID_LOG_LEVELS:
        print(f"⚠️ Invalid LOG_LEVEL '{level_str}', using default: {DEFAULT_LOG_LEVEL}")
        return VALID_LOG_LEVELS[DEFAULT_LOG_LEVEL]
    
    return VALID_LOG_LEVELS[level_str]


def get_log_file() -> str:
    """Get the configured log file path from environment variables."""
    return os.getenv("LOG_FILE", DEFAULT_LOG_FILE)


def get_max_log_size() -> int:
    """Get the maximum log file size in bytes from environment variables."""
    try:
        size_mb = float(os.getenv("LOG_MAX_SIZE_MB", "5"))
        return int(size_mb * 1024 * 1024)
    except (ValueError, TypeError):
        return DEFAULT_MAX_LOG_SIZE


def get_backup_count() -> int:
    """Get the number of backup log files to keep from environment variables."""
    try:
        count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        return max(1, min(count, 20))  # Clamp between 1 and 20
    except (ValueError, TypeError):
        return DEFAULT_BACKUP_COUNT


def setup_logging(
    log_level: Optional[int] = None,
    log_file: Optional[str] = None,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
) -> logging.Logger:
    """
    Configure the logging system with rotation and structured format.
    
    Args:
        log_level: Override log level (default: from .env or INFO)
        log_file: Override log file path (default: from .env or discord.log)
        max_bytes: Maximum log file size before rotation (default: 5 MB)
        backup_count: Number of backup files to keep (default: 5)
    
    Returns:
        The root logger configured for the application.
    """
    # Use provided values or get from environment
    level = log_level if log_level is not None else get_log_level()
    file_path = log_file if log_file is not None else get_log_file()
    max_size = max_bytes if max_bytes is not None else get_max_log_size()
    backups = backup_count if backup_count is not None else get_backup_count()
    
    # Create formatters
    # Structured format for file logging
    file_formatter = StructuredFormatter(
        fmt="[%(structured_time)s] [%(levelname)-8s] [%(module_line)-20s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Colorized format for console with icons
    console_formatter = ColoredConsoleFormatter(use_colors=True, use_icons=True)
    
    # Create handlers
    handlers = []
    
    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            filename=file_path,
            maxBytes=max_size,
            backupCount=backups,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    except (OSError, IOError) as e:
        print(f"⚠️ Could not create log file handler: {e}")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handlers
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Set lower log levels for third-party libraries
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: The name of the logger (typically __name__)
    
    Returns:
        A configured logger instance.
    """
    logger = logging.getLogger(name)
    
    # Add verbose method to logger instance
    def verbose(msg, *args, **kwargs):
        """Log a message at VERBOSE level (between DEBUG and INFO)."""
        if logger.isEnabledFor(VERBOSE):
            logger._log(VERBOSE, msg, args, **kwargs)
    
    logger.verbose = verbose
    return logger


# Module-level initialization for backward compatibility
_initialized = False


def ensure_logging_initialized() -> None:
    """Ensure logging is initialized. Safe to call multiple times."""
    global _initialized
    if not _initialized:
        setup_logging()
        _initialized = True


# Export the VERBOSE level constant for external use
__all__ = [
    "setup_logging",
    "get_logger",
    "ensure_logging_initialized",
    "VERBOSE",
    "VALID_LOG_LEVELS",
]
