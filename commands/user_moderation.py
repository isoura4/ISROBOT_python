"""
User moderation commands for ISROBOT.
Allows users to appeal warnings.
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


class UserModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="appeal", description=tr("cmd.appeal.desc"))
    @app_commands.describe(reason=tr("cmd.appeal.reason"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def appeal(self, interaction: discord.Interaction, reason: str):
        """Submit an appeal against warnings."""
        locale = get_locale(interaction)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)

            # Check if user has warnings
            warn_count = moderation_utils.get_warning_count(guild_id, user_id)
            if warn_count <= 0:
                await interaction.followup.send(
                    t("appeal.no_warns", locale), ephemeral=True
                )
                return

            # Check appeal length
            if len(reason) > 1000:
                await interaction.followup.send(
                    t("appeal.too_long", locale),
                    ephemeral=True,
                )
                return

            # Check cooldown (48 hours) - database-backed
            remaining_cooldown = moderation_utils.check_appeal_cooldown(
                guild_id, user_id
            )
            if remaining_cooldown:
                hours = int(remaining_cooldown.total_seconds() // 3600)
                minutes = int((remaining_cooldown.total_seconds() % 3600) // 60)
                await interaction.followup.send(
                    t("appeal.cooldown", locale, hours=hours, minutes=minutes),
                    ephemeral=True,
                )
                return

            # Create appeal
            appeal_id = moderation_utils.create_appeal(guild_id, user_id, reason)

            if appeal_id is None:
                await interaction.followup.send(
                    t("appeal.pending", locale), ephemeral=True
                )
                return

            # Send confirmation to user
            embed = discord.Embed(
                title=t("appeal.submitted_title", locale),
                description=t("appeal.submitted_desc", locale),
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name=t("mod.field.reason", locale), value=reason, inline=False
            )
            embed.add_field(
                name=t("appeal.next_steps", locale),
                value=t("appeal.next_steps_value", locale),
                inline=False,
            )
            embed.set_footer(text=t("mod.footer", locale))

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Post to appeal channel
            config = moderation_utils.get_moderation_config(guild_id)
            if config and config.get("appeal_channel_id"):
                await self._post_appeal_to_channel(
                    interaction.guild,
                    config["appeal_channel_id"],
                    appeal_id,
                    interaction.user,
                    warn_count,
                    reason,
                    locale,
                )

        except Exception as e:
            logger.error(f"Error in appeal command: {e}")
            await interaction.followup.send(
                t("appeal.error", locale),
                ephemeral=True,
            )

    async def _post_appeal_to_channel(
        self,
        guild: discord.Guild,
        channel_id: str,
        appeal_id: int,
        user: discord.Member,
        warn_count: int,
        reason: str,
        locale: str = None,
    ):
        """Post an appeal to the appeal review channel."""
        try:
            channel = guild.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning(f"Appeal channel {channel_id} not found")
                return

            embed = discord.Embed(
                title=t("appeal.new_title", locale, id=appeal_id),
                description=t(
                    "appeal.new_desc", locale, user=f"{user.mention} ({user.id})"
                ),
                color=discord.Color.purple(),
                timestamp=datetime.now(timezone.utc),
            )

            embed.add_field(
                name=t("appeal.current_warns", locale),
                value=str(warn_count),
                inline=True,
            )

            embed.add_field(
                name=t("appeal.reason_of_appeal", locale), value=reason, inline=False
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
                    name=t("appeal.recent_history", locale),
                    value="\n".join(recent_history),
                    inline=False,
                )

            embed.set_footer(text=t("appeal.review_footer", locale))

            # Create view with buttons
            view = AppealReviewView(appeal_id, user.id, self.bot, locale)
            await channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error posting appeal to channel: {e}")


class AppealReviewView(discord.ui.View):
    """View with buttons to review an appeal."""

    def __init__(
        self,
        appeal_id: int,
        user_id: int,
        bot: commands.Bot,
        locale: str = None,
    ):
        super().__init__(timeout=None)
        self.appeal_id = appeal_id
        self.user_id = user_id
        self.bot = bot
        self.locale = locale
        # Localiser les libellés des boutons de cette instance
        for item in self.children:
            if getattr(item, "custom_id", None) == "appeal_approve":
                item.label = t("appeal.btn_approve", locale)
            elif getattr(item, "custom_id", None) == "appeal_deny":
                item.label = t("appeal.btn_deny", locale)

    @discord.ui.button(
        label="✅ Approuver",
        style=discord.ButtonStyle.success,
        custom_id="appeal_approve",
    )
    async def approve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Approve the appeal."""
        await self._handle_appeal_decision(
            interaction,
            "approved",
            t("appeal.decision_approved_reason", self.locale),
        )

    @discord.ui.button(
        label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="appeal_deny"
    )
    async def deny_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Deny the appeal."""
        # Show modal for reason
        modal = AppealDecisionModal(
            self.appeal_id, self.user_id, "denied", self.bot, self.locale
        )
        await interaction.response.send_modal(modal)

    async def _handle_appeal_decision(
        self, interaction: discord.Interaction, decision: str, moderator_decision: str
    ):
        """Handle the appeal decision."""
        locale = self.locale
        await interaction.response.defer(ephemeral=True)

        try:
            # Check permissions
            if not interaction.user.guild_permissions.moderate_members:
                await interaction.followup.send(
                    t("appeal.no_perm", locale),
                    ephemeral=True,
                )
                return

            # Review appeal
            success = moderation_utils.review_appeal(
                self.appeal_id, str(interaction.user.id), decision, moderator_decision
            )

            if not success:
                await interaction.followup.send(
                    t("appeal.not_found", locale), ephemeral=True
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
                    t("appeal.decision_approved_db", locale),
                )

                # If warnings reach 0, remove the automatic mute (if any).
                # Manual mutes are left untouched.
                if new_count == 0:
                    active_mute = moderation_utils.get_active_mute(guild_id, user_id)
                    member = interaction.guild.get_member(int(user_id))
                    if member and active_mute and active_mute.get("is_auto"):
                        try:
                            await member.timeout(
                                None, reason=t("appeal.timeout_reason", locale)
                            )
                            moderation_utils.remove_mute(
                                guild_id,
                                user_id,
                                str(interaction.user.id),
                                t("appeal.decision_approved_db", locale),
                            )
                        except Exception as e:
                            logger.error(f"Error removing timeout: {e}")

            # Send DM to user
            member = interaction.guild.get_member(int(user_id))
            if member:
                title_key = (
                    "appeal.approved_title"
                    if decision == "approved"
                    else "appeal.denied_title"
                )
                embed = discord.Embed(
                    title=t(title_key, locale),
                    description=t(
                        "appeal.reviewed_desc", locale, guild=interaction.guild.name
                    ),
                    color=(
                        discord.Color.green()
                        if decision == "approved"
                        else discord.Color.red()
                    ),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(
                    name=t("appeal.mod_decision", locale),
                    value=moderator_decision,
                    inline=False,
                )

                if decision == "approved":
                    new_count = moderation_utils.get_warning_count(guild_id, user_id)
                    embed.add_field(
                        name=t("appeal.new_warns", locale),
                        value=str(new_count),
                        inline=True,
                    )
                    embed.add_field(
                        name=t("mod.field.reason", locale),
                        value=t("appeal.removed_msg", locale),
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name=t("appeal.next_steps", locale),
                        value=t("appeal.deny_next_steps", locale),
                        inline=False,
                    )

                embed.set_footer(text=t("mod.footer", locale))
                await moderation_utils.send_dm_notification(member, embed)

            # Update the message
            for item in self.children:
                item.disabled = True

            original_embed = interaction.message.embeds[0]
            original_embed.color = (
                discord.Color.green() if decision == "approved" else discord.Color.red()
            )
            decision_key = (
                "appeal.approved_by" if decision == "approved" else "appeal.denied_by"
            )
            original_embed.add_field(
                name=t("appeal.decision_field", locale),
                value=t(decision_key, locale, user=interaction.user.mention),
                inline=False,
            )

            await interaction.message.edit(embed=original_embed, view=self)

            result_key = (
                "appeal.result_approved"
                if decision == "approved"
                else "appeal.result_denied"
            )
            await interaction.followup.send(
                t("appeal.result", locale, status=t(result_key, locale)),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error handling appeal decision: {e}")
            await interaction.followup.send(
                t("appeal.error_generic", locale), ephemeral=True
            )


class AppealDecisionModal(discord.ui.Modal):
    """Modal to get reason for denying an appeal."""

    def __init__(
        self,
        appeal_id: int,
        user_id: int,
        decision: str,
        bot: commands.Bot,
        locale: str = None,
    ):
        super().__init__(title=t("appeal.deny_modal.title", locale))
        self.appeal_id = appeal_id
        self.user_id = user_id
        self.decision = decision
        self.bot = bot
        self.locale = locale

        self.decision_reason = discord.ui.TextInput(
            label=t("appeal.deny_modal.label", locale),
            style=discord.TextStyle.paragraph,
            placeholder=t("appeal.deny_modal.placeholder", locale),
            required=True,
            max_length=500,
        )
        self.add_item(self.decision_reason)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        moderator_decision = self.decision_reason.value

        # Find the view and call the handler
        view = AppealReviewView(self.appeal_id, self.user_id, self.bot, self.locale)
        await view._handle_appeal_decision(
            interaction, self.decision, moderator_decision
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(UserModeration(bot))
