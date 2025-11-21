import os
import discord
import sqlite3
import asyncio
import aiohttp
import logging
from typing import Optional
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv('server_id', '0'))
YOUTUBE_API_KEY = os.getenv('youtube_api_key')

# Logger pour ce module
logger = logging.getLogger(__name__)

class YouTube(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="youtube_add", description="Ajouter une chaîne YouTube à la liste de surveillance.")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def youtube_add(self, interaction: discord.Interaction, channel_id: str, channel: discord.TextChannel, 
                          notify_videos: bool = True, notify_shorts: bool = True, notify_live: bool = True, 
                          ping_role: discord.Role = None):
        """Ajouter une chaîne YouTube à surveiller. Accepte un ID de chaîne ou un handle (ex: @nom_chaine)."""
        if not YOUTUBE_API_KEY:
            await interaction.response.send_message("La clé API YouTube n'est pas configurée.")
            return
        
        # Vérifier si le channel_id est valide ou si c'est un handle
        try:
            async with aiohttp.ClientSession() as session:
                checker = checkYouTubeChannel(session)
                
                # Si l'entrée commence par @, c'est un handle
                if channel_id.startswith('@'):
                    channel_data = await checker.get_channel_by_handle(channel_id)
                    if not channel_data:
                        await interaction.response.send_message(
                            f"❌ Impossible de trouver la chaîne YouTube avec le handle **{channel_id}**.\n"
                            f"Vérifiez que le handle est correct et que la chaîne existe.\n"
                            f"Vous pouvez aussi essayer d'utiliser l'ID de la chaîne à la place."
                        )
                        return
                    # Extraire l'ID réel de la chaîne et le nom
                    actual_channel_id = channel_data['id']
                    channel_name = channel_data['snippet'].get('title', channel_id)
                else:
                    # C'est un ID de chaîne classique
                    actual_channel_id = channel_id
                    channel_info = await checker.get_channel_info(channel_id)
                    if not channel_info:
                        await interaction.response.send_message(
                            f"❌ Impossible de trouver cette chaîne YouTube avec l'ID **{channel_id}**.\n"
                            f"Vérifiez l'ID de la chaîne ou utilisez le handle (ex: @nom_chaine)."
                        )
                        return
                    channel_name = channel_info.get('title', channel_id)
        except Exception as e:
            error_message = str(e)
            await interaction.response.send_message(
                f"❌ Erreur lors de la vérification de la chaîne: {error_message}\n"
                f"Assurez-vous que la clé API YouTube est correctement configurée et valide."
            )
            return
        
        # Vérifier si la chaîne existe déjà dans la base de données
        conn = sqlite3.connect('database.sqlite3')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM youtube_channels WHERE channelId = ? AND discordChannelId = ?", 
                      (actual_channel_id, str(channel.id)))
        result = cursor.fetchone()
        conn.close()

        if result:
            await interaction.response.send_message(f"La chaîne YouTube {channel_name} est déjà dans la liste.")
            return
        
        # Ajouter la chaîne à la base de données
        conn = sqlite3.connect('database.sqlite3')
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO youtube_channels 
                         (channelId, channelName, discordChannelId, roleId, notifyVideos, notifyShorts, notifyLive) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                      (actual_channel_id, channel_name, str(channel.id), 
                       str(ping_role.id) if ping_role else None,
                       1 if notify_videos else 0,
                       1 if notify_shorts else 0,
                       1 if notify_live else 0))
        conn.commit()
        conn.close()
        
        # Envoyer un message de confirmation
        notifications = []
        if notify_videos:
            notifications.append("vidéos")
        if notify_shorts:
            notifications.append("shorts")
        if notify_live:
            notifications.append("lives")
        
        notif_text = ", ".join(notifications) if notifications else "aucune notification"
        await interaction.response.send_message(
            f"Chaîne YouTube ajoutée : **{channel_name}** dans le salon {channel.mention}.\nNotifications: {notif_text}"
        )
        if ping_role is not None:
            await interaction.followup.send(f"L'annonce sera faite avec la mention: {ping_role.mention}")

    @app_commands.command(name="youtube_remove", description="Retirer une chaîne YouTube de la liste de surveillance.")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def youtube_remove(self, interaction: discord.Interaction, channel_name: str):
        """Retirer une chaîne YouTube de la liste de surveillance."""
        if not channel_name:
            await interaction.response.send_message("Veuillez spécifier le nom de la chaîne à retirer.")
            conn = sqlite3.connect('database.sqlite3')
            cursor = conn.cursor()
            cursor.execute("SELECT channelName FROM youtube_channels")
            channels = cursor.fetchall()
            conn.close()
            if not channels:
                await interaction.followup.send("Aucune chaîne YouTube n'est actuellement enregistrée.")
                return
            channel_list = "\n".join([c[0] for c in channels])
            await interaction.followup.send(f"Chaînes disponibles :\n{channel_list}")
            return
        
        # Retirer la chaîne de la base de données
        conn = sqlite3.connect('database.sqlite3')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM youtube_channels WHERE channelName = ?", (channel_name,))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            await interaction.response.send_message(f"Chaîne YouTube retirée : {channel_name}")
        else:
            await interaction.response.send_message(f"Chaîne YouTube non trouvée : {channel_name}")

