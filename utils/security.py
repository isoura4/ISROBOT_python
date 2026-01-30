"""
Security utilities for ISROBOT.

Provides:
- Rate limiting on commands (per-user and per-server)
- Configurable cooldown system per command
- Spam detection and prevention
- Strict input validation to prevent injections
"""

import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


# --- Rate Limiting Configuration ---

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    # Per-user limits
    user_max_requests: int = 10  # Max requests per user in time window
    user_time_window: int = 60  # Time window in seconds
    
    # Per-server limits
    server_max_requests: int = 50  # Max requests per server in time window
    server_time_window: int = 60  # Time window in seconds
    
    # Spam detection
    spam_threshold: int = 5  # Number of identical commands to trigger spam detection
    spam_time_window: int = 10  # Time window for spam detection
    
    # Cooldown between same command
    default_cooldown: int = 3  # Default cooldown in seconds


@dataclass
class RateLimitEntry:
    """Entry for tracking rate limit state."""
    timestamps: list = field(default_factory=list)
    last_command: str = ""
    same_command_count: int = 0


class RateLimiter:
    """
    Rate limiter for Discord commands.
    
    Tracks requests per-user and per-server to prevent abuse.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        
        # User rate limit tracking: {user_id: RateLimitEntry}
        self._user_limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        
        # Server rate limit tracking: {guild_id: RateLimitEntry}
        self._server_limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        
        # Command-specific cooldowns: {(user_id, command_name): timestamp}
        self._cooldowns: Dict[Tuple[str, str], float] = {}
        
        # Custom cooldowns per command: {command_name: seconds}
        self._command_cooldowns: Dict[str, int] = {}
    
    def set_command_cooldown(self, command_name: str, cooldown_seconds: int) -> None:
        """
        Set a custom cooldown for a specific command.
        
        Args:
            command_name: The name of the command
            cooldown_seconds: Cooldown duration in seconds
        """
        self._command_cooldowns[command_name] = cooldown_seconds
    
    def get_command_cooldown(self, command_name: str) -> int:
        """Get the cooldown for a specific command."""
        return self._command_cooldowns.get(command_name, self.config.default_cooldown)
    
    def _clean_old_timestamps(self, entry: RateLimitEntry, time_window: int) -> None:
        """Remove timestamps older than the time window."""
        current_time = time.time()
        cutoff = current_time - time_window
        entry.timestamps = [ts for ts in entry.timestamps if ts > cutoff]
    
    def check_user_rate_limit(self, user_id: str, command_name: str) -> Tuple[bool, Optional[float]]:
        """
        Check if a user has exceeded their rate limit.
        
        Args:
            user_id: The user's ID
            command_name: The command being executed
            
        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        entry = self._user_limits[user_id]
        current_time = time.time()
        
        # Clean old timestamps
        self._clean_old_timestamps(entry, self.config.user_time_window)
        
        # Check rate limit
        if len(entry.timestamps) >= self.config.user_max_requests:
            oldest = min(entry.timestamps)
            retry_after = oldest + self.config.user_time_window - current_time
            logger.warning(f"User {user_id} rate limited (retry in {retry_after:.1f}s)")
            return True, max(0, retry_after)
        
        # Check spam (same command repeated)
        if entry.last_command == command_name:
            entry.same_command_count += 1
            if entry.same_command_count >= self.config.spam_threshold:
                logger.warning(f"Spam detected from user {user_id}: {command_name}")
                return True, float(self.config.spam_time_window)
        else:
            entry.last_command = command_name
            entry.same_command_count = 1
        
        # Add timestamp
        entry.timestamps.append(current_time)
        return False, None
    
    def check_server_rate_limit(self, guild_id: str) -> Tuple[bool, Optional[float]]:
        """
        Check if a server has exceeded its rate limit.
        
        Args:
            guild_id: The server's ID
            
        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        entry = self._server_limits[guild_id]
        current_time = time.time()
        
        # Clean old timestamps
        self._clean_old_timestamps(entry, self.config.server_time_window)
        
        # Check rate limit
        if len(entry.timestamps) >= self.config.server_max_requests:
            oldest = min(entry.timestamps)
            retry_after = oldest + self.config.server_time_window - current_time
            logger.warning(f"Server {guild_id} rate limited (retry in {retry_after:.1f}s)")
            return True, max(0, retry_after)
        
        # Add timestamp
        entry.timestamps.append(current_time)
        return False, None
    
    def check_cooldown(self, user_id: str, command_name: str) -> Tuple[bool, Optional[float]]:
        """
        Check if a user is on cooldown for a specific command.
        
        Args:
            user_id: The user's ID
            command_name: The command name
            
        Returns:
            Tuple of (is_on_cooldown, remaining_seconds)
        """
        key = (user_id, command_name)
        current_time = time.time()
        cooldown = self.get_command_cooldown(command_name)
        
        if key in self._cooldowns:
            last_use = self._cooldowns[key]
            elapsed = current_time - last_use
            
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                return True, remaining
        
        return False, None
    
    def set_cooldown(self, user_id: str, command_name: str) -> None:
        """
        Set the cooldown timestamp for a user's command.
        
        Args:
            user_id: The user's ID
            command_name: The command name
        """
        key = (user_id, command_name)
        self._cooldowns[key] = time.time()
    
    def check_all_limits(
        self, 
        user_id: str, 
        guild_id: Optional[str], 
        command_name: str
    ) -> Tuple[bool, Optional[float], str]:
        """
        Check all rate limits for a request.
        
        Args:
            user_id: The user's ID
            guild_id: The server's ID (optional)
            command_name: The command name
            
        Returns:
            Tuple of (is_limited, retry_after, reason)
        """
        # Check command cooldown
        on_cooldown, remaining = self.check_cooldown(user_id, command_name)
        if on_cooldown:
            return True, remaining, "cooldown"
        
        # Check user rate limit
        is_limited, retry_after = self.check_user_rate_limit(user_id, command_name)
        if is_limited:
            return True, retry_after, "user_rate_limit"
        
        # Check server rate limit
        if guild_id:
            is_limited, retry_after = self.check_server_rate_limit(guild_id)
            if is_limited:
                return True, retry_after, "server_rate_limit"
        
        # Set cooldown for next time
        self.set_cooldown(user_id, command_name)
        
        return False, None, ""
    
    def cleanup(self) -> None:
        """Clean up old entries to prevent memory leaks."""
        current_time = time.time()
        
        # Clean user limits
        users_to_remove = []
        for user_id, entry in self._user_limits.items():
            self._clean_old_timestamps(entry, self.config.user_time_window)
            if not entry.timestamps:
                users_to_remove.append(user_id)
        for user_id in users_to_remove:
            del self._user_limits[user_id]
        
        # Clean server limits
        servers_to_remove = []
        for guild_id, entry in self._server_limits.items():
            self._clean_old_timestamps(entry, self.config.server_time_window)
            if not entry.timestamps:
                servers_to_remove.append(guild_id)
        for guild_id in servers_to_remove:
            del self._server_limits[guild_id]
        
        # Clean old cooldowns (older than 1 hour)
        cooldown_cutoff = current_time - 3600
        self._cooldowns = {
            k: v for k, v in self._cooldowns.items() if v > cooldown_cutoff
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


# --- Input Validation ---

class InputValidator:
    """
    Input validation utilities to prevent injections and malicious input.
    """
    
    # Patterns for potentially dangerous input
    DANGEROUS_PATTERNS = [
        r"<script.*?>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript protocol
        r"on\w+\s*=",  # Event handlers
        r"eval\s*\(",  # Eval calls
        r"exec\s*\(",  # Exec calls
        r"__import__",  # Python imports
        r";\s*drop\s+",  # SQL DROP statements
        r";\s*delete\s+",  # SQL DELETE statements
        r";\s*update\s+",  # SQL UPDATE statements
        r";\s*insert\s+",  # SQL INSERT statements
        r"union\s+select",  # SQL UNION injection
        r"'--",  # SQL comment injection
        r"'\s*or\s*'",  # SQL OR injection
    ]
    
    # Maximum lengths for different input types
    MAX_LENGTHS = {
        "username": 100,
        "reason": 500,
        "message": 2000,
        "url": 2000,
        "command_input": 500,
        "search_query": 200,
        "default": 1000,
    }
    
    @classmethod
    def validate_string(
        cls,
        value: str,
        input_type: str = "default",
        allow_empty: bool = False,
        strip: bool = True,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a string input.
        
        Args:
            value: The string to validate
            input_type: Type of input for length limits
            allow_empty: Whether empty strings are allowed
            strip: Whether to strip whitespace
            
        Returns:
            Tuple of (is_valid, cleaned_value, error_message)
        """
        if strip:
            value = value.strip()
        
        # Check empty
        if not allow_empty and not value:
            return False, value, "La valeur ne peut pas être vide"
        
        # Check length
        max_length = cls.MAX_LENGTHS.get(input_type, cls.MAX_LENGTHS["default"])
        if len(value) > max_length:
            return False, value, f"La valeur dépasse la limite de {max_length} caractères"
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Dangerous input detected: {pattern} in {value[:50]}...")
                return False, value, "Entrée potentiellement dangereuse détectée"
        
        return True, value, None
    
    @classmethod
    def validate_integer(
        cls,
        value: Any,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Validate an integer input.
        
        Args:
            value: The value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            
        Returns:
            Tuple of (is_valid, parsed_value, error_message)
        """
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return False, None, "La valeur doit être un nombre entier"
        
        if min_value is not None and int_value < min_value:
            return False, int_value, f"La valeur doit être au moins {min_value}"
        
        if max_value is not None and int_value > max_value:
            return False, int_value, f"La valeur doit être au plus {max_value}"
        
        return True, int_value, None
    
    @classmethod
    def validate_discord_id(cls, value: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Validate a Discord ID (snowflake).
        
        Args:
            value: The ID string to validate
            
        Returns:
            Tuple of (is_valid, parsed_id, error_message)
        """
        # Discord IDs are 17-20 digit numbers
        if not re.match(r"^\d{17,20}$", str(value)):
            return False, None, "ID Discord invalide"
        
        try:
            id_int = int(value)
            return True, id_int, None
        except ValueError:
            return False, None, "ID Discord invalide"
    
    @classmethod
    def validate_url(cls, value: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a URL.
        
        Args:
            value: The URL string to validate
            
        Returns:
            Tuple of (is_valid, cleaned_url, error_message)
        """
        value = value.strip()
        
        # Check length
        if len(value) > cls.MAX_LENGTHS["url"]:
            return False, value, "URL trop longue"
        
        # Basic URL pattern
        url_pattern = r"^https?://[^\s<>\"{}|\\^`\[\]]+$"
        if not re.match(url_pattern, value):
            return False, value, "URL invalide"
        
        # Check for dangerous patterns
        dangerous_url_patterns = [
            r"javascript:",
            r"data:",
            r"vbscript:",
        ]
        for pattern in dangerous_url_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False, value, "URL potentiellement dangereuse"
        
        return True, value, None
    
    @classmethod
    def sanitize_for_sql(cls, value: str) -> str:
        """
        Sanitize a string for use in SQL queries.
        
        Note: Always use parameterized queries instead of this when possible.
        This is a last-resort sanitization.
        
        Args:
            value: The string to sanitize
            
        Returns:
            Sanitized string
        """
        # Remove or escape dangerous characters
        sanitized = value.replace("'", "''")  # Escape single quotes
        sanitized = sanitized.replace("\\", "\\\\")  # Escape backslashes
        sanitized = sanitized.replace("\x00", "")  # Remove null bytes
        
        return sanitized
    
    @classmethod
    def sanitize_for_display(cls, value: str) -> str:
        """
        Sanitize a string for safe display in Discord.
        
        Args:
            value: The string to sanitize
            
        Returns:
            Sanitized string
        """
        # Escape Discord formatting
        escape_chars = ["*", "_", "`", "~", "|", ">"]
        for char in escape_chars:
            value = value.replace(char, f"\\{char}")
        
        # Remove zero-width characters
        zero_width = ["\u200b", "\u200c", "\u200d", "\ufeff"]
        for char in zero_width:
            value = value.replace(char, "")
        
        return value


# --- Rate Limit Check Decorator ---

def check_rate_limit(command_cooldown: Optional[int] = None):
    """
    Decorator to check rate limits before executing a command.
    
    Args:
        command_cooldown: Optional custom cooldown for this command
    """
    def decorator(func: Callable) -> Callable:
        # Set custom cooldown if provided
        if command_cooldown is not None:
            rate_limiter.set_command_cooldown(func.__name__, command_cooldown)
        
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id) if interaction.guild else None
            command_name = interaction.command.name if interaction.command else func.__name__
            
            # Check all limits
            is_limited, retry_after, reason = rate_limiter.check_all_limits(
                user_id, guild_id, command_name
            )
            
            if is_limited:
                # Format the cooldown time inline to avoid circular imports
                def format_time(seconds: float) -> str:
                    if seconds < 60:
                        return f"{int(seconds)} seconde{'s' if seconds >= 2 else ''}"
                    elif seconds < 3600:
                        minutes = int(seconds / 60)
                        return f"{minutes} minute{'s' if minutes >= 2 else ''}"
                    else:
                        hours = int(seconds / 3600)
                        return f"{hours} heure{'s' if hours >= 2 else ''}"
                
                if reason == "cooldown":
                    message = (
                        "⏳ **Cooldown actif**\n"
                        f"Veuillez patienter {format_time(retry_after)} avant de réutiliser cette commande."
                    )
                else:
                    message = (
                        "🚫 **Limite de requêtes atteinte**\n"
                        f"Vous avez fait trop de requêtes. Veuillez patienter {format_time(retry_after)}."
                    )
                
                embed = discord.Embed(
                    title="⏳ Limite atteinte",
                    description=message,
                    color=discord.Color.orange()
                )
                
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            return await func(self, interaction, *args, **kwargs)
        
        return wrapper
    return decorator
