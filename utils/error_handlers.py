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
from typing import Any, Callable, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


# --- Error Messages (French) ---

ERROR_MESSAGES = {
    # Discord permission errors
    "discord_forbidden": (
        "❌ **Permission refusée**\n"
        "Le bot n'a pas les permissions nécessaires pour effectuer cette action.\n"
        "Vérifiez que le bot a les permissions requises sur ce serveur/canal."
    ),
    "discord_missing_permissions": (
        "❌ **Permissions insuffisantes**\n"
        "Vous n'avez pas les permissions nécessaires pour utiliser cette commande."
    ),
    "discord_bot_missing_permissions": (
        "❌ **Permissions du bot insuffisantes**\n"
        "Le bot n'a pas les permissions nécessaires: {missing}"
    ),
    
    # API timeout errors
    "api_timeout": (
        "⏱️ **Délai d'attente dépassé**\n"
        "Le service externe n'a pas répondu à temps. Veuillez réessayer plus tard."
    ),
    "twitch_timeout": (
        "⏱️ **Délai d'attente Twitch dépassé**\n"
        "L'API Twitch n'a pas répondu à temps. Veuillez réessayer plus tard."
    ),
    "youtube_timeout": (
        "⏱️ **Délai d'attente YouTube dépassé**\n"
        "L'API YouTube n'a pas répondu à temps. Veuillez réessayer plus tard."
    ),
    "ollama_timeout": (
        "⏱️ **Délai d'attente IA dépassé**\n"
        "Le serveur IA n'a pas répondu à temps. Veuillez réessayer plus tard."
    ),
    
    # Database errors
    "database_error": (
        "❌ **Erreur de base de données**\n"
        "Une erreur s'est produite lors de l'accès à la base de données. "
        "Veuillez réessayer plus tard."
    ),
    "database_locked": (
        "❌ **Base de données occupée**\n"
        "La base de données est actuellement occupée. Veuillez réessayer dans quelques secondes."
    ),
    "database_connection": (
        "❌ **Connexion impossible**\n"
        "Impossible de se connecter à la base de données. "
        "Veuillez contacter un administrateur."
    ),
    
    # Command errors
    "command_error": (
        "❌ **Erreur de commande**\n"
        "Une erreur s'est produite lors de l'exécution de la commande."
    ),
    "invalid_input": (
        "❌ **Entrée invalide**\n"
        "Les données fournies ne sont pas valides: {details}"
    ),
    "user_not_found": (
        "❌ **Utilisateur introuvable**\n"
        "L'utilisateur spécifié n'a pas été trouvé."
    ),
    "channel_not_found": (
        "❌ **Canal introuvable**\n"
        "Le canal spécifié n'a pas été trouvé."
    ),
    "cooldown": (
        "⏳ **Cooldown actif**\n"
        "Veuillez patienter {time} avant de réutiliser cette commande."
    ),
    "rate_limited": (
        "🚫 **Limite de requêtes atteinte**\n"
        "Vous avez fait trop de requêtes. Veuillez patienter {time}."
    ),
    
    # Generic errors
    "unknown_error": (
        "❌ **Erreur inattendue**\n"
        "Une erreur inattendue s'est produite. Veuillez réessayer plus tard."
    ),
}


# --- Error Classification ---

def classify_error(error: Exception) -> tuple[str, dict]:
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


def get_error_message(error: Exception) -> str:
    """
    Get a user-friendly error message for the given exception.
    
    Args:
        error: The exception
        
    Returns:
        A formatted error message string
    """
    error_key, context = classify_error(error)
    message_template = ERROR_MESSAGES.get(error_key, ERROR_MESSAGES["unknown_error"])
    
    try:
        return message_template.format(**context)
    except KeyError:
        return message_template


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
            if "locked" in str(e).lower():
                logger.warning(f"Database locked in {func.__name__}: {e}")
                raise DatabaseLockedError("La base de données est occupée") from e
            logger.error(f"Database operational error in {func.__name__}: {e}")
            raise DatabaseError("Erreur de base de données") from e
        except sqlite3.Error as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise DatabaseError("Erreur de base de données") from e
    return wrapper


def handle_api_errors(service_name: str = "API") -> Callable:
    """
    Decorator factory to handle API errors with service-specific messages.
    
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
                logger.error(f"{service_name} client error in {func.__name__}: {e}")
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
    interaction: discord.Interaction,
    error: Exception,
    ephemeral: bool = True
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
        exc_info=error if error_key == "unknown_error" else None
    )
    
    # Get user-friendly message
    message = get_error_message(error)
    
    # Create embed
    embed = discord.Embed(
        title="Erreur",
        description=message,
        color=discord.Color.red()
    )
    embed.set_footer(text="Si le problème persiste, contactez un administrateur.")
    
    # Send response
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    except discord.HTTPException as e:
        logger.error(f"Failed to send error message: {e}")


def create_error_embed(
    title: str = "Erreur",
    description: str = None,
    error: Exception = None
) -> discord.Embed:
    """
    Create a standardized error embed.
    
    Args:
        title: The embed title
        description: The error description (takes priority over error)
        error: The exception (used if description is None)
        
    Returns:
        A Discord embed with the error message
    """
    if description is None and error is not None:
        description = get_error_message(error)
    elif description is None:
        description = ERROR_MESSAGES["unknown_error"]
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red()
    )
    embed.set_footer(text="Système ISROBOT")
    
    return embed