class checkYouTubeChannel:
    """Classe pour vérifier les informations d'une chaîne YouTube."""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = YOUTUBE_API_KEY

    async def get_channel_by_handle(self, handle: str):
        """Récupérer le channel ID à partir d'un handle YouTube (ex: @username)."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")
        
        # Retirer le @ si présent
        original_handle = handle
        if handle.startswith('@'):
            handle = handle[1:]
        
        # Méthode 1: Essayer avec le paramètre forHandle (pour les nouveaux handles)
        url = f"https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id,snippet',
            'forHandle': handle,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if 'items' in data and len(data['items']) > 0:
                    return {
                        'id': data['items'][0]['id'],
                        'snippet': data['items'][0]['snippet']
                    }
            elif response.status == 400:
                # Si forHandle ne fonctionne pas, essayer forUsername (ancienne méthode)
                pass
            else:
                # Autre erreur
                error_data = await response.json() if response.content_type == 'application/json' else {}
                error_msg = error_data.get('error', {}).get('message', f"Status {response.status}")
                raise Exception(f"Erreur API YouTube: {error_msg}")
        
        # Méthode 2: Essayer avec le paramètre forUsername (pour les anciens usernames)
        params = {
            'part': 'id,snippet',
            'forUsername': handle,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if 'items' in data and len(data['items']) > 0:
                    return {
                        'id': data['items'][0]['id'],
                        'snippet': data['items'][0]['snippet']
                    }
        
        # Méthode 3: Utiliser l'API de recherche comme dernier recours
        search_url = f"https://www.googleapis.com/youtube/v3/search"
        search_params = {
            'part': 'snippet',
            'q': original_handle,
            'type': 'channel',
            'maxResults': 1,
            'key': self.api_key
        }
        
        async with self.session.get(search_url, params=search_params) as response:
            if response.status == 200:
                data = await response.json()
                if 'items' in data and len(data['items']) > 0:
                    channel_id = data['items'][0]['snippet']['channelId']
                    # Récupérer les informations complètes du channel
                    return await self.get_channel_info_by_id(channel_id)
        
        return None
    
    async def get_channel_info_by_id(self, channel_id: str):
        """Récupérer les informations complètes d'une chaîne par son ID."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")
        
        url = f"https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id,snippet',
            'id': channel_id,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if 'items' in data and len(data['items']) > 0:
                    return {
                        'id': data['items'][0]['id'],
                        'snippet': data['items'][0]['snippet']
                    }
            return None

    async def get_channel_info(self, channel_id: str):
        """Récupérer les informations d'une chaîne YouTube."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")
        
        url = f"https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'snippet',
            'id': channel_id,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Erreur lors de la récupération des informations de la chaîne: {response.status}")
            data = await response.json()
            if 'items' in data and len(data['items']) > 0:
                return data['items'][0]['snippet']
            return None

    async def get_latest_uploads(self, channel_id: str, max_results: int = 5):
        """Récupérer les dernières vidéos d'une chaîne YouTube."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")
        
        # D'abord, obtenir l'ID de la playlist d'uploads
        url = f"https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'contentDetails',
            'id': channel_id,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 404:
                # Le canal n'existe pas ou n'est pas accessible
                logger.warning(f"Canal YouTube introuvable (404): {channel_id}")
                return []
            if response.status != 200:
                try:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                except (aiohttp.ContentTypeError, ValueError):
                    error_data = {}
                error_msg = error_data.get('error', {}).get('message', f"Status {response.status}")
                raise Exception(f"Erreur lors de la récupération de l'ID de playlist: {error_msg}")
            try:
                data = await response.json()
            except Exception as e:
                logger.error(f"Erreur lors du parsing JSON pour le canal {channel_id}: {e}")
                return []
            if 'items' not in data or len(data['items']) == 0:
                logger.info(f"Aucune donnée de canal trouvée pour: {channel_id}")
                return []
            uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Ensuite, récupérer les vidéos de la playlist
        url = f"https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            'part': 'snippet',
            'playlistId': uploads_playlist_id,
            'maxResults': max_results,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 404:
                # La playlist n'existe pas ou est vide
                logger.warning(f"Playlist d'uploads introuvable (404) pour le canal: {channel_id}")
                return []
            if response.status != 200:
                try:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                except (aiohttp.ContentTypeError, ValueError):
                    error_data = {}
                error_msg = error_data.get('error', {}).get('message', f"Status {response.status}")
                raise Exception(f"Erreur lors de la récupération des vidéos: {error_msg}")
            try:
                data = await response.json()
            except Exception as e:
                logger.error(f"Erreur lors du parsing JSON de la playlist {uploads_playlist_id}: {e}")
                return []
            return data.get('items', [])

    async def get_video_details(self, video_id: str):
        """Récupérer les détails d'une vidéo YouTube."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")
        
        url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'snippet,contentDetails,liveStreamingDetails',
            'id': video_id,
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 404:
                logger.warning(f"Vidéo YouTube introuvable (404): {video_id}")
                return None
            if response.status != 200:
                try:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                except (aiohttp.ContentTypeError, ValueError):
                    error_data = {}
                error_msg = error_data.get('error', {}).get('message', f"Status {response.status}")
                raise Exception(f"Erreur lors de la récupération des détails de la vidéo: {error_msg}")
            try:
                data = await response.json()
            except Exception as e:
                logger.error(f"Erreur lors du parsing JSON pour la vidéo {video_id}: {e}")
                return None
            if 'items' in data and len(data['items']) > 0:
                return data['items'][0]
            return None

    async def check_live_status(self, channel_id: str):
        """Vérifier si une chaîne est en live."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")
        
        url = f"https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'eventType': 'live',
            'type': 'video',
            'key': self.api_key
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 404:
                logger.warning(f"Canal YouTube introuvable lors de la vérification du live (404): {channel_id}")
                return []
            if response.status != 200:
                try:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                except (aiohttp.ContentTypeError, ValueError):
                    error_data = {}
                error_msg = error_data.get('error', {}).get('message', f"Status {response.status}")
                raise Exception(f"Erreur lors de la vérification du statut live: {error_msg}")
            try:
                data = await response.json()
            except Exception as e:
                logger.error(f"Erreur lors du parsing JSON pour le statut live du canal {channel_id}: {e}")
                return []
            return data.get('items', [])

