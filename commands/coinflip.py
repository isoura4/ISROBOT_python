import logging
import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from quests import increment_quest_progress
from utils.i18n import get_locale, t, tr

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))

logger = logging.getLogger(__name__)


class CoinFlip(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description=tr("cmd.coinflip.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def coinflip(self, interaction: discord.Interaction):
        locale = get_locale(interaction)
        result = (
            t("coinflip.heads", locale)
            if random.choice([True, False])
            else t("coinflip.tails", locale)
        )

        if interaction.guild:
            try:
                increment_quest_progress(
                    str(interaction.guild.id),
                    str(interaction.user.id),
                    "coinflip_used",
                    1,
                )
            except Exception as e:
                logger.error(f"Erreur lors de la progression de quête (coinflip): {e}")

        await interaction.response.send_message(
            embed=discord.Embed(
                title=t("coinflip.title", locale),
                description=t("coinflip.result", locale, result=result),
                color=discord.Color.blue(),
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CoinFlip(bot))
