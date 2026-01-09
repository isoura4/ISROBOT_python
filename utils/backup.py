"""
Automatic backup system for ISROBOT.

Provides:
- Automatic SQLite database backups
- Critical configuration backups
- Database corruption recovery
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BACKUP_DIR = "backups"
DEFAULT_MAX_BACKUPS = 10


def get_backup_dir() -> Path:
    """Get the backup directory path from environment or default."""
    backup_dir = os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR)
    path = Path(backup_dir)
    
    # Create directory if it doesn't exist
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created backup directory: {path}")
    
    return path


def get_max_backups() -> int:
    """Get the maximum number of backups to keep."""
    try:
        max_backups = int(os.getenv("MAX_BACKUPS", DEFAULT_MAX_BACKUPS))
        return max(1, min(max_backups, 100))  # Clamp between 1 and 100
    except (ValueError, TypeError):
        return DEFAULT_MAX_BACKUPS


def get_db_path() -> Optional[Path]:
    """Get the database path from environment."""
    db_path = os.getenv("db_path")
    if db_path:
        # Handle relative paths
        if not os.path.isabs(db_path):
            script_dir = Path(__file__).parent.parent
            db_path = script_dir / db_path
        return Path(db_path)
    return None


def create_backup_filename(prefix: str = "db_backup") -> str:
    """Create a timestamped backup filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.sqlite3"