def is_short(video_duration: str) -> bool:
    """Déterminer si une vidéo est un short basé sur sa durée (moins de 61 secondes)."""
    # Format de durée ISO 8601: PT#H#M#S ou PT#M#S ou PT#S
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', video_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds <= 60
    return False

class announceYouTube:
    """Classe pour annoncer les nouveaux contenus YouTube."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def get_role(self, channel_id: str):
        """Récupérer le rôle à mentionner pour les annonces."""
        conn = sqlite3.connect('database.sqlite3')
        cursor = conn.cursor()
        cursor.execute("SELECT roleId FROM youtube_channels WHERE channelId = ?", (channel_id,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            return discord.utils.get(self.bot.guilds[0].roles, id=int(result[0]))
        return None

    async def announce_video(self, channel_id: str, channel_name: str, discord_channel: discord.TextChannel, 
                            video_id: str, video_title: str, thumbnail_url: str, 
                            discord_role: Optional[discord.Role] = None):
        """Annoncer une nouvelle vidéo dans un salon Discord."""
        if discord_role is None:
            discord_role = await self.get_role(channel_id)
        
        embed = discord.Embed(
            title=f"📹 Nouvelle vidéo : {video_title}",
            description=f"**Chaîne** : {channel_name}\n**Regardez la vidéo ici :** https://www.youtube.com/watch?v={video_id}",
            color=discord.Color.red()
        )
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)
        
        try:
            if discord_role is not None:
                await discord_channel.send(content=discord_role.mention, embed=embed)
            else:
                await discord_channel.send(embed=embed)
        except discord.errors.Forbidden as e:
            # Propager l'erreur pour qu'elle soit capturée au niveau supérieur
            raise

    async def announce_short(self, channel_id: str, channel_name: str, discord_channel: discord.TextChannel, 
                            video_id: str, video_title: str, thumbnail_url: str, 
                            discord_role: Optional[discord.Role] = None):
        """Annoncer un nouveau short dans un salon Discord."""
        if discord_role is None:
            discord_role = await self.get_role(channel_id)
        
        embed = discord.Embed(
            title=f"🎬 Nouveau short : {video_title}",
            description=f"**Chaîne** : {channel_name}\n**Regardez le short ici :** https://www.youtube.com/shorts/{video_id}",
            color=discord.Color.orange()
        )
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)
        
        try:
            if discord_role is not None:
                await discord_channel.send(content=discord_role.mention, embed=embed)
            else:
                await discord_channel.send(embed=embed)
        except discord.errors.Forbidden as e:
            # Propager l'erreur pour qu'elle soit capturée au niveau supérieur
            raise

    async def announce_live(self, channel_id: str, channel_name: str, discord_channel: discord.TextChannel, 
                           video_id: str, video_title: str, thumbnail_url: str, 
                           discord_role: Optional[discord.Role] = None):
        """Annoncer un nouveau live dans un salon Discord."""
        if discord_role is None:
            discord_role = await self.get_role(channel_id)
        
        embed = discord.Embed(
            title=f"🔴 EN DIRECT : {video_title}",
            description=f"**Chaîne** : {channel_name}\n**Regardez le live ici :** https://www.youtube.com/watch?v={video_id}",
            color=discord.Color.from_rgb(255, 0, 0)
        )
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)
        
        try:
            if discord_role is not None:
                await discord_channel.send(content=discord_role.mention, embed=embed)
            else:
                await discord_channel.send(embed=embed)
        except discord.errors.Forbidden as e:
            # Propager l'erreur pour qu'elle soit capturée au niveau supérieur
            raise

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTube(bot))
