"""
Moderation configuration commands for ISROBOT.
Allows administrators to configure the moderation system.
"""

import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import moderation_utils
from utils.i18n import get_locale, t, tr

load_dotenv()

logger = logging.getLogger(__name__)
SERVER_ID = int(os.getenv("server_id", "0"))


class ModerationConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    modconfig = app_commands.Group(
        name="modconfig",
        description=tr("cmd.modconfig.desc"),
        guild_ids=[SERVER_ID],
    )

    @modconfig.command(name="view", description=tr("cmd.modconfig.view.desc"))
    @app_commands.checks.has_permissions(administrator=True)
    async def view_config(self, interaction: discord.Interaction):
        """View current moderation configuration."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            config = moderation_utils.get_moderation_config(guild_id)

            embed = discord.Embed(
                title=t("modconfig.title", locale),
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )

            if not config:
                embed.description = t("modconfig.empty", locale)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Channels
            log_channel = (
                f"<#{config['log_channel_id']}>"
                if config.get("log_channel_id")
                else t("modconfig.not_set", locale)
            )
            appeal_channel = (
                f"<#{config['appeal_channel_id']}>"
                if config.get("appeal_channel_id")
                else t("modconfig.not_set", locale)
            )
            ai_flag_channel = (
                f"<#{config['ai_flag_channel_id']}>"
                if config.get("ai_flag_channel_id")
                else t("modconfig.not_set", locale)
            )

            embed.add_field(
                name=t("modconfig.field_channels", locale),
                value=t(
                    "modconfig.channels_value",
                    locale,
                    log=log_channel,
                    appeal=appeal_channel,
                    flag=ai_flag_channel,
                ),
                inline=False,
            )

            # AI settings
            ai_enabled = (
                t("modconfig.ai_on", locale)
                if config.get("ai_enabled", 1)
                else t("modconfig.ai_off", locale)
            )
            embed.add_field(
                name=t("modconfig.field_ai", locale),
                value=t(
                    "modconfig.ai_value",
                    locale,
                    status=ai_enabled,
                    threshold=config.get("ai_confidence_threshold", 60),
                    model=config.get("ai_model", "llama2"),
                    host=config.get("ollama_host", "http://localhost:11434"),
                ),
                inline=False,
            )

            # Warning decay settings
            embed.add_field(
                name=t("modconfig.field_decay", locale),
                value=t(
                    "modconfig.decay_value",
                    locale,
                    d1=config.get("warn_1_decay_days", 7),
                    d2=config.get("warn_2_decay_days", 14),
                    d3=config.get("warn_3_decay_days", 21),
                ),
                inline=False,
            )

            # Mute durations
            mute_2 = config.get("mute_duration_warn_2", 3600)
            mute_3 = config.get("mute_duration_warn_3", 86400)
            embed.add_field(
                name=t("modconfig.field_mute", locale),
                value=t(
                    "modconfig.mute_value",
                    locale,
                    m2=moderation_utils.format_duration(mute_2, locale),
                    m3=moderation_utils.format_duration(mute_3, locale),
                ),
                inline=False,
            )

            # Rules message
            rules_msg = config.get("rules_message_id", t("modconfig.not_set", locale))
            embed.add_field(
                name=t("modconfig.field_rules", locale),
                value=t("modconfig.rules_value", locale, id=rules_msg),
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in view_config command: {e}")
            await interaction.followup.send(
                t("modconfig.error", locale),
                ephemeral=True,
            )

    @modconfig.command(name="set", description=tr("cmd.modconfig.set.desc"))
    @app_commands.describe(
        parameter=tr("cmd.modconfig.set.param"), value=tr("cmd.modconfig.set.value")
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_config(
        self, interaction: discord.Interaction, parameter: str, value: str
    ):
        """Set a moderation configuration parameter."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild.id)

        # Valid parameters and their validation
        valid_params = {
            "log_channel": self._validate_channel,
            "appeal_channel": self._validate_channel,
            "ai_flag_channel": self._validate_channel,
            "ai_enabled": self._validate_boolean,
            "ai_confidence_threshold": self._validate_threshold,
            "ai_model": self._validate_string,
            "ollama_host": self._validate_url,
            "rules_message_id": self._validate_string,
            "warn_1_decay_days": self._validate_positive_int,
            "warn_2_decay_days": self._validate_positive_int,
            "warn_3_decay_days": self._validate_positive_int,
            "mute_duration_warn_2": self._validate_positive_int,
            "mute_duration_warn_3": self._validate_positive_int,
        }

        # Map user-friendly names to database columns
        param_map = {
            "log_channel": "log_channel_id",
            "appeal_channel": "appeal_channel_id",
            "ai_flag_channel": "ai_flag_channel_id",
            "ai_enabled": "ai_enabled",
            "ai_confidence_threshold": "ai_confidence_threshold",
            "ai_model": "ai_model",
            "ollama_host": "ollama_host",
            "rules_message_id": "rules_message_id",
            "warn_1_decay_days": "warn_1_decay_days",
            "warn_2_decay_days": "warn_2_decay_days",
            "warn_3_decay_days": "warn_3_decay_days",
            "mute_duration_2": "mute_duration_warn_2",
            "mute_duration_3": "mute_duration_warn_3",
        }

        if parameter not in valid_params:
            await interaction.followup.send(
                t("modconfig.invalid_param", locale, param=parameter),
                ephemeral=True,
            )
            return

        try:
            # Validate value
            validator = valid_params[parameter]
            validated_value = validator(value, interaction.guild)

            if validated_value is None:
                await interaction.followup.send(
                    t("modconfig.invalid_value", locale, param=parameter, value=value),
                    ephemeral=True,
                )
                return

            # Get database column name
            db_param = param_map.get(parameter, parameter)

            # Set configuration
            moderation_utils.set_moderation_config(
                guild_id, db_param, str(validated_value)
            )

            await interaction.followup.send(
                t("modconfig.updated", locale, param=parameter, value=validated_value),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error in set_config command: {e}")
            await interaction.followup.send(
                t("modconfig.set_error", locale, error=e),
                ephemeral=True,
            )

    # --- Validation Methods ---

    def _validate_channel(self, value: str, guild: discord.Guild) -> str:
        """Validate a channel ID or mention."""
        # Remove <#> if present
        channel_id = value.strip("<#>")
        try:
            channel = guild.get_channel(int(channel_id))
            if channel and isinstance(channel, discord.TextChannel):
                return channel_id
        except ValueError:
            logger.debug(f"Invalid channel ID provided: {value}")
        return None

    def _validate_boolean(self, value: str, guild: discord.Guild) -> int:
        """Validate a boolean value."""
        value = value.lower()
        if value in ["true", "1", "yes", "on", "activé"]:
            return 1
        elif value in ["false", "0", "no", "off", "désactivé"]:
            return 0
        return None

    def _validate_threshold(self, value: str, guild: discord.Guild) -> int:
        """Validate a threshold value (0-100)."""
        try:
            threshold = int(value)
            if 0 <= threshold <= 100:
                return threshold
        except ValueError:
            logger.debug(f"Invalid threshold value provided: {value}")
        return None

    def _validate_positive_int(self, value: str, guild: discord.Guild) -> int:
        """Validate a positive integer."""
        try:
            num = int(value)
            if num > 0:
                return num
        except ValueError:
            logger.debug(f"Invalid positive integer value provided: {value}")
        return None

    def _validate_string(self, value: str, guild: discord.Guild) -> str:
        """Validate a generic string."""
        return value if value else None

    def _validate_url(self, value: str, guild: discord.Guild) -> str:
        """Validate a URL."""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return None


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationConfig(bot))
