import asyncio
import logging
import os
import re
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database

# Chargement du fichier .env
load_dotenv()

# Logger pour ce module
logger = logging.getLogger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))
TWITCH_CLIENT_ID = os.getenv("twitch_client_id")
TWITCH_CLIENT_SECRET = os.getenv("twitch_client_secret")


class Stream(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="stream_add", description="Ajouter un streamer à la liste des streamers."
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def stream(
        self,
        interaction: discord.Interaction,
        streamer_name: str,
        channel: discord.TextChannel,
        ping_role: discord.Role = None,
    ):
        # Validation des entrées
        if not streamer_name or not streamer_name.strip():
            await interaction.response.send_message(
                "❌ Le nom du streamer ne peut pas être vide.", ephemeral=True
            )
            return
        
        # Nettoyer le nom du streamer (enlever les espaces et convertir en minuscules)
        streamer_name = streamer_name.strip().lower()
        
        # Valider que le nom respecte les règles Twitch (4-25 caractères, alphanumériques, underscores et tirets)
        if not re.match(r'^[a-zA-Z0-9_-]{4,25}$', streamer_name):
            await interaction.response.send_message(
                "❌ Le nom du streamer est invalide. Les noms Twitch doivent contenir 4-25 caractères (lettres, chiffres, underscores, tirets).", 
                ephemeral=True
            )
            return
        
        # Logique pour ajouter le streamer à la base de données
        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
            await interaction.response.send_message(
                "❌ Les identifiants Twitch ne sont pas configurés.", ephemeral=True
            )
            return
        
        try:
            # Connexion à la base de données SQLite:
            # Vérifier si le streamer existe déjà dans la base de données
            conn = database.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM streamers WHERE streamerName = ? AND streamChannelId = ?",
                    (streamer_name, str(channel.id)),
                )
                result = cursor.fetchone()
            finally:
                conn.close()

            if result:
                await interaction.response.send_message(
                    f"ℹ️ Le streamer {streamer_name} est déjà dans la liste.", ephemeral=True
                )
                return
            
            # Ajouter le streamer et le channel id sélectionné à la base de données
            conn = database.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO streamers (streamerName, streamChannelId, roleId) VALUES (?, ?, ?)",
                    (
                        streamer_name,
                        str(channel.id),
                        str(ping_role.id) if ping_role else None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            
            # Envoyer un message de confirmation
            await interaction.response.send_message(
                f"✅ Streamer ajouté : **{streamer_name}** dans le salon {channel.mention}."
            )
            if ping_role is not None:
                await interaction.followup.send(
                    f"L'annonce sera faite avec la mention: {ping_role.mention}"
                )
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du streamer {streamer_name}: {e}")
            await interaction.response.send_message(
                f"❌ Erreur lors de l'ajout du streamer: {str(e)}", ephemeral=True
            )

    async def check_streams(self):
        """Vérifier le statut de tous les streamers dans la base de données."""
        try:
            conn = database.get_db_connection()
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

    @app_commands.command(
        name="stream_remove",
        description="Retirer un streamer de la liste des streamers.",
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def stream_remove(self, interaction: discord.Interaction, streamer_name: str):
        """Retirer un streamer de la liste des streamers."""
        # Validation des entrées
        if not streamer_name or not streamer_name.strip():
            await interaction.response.send_message(
                "❌ Le nom du streamer ne peut pas être vide.", ephemeral=True
            )
            return
        
        streamer_name = streamer_name.strip().lower()
        
        try:
            # Logique pour retirer le streamer de la base de données
            conn = database.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM streamers WHERE streamerName = ?", (streamer_name,))
                rows_deleted = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
            
            if rows_deleted > 0:
                await interaction.response.send_message(
                    f"✅ Streamer retiré : **{streamer_name}**"
                )
            else:
                await interaction.response.send_message(
                    f"❌ Streamer non trouvé : **{streamer_name}**\nVérifiez l'orthographe du nom.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du streamer {streamer_name}: {e}")
            await interaction.response.send_message(
                f"❌ Erreur lors de la suppression du streamer: {str(e)}", ephemeral=True
            )


class GetTwitchOAuth:
    """Classe pour gérer l'authentification avec l'API Twitch."""

    def __init__(self, session: aiohttp.ClientSession):
        self.client_id = TWITCH_CLIENT_ID
        self.client_secret = TWITCH_CLIENT_SECRET
        self.session = session

    async def get_auth_token(self, retry_count: int = 3):
        """Obtenir un token d'authentification pour l'API Twitch avec retry."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Les identifiants Twitch ne sont pas configurés.")

        urlOAuth = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        
        last_error = None
        for attempt in range(retry_count):
            try:
                async with self.session.post(urlOAuth, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["access_token"]
                    elif response.status >= 500:
                        # Erreur serveur, réessayer
                        last_error = f"Erreur serveur Twitch: {response.status}"
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2 ** attempt)  # Backoff exponentiel
                            continue
                    else:
                        # Erreur client (4xx), ne pas réessayer
                        raise Exception(
                            f"Erreur lors de la récupération du token OAuth: {response.status}"
                        )
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    logger.warning(f"Tentative {attempt + 1}/{retry_count} échouée pour l'authentification Twitch: {e}")
                    await asyncio.sleep(2 ** attempt)
                    continue
                    
        raise Exception(f"Échec de l'authentification Twitch après {retry_count} tentatives: {last_error}")


class StartStreamCheckInterval:
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


class CheckTwitchStatus:
    """Classe pour vérifier le statut des streamers sur Twitch."""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.oauth = GetTwitchOAuth(session)

    async def check_streamer_status(self, streamer_name: str, retry_count: int = 3):
        """Vérifier si un streamer est en ligne avec retry."""
        last_error = None
        
        for attempt in range(retry_count):
            try:
                token = await self.oauth.get_auth_token()
                headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
                url = f"https://api.twitch.tv/helix/streams?user_login={streamer_name}"

                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    elif response.status >= 500:
                        # Erreur serveur, réessayer
                        last_error = f"Erreur serveur Twitch: {response.status}"
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                    else:
                        # Erreur client, ne pas réessayer
                        raise Exception(
                            f"Erreur lors de la vérification du statut du streamer: {response.status}"
                        )
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    logger.warning(f"Tentative {attempt + 1}/{retry_count} échouée pour {streamer_name}: {e}")
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        raise Exception(f"Échec de la vérification du streamer {streamer_name} après {retry_count} tentatives: {last_error}")


class AnnounceStream:
    """Classe pour annoncer le début d'un stream."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_role(self, streamer_name: str):
        """Récupérer le rôle à mentionner pour les annonces."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT roleId FROM streamers WHERE streamerName = ?", (streamer_name,)
        )
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            return discord.utils.get(self.bot.guilds[0].roles, id=int(result[0]))
        return None

    async def announce(
        self,
        streamer_name: str,
        channel: discord.TextChannel,
        stream_title: str,
        category: str,
        discordRole: Optional[discord.Role] = None,
    ):
        """Annoncer le début d'un stream dans un salon Discord."""
        # Si aucun rôle n'est fourni, le récupérer
        if discordRole is None:
            discordRole = await self.get_role(streamer_name)

        embed = discord.Embed(
            title=f"{stream_title}",
            description=f"**Channel** : {streamer_name} \n**Catégorie** : {category}\n **Regardez le stream ici :** https://www.twitch.tv/{streamer_name}",
            color=discord.Color.purple(),
        )
        if streamer_name:
            embed.set_image(
                url=f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{streamer_name}-1920x1080.jpg"
            )

        # Envoyer la mention séparément pour déclencher les notifications
        if discordRole is not None:
            await channel.send(content=discordRole.mention, embed=embed)
        else:
            await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stream(bot))
