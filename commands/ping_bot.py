import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.i18n import get_locale, t, tr

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))


class PingBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping_bot", description=tr("cmd.ping_bot.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000  # Convert to milliseconds
        await interaction.response.send_message(
            t("ping_bot.response", get_locale(interaction), latency=latency)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PingBot(bot))
    # Enregistrer la commande ping_bot dans le bot
