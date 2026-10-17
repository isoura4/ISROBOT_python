"""
Moderation commands for ISROBOT.
Provides warning, muting, and configuration management.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import moderation_utils
from utils.i18n import get_locale, t, tr
from utils.security_fixes import create_audit_log_message, escape_user_content

load_dotenv()

logger = logging.getLogger(__name__)
SERVER_ID = int(os.getenv("server_id", "0"))


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Warning Commands ---

    @app_commands.command(name="warn", description=tr("cmd.warn.desc"))
    @app_commands.describe(user=tr("cmd.warn.user"), reason=tr("cmd.warn.reason"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(
        self, interaction: discord.Interaction, user: discord.Member, reason: str
    ):
        """Issue a warning to a user."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        if user.bot:
            await interaction.followup.send(t("mod.ctx.bot", locale), ephemeral=True)
            return

        if user.id == interaction.user.id:
            await interaction.followup.send(t("mod.ctx.self", locale), ephemeral=True)
            return

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            moderator_id = str(interaction.user.id)

            # Create audit log entry
            audit_msg = create_audit_log_message(
                action="WARN",
                actor=interaction.user,
                target=user,
                reason=reason,
                details={"guild": interaction.guild.name},
            )
            logger.info(audit_msg)

            # Increment warning (store the raw reason; escaping happens at display)
            new_count = moderation_utils.increment_warning(
                guild_id, user_id, moderator_id, reason
            )

            # Get config
            config = moderation_utils.get_moderation_config(guild_id)

            # Send DM to user
            rules_link = None
            if config and config.get("rules_message_id"):
                # We could construct a link, but for now we'll skip it
                logger.debug(
                    "Rules message ID configured but link construction not implemented"
                )

            dm_embed = moderation_utils.create_warning_embed(
                reason, new_count, interaction.guild.name, rules_link, locale=locale
            )
            dm_sent = await moderation_utils.send_dm_notification(user, dm_embed)

            # Apply automatic actions based on warning count
            action_taken = ""
            if new_count == 2:
                # Apply 1-hour mute
                duration = config.get("mute_duration_warn_2", 3600) if config else 3600
                await self._apply_mute(
                    interaction.guild,
                    user,
                    moderator_id,
                    t("mod.ctx.auto_mute_reason_2", locale),
                    duration,
                    is_auto=True,
                )
                action_taken = t(
                    "warn.action_auto_mute",
                    locale,
                    duration=moderation_utils.format_duration(duration, locale),
                )

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    t("mod.ctx.auto_mute_reason_2", locale),
                    duration,
                    interaction.guild.name,
                    locale=locale,
                )
                await moderation_utils.send_dm_notification(user, mute_embed)

            elif new_count == 3:
                # Apply 24-hour mute
                duration = (
                    config.get("mute_duration_warn_3", 86400) if config else 86400
                )
                await self._apply_mute(
                    interaction.guild,
                    user,
                    moderator_id,
                    t("mod.ctx.auto_mute_reason_3", locale),
                    duration,
                    is_auto=True,
                )
                action_taken = t(
                    "warn.action_auto_mute",
                    locale,
                    duration=moderation_utils.format_duration(duration, locale),
                )

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    t("mod.ctx.auto_mute_reason_3", locale),
                    duration,
                    interaction.guild.name,
                    locale=locale,
                )
                await moderation_utils.send_dm_notification(user, mute_embed)

            elif new_count >= 4:
                action_taken = t("warn.action_warn4", locale)

            # Post to moderation log
            if config and config.get("log_channel_id"):
                await self._post_to_modlog(
                    interaction.guild,
                    config["log_channel_id"],
                    "warn",
                    user,
                    interaction.user,
                    locale=locale,
                    reason=reason,
                    warn_count=new_count,
                )

            # Send response
            dm_status = (
                t("mod.ctx.dm_sent", locale)
                if dm_sent
                else t("warn.dm_not_sent", locale)
            )
            await interaction.followup.send(
                t(
                    "mod.ctx.warn_issued",
                    locale,
                    user=user.mention,
                    reason=reason,
                    count=new_count,
                    dm=dm_status,
                    action=action_taken,
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error in warn command: {e}")
            await interaction.followup.send(
                t("warn.error", locale),
                ephemeral=True,
            )

    @app_commands.command(
        name="warns",
        description=tr("cmd.warns.desc"),
    )
    @app_commands.describe(user=tr("cmd.warns.user"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warns(self, interaction: discord.Interaction, user: discord.Member):
        """Show warning history for a user."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)

            # Get current warning count
            warn_count = moderation_utils.get_warning_count(guild_id, user_id)

            # Get history
            history = moderation_utils.get_warning_history(guild_id, user_id)

            embed = discord.Embed(
                title=t("warns.title", locale, user=user.display_name),
                description=t("warns.current", locale, count=warn_count),
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )

            if history:
                history_text = []
                for entry in history[:10]:  # Show last 10 entries
                    action = entry["action"]
                    created_at = datetime.fromisoformat(entry["created_at"])
                    reason = (
                        escape_user_content(entry["reason"])
                        if entry["reason"]
                        else t("mod.no_reason", locale)
                    )

                    action_emoji = {
                        "warn_issued": "⚠️",
                        "warn_decreased": "✅",
                        "mute_applied": "🔇",
                        "mute_removed": "🔊",
                        "appeal_created": "📝",
                        "appeal_reviewed": "⚖️",
                    }.get(action, "📌")

                    history_text.append(
                        f"{action_emoji} **{action.replace('_', ' ').title()}** "
                        f"<t:{int(created_at.timestamp())}:R>\n"
                        f"└─ {reason}"
                    )

                embed.add_field(
                    name=t("appeal.recent_history", locale),
                    value="\n\n".join(history_text),
                    inline=False,
                )
            else:
                embed.add_field(
                    name=t("warns.history_field", locale),
                    value=t("warns.no_history", locale),
                    inline=False,
                )

            # Calculate next decay if applicable
            if warn_count > 0:
                config = moderation_utils.get_moderation_config(guild_id)
                decay_days = moderation_utils.calculate_decay_days(warn_count, config)
                embed.add_field(
                    name=t("warns.next_decay", locale),
                    value=t("warns.next_decay_value", locale, days=decay_days),
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in warns command: {e}")
            await interaction.followup.send(
                t("warns.error", locale),
                ephemeral=True,
            )

    @app_commands.command(name="unwarn", description=tr("cmd.unwarn.desc"))
    @app_commands.describe(user=tr("cmd.unwarn.user"), reason=tr("cmd.unwarn.reason"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unwarn(
        self, interaction: discord.Interaction, user: discord.Member, reason: str = None
    ):
        """Remove a warning from a user."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            moderator_id = str(interaction.user.id)

            # Get current count
            current_count = moderation_utils.get_warning_count(guild_id, user_id)
            if current_count <= 0:
                await interaction.followup.send(
                    t("unwarn.none", locale, user=user.mention), ephemeral=True
                )
                return

            # Decrement warning
            new_count = moderation_utils.decrement_warning(
                guild_id,
                user_id,
                moderator_id,
                reason or t("unwarn.default_reason", locale),
            )

            # If warn count reaches 0, remove the automatic mute (if any).
            # Manual mutes are left untouched.
            if new_count == 0:
                active_mute = moderation_utils.get_active_mute(guild_id, user_id)
                if active_mute and active_mute.get("is_auto"):
                    await self._remove_mute(
                        interaction.guild,
                        user,
                        moderator_id,
                        t("unwarn.timeout_reason", locale),
                    )

            # Post to modlog
            config = moderation_utils.get_moderation_config(guild_id)
            if config and config.get("log_channel_id"):
                await self._post_to_modlog(
                    interaction.guild,
                    config["log_channel_id"],
                    "unwarn",
                    user,
                    interaction.user,
                    locale=locale,
                    reason=reason or t("unwarn.default_reason", locale),
                    warn_count=new_count,
                )

            await interaction.followup.send(
                t("unwarn.success", locale, user=user.mention, count=new_count),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error in unwarn command: {e}")
            await interaction.followup.send(
                t("unwarn.error", locale),
                ephemeral=True,
            )

    # --- Mute Commands ---

    @app_commands.command(name="mute", description=tr("cmd.mute.desc"))
    @app_commands.describe(
        user=tr("cmd.mute.user"),
        duration=tr("cmd.mute.duration"),
        reason=tr("cmd.mute.reason"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: str,
        reason: str,
    ):
        """Manually mute a user."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        if user.bot:
            await interaction.followup.send(t("mute.bot", locale), ephemeral=True)
            return

        try:
            # Parse duration
            duration_seconds = moderation_utils.parse_duration(duration)
            if not duration_seconds:
                await interaction.followup.send(
                    t("mute.bad_duration", locale),
                    ephemeral=True,
                )
                return

            guild_id = str(interaction.guild.id)
            moderator_id = str(interaction.user.id)

            # Apply mute
            await self._apply_mute(
                interaction.guild, user, moderator_id, reason, duration_seconds
            )

            # Send DM
            mute_embed = moderation_utils.create_mute_embed(
                reason, duration_seconds, interaction.guild.name, locale=locale
            )
            dm_sent = await moderation_utils.send_dm_notification(user, mute_embed)

            # Post to modlog
            config = moderation_utils.get_moderation_config(guild_id)
            if config and config.get("log_channel_id"):
                await self._post_to_modlog(
                    interaction.guild,
                    config["log_channel_id"],
                    "mute",
                    user,
                    interaction.user,
                    locale=locale,
                    reason=reason,
                    duration=moderation_utils.format_duration(duration_seconds, locale),
                )

            dm_status = (
                t("mod.ctx.dm_sent", locale)
                if dm_sent
                else t("mod.ctx.dm_not_sent", locale)
            )
            await interaction.followup.send(
                t(
                    "mute.success",
                    locale,
                    user=user.mention,
                    duration=moderation_utils.format_duration(duration_seconds, locale),
                    reason=reason,
                    dm=dm_status,
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error in mute command: {e}")
            await interaction.followup.send(
                t("mute.error", locale),
                ephemeral=True,
            )

    @app_commands.command(name="unmute", description=tr("cmd.unmute.desc"))
    @app_commands.describe(user=tr("cmd.unmute.user"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        """Manually unmute a user."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            moderator_id = str(interaction.user.id)

            # Check if user is muted
            active_mute = moderation_utils.get_active_mute(guild_id, user_id)
            if not active_mute:
                await interaction.followup.send(
                    t("unmute.not_muted", locale, user=user.mention), ephemeral=True
                )
                return

            # Remove mute
            await self._remove_mute(
                interaction.guild,
                user,
                moderator_id,
                t("unmute.reason", locale),
            )

            # Post to modlog
            config = moderation_utils.get_moderation_config(guild_id)
            if config and config.get("log_channel_id"):
                await self._post_to_modlog(
                    interaction.guild,
                    config["log_channel_id"],
                    "unmute",
                    user,
                    interaction.user,
                    locale=locale,
                    reason=t("unmute.reason", locale),
                )

            await interaction.followup.send(
                t("unmute.success", locale, user=user.mention), ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in unmute command: {e}")
            await interaction.followup.send(
                t("unmute.error", locale),
                ephemeral=True,
            )

    # --- Modlog Command ---

    @app_commands.command(name="modlog", description=tr("cmd.modlog.desc"))
    @app_commands.describe(user=tr("cmd.modlog.user"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def modlog(
        self, interaction: discord.Interaction, user: discord.Member = None
    ):
        """Show moderation log."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)

            if user:
                # Show logs for specific user
                user_id = str(user.id)
                history = moderation_utils.get_warning_history(guild_id, user_id)

                embed = discord.Embed(
                    title=t("modlog.title_user", locale, user=user.display_name),
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc),
                )

                if history:
                    log_entries = []
                    for entry in history[:15]:  # Show last 15 entries
                        action = entry["action"]
                        created_at = datetime.fromisoformat(entry["created_at"])
                        reason = (
                            escape_user_content(entry["reason"])
                            if entry["reason"]
                            else t("mod.no_reason", locale)
                        )

                        log_entries.append(
                            f"**{action.replace('_', ' ').title()}** "
                            f"<t:{int(created_at.timestamp())}:R>\n"
                            f"└─ {reason}"
                        )

                    embed.description = "\n\n".join(log_entries)
                else:
                    embed.description = t("modlog.no_entries", locale)

            else:
                # Show recent server-wide logs
                import database

                conn = database.get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT * FROM warning_history 
                        WHERE guild_id = ?
                        ORDER BY created_at DESC
                        LIMIT 20
                    """,
                        (guild_id,),
                    )
                    history = cursor.fetchall()
                finally:
                    conn.close()

                embed = discord.Embed(
                    title=t("modlog.title_server", locale),
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc),
                )

                if history:
                    log_entries = []
                    for entry in history:
                        action = entry["action"]
                        created_at = datetime.fromisoformat(entry["created_at"])
                        user_id = entry["user_id"]
                        reason = (
                            escape_user_content(entry["reason"])
                            if entry["reason"]
                            else t("mod.no_reason", locale)
                        )

                        log_entries.append(
                            f"<@{user_id}> - **{action.replace('_', ' ').title()}** "
                            f"<t:{int(created_at.timestamp())}:R>\n"
                            f"└─ {reason}"
                        )

                    embed.description = "\n\n".join(log_entries)
                else:
                    embed.description = t("modlog.no_entries", locale)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in modlog command: {e}")
            await interaction.followup.send(
                t("modlog.error", locale),
                ephemeral=True,
            )

    # --- Helper Methods ---

    async def _apply_mute(
        self,
        guild: discord.Guild,
        user: discord.Member,
        moderator_id: str,
        reason: str,
        duration_seconds: int,
        is_auto: bool = False,
    ):
        """Apply a mute to a user."""
        await moderation_utils.apply_mute(
            guild,
            user,
            moderator_id,
            reason,
            duration_seconds,
            is_auto=is_auto,
        )

    async def _remove_mute(
        self, guild: discord.Guild, user: discord.Member, moderator_id: str, reason: str
    ):
        """Remove a mute from a user."""
        # Remove Discord timeout
        await user.timeout(None, reason=reason)

        # Remove from database
        moderation_utils.remove_mute(str(guild.id), str(user.id), moderator_id, reason)

    async def _post_to_modlog(
        self,
        guild: discord.Guild,
        log_channel_id: str,
        action: str,
        user: discord.Member,
        moderator: discord.Member,
        locale: Optional[str] = None,
        **kwargs,
    ):
        """Post an action to the moderation log channel."""
        try:
            channel = guild.get_channel(int(log_channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            embed = moderation_utils.create_modlog_embed(
                action, user, moderator, locale=locale, **kwargs
            )
            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error posting to modlog: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
