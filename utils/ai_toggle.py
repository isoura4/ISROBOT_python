"""
AI feature management for ISROBOT.

Provides centralized control for enabling/disabling all AI-related features
through environment variables.

Features controlled:
- /ai command (AI chat with Ollama)
- AI moderation (automatic message analysis)
- AI-powered content filtering
"""

import logging
import os
from functools import wraps
from typing import Callable, Optional

import discord
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _parse_bool_env(value: Optional[str], default: bool = True) -> bool:
    """
    Parse a boolean value from environment variable.
    
    Accepts: true, false, 1, 0, yes, no, on, off
    
    Args:
        value: The environment variable value
        default: Default value if parsing fails
        
    Returns:
        Boolean value
    """
    if value is None:
        return default
    
    value = value.lower().strip()
    
    if value in ("true", "1", "yes", "on", "enabled"):
        return True
    elif value in ("false", "0", "no", "off", "disabled"):
        return False
    else:
        logger.warning(f"Invalid boolean value '{value}', using default: {default}")
        return default


class AIFeatureManager:
    """
    Manages AI feature toggles from environment variables.
    
    Environment variables:
    - AI_ENABLED: Master toggle for all AI features (default: true)
    - AI_COMMAND_ENABLED: Toggle for /ai command (default: true)
    - AI_MODERATION_ENABLED: Toggle for AI message moderation (default: true)
    - AI_CONTENT_FILTER_ENABLED: Toggle for AI content filtering (default: true)
    """
    
    def __init__(self):
        self._load_config()
    
    def _load_config(self) -> None:
        """Load AI configuration from environment variables."""
        # Master toggle
        self._ai_enabled = _parse_bool_env(os.getenv("AI_ENABLED"), default=True)
        
        # Individual feature toggles
        self._ai_command_enabled = _parse_bool_env(
            os.getenv("AI_COMMAND_ENABLED"), default=True
        )
        self._ai_moderation_enabled = _parse_bool_env(
            os.getenv("AI_MODERATION_ENABLED"), default=True
        )
        self._ai_content_filter_enabled = _parse_bool_env(
            os.getenv("AI_CONTENT_FILTER_ENABLED"), default=True
        )
        
        # Log configuration
        logger.info(
            f"AI Feature Configuration: "
            f"Master={self._ai_enabled}, "
            f"Command={self._ai_command_enabled}, "
            f"Moderation={self._ai_moderation_enabled}, "
            f"ContentFilter={self._ai_content_filter_enabled}"
        )
    
    def reload_config(self) -> None:
        """Reload configuration from environment variables."""
        load_dotenv(override=True)
        self._load_config()
    
    @property
    def is_ai_enabled(self) -> bool:
        """Check if AI features are globally enabled."""
        return self._ai_enabled
    
    @property
    def is_ai_command_enabled(self) -> bool:
        """Check if the /ai command is enabled."""
        return self._ai_enabled and self._ai_command_enabled
    
    @property
    def is_ai_moderation_enabled(self) -> bool:
        """Check if AI moderation is enabled."""
        return self._ai_enabled and self._ai_moderation_enabled
    
    @property
    def is_ai_content_filter_enabled(self) -> bool:
        """Check if AI content filtering is enabled."""
        return self._ai_enabled and self._ai_content_filter_enabled
    
    def get_status(self) -> dict:
        """
        Get the current status of all AI features.
        
        Returns:
            Dictionary with feature status
        """
        return {
            "master_enabled": self._ai_enabled,
            "command_enabled": self.is_ai_command_enabled,
            "moderation_enabled": self.is_ai_moderation_enabled,
            "content_filter_enabled": self.is_ai_content_filter_enabled,
        }
    
    def get_disabled_message(self, feature: str = "ai") -> str:
        """
        Get a user-friendly message explaining that an AI feature is disabled.
        
        Args:
            feature: The feature that is disabled
            
        Returns:
            Formatted message string
        """
        messages = {
            "ai": (
                "🤖 **Fonctionnalités IA désactivées**\n\n"
                "Les fonctionnalités d'intelligence artificielle sont actuellement "
                "désactivées sur ce bot.\n\n"
                "Contactez un administrateur pour plus d'informations."
            ),
            "command": (
                "🤖 **Commande IA désactivée**\n\n"
                "La commande `/ai` est actuellement désactivée sur ce bot.\n\n"
                "Contactez un administrateur pour plus d'informations."
            ),
            "moderation": (
                "🤖 **Modération IA désactivée**\n\n"
                "La modération automatique par IA est actuellement désactivée."
            ),
            "content_filter": (
                "🤖 **Filtre de contenu IA désactivé**\n\n"
                "Le filtrage de contenu par IA est actuellement désactivé."
            ),
        }
        return messages.get(feature, messages["ai"])


# Global instance
ai_manager = AIFeatureManager()


def require_ai_enabled(feature: str = "ai"):
    """
    Decorator to require AI features to be enabled.
    
    Args:
        feature: The specific feature to check ("ai", "command", "moderation", "content_filter")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check feature availability
            feature_checks = {
                "ai": ai_manager.is_ai_enabled,
                "command": ai_manager.is_ai_command_enabled,
                "moderation": ai_manager.is_ai_moderation_enabled,
                "content_filter": ai_manager.is_ai_content_filter_enabled,
            }
            
            is_enabled = feature_checks.get(feature, ai_manager.is_ai_enabled)
            
            if not is_enabled:
                # Find interaction in args
                interaction = None
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break
                
                if interaction:
                    message = ai_manager.get_disabled_message(feature)
                    embed = discord.Embed(
                        title="Fonctionnalité désactivée",
                        description=message,
                        color=discord.Color.orange()
                    )
                    
                    if interaction.response.is_done():
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                
                return None
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_ai_enabled(feature: str = "ai") -> bool:
    """
    Simple function to check if an AI feature is enabled.
    
    Args:
        feature: The feature to check
        
    Returns:
        True if enabled, False otherwise
    """
    feature_checks = {
        "ai": ai_manager.is_ai_enabled,
        "command": ai_manager.is_ai_command_enabled,
        "moderation": ai_manager.is_ai_moderation_enabled,
        "content_filter": ai_manager.is_ai_content_filter_enabled,
    }
    
    return feature_checks.get(feature, ai_manager.is_ai_enabled)
