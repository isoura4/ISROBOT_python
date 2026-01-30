import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.logging_config import get_logger

# Chargement du fichier .env
load_dotenv()

# Configure logging for this module
logger = get_logger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))


class Reload(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reload", description="Recharge les commandes du bot.")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Différer la réponse car le processus peut prendre du temps

        reloaded_extensions = []
        failed_extensions = []

        # Parcourir les fichiers contenant des commandes
        commands_path = os.path.join(os.getcwd(), "commands")
        for file in os.listdir(commands_path):
            if file.endswith(".py") and not file.startswith("_"):
                module_name = f"commands.{file[:-3]}"
                try:
                    # Essayer de recharger l'extension (si elle est déjà chargée)
                    try:
                        await self.bot.reload_extension(module_name)
                        reloaded_extensions.append(module_name)
                        logger.debug(f"Extension {module_name} rechargée avec succès")
                    except commands.ExtensionNotLoaded:
                        # Si l'extension n'est pas chargée, la charger
                        await self.bot.load_extension(module_name)
                        reloaded_extensions.append(module_name)
                        logger.debug(f"Extension {module_name} chargée avec succès")
                except Exception as e:
                    failed_extensions.append(f"{module_name}: {str(e)}")
                    logger.error(f"Erreur lors du rechargement de {module_name}: {e}")

        # Synchroniser les commandes avec Discord
        try:
            await self.bot.tree.sync(guild=discord.Object(id=SERVER_ID))
            sync_success = True
        except Exception as e:
            sync_success = False
            logger.error(f"Erreur lors de la synchronisation: {e}")

        # Préparer le message de réponse
        embed = discord.Embed(
            title="Rechargement des commandes",
            color=(
                discord.Color.green()
                if not failed_extensions
                else discord.Color.orange()
            ),
        )

        if reloaded_extensions:
            embed.add_field(
                name="✅ Extensions rechargées",
                value="\n".join([f"• {ext}" for ext in reloaded_extensions]),
                inline=False,
            )

        if failed_extensions:
            embed.add_field(
                name="❌ Extensions échouées",
                value="\n".join([f"• {ext}" for ext in failed_extensions]),
                inline=False,
            )

        if sync_success:
            embed.add_field(
                name="🔄 Synchronisation",
                value="Commandes synchronisées avec Discord",
                inline=False,
            )
        else:
            embed.add_field(
                name="⚠️ Synchronisation",
                value="Erreur lors de la synchronisation",
                inline=False,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Reload(bot))
