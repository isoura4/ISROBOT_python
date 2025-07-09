import os
import discord
import sqlite3
import asyncio
import aiohttp
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv('server_id', '0'))
TWITCH_CLIENT_ID = os.getenv('twitch_client_id')
TWITCH_CLIENT_SECRET = os.getenv('twitch_client_secret')

class Stream(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stream_add", description="Ajouter un streamer à la liste des streamers.")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def stream(self, interaction: discord.Interaction, streamer_name: str, channel: discord.TextChannel):
        # Logique pour ajouter le streamer à la base de données
        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
            await interaction.response.send_message("Les identifiants Twitch ne sont pas configurés.")
            return
        else:
            # Connexion à la base de données SQLite:
            # Vérifier si le streamer existe déjà dans la base de données
            conn = sqlite3.connect('database.sqlite3')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM streamers WHERE streamerName = ? AND streamChannelId = ?", (streamer_name, str(channel.id)))
            result = cursor.fetchone()
            conn.close()

            if result:
                await interaction.response.send_message(f"Le streamer {streamer_name} est déjà dans la liste.")
                return
            if result is None:
                # Ajouter le streamer et le channel id sélectionné à la base de données
                conn = sqlite3.connect('database.sqlite3')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO streamers (streamerName, streamChannelId) VALUES (?, ?)", (streamer_name, str(channel.id)))
                conn.commit()
                conn.close()
                # Envoyer un message de confirmation
                await interaction.response.send_message(f"Streamer ajouté : {streamer_name} dans le salon {channel.mention}.")

    async def check_streams(self):
        """Vérifier le statut de tous les streamers dans la base de données."""
        try:
            conn = sqlite3.connect('database.sqlite3')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM streamers")
            streamers = cursor.fetchall()
            conn.close()
            
            for streamer in streamers:
                # Logique de vérification du stream
                # Cette méthode sera appelée périodiquement
                pass
        except Exception as e:
            print(f"Erreur lors de la vérification des streams: {e}")

    async def announce(self, streamer_name: str, channel: discord.TextChannel):
        """Annoncer le début d'un stream dans un salon Discord."""
        embed = discord.Embed(
            title=f"🔴 {streamer_name} est en live !",
            description=f"Regardez le stream ici : https://www.twitch.tv/{streamer_name}",
            color=discord.Color.purple()
        )
        if streamer_name:
            embed.set_image(url=f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{streamer_name}-1920x1080.jpg")
        await channel.send(embed=embed)


class getTwitchOAuth:
    """Classe pour gérer l'authentification avec l'API Twitch."""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.client_id = TWITCH_CLIENT_ID
        self.client_secret = TWITCH_CLIENT_SECRET
        self.session = session

    async def get_auth_token(self):
        """Obtenir un token d'authentification pour l'API Twitch."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Les identifiants Twitch ne sont pas configurés.")
        
        urlOAuth = "https://id.twitch.tv/oauth2/token"
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        async with self.session.post(urlOAuth, params=params) as response:
            if response.status != 200:
                raise Exception(f"Erreur lors de la récupération du token OAuth: {response.status}")
            data = await response.json()
            return data['access_token']

class startStreamCheckInterval:
    """Classe pour démarrer un intervalle de vérification des streamers."""
    
    def __init__(self, bot: commands.Bot, interval: int = 60):
        self.bot = bot
        self.interval = interval
        self.check_task = None

    async def start_check(self):
        """Démarrer la tâche de vérification des streamers."""
        if self.check_task is not None:
            return  # La tâche est déjà en cours
        
        self.check_task = self.bot.loop.create_task(self.check_streamers())

    async def check_streamers(self):
        """Vérifier régulièrement le statut des streamers."""
        while True:
            # Logique pour vérifier les streamers
            await asyncio.sleep(self.interval)

class checkTwitchStatus:
    """Classe pour vérifier le statut des streamers sur Twitch."""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.oauth = getTwitchOAuth(session)

    async def check_streamer_status(self, streamer_name: str):
        """Vérifier si un streamer est en ligne."""
        token = await self.oauth.get_auth_token()
        headers = {
            'Client-ID': TWITCH_CLIENT_ID,
            'Authorization': f'Bearer {token}'
        }
        url = f"https://api.twitch.tv/helix/streams?user_login={streamer_name}"
        
        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"Erreur lors de la vérification du statut du streamer: {response.status}")
            data = await response.json()
            return data['data']

class announceStream:
    """Classe pour annoncer le début d'un stream."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Annonce le début d'un stream dans un salon Discord dans un Embed.
    async def announce(self, streamer_name: str, channel: discord.TextChannel):
        """Annoncer le début d'un stream dans un salon Discord."""
        embed = discord.Embed(
            title=f"🔴 {streamer_name} est en live !",
            description=f"Regardez le stream ici : https://www.twitch.tv/{streamer_name}",
            color=discord.Color.purple()
        )
        if streamer_name:
            embed.set_image(url=f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{streamer_name}-1920x1080.jpg")
        await channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Stream(bot))