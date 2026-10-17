"""
Context menu integration for moderation.
Allows moderators to warn users by right-clicking on messages.
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import moderation_utils
from utils.i18n import get_locale, t, tr

load_dotenv()

logger = logging.getLogger(__name__)
SERVER_ID = int(os.getenv("server_id", "0"))


class ModerationContextMenu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name="Warn User",
            callback=self.warn_user_context,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def warn_user_context(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """Context menu command to warn a user."""
        # Check permissions
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                t("mod.ctx.no_perm", get_locale(interaction)),
                ephemeral=True,
            )
            return

        # Can't warn bots
        if message.author.bot:
            await interaction.response.send_message(
                t("mod.ctx.bot", get_locale(interaction)), ephemeral=True
            )
            return

        # Can't warn yourself
        if message.author.id == interaction.user.id:
            await interaction.response.send_message(
                t("mod.ctx.self", get_locale(interaction)), ephemeral=True
            )
            return

        # Get current warning count
        guild_id = str(interaction.guild.id)
        user_id = str(message.author.id)
        current_warns = moderation_utils.get_warning_count(guild_id, user_id)

        # Show modal for warning details
        modal = WarnModal(message, current_warns, self.bot)
        await interaction.response.send_modal(modal)


class WarnModal(discord.ui.Modal):
    """Modal for warning a user with details."""

    def __init__(self, message: discord.Message, current_warns: int, bot: commands.Bot):
        locale = None  # We'll infer from interaction in on_submit? Or pass locale
        super().__init__(title=t("mod.modal.title"))
        self.message = message
        self.current_warns = current_warns
        self.bot = bot
        self.locale = locale

        plural = "s" if current_warns != 1 else ""
        self.title = t(
            "mod.modal.heading",
            user=message.author.display_name,
            count=current_warns,
            s=plural,
        )

        self.reason_input = discord.ui.TextInput(
            label=t("mod.modal.reason_label"),
            style=discord.TextStyle.short,
            placeholder=t("mod.modal.reason_placeholder"),
            required=True,
            max_length=100,
        )
        self.additional_notes = discord.ui.TextInput(
            label=t("mod.modal.notes_label"),
            style=discord.TextStyle.paragraph,
            placeholder=t("mod.modal.notes_placeholder"),
            required=False,
            max_length=500,
        )
        self.add_item(self.reason_input)
        self.add_item(self.additional_notes)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(ephemeral=True)

        try:
            reason = (self.reason_input.value or "").strip()
            notes = (self.additional_notes.value or "").strip()
            if notes:
                reason = f"{reason} — {notes}" if reason else notes
            if not reason:
                reason = t("mod.ctx.default_reason")

            locale = get_locale(interaction)
            guild_id = str(interaction.guild.id)
            user_id = str(self.message.author.id)
            moderator_id = str(interaction.user.id)

            # Increment warning
            new_count = moderation_utils.increment_warning(
                guild_id, user_id, moderator_id, reason
            )

            # Get config
            config = moderation_utils.get_moderation_config(guild_id)

            # Send DM to user
            dm_embed = moderation_utils.create_warning_embed(
                reason, new_count, interaction.guild.name, locale=locale
            )
            dm_sent = await moderation_utils.send_dm_notification(
                self.message.author, dm_embed
            )

            # Apply automatic actions based on warning count
            action_taken = ""
            if new_count == 2:
                # Apply 1-hour mute
                duration = config.get("mute_duration_warn_2", 3600) if config else 3600
                await self._apply_mute(
                    interaction.guild,
                    self.message.author,
                    moderator_id,
                    t("mod.ctx.auto_mute_reason_2"),
                    duration,
                    is_auto=True,
                )
                action_taken = t(
                    "mod.ctx.action_auto_mute",
                    duration=moderation_utils.format_duration(duration, locale),
                )

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    t("mod.ctx.auto_mute_reason_2"),
                    duration,
                    interaction.guild.name,
                    locale=locale,
                )
                await moderation_utils.send_dm_notification(
                    self.message.author, mute_embed
                )

            elif new_count == 3:
                # Apply 24-hour mute
                duration = (
                    config.get("mute_duration_warn_3", 86400) if config else 86400
                )
                await self._apply_mute(
                    interaction.guild,
                    self.message.author,
                    moderator_id,
                    t("mod.ctx.auto_mute_reason_3"),
                    duration,
                    is_auto=True,
                )
                action_taken = t(
                    "mod.ctx.action_auto_mute",
                    duration=moderation_utils.format_duration(duration, locale),
                )

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    t("mod.ctx.auto_mute_reason_3"),
                    duration,
                    interaction.guild.name,
                    locale=locale,
                )
                await moderation_utils.send_dm_notification(
                    self.message.author, mute_embed
                )

            elif new_count >= 4:
                action_taken = t("mod.ctx.action_warn4", locale)

            # Delete message if requested (we'll always delete for context menu)
            try:
                await self.message.delete()
                action_taken += t("mod.ctx.action_msg_deleted", locale)
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du message: {e}")
                action_taken += t("mod.ctx.action_msg_delete_failed", locale)

            # Post to modlog
            if config and config.get("log_channel_id"):
                channel = interaction.guild.get_channel(int(config["log_channel_id"]))
                if channel and isinstance(channel, discord.TextChannel):
                    log_embed = moderation_utils.create_modlog_embed(
                        "warn",
                        self.message.author,
                        interaction.user,
                        locale=locale,
                        reason=reason,
                        warn_count=new_count,
                        message_link=self.message.jump_url,
                    )
                    await channel.send(embed=log_embed)

            # Send response
            dm_status = (
                t("mod.ctx.dm_sent", locale)
                if dm_sent
                else t("mod.ctx.dm_not_sent", locale)
            )
            await interaction.followup.send(
                t(
                    "mod.ctx.warn_issued",
                    locale,
                    user=self.message.author.mention,
                    reason=reason,
                    count=new_count,
                    dm=dm_status,
                    action=action_taken,
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'avertissement via menu contextuel: {e}")
            await interaction.followup.send(
                t("mod.ctx.error", get_locale(interaction)), ephemeral=True
            )

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


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationContextMenu(bot))
