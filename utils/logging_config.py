"""
Advanced logging configuration for ISROBOT.

Features:
- Configurable log levels (DEBUG, INFO, WARNING, ERROR) via .env
- Automatic log file rotation to prevent oversized log files
- Structured logging format for easier analysis and debugging
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Default configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "discord.log"
DEFAULT_MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 5

# Valid log levels
VALID_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredFormatter(logging.Formatter):
    """
    Structured log formatter for easier parsing and analysis.
    
    Format: [TIMESTAMP] [LEVEL] [MODULE:LINE] MESSAGE
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Add structured fields
        record.structured_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        record.module_line = f"{record.module}:{record.lineno}"
        
        return super().format(record)


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
    
    # Simpler format for console
    console_formatter = logging.Formatter(
        fmt="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
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
    return logging.getLogger(name)


# Module-level initialization for backward compatibility
_initialized = False


def ensure_logging_initialized() -> None:
    """Ensure logging is initialized. Safe to call multiple times."""
    global _initialized
    if not _initialized:
        setup_logging()
        _initialized = True
