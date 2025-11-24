"""
User moderation commands for ISROBOT.
Allows users to appeal warnings.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import moderation_utils

load_dotenv()

logger = logging.getLogger(__name__)
SERVER_ID = int(os.getenv("server_id", "0"))


class UserModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.appeal_cooldowns = {}  # Track appeal cooldowns

    @app_commands.command(
        name="appeal",
        description="Faire appel d'un avertissement"
    )
    @app_commands.describe(reason="Raison de votre appel (max 1000 caractères)")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def appeal(self, interaction: discord.Interaction, reason: str):
        """Submit an appeal against warnings."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)

            # Check if user has warnings
            warn_count = moderation_utils.get_warning_count(guild_id, user_id)
            if warn_count <= 0:
                await interaction.followup.send(
                    "❌ Vous n'avez aucun avertissement actif.",
                    ephemeral=True
                )
                return

            # Check appeal length
            if len(reason) > 1000:
                await interaction.followup.send(
                    "❌ Votre raison d'appel est trop longue (max 1000 caractères).",
                    ephemeral=True
                )
                return

            # Check cooldown (48 hours)
            cooldown_key = f"{guild_id}:{user_id}"
            if cooldown_key in self.appeal_cooldowns:
                last_appeal = self.appeal_cooldowns[cooldown_key]
                time_since = datetime.now(timezone.utc) - last_appeal
                if time_since < timedelta(hours=48):
                    remaining = timedelta(hours=48) - time_since
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    await interaction.followup.send(
                        f"⏳ Vous devez attendre encore {hours}h {minutes}m "
                        f"avant de soumettre un nouvel appel.",
                        ephemeral=True
                    )
                    return

            # Create appeal
            appeal_id = moderation_utils.create_appeal(guild_id, user_id, reason)

            if appeal_id is None:
                await interaction.followup.send(
                    "❌ Vous avez déjà un appel en attente.",
                    ephemeral=True
                )
                return

            # Update cooldown
            self.appeal_cooldowns[cooldown_key] = datetime.now(timezone.utc)

            # Send confirmation to user
            embed = discord.Embed(
                title="✅ Appel soumis",
                description="Votre appel a été soumis aux modérateurs.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Raison", value=reason, inline=False)
            embed.add_field(
                name="Prochaines étapes",
                value="Les modérateurs examineront votre appel. "
                      "Vous recevrez un message privé avec leur décision.",
                inline=False
            )
            embed.set_footer(text="Système de modération ISROBOT")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Post to appeal channel
            config = moderation_utils.get_moderation_config(guild_id)
            if config and config.get('appeal_channel_id'):
                await self._post_appeal_to_channel(
                    interaction.guild,
                    config['appeal_channel_id'],
                    appeal_id,
                    interaction.user,
                    warn_count,
                    reason
                )

        except Exception as e:
            logger.error(f"Error in appeal command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors de la soumission de votre appel.",
                ephemeral=True
            )

    async def _post_appeal_to_channel(
        self,
        guild: discord.Guild,
        channel_id: str,
        appeal_id: int,
        user: discord.Member,
        warn_count: int,
        reason: str
    ):
        """Post an appeal to the appeal review channel."""
        try:
            channel = guild.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning(f"Appeal channel {channel_id} not found")
                return

            embed = discord.Embed(
                title=f"📝 Nouvel appel - ID #{appeal_id}",
                description=f"**Utilisateur:** {user.mention} ({user.id})",
                color=discord.Color.purple(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Avertissements actuels",
                value=str(warn_count),
                inline=True
            )

            embed.add_field(
                name="Raison de l'appel",
                value=reason,
                inline=False
            )

            # Get user history
            history = moderation_utils.get_warning_history(str(guild.id), str(user.id))
            if history:
                recent_history = []
                for entry in history[:5]:
                    action = entry["action"]
                    created_at = datetime.fromisoformat(entry["created_at"])
                    recent_history.append(
                        f"• {action.replace('_', ' ').title()} "
                        f"<t:{int(created_at.timestamp())}:R>"
                    )
                embed.add_field(
                    name="Historique récent",
                    value="\n".join(recent_history),
                    inline=False
                )

            embed.set_footer(text="Utilisez les boutons ci-dessous pour examiner l'appel")

            # Create view with buttons
            view = AppealReviewView(appeal_id, user.id, self.bot)
            await channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error posting appeal to channel: {e}")


class AppealReviewView(discord.ui.View):
    """View with buttons to review an appeal."""

    def __init__(self, appeal_id: int, user_id: int, bot: commands.Bot):
        super().__init__(timeout=None)
        self.appeal_id = appeal_id
        self.user_id = user_id
        self.bot = bot

    @discord.ui.button(
        label="✅ Approuver",
        style=discord.ButtonStyle.success,
        custom_id="appeal_approve"
    )
    async def approve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Approve the appeal."""
        await self._handle_appeal_decision(interaction, "approved", "Appel approuvé par le modérateur")

    @discord.ui.button(
        label="❌ Refuser",
        style=discord.ButtonStyle.danger,
        custom_id="appeal_deny"
    )
    async def deny_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Deny the appeal."""
        # Show modal for reason
        modal = AppealDecisionModal(self.appeal_id, self.user_id, "denied", self.bot)
        await interaction.response.send_modal(modal)

    async def _handle_appeal_decision(
        self, interaction: discord.Interaction, decision: str, moderator_decision: str
    ):
        """Handle the appeal decision."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Check permissions
            if not interaction.user.guild_permissions.moderate_members:
                await interaction.followup.send(
                    "❌ Vous n'avez pas la permission de gérer les appels.",
                    ephemeral=True
                )
                return

            # Review appeal
            success = moderation_utils.review_appeal(
                self.appeal_id,
                str(interaction.user.id),
                decision,
                moderator_decision
            )

            if not success:
                await interaction.followup.send(
                    "❌ Appel introuvable.",
                    ephemeral=True
                )
                return

            # If approved, remove one warning
            guild_id = str(interaction.guild.id)
            user_id = str(self.user_id)

            if decision == "approved":
                new_count = moderation_utils.decrement_warning(
                    guild_id,
                    user_id,
                    str(interaction.user.id),
                    "Appel approuvé"
                )

                # If warnings reach 0, remove mute
                if new_count == 0:
                    member = interaction.guild.get_member(int(user_id))
                    if member:
                        try:
                            await member.timeout(None, reason="Appel approuvé - avertissements = 0")
                            moderation_utils.remove_mute(
                                guild_id,
                                user_id,
                                str(interaction.user.id),
                                "Appel approuvé"
                            )
                        except Exception as e:
                            logger.error(f"Error removing timeout: {e}")

            # Send DM to user
            member = interaction.guild.get_member(int(user_id))
            if member:
                embed = discord.Embed(
                    title=f"{'✅ Appel approuvé' if decision == 'approved' else '❌ Appel refusé'}",
                    description=f"Votre appel sur **{interaction.guild.name}** a été examiné.",
                    color=discord.Color.green() if decision == "approved" else discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="Décision du modérateur",
                    value=moderator_decision,
                    inline=False
                )

                if decision == "approved":
                    new_count = moderation_utils.get_warning_count(guild_id, user_id)
                    embed.add_field(
                        name="Nouveaux avertissements",
                        value=str(new_count),
                        inline=True
                    )
                    embed.add_field(
                        name="Message",
                        value="Un avertissement a été retiré. Continuez à respecter les règles!",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Prochaines étapes",
                        value="Si vous n'êtes pas d'accord avec cette décision, "
                              "vous pouvez contacter un administrateur.",
                        inline=False
                    )

                embed.set_footer(text="Système de modération ISROBOT")
                await moderation_utils.send_dm_notification(member, embed)

            # Update the message
            for item in self.children:
                item.disabled = True

            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.green() if decision == "approved" else discord.Color.red()
            original_embed.add_field(
                name="Décision",
                value=f"{'✅ Approuvé' if decision == 'approved' else '❌ Refusé'} par {interaction.user.mention}",
                inline=False
            )

            await interaction.message.edit(embed=original_embed, view=self)

            await interaction.followup.send(
                f"✅ Appel {'approuvé' if decision == 'approved' else 'refusé'}.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error handling appeal decision: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite.",
                ephemeral=True
            )


class AppealDecisionModal(discord.ui.Modal, title="Refuser l'appel"):
    """Modal to get reason for denying an appeal."""

    decision_reason = discord.ui.TextInput(
        label="Raison du refus",
        style=discord.TextStyle.paragraph,
        placeholder="Expliquez pourquoi l'appel est refusé...",
        required=True,
        max_length=500
    )

    def __init__(self, appeal_id: int, user_id: int, decision: str, bot: commands.Bot):
        super().__init__()
        self.appeal_id = appeal_id
        self.user_id = user_id
        self.decision = decision
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        moderator_decision = self.decision_reason.value

        # Find the view and call the handler
        view = AppealReviewView(self.appeal_id, self.user_id, self.bot)
        await view._handle_appeal_decision(interaction, self.decision, moderator_decision)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserModeration(bot))
