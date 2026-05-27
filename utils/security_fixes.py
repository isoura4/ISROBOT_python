"""
Security utilities for ISROBOT Discord Bot.
Provides input sanitization, escaping, and validation functions.
"""

import logging
import re
from typing import Optional

import discord

logger = logging.getLogger(__name__)


def escape_user_content(content: str, escape_mentions: bool = True) -> str:
    """
    Escape user-provided content to prevent Discord markdown injection.
    
    Args:
        content: The user content to escape
        escape_mentions: Whether to also escape @mentions and #channels
        
    Returns:
        Escaped content safe for Discord messages
    """
    if not content:
        return content
    
    # Escape Discord markdown characters
    content = discord.utils.escape_markdown(content)
    
    # Optionally escape mentions and channels
    if escape_mentions:
        # Escape @mentions pattern
        content = re.sub(r'@(\w+)', r'\\@\1', content)
        # Escape #channels pattern
        content = re.sub(r'#(\w+)', r'\\#\1', content)
    
    return content


def sanitize_api_error(error_message: str) -> str:
    """
    Remove sensitive information from API error messages.
    Prevents API keys from being exposed in logs or error responses.
    
    Args:
        error_message: The error message to sanitize
        
    Returns:
        Sanitized error message with credentials removed
    """
    # Remove common API key patterns
    patterns = [
        r'["\']?(?:key|token|api_key|access_token|secret)["\']?\s*[:=]\s*[^,\s}\]]+',
        r'Bearer\s+[^,\s\)]+',
        r'Authorization:\s*[^,\s\n]+',
        r'https?://[^:]+:[^@]+@',  # Basic auth in URLs
    ]
    
    sanitized = error_message
    for pattern in patterns:
        sanitized = re.sub(
            pattern,
            '[REDACTED]',
            sanitized,
            flags=re.IGNORECASE
        )
    
    return sanitized


def validate_username(username: str, min_length: int = 1, max_length: int = 32) -> tuple[bool, str]:
    """
    Validate a Discord username.
    
    Args:
        username: Username to validate
        min_length: Minimum username length
        max_length: Maximum username length
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username or not isinstance(username, str):
        return False, "Username must be a non-empty string"
    
    username = username.strip()
    
    if len(username) < min_length:
        return False, f"Username must be at least {min_length} character(s)"
    
    if len(username) > max_length:
        return False, f"Username must be at most {max_length} character(s)"
    
    # Check for invalid characters (only alphanumeric, spaces, underscores, hyphens allowed)
    if not re.match(r'^[\w\s\-]+$', username):
        return False, "Username contains invalid characters. Only letters, numbers, spaces, underscores, and hyphens are allowed"
    
    return True, ""


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate a URL for basic correctness.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    url = url.strip()
    
    # Basic URL validation regex
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return False, "Invalid URL format"
    
    # Check URL length
    if len(url) > 2048:
        return False, "URL is too long (max 2048 characters)"
    
    return True, ""


def create_audit_log_message(
    action: str,
    actor: discord.User,
    target: Optional[discord.User] = None,
    reason: Optional[str] = None,
    details: Optional[dict] = None
) -> str:
    """
    Create a formatted audit log message.
    
    Args:
        action: Action performed (e.g., "WARN", "MUTE", "KICK")
        actor: User who performed the action
        target: User who was targeted (if applicable)
        reason: Reason for the action
        details: Additional details dictionary
        
    Returns:
        Formatted audit log message
    """
    timestamp = discord.utils.utcnow().isoformat()
    
    log_parts = [
        f"[{timestamp}]",
        f"ACTION: {action}",
        f"ACTOR: {actor} (ID: {actor.id})",
    ]
    
    if target:
        log_parts.append(f"TARGET: {target} (ID: {target.id})")
    
    if reason:
        log_parts.append(f"REASON: {escape_user_content(reason)}")
    
    if details:
        details_str = ", ".join(f"{k}={v}" for k, v in details.items())
        log_parts.append(f"DETAILS: {details_str}")
    
    return " | ".join(log_parts)


def is_user_input_safe(content: str) -> tuple[bool, Optional[str]]:
    """
    Check if user input is safe (no obvious injection attempts).
    
    Args:
        content: User input to check
        
    Returns:
        Tuple of (is_safe, risk_reason)
    """
    if not content or not isinstance(content, str):
        return True, None
    
    # Check for code injection attempts
    dangerous_patterns = [
        r'`{3,}',  # Code blocks
        r'__.*__',  # Spoilers
        r'\|\|.*\|\|',  # Hidden content
        r'@everyone|@here',  # Mass mentions
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, content):
            return False, f"Potential injection attempt detected: {pattern}"
    
    return True, None
