import os
import discord
import dotenv
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv('server_id', '0'))

class count(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="count", description="Paramétré le salon du minijeux du compteur.")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)