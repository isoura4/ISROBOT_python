import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))


class CoinFlip(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="coinflip", description="Lance une pièce et répond avec le résultat!"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def coinflip(self, interaction: discord.Interaction):
        result = "pile" if random.choice([True, False]) else "face"
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Lancer de pièce :coin:",
                description=f"Le résultat est : {result}",
                color=discord.Color.blue(),
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CoinFlip(bot))
