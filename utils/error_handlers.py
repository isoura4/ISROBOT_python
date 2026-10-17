"""
Global error handlers for ISROBOT.

Provides centralized error handling for:
- Discord permission errors
- API timeouts (Twitch, YouTube, Ollama)
- SQLite database errors
- User command errors with explanatory messages
"""

import asyncio
import logging
import sqlite3
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_locale, t

logger = logging.getLogger(__name__)


# Error message keys are stored in locales/*.json under the "errors." namespace.


# --- Error Classification ---


def classify_error(error: Exception) -> Tuple[str, Dict[str, Any]]:
    """
    Classify an exception and return the appropriate error key and context.

    Args:
        error: The exception to classify

    Returns:
        Tuple of (error_key, context_dict)
    """
    # Discord permission errors
    if isinstance(error, discord.Forbidden):
        return "discord_forbidden", {}

    if isinstance(error, app_commands.MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        return "discord_missing_permissions", {"missing": missing}

    if isinstance(error, app_commands.BotMissingPermissions):
        missing = ", ".join(error.missing_permissions)
        return "discord_bot_missing_permissions", {"missing": missing}

    # Timeout errors
    if isinstance(error, asyncio.TimeoutError):
        return "api_timeout", {}

    if isinstance(error, aiohttp.ServerTimeoutError):
        return "api_timeout", {}

    # Database errors
    if isinstance(error, sqlite3.OperationalError):
        if "locked" in str(error).lower():
            return "database_locked", {}
        return "database_error", {}

    if isinstance(error, sqlite3.Error):
        return "database_error", {}

    # Command errors
    if isinstance(error, app_commands.CommandOnCooldown):
        time_str = format_cooldown_time(error.retry_after)
        return "cooldown", {"time": time_str}

    if isinstance(error, commands.CommandOnCooldown):
        time_str = format_cooldown_time(error.retry_after)
        return "cooldown", {"time": time_str}

    if isinstance(error, ValueError):
        return "invalid_input", {"details": str(error)}

    # Default
    return "unknown_error", {}


def get_error_message(error: Exception, locale: Optional[str] = None) -> str:
    """
    Get a user-friendly error message for the given exception.

    Args:
        error: The exception
        locale: Optional Discord locale for localization

    Returns:
        A formatted error message string
    """
    error_key, context = classify_error(error)
    key = f"errors.{error_key}"
    message = t(key, locale, **context)
    if message == key:
        message = t("errors.unknown_error", locale)
    return message


def format_cooldown_time(seconds: float) -> str:
    """Format cooldown time in a human-readable format."""
    if seconds < 60:
        return f"{int(seconds)} seconde{'s' if seconds >= 2 else ''}"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes >= 2 else ''}"
    else:
        hours = int(seconds / 3600)
        return f"{hours} heure{'s' if hours >= 2 else ''}"


# --- Error Handler Decorators ---


def handle_database_errors(func: Callable) -> Callable:
    """
    Decorator to handle database errors in async functions.
    Logs the error and re-raises a user-friendly exception.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            error_msg = str(e)
            if "locked" in error_msg.lower():
                logger.warning(f"Database locked in {func.__name__}: {error_msg}")
                raise DatabaseLockedError("La base de données est occupée") from e
            logger.error(f"Database operational error in {func.__name__}: {error_msg}")
            raise DatabaseError("Erreur de base de données") from e
        except sqlite3.Error as e:
            error_msg = str(e)
            logger.error(f"Database error in {func.__name__}: {error_msg}")
            raise DatabaseError("Erreur de base de données") from e

    return wrapper


def handle_api_errors(service_name: str = "API") -> Callable:
    """
    Decorator factory to handle API errors with service-specific messages.
    Sanitizes error messages to prevent credential exposure.

    Args:
        service_name: Name of the service (e.g., "Twitch", "YouTube", "Ollama")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except asyncio.TimeoutError as e:
                logger.warning(f"{service_name} timeout in {func.__name__}")
                raise APITimeoutError(f"Délai d'attente {service_name} dépassé") from e
            except aiohttp.ClientError as e:
                # Sanitize error message to prevent credential exposure
                error_msg = str(e)
                import re

                sanitized_msg = re.sub(
                    r'["\']?(?:key|token|api_key|access_token|secret)["\']?\s*[:=]\s*[^,\s}\]]+',
                    "[REDACTED]",
                    error_msg,
                    flags=re.IGNORECASE,
                )
                logger.error(
                    f"{service_name} client error in {func.__name__}: {sanitized_msg}"
                )
                raise APIError(f"Erreur de connexion {service_name}") from e

        return wrapper

    return decorator


# --- Custom Exceptions ---


class ISROBOTError(Exception):
    """Base exception for ISROBOT errors."""

    pass


class DatabaseError(ISROBOTError):
    """Raised when a database operation fails."""

    pass


class DatabaseLockedError(DatabaseError):
    """Raised when the database is locked."""

    pass


class APIError(ISROBOTError):
    """Raised when an API call fails."""

    pass


class APITimeoutError(APIError):
    """Raised when an API call times out."""

    pass


class ValidationError(ISROBOTError):
    """Raised when input validation fails."""

    pass


class RateLimitError(ISROBOTError):
    """Raised when rate limit is exceeded."""

    pass


# --- Global Error Handler for Commands ---


async def handle_interaction_error(
    interaction: discord.Interaction, error: Exception, ephemeral: bool = True
) -> None:
    """
    Handle errors in slash command interactions.

    Args:
        interaction: The Discord interaction
        error: The exception that occurred
        ephemeral: Whether the error message should be ephemeral
    """
    # Log the error
    error_key, _ = classify_error(error)
    logger.error(
        f"Command error in {interaction.command.name if interaction.command else 'unknown'}: "
        f"[{error_key}] {error}",
        exc_info=error if error_key == "unknown_error" else None,
    )

    # Get user-friendly message
    locale = get_locale(interaction)
    message = get_error_message(error, locale)

    # Create embed
    embed = discord.Embed(
        title=t("errors.title", locale), description=message, color=discord.Color.red()
    )
    embed.set_footer(text=t("errors.footer", locale))

    # Send response
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    except discord.HTTPException as e:
        logger.error(f"Failed to send error message: {e}")


def create_error_embed(
    title: Optional[str] = None,
    description: str = None,
    error: Exception = None,
    locale: Optional[str] = None,
) -> discord.Embed:
    """
    Create a standardized error embed.

    Args:
        title: The embed title
        description: The error description (takes priority over error)
        error: The exception (used if description is None)
        locale: Optional Discord locale for localization

    Returns:
        A Discord embed with the error message
    """
    if description is None and error is not None:
        description = get_error_message(error, locale)
    elif description is None:
        description = t("errors.unknown_error", locale)

    embed = discord.Embed(
        title=title or t("errors.title", locale),
        description=description,
        color=discord.Color.red(),
    )
    embed.set_footer(text=t("errors.system_footer", locale))

    return embed
