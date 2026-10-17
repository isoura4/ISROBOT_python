import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database
from utils.i18n import get_locale, t, tr

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))
YOUTUBE_API_KEY = os.getenv("youtube_api_key")

# Logger pour ce module
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _http_session(bot: commands.Bot):
    """Réutilise la session HTTP partagée du bot si disponible.

    Évite de créer une nouvelle ``aiohttp.ClientSession`` à chaque commande ;
    n'en crée une (temporaire, fermée en sortie) que si le bot n'en a pas.
    """
    session = getattr(bot, "session", None)
    if session is not None and not session.closed:
        yield session
        return

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as temp_session:
        yield temp_session


def _db_channel_exists(channel_id: str, discord_channel_id: str) -> bool:
    """Indique si la chaîne YouTube est déjà surveillée dans ce salon."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM youtube_channels "
            "WHERE channelId = ? AND discordChannelId = ?",
            (channel_id, discord_channel_id),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def _db_add_channel(
    channel_id: str,
    channel_name: str,
    discord_channel_id: str,
    role_id: Optional[str],
    notify_videos: bool,
    notify_shorts: bool,
    last_video_id: Optional[str],
    last_short_id: Optional[str],
) -> None:
    """Insère une nouvelle chaîne à surveiller."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO youtube_channels
               (channelId, channelName, discordChannelId, roleId,
                notifyVideos, notifyShorts, notifyLive,
                lastVideoId, lastShortId, lastLiveId)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                channel_id,
                channel_name,
                discord_channel_id,
                role_id,
                1 if notify_videos else 0,
                1 if notify_shorts else 0,
                0,  # notifyLive désactivé (fonctionnalité supprimée)
                last_video_id,
                last_short_id,
                None,  # lastLiveId non utilisé (fonctionnalité supprimée)
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _db_list_channel_names() -> list:
    """Retourne la liste des noms de chaînes surveillées."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT channelName FROM youtube_channels")
        return cursor.fetchall()
    finally:
        conn.close()


def _db_remove_channel(channel_name: str) -> int:
    """Supprime une chaîne par son nom, retourne le nombre de lignes affectées."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM youtube_channels WHERE channelName = ?",
            (channel_name,),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def validate_youtube_identifier(
    identifier: str, locale: Optional[str] = None
) -> tuple[bool, str]:
    """
    Valide un identifiant YouTube (handle ou channel ID).

    Args:
        identifier: L'identifiant à valider (handle ou channel ID)

    Returns:
        tuple: (is_valid, error_message) - is_valid est True si valide, error_message contient le message d'erreur si invalide
    """
    if identifier.startswith("@"):
        # Valider le handle: doit commencer par @ et contenir uniquement des caractères alphanumériques, tirets, underscores, points
        # Les handles YouTube peuvent contenir des lettres, chiffres, tirets, underscores et points
        if len(identifier) < 2:
            return False, t("youtube.handle_short", locale)

        handle_part = identifier[1:]
        # Regex pour valider: lettres, chiffres, tirets, underscores, points
        if not re.match(r"^[a-zA-Z0-9._-]+$", handle_part):
            return False, t("youtube.handle_invalid", locale)
    else:
        # Valider l'ID de chaîne: doit commencer par UC et avoir exactement 24 caractères
        if not identifier.startswith("UC") or len(identifier) != 24:
            return (
                False,
                t("youtube.id_invalid", locale),
            )

    return True, ""


