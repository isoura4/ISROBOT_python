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
                "❌ Vous n'avez pas la permission d'avertir des utilisateurs.",
                ephemeral=True
            )
            return

        # Can't warn bots
        if message.author.bot:
            await interaction.response.send_message(
                "❌ Vous ne pouvez pas avertir un bot.",
                ephemeral=True
            )
            return

        # Can't warn yourself
        if message.author.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Vous ne pouvez pas vous avertir vous-même.",
                ephemeral=True
            )
            return

        # Get current warning count
        guild_id = str(interaction.guild.id)
        user_id = str(message.author.id)
        current_warns = moderation_utils.get_warning_count(guild_id, user_id)

        # Show modal for warning details
        modal = WarnModal(message, current_warns, self.bot)
        await interaction.response.send_modal(modal)


class WarnModal(discord.ui.Modal, title="Avertir l'utilisateur"):
    """Modal for warning a user with details."""

    reason_select = discord.ui.Select(
        placeholder="Sélectionnez une raison...",
        options=[
            discord.SelectOption(label="Spam", value="Spam", emoji="📢"),
            discord.SelectOption(label="Toxicité", value="Toxicité", emoji="⚠️"),
            discord.SelectOption(label="Insultes", value="Insultes", emoji="🤬"),
            discord.SelectOption(label="NSFW", value="NSFW", emoji="🔞"),
            discord.SelectOption(label="Violation des règles", value="Violation des règles", emoji="📋"),
            discord.SelectOption(label="Autre", value="Autre", emoji="❓"),
        ]
    )

    additional_notes = discord.ui.TextInput(
        label="Notes additionnelles (optionnel)",
        style=discord.TextStyle.paragraph,
        placeholder="Ajoutez des détails supplémentaires...",
        required=False,
        max_length=500
    )

    def __init__(self, message: discord.Message, current_warns: int, bot: commands.Bot):
        super().__init__()
        self.message = message
        self.current_warns = current_warns
        self.bot = bot

        # Add description showing current warns
        self.title = f"Avertir {message.author.display_name} ({current_warns} avertissement{'s' if current_warns != 1 else ''})"

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Build reason from modal inputs
            # Note: Since we can't add Select to Modal directly, we'll use a simplified approach
            # Users will need to type the reason
            reason = self.additional_notes.value or "Avertissement via menu contextuel"

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
                reason, new_count, interaction.guild.name
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
                    interaction.guild, self.message.author, moderator_id,
                    "Mute automatique - 2 avertissements", duration
                )
                action_taken = f"\n🔇 **Mute automatique:** {moderation_utils.format_duration(duration)}"

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    "Mute automatique - 2 avertissements", duration, interaction.guild.name
                )
                await moderation_utils.send_dm_notification(self.message.author, mute_embed)

            elif new_count == 3:
                # Apply 24-hour mute
                duration = config.get("mute_duration_warn_3", 86400) if config else 86400
                await self._apply_mute(
                    interaction.guild, self.message.author, moderator_id,
                    "Mute automatique - 3 avertissements", duration
                )
                action_taken = f"\n🔇 **Mute automatique:** {moderation_utils.format_duration(duration)}"

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    "Mute automatique - 3 avertissements", duration, interaction.guild.name
                )
                await moderation_utils.send_dm_notification(self.message.author, mute_embed)

            elif new_count >= 4:
                action_taken = "\n⚠️ **Attention:** 4+ avertissements - action manuelle requise."

            # Delete message if requested (we'll always delete for context menu)
            try:
                await self.message.delete()
                action_taken += "\n🗑️ Message supprimé"
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du message: {e}")
                action_taken += "\n⚠️ Impossible de supprimer le message"

            # Post to modlog
            if config and config.get("log_channel_id"):
                channel = interaction.guild.get_channel(int(config["log_channel_id"]))
                if channel and isinstance(channel, discord.TextChannel):
                    log_embed = moderation_utils.create_modlog_embed(
                        "warn",
                        self.message.author,
                        interaction.user,
                        reason=reason,
                        warn_count=new_count,
                        message_link=self.message.jump_url
                    )
                    await channel.send(embed=log_embed)

            # Send response
            dm_status = "✅ DM envoyé" if dm_sent else "⚠️ DM non envoyé"
            await interaction.followup.send(
                f"✅ **Avertissement émis** à {self.message.author.mention}\n"
                f"**Raison:** {reason}\n"
                f"**Avertissements totaux:** {new_count}\n"
                f"{dm_status}{action_taken}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'avertissement via menu contextuel: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite.",
                ephemeral=True
            )

    async def _apply_mute(
        self, guild: discord.Guild, user: discord.Member,
        moderator_id: str, reason: str, duration_seconds: int
    ):
        """Apply a mute to a user."""
        from datetime import datetime, timedelta, timezone

        # Use Discord's timeout feature
        timeout_until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        await user.timeout(timeout_until, reason=reason)

        # Store in database
        moderation_utils.add_mute(
            str(guild.id), str(user.id), moderator_id, reason, duration_seconds
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationContextMenu(bot))
