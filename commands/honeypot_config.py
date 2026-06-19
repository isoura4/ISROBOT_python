"""
Honeypot configuration commands for ISROBOT.
Allows administrators to configure honeypot channels.
"""

import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import moderation_utils

load_dotenv()

logger = logging.getLogger(__name__)
SERVER_ID = int(os.getenv("server_id", "0"))


class HoneypotConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    honeypot = app_commands.Group(
        name="honeypot",
        description="Configurer les canaux honeypot",
        guild_ids=[SERVER_ID]
    )

    @honeypot.command(name="add", description="Ajouter un canal honeypot")
    @app_commands.describe(
        channel="Le canal à ajouter en tant que honeypot"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_honeypot(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Add a text channel as a honeypot channel."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            channel_id = str(channel.id)

            # Add to database
            success = moderation_utils.add_honeypot_channel(guild_id, channel_id)

            if success:
                embed = discord.Embed(
                    title="✅ Canal honeypot ajouté",
                    description=f"{channel.mention} a été ajouté en tant que canal honeypot.",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="ℹ️ Information",
                    value="Les messages envoyés dans ce canal entraîneront une exclusion du serveur (softban).",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"Honeypot channel added: {channel.name} ({channel_id}) in guild {guild_id}")
            else:
                embed = discord.Embed(
                    title="⚠️ Canal déjà configuré",
                    description=f"{channel.mention} est déjà un canal honeypot.",
                    color=discord.Color.orange(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du canal honeypot: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors de l'ajout du canal honeypot.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @honeypot.command(name="remove", description="Retirer un canal honeypot")
    @app_commands.describe(
        channel="Le canal à retirer en tant que honeypot"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_honeypot(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Remove a channel from honeypot channels."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            channel_id = str(channel.id)

            # Remove from database
            success = moderation_utils.remove_honeypot_channel(guild_id, channel_id)

            if success:
                embed = discord.Embed(
                    title="✅ Canal honeypot retiré",
                    description=f"{channel.mention} n'est plus un canal honeypot.",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"Honeypot channel removed: {channel.name} ({channel_id}) in guild {guild_id}")
            else:
                embed = discord.Embed(
                    title="⚠️ Canal non trouvé",
                    description=f"{channel.mention} n'est pas configuré en tant que canal honeypot.",
                    color=discord.Color.orange(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur lors du retrait du canal honeypot: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors du retrait du canal honeypot.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @honeypot.command(name="list", description="Lister les canaux honeypot")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_honeypots(self, interaction: discord.Interaction):
        """List all honeypot channels in the guild."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            honeypot_channels = moderation_utils.get_honeypot_channels(guild_id)

            embed = discord.Embed(
                title="🍯 Canaux honeypot",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            if not honeypot_channels:
                embed.description = "Aucun canal honeypot configuré."
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Build channel list with stats
            channel_list = []
            for channel_id in honeypot_channels:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    stats = moderation_utils.get_honeypot_stats(guild_id, channel_id)
                    channel_list.append(
                        f"• {channel.mention} - {stats['violation_count']} violation(s), {stats['unique_users']} utilisateur(s)"
                    )

            if channel_list:
                embed.description = "\n".join(channel_list)
            else:
                embed.description = "Aucun canal honeypot trouvé."

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur lors de la listage des canaux honeypot: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors du listage des canaux honeypot.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @honeypot.command(name="stats", description="Afficher les statistiques des honeypots")
    @app_commands.checks.has_permissions(administrator=True)
    async def honeypot_stats(self, interaction: discord.Interaction):
        """Show honeypot statistics for the guild."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild.id)
            honeypot_channels = moderation_utils.get_honeypot_channels(guild_id)

            embed = discord.Embed(
                title="📊 Statistiques honeypot",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            if not honeypot_channels:
                embed.description = "Aucun canal honeypot configuré."
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Calculate total stats
            total_violations = 0
            total_users = set()
            stats_lines = []

            for channel_id in honeypot_channels:
                channel = interaction.guild.get_channel(int(channel_id))
                stats = moderation_utils.get_honeypot_stats(guild_id, channel_id)
                
                total_violations += stats["violation_count"]
                
                if channel:
                    stats_lines.append(
                        f"**{channel.mention}**\n"
                        f"  🎯 Violations: {stats['violation_count']}\n"
                        f"  👥 Utilisateurs uniques: {stats['unique_users']}"
                    )

            embed.description = "\n".join(stats_lines) if stats_lines else "Aucune statistique disponible."
            
            embed.add_field(
                name="📈 Total",
                value=f"**{total_violations}** violation(s)",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur lors de l'affichage des statistiques honeypot: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors de l'affichage des statistiques.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup the honeypot configuration cog."""
    await bot.add_cog(HoneypotConfig(bot))