class YouTube(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="youtube_add",
        description=tr("cmd.youtube_add.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def youtube_add(
        self,
        interaction: discord.Interaction,
        channel_id: str,
        channel: discord.TextChannel,
        notify_videos: bool = True,
        notify_shorts: bool = True,
        ping_role: discord.Role = None,
    ):
        """Ajouter une chaîne YouTube à surveiller. Accepte un ID de chaîne ou un handle (ex: @nom_chaine)."""
        locale = get_locale(interaction)
        if not YOUTUBE_API_KEY:
            await interaction.response.send_message(
                t("youtube.no_api", locale), ephemeral=True
            )
            return

        # Validation des entrées
        if not channel_id or not channel_id.strip():
            await interaction.response.send_message(
                t("youtube.empty_input", locale),
                ephemeral=True,
            )
            return

        channel_id = channel_id.strip()

        # Valider le format de base du channel_id ou handle
        is_valid, error_msg = validate_youtube_identifier(channel_id, locale)
        if not is_valid:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        # Vérifier si le channel_id est valide ou si c'est un handle
        actual_channel_id = None
        channel_name = None
        try:
            async with _http_session(self.bot) as session:
                checker = CheckYouTubeChannel(session)

                # Si l'entrée commence par @, c'est un handle
                if channel_id.startswith("@"):
                    channel_data = await checker.get_channel_by_handle(channel_id)
                    if not channel_data:
                        await interaction.response.send_message(
                            t("youtube.handle_not_found", locale, handle=channel_id)
                        )
                        return
                    # Extraire l'ID réel de la chaîne et le nom
                    actual_channel_id = channel_data["id"]
                    channel_name = channel_data["snippet"].get("title", channel_id)
                else:
                    # C'est un ID de chaîne classique
                    actual_channel_id = channel_id
                    channel_info = await checker.get_channel_info(channel_id)
                    if not channel_info:
                        await interaction.response.send_message(
                            t("youtube.id_not_found", locale, id=channel_id)
                        )
                        return
                    channel_name = channel_info.get("title", channel_id)

                # Vérifier si la chaîne existe déjà dans la base de données
                exists = await asyncio.to_thread(
                    _db_channel_exists, actual_channel_id, str(channel.id)
                )

                if exists:
                    await interaction.response.send_message(
                        t("youtube.already", locale, name=channel_name)
                    )
                    return

                # Initialiser les IDs de suivi pour éviter d'annoncer l'ancien contenu
                last_video_id = None
                last_short_id = None

                # Récupérer les dernières vidéos pour initialiser les IDs de suivi
                latest_uploads = await checker.get_latest_uploads(
                    actual_channel_id, max_results=5
                )

                # Récupérer les détails en un seul appel API (évite le N+1)
                upload_ids = [
                    upload["snippet"]["resourceId"]["videoId"]
                    for upload in latest_uploads
                ]
                details_map = await checker.get_video_details_batch(upload_ids)

                # Parcourir les uploads récents pour trouver la dernière vidéo et le dernier short
                for upload in latest_uploads:
                    video_id = upload["snippet"]["resourceId"]["videoId"]
                    video_details = details_map.get(video_id)

                    if video_details:
                        duration = video_details["contentDetails"]["duration"]
                        is_short_video = is_short(duration)

                        # Enregistrer le dernier short trouvé
                        if is_short_video and last_short_id is None:
                            last_short_id = video_id

                        # Enregistrer la dernière vidéo normale trouvée
                        if not is_short_video and last_video_id is None:
                            last_video_id = video_id

                        # Si on a trouvé les deux, on peut arrêter
                        if last_video_id and last_short_id:
                            break

        except Exception as e:
            error_message = str(e)
            await interaction.response.send_message(
                t("youtube.check_error", locale, error=error_message)
            )
            logger.warning(
                f"Impossible d'initialiser les IDs de suivi pour {channel_name if channel_name else channel_id}: {e}"
            )
            return

        # Ajouter la chaîne à la base de données
        # Note: notifyLive et lastLiveId sont conservés dans la DB pour la compatibilité
        # mais sont désactivés (0 et None) car la fonctionnalité live est supprimée
        await asyncio.to_thread(
            _db_add_channel,
            actual_channel_id,
            channel_name,
            str(channel.id),
            str(ping_role.id) if ping_role else None,
            notify_videos,
            notify_shorts,
            last_video_id,
            last_short_id,
        )

        # Envoyer un message de confirmation
        notifications = []
        if notify_videos:
            notifications.append(t("youtube.notif_videos", locale))
        if notify_shorts:
            notifications.append(t("youtube.notif_shorts", locale))

        notif_text = (
            ", ".join(notifications)
            if notifications
            else t("youtube.notif_none", locale)
        )

        # Avertir si aucune notification n'est activée
        if not notifications:
            await interaction.response.send_message(
                t(
                    "youtube.added_warning",
                    locale,
                    name=channel_name,
                    channel=channel.mention,
                    notifications=notif_text,
                )
            )
            return

        # Préparer le message de confirmation avec les infos de suivi
        tracking_info = []
        if last_video_id:
            tracking_info.append(
                t("youtube.tracking_last_video", locale, id=last_video_id[:8])
            )
        if last_short_id:
            tracking_info.append(
                t("youtube.tracking_last_short", locale, id=last_short_id[:8])
            )

        tracking_text = (
            t("youtube.tracking_init", locale, items=", ".join(tracking_info))
            if tracking_info
            else t("youtube.tracking_none", locale)
        )

        await interaction.response.send_message(
            t(
                "youtube.added",
                locale,
                name=channel_name,
                channel=channel.mention,
                notifications=notif_text,
                tracking=tracking_text,
            )
        )
        if ping_role is not None:
            await interaction.followup.send(
                t("stream.role_announce", locale, role=ping_role.mention)
            )

    @app_commands.command(
        name="youtube_remove",
        description=tr("cmd.youtube_remove.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def youtube_remove(self, interaction: discord.Interaction, channel_name: str):
        """Retirer une chaîne YouTube de la liste de surveillance."""
        locale = get_locale(interaction)
        if not channel_name:
            channels = await asyncio.to_thread(_db_list_channel_names)
            if not channels:
                await interaction.response.send_message(
                    t("youtube.remove_none", locale)
                )
                return
            channel_list = "\n".join([c[0] for c in channels])
            await interaction.response.send_message(
                t("youtube.remove_specify", locale, list=channel_list)
            )
            return

        # Retirer la chaîne de la base de données
        rows_affected = await asyncio.to_thread(_db_remove_channel, channel_name)

        if rows_affected > 0:
            await interaction.response.send_message(
                t("youtube.removed", locale, name=channel_name)
            )
        else:
            await interaction.response.send_message(
                t("youtube.remove_not_found", locale, name=channel_name)
            )


class CheckYouTubeChannel:
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
        if handle.startswith("@"):
            handle = handle[1:]

        # Méthode 1: Essayer avec le paramètre forHandle (pour les nouveaux handles)
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "id,snippet", "forHandle": handle, "key": self.api_key}

        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if "items" in data and len(data["items"]) > 0:
                    return {
                        "id": data["items"][0]["id"],
                        "snippet": data["items"][0]["snippet"],
                    }
            elif response.status == 400:
                # Si forHandle ne fonctionne pas, essayer forUsername (ancienne méthode)
                logger.debug(
                    "forHandle method failed (400), will try forUsername method"
                )
            else:
                # Autre erreur
                error_data = (
                    await response.json()
                    if response.content_type == "application/json"
                    else {}
                )
                error_msg = error_data.get("error", {}).get(
                    "message", f"Status {response.status}"
                )
                raise Exception(f"Erreur API YouTube: {error_msg}")

        # Méthode 2: Essayer avec le paramètre forUsername (pour les anciens usernames)
        params = {"part": "id,snippet", "forUsername": handle, "key": self.api_key}

        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if "items" in data and len(data["items"]) > 0:
                    return {
                        "id": data["items"][0]["id"],
                        "snippet": data["items"][0]["snippet"],
                    }
            else:
                logger.debug(
                    f"Méthode forUsername échouée pour '{handle}' (status {response.status})"
                )

        # Méthode 3: Utiliser l'API de recherche comme dernier recours
        search_url = "https://www.googleapis.com/youtube/v3/search"
        search_params = {
            "part": "snippet",
            "q": original_handle,
            "type": "channel",
            "maxResults": 1,
            "key": self.api_key,
        }

        async with self.session.get(search_url, params=search_params) as response:
            if response.status == 200:
                data = await response.json()
                if "items" in data and len(data["items"]) > 0:
                    channel_id = data["items"][0]["snippet"]["channelId"]
                    # Récupérer les informations complètes du channel
                    return await self.get_channel_info_by_id(channel_id)
            else:
                logger.debug(
                    f"Méthode search échouée pour '{original_handle}' (status {response.status})"
                )

        logger.warning(
            f"Aucune chaîne YouTube trouvée pour le handle '{original_handle}' "
            f"(essayé forHandle, forUsername et search)"
        )
        return None

    async def get_channel_info_by_id(self, channel_id: str):
        """Récupérer les informations complètes d'une chaîne par son ID."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")

        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "id,snippet", "id": channel_id, "key": self.api_key}

        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(
                    f"Erreur lors de la vérification de la chaîne: {response.status}"
                )
            data = await response.json()
            if "items" in data and len(data["items"]) > 0:
                return {
                    "id": data["items"][0]["id"],
                    "snippet": data["items"][0]["snippet"],
                }
            return None

    async def get_channel_info(self, channel_id: str):
        """Récupérer les informations d'une chaîne YouTube."""
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")

        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "snippet", "id": channel_id, "key": self.api_key}

        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(
                    f"Erreur lors de la récupération des informations de la chaîne: {response.status}"
                )
            data = await response.json()
            if "items" in data and len(data["items"]) > 0:
                return data["items"][0]["snippet"]
            return None

    async def get_latest_uploads(self, channel_id: str, max_results: int = 5):
        """Récupérer les dernières vidéos d'une chaîne YouTube.

        Note: YouTube API returns playlist items in reverse chronological order
        (newest first). This ordering is relied upon in check_youtube_loop() for
        date-based filtering and early stopping optimizations.
        """
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")

        # D'abord, obtenir l'ID de la playlist d'uploads
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "contentDetails", "id": channel_id, "key": self.api_key}

        async with self.session.get(url, params=params) as response:
            if response.status == 404:
                # Le canal n'existe pas ou n'est pas accessible
                logger.warning(f"Canal YouTube introuvable (404): {channel_id}")
                return []
            if response.status != 200:
                try:
                    error_data = (
                        await response.json()
                        if response.content_type == "application/json"
                        else {}
                    )
                except (aiohttp.ContentTypeError, ValueError):
                    error_data = {}
                error_msg = error_data.get("error", {}).get(
                    "message", f"Status {response.status}"
                )
                raise Exception(
                    f"Erreur lors de la récupération de l'ID de playlist: {error_msg}"
                )
            try:
                data = await response.json()
            except Exception as e:
                logger.error(
                    f"Erreur lors du parsing JSON pour le canal {channel_id}: {e}"
                )
                return []
            if "items" not in data or len(data["items"]) == 0:
                logger.info(f"Aucune donnée de canal trouvée pour: {channel_id}")
                return []
            uploads_playlist_id = data["items"][0]["contentDetails"][
                "relatedPlaylists"
            ]["uploads"]

        # Ensuite, récupérer les vidéos de la playlist
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "part": "snippet",
            "playlistId": uploads_playlist_id,
            "maxResults": max_results,
            "key": self.api_key,
        }

        async with self.session.get(url, params=params) as response:
            if response.status == 404:
                # La playlist n'existe pas ou est vide
                logger.warning(
                    f"Playlist d'uploads introuvable (404) pour le canal: {channel_id}"
                )
                return []
            if response.status != 200:
                try:
                    error_data = (
                        await response.json()
                        if response.content_type == "application/json"
                        else {}
                    )
                except (aiohttp.ContentTypeError, ValueError):
                    error_data = {}
                error_msg = error_data.get("error", {}).get(
                    "message", f"Status {response.status}"
                )
                raise Exception(
                    f"Erreur lors de la récupération des vidéos: {error_msg}"
                )
            try:
                data = await response.json()
            except Exception as e:
                logger.error(
                    f"Erreur lors du parsing JSON de la playlist {uploads_playlist_id}: {e}"
                )
                return []
            return data.get("items", [])

    async def get_video_details_batch(self, video_ids: list) -> dict:
        """Récupérer les détails de plusieurs vidéos en un seul appel API.

        Utilise ``videos.list`` avec plusieurs IDs (coût: 1 unité de quota au
        lieu d'un appel par vidéo) et retourne un mapping {video_id: item}.

        Retourne un dict vide en cas d'erreur (les appelants ignorent alors
        les vidéos manquantes).
        """
        video_ids = [vid for vid in video_ids if vid]
        if not video_ids:
            return {}
        if not self.api_key:
            raise ValueError("La clé API YouTube n'est pas configurée.")

        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,contentDetails,liveStreamingDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }

        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    try:
                        error_data = (
                            await response.json()
                            if response.content_type == "application/json"
                            else {}
                        )
                    except (aiohttp.ContentTypeError, ValueError):
                        error_data = {}
                    error_msg = error_data.get("error", {}).get(
                        "message", f"Status {response.status}"
                    )
                    logger.error(
                        f"Erreur lors de la récupération des détails vidéos: {error_msg}"
                    )
                    return {}

                data = await response.json()
                return {item["id"]: item for item in data.get("items", [])}
        except (aiohttp.ContentTypeError, ValueError) as e:
            logger.error(f"Erreur lors du parsing JSON des détails vidéos: {e}")
            return {}


