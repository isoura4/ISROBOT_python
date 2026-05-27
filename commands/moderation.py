"""
Moderation commands for ISROBOT.
Provides warning, muting, and configuration management.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import moderation_utils
from utils.security_fixes import escape_user_content, create_audit_log_message

load_dotenv()

logger = logging.getLogger(__name__)
SERVER_ID = int(os.getenv("server_id", "0"))


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Warning Commands ---

    @app_commands.command(name="warn", description="Émettre un avertissement à un utilisateur")
    @app_commands.describe(
        user="L'utilisateur à avertir",
        reason="Raison de l'avertissement"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(
        self, interaction: discord.Interaction, user: discord.Member, reason: str
    ):
        """Issue a warning to a user."""
        await interaction.response.defer(ephemeral=True)

        if user.bot:
            await interaction.followup.send("❌ Vous ne pouvez pas avertir un bot.", ephemeral=True)
            return

        if user.id == interaction.user.id:
            await interaction.followup.send("❌ Vous ne pouvez pas vous avertir vous-même.", ephemeral=True)
            return

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            moderator_id = str(interaction.user.id)

            # Sanitize and escape user input
            escaped_reason = escape_user_content(reason)
            
            # Create audit log entry
            audit_msg = create_audit_log_message(
                action="WARN",
                actor=interaction.user,
                target=user,
                reason=reason,
                details={"guild": interaction.guild.name}
            )
            logger.info(audit_msg)

            # Increment warning
            new_count = moderation_utils.increment_warning(
                guild_id, user_id, moderator_id, escaped_reason
            )

            # Get config
            config = moderation_utils.get_moderation_config(guild_id)

            # Send DM to user
            rules_link = None
            if config and config.get("rules_message_id"):
                # We could construct a link, but for now we'll skip it
                logger.debug("Rules message ID configured but link construction not implemented")

            dm_embed = moderation_utils.create_warning_embed(
                reason, new_count, interaction.guild.name, rules_link
            )
            dm_sent = await moderation_utils.send_dm_notification(user, dm_embed)

            # Apply automatic actions based on warning count
            action_taken = ""
            if new_count == 2:
                # Apply 1-hour mute
                duration = config.get("mute_duration_warn_2", 3600) if config else 3600
                await self._apply_mute(
                    interaction.guild, user, moderator_id, 
                    "Mute automatique - 2 avertissements", duration
                )
                action_taken = f"\n🔇 **Mute automatique appliqué:** {moderation_utils.format_duration(duration)}"

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    "Mute automatique - 2 avertissements", duration, interaction.guild.name
                )
                await moderation_utils.send_dm_notification(user, mute_embed)

            elif new_count == 3:
                # Apply 24-hour mute
                duration = config.get("mute_duration_warn_3", 86400) if config else 86400
                await self._apply_mute(
                    interaction.guild, user, moderator_id,
                    "Mute automatique - 3 avertissements", duration
                )
                action_taken = f"\n🔇 **Mute automatique appliqué:** {moderation_utils.format_duration(duration)}"

                # Send mute DM
                mute_embed = moderation_utils.create_mute_embed(
                    "Mute automatique - 3 avertissements", duration, interaction.guild.name
                )
                await moderation_utils.send_dm_notification(user, mute_embed)

            elif new_count >= 4:
                action_taken = "\n⚠️ **Attention:** L'utilisateur a 4+ avertissements. Action manuelle requise."

            # Post to moderation log
            if config and config.get("log_channel_id"):
                await self._post_to_modlog(
                    interaction.guild,
                    config["log_channel_id"],
                    "warn",
                    user,
                    interaction.user,
                    reason=reason,
                    warn_count=new_count,
                )

            # Send response
            dm_status = "✅ DM envoyé" if dm_sent else "⚠️ DM non envoyé (désactivés)"
            await interaction.followup.send(
                f"✅ **Avertissement émis** à {user.mention}\n"
                f"**Raison:** {reason}\n"
                f"**Avertissements totaux:** {new_count}\n"
                f"{dm_status}{action_taken}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in warn command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors de l'émission de l'avertissement.",
                ephemeral=True
            )

    @app_commands.command(name="warns", description="Afficher l'historique des avertissements d'un utilisateur")
    @app_commands.describe(user="L'utilisateur à consulter")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warns(self, interaction: discord.Interaction, user: discord.Member):
        """Show warning history for a user."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)

            # Get current warning count
            warn_count = moderation_utils.get_warning_count(guild_id, user_id)

            # Get history
            history = moderation_utils.get_warning_history(guild_id, user_id)

            embed = discord.Embed(
                title=f"📋 Avertissements de {user.display_name}",
                description=f"**Avertissements actuels:** {warn_count}",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            if history:
                history_text = []
                for entry in history[:10]:  # Show last 10 entries
                    action = entry["action"]
                    created_at = datetime.fromisoformat(entry["created_at"])
                    reason = entry["reason"] or "Aucune raison"

                    action_emoji = {
                        "warn_issued": "⚠️",
                        "warn_decreased": "✅",
                        "mute_applied": "🔇",
                        "mute_removed": "🔊",
                        "appeal_created": "📝",
                        "appeal_reviewed": "⚖️"
                    }.get(action, "📌")

                    history_text.append(
                        f"{action_emoji} **{action.replace('_', ' ').title()}** "
                        f"<t:{int(created_at.timestamp())}:R>\n"
                        f"└─ {reason}"
                    )

                embed.add_field(
                    name="Historique récent",
                    value="\n\n".join(history_text),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Historique",
                    value="Aucun historique trouvé",
                    inline=False
                )

            # Calculate next decay if applicable
            if warn_count > 0:
                config = moderation_utils.get_moderation_config(guild_id)
                decay_days = moderation_utils.calculate_decay_days(warn_count, config)
                embed.add_field(
                    name="⏰ Prochain expiration",
                    value=f"Dans {decay_days} jours",
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in warns command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors de la récupération de l'historique.",
                ephemeral=True
            )

    @app_commands.command(name="unwarn", description="Retirer un avertissement d'un utilisateur")
    @app_commands.describe(
        user="L'utilisateur à désavertir",
        reason="Raison du retrait (optionnel)"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unwarn(
        self, interaction: discord.Interaction, user: discord.Member, reason: str = None
    ):
        """Remove a warning from a user."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            moderator_id = str(interaction.user.id)

            # Get current count
            current_count = moderation_utils.get_warning_count(guild_id, user_id)
            if current_count <= 0:
                await interaction.followup.send(
                    f"❌ {user.mention} n'a aucun avertissement.",
                    ephemeral=True
                )
                return

            # Decrement warning
            new_count = moderation_utils.decrement_warning(
                guild_id, user_id, moderator_id, reason or "Retiré par un modérateur"
            )

            # If warn count reaches 0, remove active mute
            if new_count == 0:
                active_mute = moderation_utils.get_active_mute(guild_id, user_id)
                if active_mute:
                    await self._remove_mute(interaction.guild, user, moderator_id, "Avertissements = 0")

            # Post to modlog
            config = moderation_utils.get_moderation_config(guild_id)
            if config and config.get("log_channel_id"):
                await self._post_to_modlog(
                    interaction.guild,
                    config["log_channel_id"],
                    "unwarn",
                    user,
                    interaction.user,
                    reason=reason or "Retiré par un modérateur",
                    warn_count=new_count,
                )

            await interaction.followup.send(
                f"✅ **Avertissement retiré** de {user.mention}\n"
                f"**Avertissements restants:** {new_count}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in unwarn command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors du retrait de l'avertissement.",
                ephemeral=True
            )

    # --- Mute Commands ---

    @app_commands.command(name="mute", description="Muter un utilisateur")
    @app_commands.describe(
        user="L'utilisateur à muter",
        duration="Durée (ex: 1h, 30m, 1d)",
        reason="Raison du mute"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(
        self, interaction: discord.Interaction, user: discord.Member, 
        duration: str, reason: str
    ):
        """Manually mute a user."""
        await interaction.response.defer(ephemeral=True)

        if user.bot:
            await interaction.followup.send("❌ Vous ne pouvez pas muter un bot.", ephemeral=True)
            return

        try:
            # Parse duration
            duration_seconds = moderation_utils.parse_duration(duration)
            if not duration_seconds:
                await interaction.followup.send(
                    "❌ Format de durée invalide. Utilisez: 1h, 30m, 1d, etc.",
                    ephemeral=True
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
                reason, duration_seconds, interaction.guild.name
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
                    reason=reason,
                    duration=moderation_utils.format_duration(duration_seconds),
                )

            dm_status = "✅ DM envoyé" if dm_sent else "⚠️ DM non envoyé"
            await interaction.followup.send(
                f"✅ **{user.mention} a été muté**\n"
                f"**Durée:** {moderation_utils.format_duration(duration_seconds)}\n"
                f"**Raison:** {reason}\n"
                f"{dm_status}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in mute command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors du mute.",
                ephemeral=True
            )

    @app_commands.command(name="unmute", description="Démuter un utilisateur")
    @app_commands.describe(user="L'utilisateur à démuter")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        """Manually unmute a user."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            moderator_id = str(interaction.user.id)

            # Check if user is muted
            active_mute = moderation_utils.get_active_mute(guild_id, user_id)
            if not active_mute:
                await interaction.followup.send(
                    f"❌ {user.mention} n'est pas muté.",
                    ephemeral=True
                )
                return

            # Remove mute
            await self._remove_mute(
                interaction.guild, user, moderator_id, "Démuté par un modérateur"
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
                    reason="Démuté par un modérateur",
                )

            await interaction.followup.send(
                f"✅ **{user.mention} a été démuté**",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in unmute command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors du démute.",
                ephemeral=True
            )

    # --- Modlog Command ---

    @app_commands.command(name="modlog", description="Afficher le journal de modération")
    @app_commands.describe(user="Utilisateur spécifique (optionnel)")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.checks.has_permissions(moderate_members=True)
    async def modlog(
        self, interaction: discord.Interaction, user: discord.Member = None
    ):
        """Show moderation log."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)

            if user:
                # Show logs for specific user
                user_id = str(user.id)
                history = moderation_utils.get_warning_history(guild_id, user_id)

                embed = discord.Embed(
                    title=f"📋 Journal de modération - {user.display_name}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )

                if history:
                    log_entries = []
                    for entry in history[:15]:  # Show last 15 entries
                        action = entry["action"]
                        created_at = datetime.fromisoformat(entry["created_at"])
                        reason = entry["reason"] or "Aucune raison"

                        log_entries.append(
                            f"**{action.replace('_', ' ').title()}** "
                            f"<t:{int(created_at.timestamp())}:R>\n"
                            f"└─ {reason}"
                        )

                    embed.description = "\n\n".join(log_entries)
                else:
                    embed.description = "Aucune entrée trouvée"

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
                    title="📋 Journal de modération - Serveur",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )

                if history:
                    log_entries = []
                    for entry in history:
                        action = entry["action"]
                        created_at = datetime.fromisoformat(entry["created_at"])
                        user_id = entry["user_id"]
                        reason = entry["reason"] or "Aucune raison"

                        log_entries.append(
                            f"<@{user_id}> - **{action.replace('_', ' ').title()}** "
                            f"<t:{int(created_at.timestamp())}:R>\n"
                            f"└─ {reason}"
                        )

                    embed.description = "\n\n".join(log_entries)
                else:
                    embed.description = "Aucune entrée trouvée"

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in modlog command: {e}")
            await interaction.followup.send(
                "❌ Une erreur s'est produite lors de la récupération du journal.",
                ephemeral=True
            )

    # --- Helper Methods ---

    async def _apply_mute(
        self, guild: discord.Guild, user: discord.Member, 
        moderator_id: str, reason: str, duration_seconds: int
    ):
        """Apply a mute to a user."""
        # Use Discord's timeout feature
        timeout_until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        await user.timeout(timeout_until, reason=reason)

        # Store in database
        moderation_utils.add_mute(
            str(guild.id), str(user.id), moderator_id, reason, duration_seconds
        )

    async def _remove_mute(
        self, guild: discord.Guild, user: discord.Member, 
        moderator_id: str, reason: str
    ):
        """Remove a mute from a user."""
        # Remove Discord timeout
        await user.timeout(None, reason=reason)

        # Remove from database
        moderation_utils.remove_mute(str(guild.id), str(user.id), moderator_id, reason)

    async def _post_to_modlog(
        self, guild: discord.Guild, log_channel_id: str, 
        action: str, user: discord.Member, 
        moderator: discord.Member, **kwargs
    ):
        """Post an action to the moderation log channel."""
        try:
            channel = guild.get_channel(int(log_channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            embed = moderation_utils.create_modlog_embed(
                action, user, moderator, **kwargs
            )
            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error posting to modlog: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