def backup_database(
    source_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
    prefix: str = "db_backup"
) -> Optional[Path]:
    """
    Create a backup of the SQLite database.
    
    Uses SQLite's online backup API for safe backup while the database
    may be in use.
    
    Args:
        source_path: Path to the source database (default: from .env)
        backup_dir: Directory for backups (default: from .env or 'backups')
        prefix: Prefix for backup filename
        
    Returns:
        Path to the created backup, or None if backup failed
    """
    # Get paths
    source = source_path or get_db_path()
    dest_dir = backup_dir or get_backup_dir()
    
    if not source:
        logger.error("No database path configured")
        return None
    
    if not source.exists():
        logger.error(f"Source database does not exist: {source}")
        return None
    
    # Create backup filename
    backup_name = create_backup_filename(prefix)
    backup_path = dest_dir / backup_name
    
    try:
        # Use SQLite's backup API for safe backup
        source_conn = sqlite3.connect(str(source))
        backup_conn = sqlite3.connect(str(backup_path))
        
        try:
            source_conn.backup(backup_conn)
            logger.info(f"Database backup created: {backup_path}")
        finally:
            backup_conn.close()
            source_conn.close()
        
        # Verify backup integrity
        if verify_backup_integrity(backup_path):
            logger.info(f"Backup integrity verified: {backup_path}")
            
            # Clean up old backups
            cleanup_old_backups(dest_dir, prefix)
            
            return backup_path
        else:
            logger.error(f"Backup integrity check failed: {backup_path}")
            backup_path.unlink(missing_ok=True)
            return None
            
    except sqlite3.Error as e:
        logger.error(f"SQLite error during backup: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None


def verify_backup_integrity(backup_path: Path) -> bool:
    """
    Verify the integrity of a backup database.
    
    Args:
        backup_path: Path to the backup file
        
    Returns:
        True if backup is valid, False otherwise
    """
    try:
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.cursor()
        
        # Run SQLite integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        conn.close()
        
        return result and result[0] == "ok"
        
    except sqlite3.Error as e:
        logger.error(f"Integrity check failed: {e}")
        return False


def cleanup_old_backups(
    backup_dir: Optional[Path] = None,
    prefix: str = "db_backup",
    max_backups: Optional[int] = None
) -> int:
    """
    Clean up old backups, keeping only the most recent ones.
    
    Args:
        backup_dir: Directory containing backups
        prefix: Prefix of backup files to clean
        max_backups: Maximum number of backups to keep
        
    Returns:
        Number of backups deleted
    """
    dest_dir = backup_dir or get_backup_dir()
    max_keep = max_backups or get_max_backups()
    
    # Find all backups with the given prefix
    pattern = f"{prefix}_*.sqlite3"
    backups = sorted(dest_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Delete old backups
    deleted = 0
    for backup in backups[max_keep:]:
        try:
            backup.unlink()
            logger.info(f"Deleted old backup: {backup}")
            deleted += 1
        except Exception as e:
            logger.warning(f"Failed to delete old backup {backup}: {e}")
    
    return deleted


def restore_database(
    backup_path: Path,
    dest_path: Optional[Path] = None,
    create_backup_first: bool = True
) -> bool:
    """
    Restore the database from a backup.
    
    Args:
        backup_path: Path to the backup file
        dest_path: Destination path (default: from .env)
        create_backup_first: Whether to backup current DB before restoring
        
    Returns:
        True if restore was successful, False otherwise
    """
    dest = dest_path or get_db_path()
    
    if not dest:
        logger.error("No database path configured")
        return False
    
    if not backup_path.exists():
        logger.error(f"Backup file does not exist: {backup_path}")
        return False
    
    # Verify backup integrity first
    if not verify_backup_integrity(backup_path):
        logger.error(f"Backup is corrupted, cannot restore: {backup_path}")
        return False
    
    try:
        # Backup current database before restoring
        if create_backup_first and dest.exists():
            backup_database(dest, prefix="pre_restore")
            logger.info("Created pre-restore backup")
        
        # Use SQLite backup API for restore
        source_conn = sqlite3.connect(str(backup_path))
        dest_conn = sqlite3.connect(str(dest))
        
        try:
            source_conn.backup(dest_conn)
            logger.info(f"Database restored from: {backup_path}")
        finally:
            dest_conn.close()
            source_conn.close()
        
        return True
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error during restore: {e}")
        return False
    except Exception as e:
        logger.error(f"Error restoring database: {e}")
        return False


def check_database_corruption(db_path: Optional[Path] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if the database is corrupted.
    
    Args:
        db_path: Path to the database (default: from .env)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = db_path or get_db_path()
    
    if not path:
        return False, "No database path configured"
    
    if not path.exists():
        return False, f"Database does not exist: {path}"
    
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        conn.close()
        
        if result and result[0] == "ok":
            return True, None
        else:
            return False, f"Integrity check failed: {result[0] if result else 'unknown'}"
            
    except sqlite3.Error as e:
        return False, f"SQLite error: {e}"


def auto_recover_database() -> bool:
    """
    Automatically recover a corrupted database from the most recent backup.
    
    Returns:
        True if recovery was successful or not needed, False otherwise
    """
    # Check if database is corrupted
    is_valid, error = check_database_corruption()
    
    if is_valid:
        logger.info("Database is healthy, no recovery needed")
        return True
    
    logger.warning(f"Database corruption detected: {error}")
    
    # Find the most recent valid backup
    backup_dir = get_backup_dir()
    backups = sorted(
        backup_dir.glob("db_backup_*.sqlite3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    for backup in backups:
        if verify_backup_integrity(backup):
            logger.info(f"Found valid backup: {backup}")
            
            if restore_database(backup, create_backup_first=False):
                logger.info("Database recovery successful")
                return True
            else:
                logger.error("Failed to restore from backup")
    
    logger.error("No valid backups found for recovery")
    return False


def backup_config_files(
    config_files: Optional[List[str]] = None,
    backup_dir: Optional[Path] = None
) -> List[Path]:
    """
    Backup critical configuration files.
    
    Args:
        config_files: List of config file paths to backup
        backup_dir: Directory for backups
        
    Returns:
        List of created backup paths
    """
    dest_dir = backup_dir or get_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Default config files to backup
    if config_files is None:
        config_files = [".env.example", "pyproject.toml", "requirements.txt"]
    
    created_backups = []
    
    for config_file in config_files:
        source = Path(config_file)
        if not source.exists():
            logger.warning(f"Config file not found: {config_file}")
            continue
        
        try:
            backup_name = f"config_{source.name}_{timestamp}"
            backup_path = dest_dir / backup_name
            shutil.copy2(source, backup_path)
            created_backups.append(backup_path)
            logger.info(f"Backed up config: {source} -> {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup config {config_file}: {e}")
    
    return created_backups


def get_backup_list(
    backup_dir: Optional[Path] = None,
    prefix: str = "db_backup"
) -> List[Dict[str, Any]]:
    """
    Get a list of available backups with metadata.
    
    Args:
        backup_dir: Directory containing backups
        prefix: Prefix of backup files to list
        
    Returns:
        List of backup info dictionaries
    """
    dest_dir = backup_dir or get_backup_dir()
    pattern = f"{prefix}_*.sqlite3"
    
    backups = []
    for backup in dest_dir.glob(pattern):
        try:
            stat = backup.stat()
            backups.append({
                "path": backup,
                "name": backup.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime),
                "is_valid": verify_backup_integrity(backup)
            })
        except Exception as e:
            logger.warning(f"Failed to get info for backup {backup}: {e}")
    
    # Sort by creation time, newest first
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    
    return backups


# --- Scheduled Backup Task ---

async def scheduled_backup() -> Optional[Path]:
    """
    Async wrapper for creating a scheduled backup.
    Can be called from the bot's background task loop.
    
    Returns:
        Path to the created backup, or None if backup failed
    """
    import asyncio
    
    # Run backup in executor to avoid blocking
    loop = asyncio.get_event_loop()
    backup_path = await loop.run_in_executor(None, backup_database)
    
    if backup_path:
        logger.info(f"Scheduled backup completed: {backup_path}")
    else:
        logger.error("Scheduled backup failed")
    
    return backup_path