def is_short(video_duration: str) -> bool:
    """Déterminer si une vidéo est un short basé sur sa durée (moins de 61 secondes)."""
    # Format de durée ISO 8601: PT#H#M#S ou PT#M#S ou PT#S
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", video_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds <= 60
    return False


class AnnounceYouTube:
    """Classe pour annoncer les nouveaux contenus YouTube."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_role(self, channel_id: str):
        """Récupérer le rôle à mentionner pour les annonces."""

        def _do():
            conn = database.get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT roleId FROM youtube_channels WHERE channelId = ?",
                    (channel_id,),
                )
                return cursor.fetchone()
            finally:
                conn.close()

        result = await asyncio.to_thread(_do)
        if result and result[0]:
            return discord.utils.get(self.bot.guilds[0].roles, id=int(result[0]))
        return None

    async def announce_video(
        self,
        channel_id: str,
        channel_name: str,
        discord_channel: discord.TextChannel,
        video_id: str,
        video_title: str,
        thumbnail_url: str,
        discord_role: Optional[discord.Role] = None,
    ):
        """Annoncer une nouvelle vidéo dans un salon Discord."""
        if discord_role is None:
            discord_role = await self.get_role(channel_id)

        embed = discord.Embed(
            title=t("youtube.new_video_title", None, title=video_title),
            description=t(
                "youtube.new_video_desc",
                None,
                name=channel_name,
                url=f"https://www.youtube.com/watch?v={video_id}",
            ),
            color=discord.Color.red(),
        )
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)

        if discord_role is not None:
            await discord_channel.send(content=discord_role.mention, embed=embed)
        else:
            await discord_channel.send(embed=embed)

    async def announce_short(
        self,
        channel_id: str,
        channel_name: str,
        discord_channel: discord.TextChannel,
        video_id: str,
        video_title: str,
        thumbnail_url: str,
        discord_role: Optional[discord.Role] = None,
    ):
        """Annoncer un nouveau short dans un salon Discord."""
        if discord_role is None:
            discord_role = await self.get_role(channel_id)

        embed = discord.Embed(
            title=t("youtube.new_short_title", None, title=video_title),
            description=t(
                "youtube.new_short_desc",
                None,
                name=channel_name,
                url=f"https://www.youtube.com/shorts/{video_id}",
            ),
            color=discord.Color.orange(),
        )
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)

        if discord_role is not None:
            await discord_channel.send(content=discord_role.mention, embed=embed)
        else:
            await discord_channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(YouTube(bot))
