# Importation des bibliothèques et modules
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import signal
import sqlite3
import sys

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database

# ============================================================================
# GameVox Configuration - Support for running on GameVox platform
# ============================================================================
# The bot supports both Discord and GameVox platforms.
# Configure your platform using the PLATFORM environment variable:
#   PLATFORM=discord  (default - connect to Discord)
#   PLATFORM=gamevox  (connect to GameVox)
# See the configuration section below for more details.


# Répertoire racine du bot
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# Synchroniser le fichier .env avec .env.example avant le chargement
def ensure_env_variables():
    """Ajoute les variables manquantes dans .env à partir de .env.example."""
    env_path = os.path.join(_SCRIPT_DIR, ".env")
    env_example_path = os.path.join(_SCRIPT_DIR, ".env.example")

    if not os.path.exists(env_example_path):
        return

    # Lire les clés et valeurs par défaut depuis .env.example
    example_entries = {}
    with open(env_example_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                value = stripped.split("=", 1)[1].strip()
                example_entries[key] = value

    # Lire les clés existantes dans .env
    existing_keys = set()
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)

    # Ajouter les variables manquantes
    missing = {k: v for k, v in example_entries.items() if k not in existing_keys}
    if missing:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n# Variables ajoutées automatiquement depuis .env.example\n")
            for key, value in missing.items():
                f.write(f"{key}={value}\n")


ensure_env_variables()

# Chargement du fichier .env
load_dotenv()

# Configure logging using the new logging system
from utils.logging_config import setup_logging, get_logger

# Setup logging with rotation and configurable levels
setup_logging()
logger = get_logger(__name__)

# Log des variables .env synchronisées
if os.path.exists(os.path.join(_SCRIPT_DIR, ".env.example")):
    logger.debug("Fichier .env synchronisé avec .env.example")


def validate_environment_variables():
    """Valide que toutes les variables d'environnement requises sont définies."""
    # Determine platform
    platform = os.getenv("PLATFORM", "discord").lower()

    # Common required variables for both platforms
    required_vars = {
        "db_path": "Le chemin de la base de données est requis",
    }

    # Platform-specific required variables
    if platform == "gamevox":
        required_vars.update({
            "app_id": "L'ID de l'application GameVox est requis",
            "gamevox_bot_token": "Le token du bot GameVox est requis",
            "server_id": "L'ID du serveur GameVox est requis",
        })
    else:
        # Discord is the default
        required_vars.update({
            "app_id": "L'ID de l'application Discord est requis",
            "secret_key": "Le token du bot Discord est requis",
            "server_id": "L'ID du serveur Discord est requis",
        })

    missing_vars = []
    invalid_vars = []

    for var_name, error_msg in required_vars.items():
        value = os.getenv(var_name)
        if not value:
            missing_vars.append(f"  - {var_name}: {error_msg}")
        elif var_name in ["app_id", "server_id"]:
            # Valider que les IDs sont des nombres valides
            try:
                int_value = int(value)
                if int_value <= 0:
                    invalid_vars.append(f"  - {var_name}: Doit être un nombre positif")
            except ValueError:
                invalid_vars.append(f"  - {var_name}: Doit être un nombre valide")

    if missing_vars or invalid_vars:
        error_message = "❌ Erreur de configuration:\n"
        if missing_vars:
            error_message += "\nVariables manquantes:\n" + "\n".join(missing_vars)
        if invalid_vars:
            error_message += "\nVariables invalides:\n" + "\n".join(invalid_vars)
        error_message += "\n\nVeuillez vérifier votre fichier .env et vous assurer que toutes les variables requises sont définies correctement."
        raise ValueError(error_message)


# Valider les variables d'environnement au démarrage
try:
    validate_environment_variables()
except ValueError as e:
    logger.critical(f"Erreur de validation des variables d'environnement: {e}")
    sys.exit(1)

# Récupération des variables d'environnement
APP_ID = int(os.getenv("app_id", "0"))
TOKEN = os.getenv("secret_key")
SERVER_ID = int(os.getenv("server_id", "0"))
DB_PATH = os.getenv("db_path")

# ============================================================================
# Platform Configuration (Discord or GameVox)
# ============================================================================
# NOTE: This configuration MUST happen before the ISROBOT client is instantiated
# (which occurs much later in the file). Modifying discord.py's global state here
# ensures it uses the correct API endpoints when the client is created.

# API version for both Discord and GameVox
# Both platforms use the same Discord-compatible API version (v10)
API_VERSION = "v10"
API_VERSION_NUM = API_VERSION.lstrip("v")

# GameVox API endpoints
GAMEVOX_API_BASE = "https://bot-api.gamevox.com"
GAMEVOX_GATEWAY_BASE = "wss://gateway.gamevox.com"

# Determine platform from environment
PLATFORM = os.getenv("PLATFORM", "discord").lower()
GAMEVOX_BOT_TOKEN = os.getenv("gamevox_bot_token")

# Configure discord.py for GameVox if PLATFORM is set to gamevox
if PLATFORM == "gamevox":
    logger.info("🎮 Configuring bot for GameVox platform")

    # Set the REST API base URL to GameVox
    discord.http.Route.BASE = f"{GAMEVOX_API_BASE}/api/{API_VERSION}"

    # Set the Gateway WebSocket URL to GameVox
    discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY = (
        f"{GAMEVOX_GATEWAY_BASE}/?v={API_VERSION_NUM}&encoding=json"
    )

    # Use GameVox token (validation already done in validate_environment_variables)
    # Note: TOKEN is used throughout the rest of the file to pass to client.run()
    TOKEN = GAMEVOX_BOT_TOKEN
    logger.info("✅ GameVox bot token configured")
else:
    logger.info("🤖 Configuring bot for Discord platform")

# Configuration des intents - Optimisé pour réduire la charge WebSocket
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
# Désactiver les intents non nécessaires pour réduire la charge
intents.presences = False
intents.typing = False
intents.reactions = False


# --- Événements du bot ---


class ISROBOT(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="µ", intents=intents, application_id=APP_ID)
        self.session = None
        self.voice_xp_tasks = {}
        # Lock dictionary for counter game to prevent race conditions
        # Key: (guild_id, channel_id), Value: asyncio.Lock()
        # Note: This grows with new channels but counter games are typically
        # limited to one per guild, so memory impact is minimal
        self._counter_locks: dict[tuple[str, str], asyncio.Lock] = {}

    def _get_counter_lock(self, guild_id: str, channel_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific counter game channel.

        Args:
            guild_id: The guild ID
            channel_id: The channel ID

        Returns:
            An asyncio.Lock for this guild/channel combination
        """
        key = (guild_id, channel_id)
        if key not in self._counter_locks:
            self._counter_locks[key] = asyncio.Lock()
        return self._counter_locks[key]

    async def setup_hook(self):
        # Créer une session HTTP pour les requêtes API avec timeout
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)
        self.session = aiohttp.ClientSession(timeout=timeout)

        # Configure global error handler for app commands
        self.tree.on_error = self.on_app_command_error

        # Lancer le script database.py pour créer la base de données
        logger.info("Initialisation de la base de données...")
        try:
            import database

            database.create_database()
            logger.info("Base de données initialisée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")

        # Exécuter les migrations pour mettre à jour la base de données
        logger.info("Vérification des migrations de la base de données...")
        try:
            import db_migrations

            db_migrations.run_all_migrations()
            logger.info("Migrations de la base de données terminées avec succès")
        except Exception as e:
            logger.error(f"Erreur lors des migrations de la base de données: {e}")

        # Supprimer toutes les commandes /
        self.tree.clear_commands(guild=None)
        logger.debug("Commandes existantes vidées")

        # Parcourir les fichiers contenant des commandes
        commands_path = Path("commands/")
        for file in commands_path.glob("*.py"):
            if file.name.startswith("_"):
                continue
            # Charger le module comme extension
            module_name = f"commands.{file.stem}"
            try:
                await self.load_extension(module_name)
                logger.debug(f"Extension {module_name} chargée avec succès")
            except Exception as e:
                logger.error(f"Erreur lors du chargement de {module_name}: {e}")

        # Synchroniser les commandes avec Discord
        try:
            # Synchronisation globale (peut prendre jusqu'à 1 heure)
            synced_global = await self.tree.sync()
            logger.info(f"{len(synced_global)} commande(s) synchronisée(s) globalement")

            # Synchronisation sur le serveur spécifique (instantané)
            synced_guild = await self.tree.sync(guild=discord.Object(id=SERVER_ID))
            logger.info(f"{len(synced_guild)} commande(s) synchronisée(s) avec le serveur")

        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation: {e}", exc_info=True)

        # Vérifie si le minijeux du compteur est configuré
        try:
            import database

            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM counter_game WHERE guildId = ?", (str(SERVER_ID),)
            )
            result = cursor.fetchone()
            if result:
                logger.debug("Le minijeux du compteur est déjà configuré")
            else:
                logger.debug("Le minijeux du compteur n'est pas configuré")
            conn.close()
        except Exception as e:
            logger.error(
                f"Erreur lors de la vérification du minijeux du compteur: {e}",
                exc_info=True
            )

        # Démarrer la tâche de vérification des streams en arrière-plan
        self.stream_check_task = self.loop.create_task(self.check_streams_loop())

        # Démarrer la tâche de vérification YouTube en arrière-plan
        self.youtube_check_task = self.loop.create_task(self.check_youtube_loop())

        # Démarrer les tâches de modération en arrière-plan
        self.warning_decay_task = self.loop.create_task(self.warning_decay_loop())
        self.mute_expiration_task = self.loop.create_task(self.mute_expiration_loop())

        # Démarrer la tâche de sauvegarde automatique
        self.backup_task = self.loop.create_task(self.scheduled_backup_loop())

        # Démarrer la tâche de nettoyage du rate limiter
        self.rate_limit_cleanup_task = self.loop.create_task(self.rate_limit_cleanup_loop())

    async def check_streams_loop(self):
        """Vérifier périodiquement le statut des streamers."""
        await self.wait_until_ready()  # Attendre que le bot soit prêt
        logger.info("Démarrage de la boucle de vérification Twitch")

        while not self.is_closed():
            try:
                from commands.stream import CheckTwitchStatus

                if self.session:
                    stream_checker = CheckTwitchStatus(self.session)

                    # Récupérer tous les streamers de la base de données
                    conn = database.get_db_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM streamers")
                        streamers = cursor.fetchall()
                    finally:
                        conn.close()

                    logger.debug(f"[Twitch] Vérification de {len(streamers)} streamer(s)")

                    for streamer in streamers:
                        try:
                            # Database schema: streamers table
                            # [0]=id, [1]=streamerName, [2]=streamChannelId,
                            # [3]=roleId, [4]=announced, [5]=startTime

                            streamer_id = streamer[0]
                            streamer_name = streamer[1]
                            stream_channel_id = streamer[2]
                            announced = streamer[4]

                            logger.debug(
                                f"[Twitch] Vérification du statut de {streamer_name}"
                            )

                            # Vérifier si le streamer est en ligne
                            stream_data = await stream_checker.check_streamer_status(
                                streamer_name
                            )
                            if (
                                stream_data and len(stream_data) > 0
                            ):  # Si des données sont retournées, le streamer est en ligne
                                logger.debug(
                                    f"[Twitch] {streamer_name} est actuellement en ligne"
                                )
                                # Vérifier si on a déjà annoncé ce stream
                                if announced == 0:
                                    channel = self.get_channel(int(stream_channel_id))
                                    if channel and isinstance(
                                        channel, discord.TextChannel
                                    ):
                                        from commands.stream import AnnounceStream

                                        announcer = AnnounceStream(self)
                                        # stream_data est une liste, on prend le premier élément
                                        stream_info = stream_data[0]
                                        stream_title = stream_info.get(
                                            "title", "Stream en direct"
                                        )
                                        category = stream_info.get(
                                            "game_name", "Inconnu"
                                        )
                                        await announcer.announce(
                                            streamer_name,
                                            channel,
                                            stream_title,
                                            category,
                                        )

                                        # Marquer comme annoncé
                                        conn = database.get_db_connection()
                                        try:
                                            cursor = conn.cursor()
                                            cursor.execute(
                                                "UPDATE streamers SET announced = 1 WHERE id = ?",
                                                (streamer_id,),
                                            )
                                            conn.commit()
                                            logger.info(
                                                f"Annonce envoyée pour le streamer {streamer_name}"
                                            )
                                        finally:
                                            conn.close()
                                else:
                                    logger.debug(
                                        f"[Twitch] {streamer_name} est en ligne mais "
                                        f"déjà annoncé"
                                    )
                            else:
                                logger.debug(
                                    f"[Twitch] {streamer_name} n'est pas en ligne"
                                )
                                # Le streamer n'est pas en ligne, réinitialiser le statut d'annonce
                                if announced == 1:  # Si était annoncé
                                    conn = database.get_db_connection()
                                    try:
                                        cursor = conn.cursor()
                                        cursor.execute(
                                            "UPDATE streamers SET announced = 0 WHERE id = ?",
                                            (streamer_id,),
                                        )
                                        conn.commit()
                                        logger.debug(
                                            f"Statut réinitialisé pour le streamer {streamer_name}"
                                        )
                                    finally:
                                        conn.close()
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"Timeout lors de la vérification du streamer {streamer[1]}"
                            )
                        except aiohttp.ClientError as e:
                            logger.error(
                                f"Erreur réseau lors de la vérification du streamer {streamer[1]}: {e}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Erreur lors de la vérification du streamer {streamer[1]}: {e}"
                            )

            except asyncio.TimeoutError:
                logger.warning("Timeout global lors de la vérification des streams Twitch")
            except aiohttp.ClientError as e:
                logger.error(f"Erreur réseau lors de la vérification des streams: {e}")
            except sqlite3.Error as e:
                logger.error(f"Erreur de base de données lors de la vérification des streams: {e}")
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des streams: {e}")

            # Attendre 5 minutes avant la prochaine vérification
            # Note: Rate limiting naturel via intervalle de 5min entre vérifications
            # qui garantit le respect des limites de l'API Twitch
            await asyncio.sleep(300)

    def _is_recently_published(self, published_at_str: str, hours: int = 24) -> bool:
        """Check if content was published within the specified number of hours.

        Args:
            published_at_str: ISO 8601 timestamp string from YouTube API (e.g., "2025-12-20T12:00:00Z")
            hours: Number of hours to consider as "recent" (default: 24)

        Returns:
            True if published within the specified hours, False otherwise
        """
        try:
            # Parse the ISO 8601 timestamp from YouTube API
            # YouTube API always returns timestamps in format: YYYY-MM-DDTHH:MM:SSZ
            # The 'Z' suffix indicates UTC timezone and is replaced with '+00:00' for Python's fromisoformat()
            published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            time_diff = now - published_at

            return time_diff <= timedelta(hours=hours)
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error parsing published date '{published_at_str}': {e}")
            # If we can't parse the date, assume it's old to be safe
            return False

    async def check_youtube_loop(self):
        """Vérifier périodiquement les nouvelles vidéos et shorts YouTube."""
        await self.wait_until_ready()  # Attendre que le bot soit prêt
        logger.info("Démarrage de la boucle de vérification YouTube")

        while not self.is_closed():
            try:
                from commands.youtube import (
                    AnnounceYouTube,
                    CheckYouTubeChannel,
                    is_short,
                )

                if self.session:
                    youtube_checker = CheckYouTubeChannel(self.session)

                    # Récupérer toutes les chaînes YouTube de la base de données
                    conn = database.get_db_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM youtube_channels")
                        channels = cursor.fetchall()
                    finally:
                        conn.close()

                    logger.debug(f"[YouTube] Vérification de {len(channels)} chaîne(s)")

                    for channel_data in channels:
                        try:
                            channel_id = channel_data[1]  # channelId
                            channel_name = channel_data[2]  # channelName
                            discord_channel_id = int(
                                channel_data[3]
                            )  # discordChannelId
                            last_video_id = channel_data[5]  # lastVideoId
                            last_short_id = channel_data[6]  # lastShortId
                            notify_videos = channel_data[8]  # notifyVideos
                            notify_shorts = channel_data[9]  # notifyShorts

                            logger.debug(
                                f"[YouTube] Vérification de {channel_name} "
                                f"(vidéos={bool(notify_videos)}, "
                                f"shorts={bool(notify_shorts)})"
                            )

                            discord_channel = self.get_channel(discord_channel_id)
                            if not discord_channel or not isinstance(
                                discord_channel, discord.TextChannel
                            ):
                                logger.warning(
                                    f"Canal Discord introuvable ou invalide pour {channel_name}: {discord_channel_id}"
                                )
                                continue

                            # Vérifier les permissions du bot dans le canal Discord
                            if discord_channel.guild and discord_channel.guild.me:
                                permissions = discord_channel.permissions_for(
                                    discord_channel.guild.me
                                )
                                if not permissions.send_messages:
                                    logger.warning(
                                        f"Permission manquante pour envoyer des messages dans {discord_channel.name} (ID: {discord_channel_id}) pour la chaîne YouTube {channel_name}"
                                    )
                                    continue
                                if not permissions.embed_links:
                                    logger.warning(
                                        f"Permission manquante pour envoyer des embeds dans {discord_channel.name} (ID: {discord_channel_id}) pour la chaîne YouTube {channel_name}"
                                    )
                                    continue

                            announcer = AnnounceYouTube(self)

                            # Vérifier si au moins un type de notification est activé
                            if not notify_videos and not notify_shorts:
                                logger.warning(
                                    f"[YouTube] Aucune notification activée pour {channel_name}"
                                )
                                continue

                            # Vérifier les nouvelles vidéos et shorts
                            if notify_videos or notify_shorts:
                                logger.debug(
                                    f"[YouTube] Vérification des uploads pour "
                                    f"{channel_name} (vidéos: {notify_videos}, "
                                    f"shorts: {notify_shorts})"
                                )
                                try:
                                    latest_uploads = (
                                        await youtube_checker.get_latest_uploads(
                                            channel_id, max_results=3
                                        )
                                    )

                                    # Track the newest content to announce (only one of each type per cycle)
                                    newest_video_to_announce = None
                                    newest_short_to_announce = None

                                    # Track the most recent IDs we've seen (to update in DB)
                                    most_recent_video_id = last_video_id
                                    most_recent_short_id = last_short_id

                                    # Track if we've found the last known content (to stop checking older content)
                                    found_last_video = False
                                    found_last_short = False

                                    if not latest_uploads:
                                        logger.debug(
                                            f"[YouTube] Aucune vidéo trouvée pour "
                                            f"{channel_name}"
                                        )
                                    else:
                                        logger.debug(
                                            f"[YouTube] {len(latest_uploads)} vidéo(s) "
                                            f"trouvée(s) pour {channel_name}"
                                        )

                                    # First pass: identify all new content and find the newest of each type
                                    for upload in latest_uploads:
                                        video_id = upload["snippet"]["resourceId"][
                                            "videoId"
                                        ]

                                        # Get the published date from the upload snippet
                                        published_at = upload["snippet"].get("publishedAt", "")

                                        # Check if the content was published recently (within 24 hours)
                                        # Note: We rely on YouTube API returning items in reverse chronological order
                                        # (newest first). Since the API returns both videos and shorts mixed together
                                        # in the uploads playlist, if an item is older than 24h, ALL subsequent items
                                        # will also be older (regardless of type), so we can safely break.
                                        if not self._is_recently_published(published_at, hours=24):
                                            logger.debug(
                                                f"[YouTube] Contenu ignoré car trop ancien pour "
                                                f"{channel_name}: {video_id} (date: {published_at})"
                                            )
                                            # Stop checking: all subsequent items will be older than this one
                                            break

                                        # Récupérer les détails de la vidéo pour déterminer si c'est un short
                                        video_details = (
                                            await youtube_checker.get_video_details(
                                                video_id
                                            )
                                        )
                                        if not video_details:
                                            logger.warning(
                                                f"[YouTube] Impossible de récupérer les détails "
                                                f"de la vidéo {video_id}"
                                            )
                                            continue

                                        video_title = video_details["snippet"]["title"]
                                        thumbnail_url = video_details["snippet"][
                                            "thumbnails"
                                        ]["high"]["url"]
                                        duration = video_details["contentDetails"][
                                            "duration"
                                        ]

                                        is_short_video = is_short(duration)
                                        content_type = (
                                            "short" if is_short_video else "vidéo"
                                        )

                                        logger.debug(
                                            f"[YouTube] Vérification: {content_type} "
                                            f"'{video_title[:50]}' (ID: {video_id[:8]})"
                                        )

                                        # Process shorts
                                        if is_short_video:
                                            # Check if this is the last known short (stop checking older shorts)
                                            if video_id == last_short_id:
                                                found_last_short = True
                                                logger.debug(
                                                    f"[YouTube] Short déjà connu trouvé "
                                                    f"(ID: {video_id[:8]}) - arrêt"
                                                )
                                                # Continue to check remaining uploads (may still have new videos)
                                                continue

                                            # Skip if we've already found the last known short
                                            if found_last_short:
                                                logger.debug(
                                                    f"[YouTube] Short ignoré (plus ancien): {video_id[:8]}"
                                                )
                                                continue

                                            # Check if this is new content (not previously announced)
                                            if notify_shorts:
                                                # Update the most recent short ID only if this is new content
                                                # Since YouTube API returns newest first, only update on first new short
                                                # This ensures we track the newest short, not an older one
                                                if (
                                                    most_recent_short_id
                                                    == last_short_id
                                                ):
                                                    most_recent_short_id = video_id

                                                # Only announce if we haven't already selected one to announce
                                                if newest_short_to_announce is None:
                                                    logger.debug(
                                                        f"[YouTube] Nouveau short détecté pour "
                                                        f"{channel_name}: {video_id}"
                                                    )
                                                    newest_short_to_announce = {
                                                        "video_id": video_id,
                                                        "video_title": video_title,
                                                        "thumbnail_url": thumbnail_url,
                                                    }
                                                else:
                                                    logger.debug(
                                                        f"[YouTube] Short ignoré (un plus récent sera annoncé): {video_id[:8]}"
                                                    )
                                            elif not notify_shorts:
                                                logger.debug(
                                                    "[YouTube] Short ignoré (notifications désactivées)"
                                                )

                                        # Process regular videos
                                        else:
                                            # Check if this is the last known video (stop checking older videos)
                                            if video_id == last_video_id:
                                                found_last_video = True
                                                logger.debug(
                                                    f"[YouTube] Vidéo déjà connue trouvée "
                                                    f"(ID: {video_id[:8]}) - arrêt"
                                                )
                                                # Continue to check remaining uploads (may still have new shorts)
                                                continue

                                            # Skip if we've already found the last known video
                                            if found_last_video:
                                                logger.debug(
                                                    f"[YouTube] Vidéo ignorée (plus ancienne): {video_id[:8]}"
                                                )
                                                continue

                                            # Check if this is new content (not previously announced)
                                            if notify_videos:
                                                # Update the most recent video ID only if this is new content
                                                # Since YouTube API returns newest first, only update on first new video
                                                # This ensures we track the newest video, not an older one
                                                if (
                                                    most_recent_video_id
                                                    == last_video_id
                                                ):
                                                    most_recent_video_id = video_id

                                                # Only announce if we haven't already selected one to announce
                                                if newest_video_to_announce is None:
                                                    logger.debug(
                                                        f"[YouTube] Nouvelle vidéo détectée pour "
                                                        f"{channel_name}: {video_id}"
                                                    )
                                                    newest_video_to_announce = {
                                                        "video_id": video_id,
                                                        "video_title": video_title,
                                                        "thumbnail_url": thumbnail_url,
                                                    }
                                                else:
                                                    logger.debug(
                                                        f"[YouTube] Vidéo ignorée (une plus récente sera annoncée): {video_id[:8]}"
                                                    )
                                            elif not notify_videos:
                                                logger.debug(
                                                    "[YouTube] Vidéo ignorée (notifications désactivées)"
                                                )

                                    # Second pass: update database with most recent IDs and announce new content
                                    # Update database with the most recent IDs we found
                                    if (
                                        most_recent_video_id != last_video_id
                                        or most_recent_short_id != last_short_id
                                    ):
                                        conn = database.get_db_connection()
                                        try:
                                            cursor = conn.cursor()

                                            # Update both IDs in a single query to maintain consistency
                                            cursor.execute(
                                                "UPDATE youtube_channels SET lastVideoId = ?, lastShortId = ? WHERE id = ?",
                                                (
                                                    most_recent_video_id,
                                                    most_recent_short_id,
                                                    channel_data[0],
                                                ),
                                            )
                                            conn.commit()
                                            logger.info(
                                                f"IDs mis à jour pour {channel_name}: "
                                                f"lastVideoId={most_recent_video_id}, "
                                                f"lastShortId={most_recent_short_id}"
                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Erreur lors de la mise à jour des IDs pour {channel_name}: {e}"
                                            )
                                        finally:
                                            conn.close()

                                    # Announce the newest short if we found one
                                    if newest_short_to_announce:
                                        try:
                                            await announcer.announce_short(
                                                channel_id,
                                                channel_name,
                                                discord_channel,
                                                newest_short_to_announce["video_id"],
                                                newest_short_to_announce["video_title"],
                                                newest_short_to_announce[
                                                    "thumbnail_url"
                                                ],
                                            )
                                            logger.info(
                                                f"Annonce short envoyée pour {channel_name}"
                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Erreur lors de l'annonce du short pour {channel_name}: {e}"
                                            )

                                    # Announce the newest video if we found one
                                    if newest_video_to_announce:
                                        try:
                                            await announcer.announce_video(
                                                channel_id,
                                                channel_name,
                                                discord_channel,
                                                newest_video_to_announce["video_id"],
                                                newest_video_to_announce["video_title"],
                                                newest_video_to_announce[
                                                    "thumbnail_url"
                                                ],
                                            )
                                            logger.info(
                                                f"Annonce vidéo envoyée pour {channel_name}"
                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Erreur lors de l'annonce de la vidéo pour {channel_name}: {e}"
                                            )

                                except discord.errors.Forbidden as e:
                                    logger.error(
                                        f"Permission Discord refusée pour {channel_name} lors de l'annonce d'une vidéo/short: {e}"
                                    )
                                except asyncio.TimeoutError:
                                    logger.warning(
                                        f"Timeout lors de la vérification des uploads pour {channel_name}"
                                    )
                                except aiohttp.ClientError as e:
                                    logger.error(
                                        f"Erreur réseau lors de la vérification des uploads pour {channel_name}: {e}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Erreur lors de la vérification des uploads pour {channel_name}: {e}"
                                    )

                        except asyncio.TimeoutError:
                            logger.warning(
                                f"Timeout lors de la vérification de la chaîne {channel_data[2]}"
                            )
                        except aiohttp.ClientError as e:
                            logger.error(
                                f"Erreur réseau lors de la vérification de la chaîne {channel_data[2]}: {e}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Erreur lors de la vérification de la chaîne {channel_data[2]}: {e}"
                            )

            except asyncio.TimeoutError:
                logger.warning("Timeout global lors de la vérification YouTube")
            except aiohttp.ClientError as e:
                logger.error(f"Erreur réseau lors de la vérification YouTube: {e}")
            except sqlite3.Error as e:
                logger.error(f"Erreur de base de données lors de la vérification YouTube: {e}")
            except Exception as e:
                error_msg = str(e)
                # Détecter les erreurs de quota
                if "quota" in error_msg.lower() or "403" in error_msg:
                    logger.error(
                        f"[YouTube] QUOTA API DÉPASSÉ! Vérification ignorée. "
                        f"Le quota se réinitialise à minuit PST. Erreur: {e}"
                    )
                else:
                    logger.error(f"[YouTube] Erreur lors de la vérification: {e}")

            # Attendre 10 minutes avant la prochaine vérification
            # Note: Rate limiting naturel via intervalle de 10min entre vérifications
            # optimisé pour respecter le quota YouTube API (~9500 unités/jour)
            # En cas de dépassement de quota, la boucle continue mais les erreurs sont loggées
            await asyncio.sleep(600)

    async def warning_decay_loop(self):
        """
        Vérifier périodiquement et faire expirer les avertissements.

        Note: There's a theoretical race condition if a moderator manually
        decrements warnings while this loop is running. However, this is
        acceptable because:
        - The loop runs only every 6 hours
        - Manual decrements are rare
        - Database operations are atomic
        - Worst case: warning decays one cycle later
        """
        await self.wait_until_ready()
        logger.info("Démarrage de la boucle d'expiration des avertissements")

        while not self.is_closed():
            try:
                from utils import moderation_utils

                # Get users whose warnings should decay
                users_to_decay = moderation_utils.get_users_for_decay()

                logger.debug(f"[Modération] Vérification de {len(users_to_decay)} utilisateurs pour expiration")

                for user_data in users_to_decay:
                    try:
                        guild_id = user_data["guild_id"]
                        user_id = user_data["user_id"]
                        warn_count = user_data["warn_count"]

                        # Decrement warning
                        new_count = moderation_utils.decrement_warning(
                            guild_id, user_id, None, "Expiration automatique"
                        )

                        logger.info(f"[Modération] Avertissement expiré: {user_id} @ {guild_id} ({warn_count} -> {new_count})")

                        # If warnings reach 0, remove active mute
                        if new_count == 0:
                            active_mute = moderation_utils.get_active_mute(guild_id, user_id)
                            if active_mute:
                                guild = self.get_guild(int(guild_id))
                                if guild:
                                    member = guild.get_member(int(user_id))
                                    if member:
                                        try:
                                            await member.timeout(None, reason="Avertissements expirés")
                                            moderation_utils.remove_mute(
                                                guild_id, user_id, None, "Avertissements expirés"
                                            )
                                            logger.info(f"Mute retiré pour {user_id} @ {guild_id}")
                                        except Exception as e:
                                            logger.error(f"Erreur lors du retrait du timeout: {e}")

                        # Send DM notification
                        guild = self.get_guild(int(guild_id))
                        if guild:
                            member = guild.get_member(int(user_id))
                            if member:
                                embed = moderation_utils.create_decay_embed(new_count, guild.name)
                                await moderation_utils.send_dm_notification(member, embed)

                            # Post to modlog
                            config = moderation_utils.get_moderation_config(guild_id)
                            if config and config.get("log_channel_id"):
                                channel = guild.get_channel(int(config["log_channel_id"]))
                                if channel and isinstance(channel, discord.TextChannel):
                                    log_embed = moderation_utils.create_modlog_embed(
                                        "decay",
                                        member,
                                        None,
                                        warn_count_before=warn_count,
                                        warn_count_after=new_count,
                                    )
                                    await channel.send(embed=log_embed)

                    except Exception as e:
                        logger.error(f"Erreur lors de l'expiration pour {user_data}: {e}")

            except Exception as e:
                logger.error(f"Erreur lors de la vérification d'expiration des avertissements: {e}")

            # Attendre 6 heures avant la prochaine vérification
            await asyncio.sleep(21600)

    async def mute_expiration_loop(self):
        """Vérifier périodiquement et retirer les mutes expirés."""
        await self.wait_until_ready()
        logger.info("Démarrage de la boucle d'expiration des mutes")

        while not self.is_closed():
            try:
                from utils import moderation_utils

                # Get expired mutes
                expired_mutes = moderation_utils.get_expired_mutes()

                if expired_mutes:
                    logger.debug(f"[Modération] Traitement de {len(expired_mutes)} mutes expirés")

                for mute in expired_mutes:
                    try:
                        guild_id = mute["guild_id"]
                        user_id = mute["user_id"]

                        guild = self.get_guild(int(guild_id))
                        if not guild:
                            continue

                        member = guild.get_member(int(user_id))
                        if not member:
                            # User left the server, just remove from database
                            moderation_utils.remove_mute(guild_id, user_id, None, "Utilisateur absent")
                            continue

                        # Remove timeout
                        try:
                            await member.timeout(None, reason="Mute expiré")
                            logger.info(f"[Modération] Mute expiré: {user_id} @ {guild_id}")
                        except Exception as e:
                            logger.error(f"[Modération] Erreur lors du retrait du timeout: {e}")

                        # Remove from database
                        moderation_utils.remove_mute(guild_id, user_id, None, "Expiré")

                        # Send DM notification
                        embed = discord.Embed(
                            title="🔊 Mute expiré",
                            description=f"Votre mute sur **{guild.name}** a expiré.",
                            color=discord.Color.green(),
                        )
                        embed.add_field(
                            name="Rappel",
                            value="N'oubliez pas de respecter les règles du serveur.",
                            inline=False
                        )
                        embed.set_footer(text="Système de modération ISROBOT")
                        await moderation_utils.send_dm_notification(member, embed)

                        # Post to modlog
                        config = moderation_utils.get_moderation_config(guild_id)
                        if config and config.get("log_channel_id"):
                            channel = guild.get_channel(int(config["log_channel_id"]))
                            if channel and isinstance(channel, discord.TextChannel):
                                log_embed = moderation_utils.create_modlog_embed(
                                    "unmute",
                                    member,
                                    None,
                                    reason="Mute expiré automatiquement",
                                )
                                await channel.send(embed=log_embed)

                    except Exception as e:
                        logger.error(f"Erreur lors de l'expiration du mute pour {mute}: {e}")

            except Exception as e:
                logger.error(f"Erreur lors de la vérification d'expiration des mutes: {e}")

            # Attendre 1 minute avant la prochaine vérification
            await asyncio.sleep(60)

    async def scheduled_backup_loop(self):
        """Périodiquement créer des sauvegardes automatiques de la base de données."""
        await self.wait_until_ready()
        logger.info("Démarrage de la boucle de sauvegarde automatique")

        while not self.is_closed():
            try:
                from utils.backup import scheduled_backup, auto_recover_database

                # Check database integrity first
                is_healthy = auto_recover_database()
                if not is_healthy:
                    logger.critical(
                        "[Backup] ALERTE CRITIQUE: La base de données est corrompue et n'a pas pu être récupérée! "
                        "Le bot continue de fonctionner mais certaines fonctionnalités peuvent échouer. "
                        "Intervention manuelle requise."
                    )

                # Create scheduled backup
                backup_path = await scheduled_backup()
                if backup_path:
                    logger.info(f"[Backup] Sauvegarde automatique créée: {backup_path.name}")
                else:
                    logger.warning("[Backup] La sauvegarde automatique a échoué")

            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde automatique: {e}")

            # Attendre 6 heures avant la prochaine sauvegarde
            await asyncio.sleep(21600)

    async def rate_limit_cleanup_loop(self):
        """Périodiquement nettoyer les anciennes entrées de rate limiting."""
        await self.wait_until_ready()
        logger.info("Démarrage de la boucle de nettoyage du rate limiter")

        while not self.is_closed():
            try:
                from utils.security import rate_limiter
                rate_limiter.cleanup()
                logger.debug("Nettoyage du rate limiter effectué")

            except Exception as e:
                logger.error(f"Erreur lors du nettoyage du rate limiter: {e}")

            # Attendre 10 minutes avant le prochain nettoyage
            await asyncio.sleep(600)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        """Global error handler for app commands (slash commands)."""
        from utils.error_handlers import handle_interaction_error, classify_error

        # Unwrap the error if it's wrapped
        original_error = error
        if hasattr(error, 'original'):
            original_error = error.original

        # Log the error
        error_key, _ = classify_error(original_error)
        command_name = interaction.command.name if interaction.command else "unknown"

        logger.error(
            f"App command error in /{command_name}: [{error_key}] {original_error}",
            exc_info=original_error if error_key == "unknown_error" else None
        )

        # Handle the error and send user-friendly message
        await handle_interaction_error(interaction, original_error)

    async def reset_counter_game(
        self, message: discord.Message, cursor, conn, error_message: str
    ):
        """Réinitialiser le compteur du minijeu après une erreur."""
        await message.add_reaction("❌")
        await message.channel.send(error_message)
        await message.channel.send("On recommence à zéro !")
        # Réinitialiser le compteur
        cursor.execute(
            "UPDATE counter_game SET count = 0, lastUserId = NULL WHERE guildId = ?",
            (str(message.guild.id),),
        )
        conn.commit()
        await message.channel.send("Le compteur a été réinitialisé.")
        conn.close()

    async def on_message(self, message: discord.Message):
        # Ignorer les messages des bots
        if message.author.bot:
            return

        # Vérifier que le message est dans un serveur
        if not message.guild:
            return

        # --- HONEYPOT CHECK ---
        # Check if message is in a honeypot channel and softban the user
        try:
            from utils import moderation_utils

            guild_id = str(message.guild.id)
            channel_id = str(message.channel.id)

            if moderation_utils.is_honeypot_channel(guild_id, channel_id):
                # Log the violation
                moderation_utils.log_honeypot_violation(guild_id, str(message.author.id), channel_id)

                # Track the cleanup task properly
                async def cleanup_and_kick():
                    # Send warning message
                    try:
                        # Keep the warning minimal to avoid tipping off bots
                        embed = discord.Embed(
                            title="⚠️ Warning",
                            description="This action is not allowed in this channel.",
                            color=discord.Color.red(),
                        )

                        warning_msg = await message.channel.send(embed=embed)

                        # Delete messages after 10 seconds
                        await asyncio.sleep(10)
                        try:
                            await message.delete()
                        except (discord.NotFound, discord.Forbidden):
                            pass
                        try:
                            await warning_msg.delete()
                        except (discord.NotFound, discord.Forbidden):
                            pass

                    except Exception as e:
                        logger.error(f"Error sending honeypot warning message: {e}")

                    # Softban (kick) the user
                    try:
                        await message.guild.kick(
                            message.author,
                            reason="Honeypot violation - Message sent in honeypot channel"
                        )
                        logger.info(
                            f"User {message.author.id} ({message.author.name}) kicked from honeypot channel "
                            f"{channel_id} in guild {guild_id}"
                        )
                    except discord.Forbidden:
                        logger.error(f"Bot does not have permission to kick user {message.author.id}")
                    except Exception as e:
                        logger.error(f"Error performing honeypot softban: {e}")

                # Create and track the task
                self.loop.create_task(cleanup_and_kick())

                # Stop processing this message
                return

        except Exception as e:
            logger.error(f"Error during honeypot check: {e}")

        # --- AI MODERATION ---
        # Analyze message with AI if enabled and not in counter game
        try:
            from utils import ai_moderation, moderation_utils
            from utils.ai_toggle import check_ai_enabled

            guild_id = str(message.guild.id)

            # Check global AI toggle first
            if not check_ai_enabled("moderation"):
                pass  # AI moderation is globally disabled, skip analysis
            else:
                config = moderation_utils.get_moderation_config(guild_id)

                # Only analyze if AI is enabled and message has content
                if config and config.get("ai_enabled", 0) == 1 and message.content:
                    # Get configuration
                    confidence_threshold = config.get("ai_confidence_threshold", 60)
                    ai_model = config.get("ai_model", "llama2")
                    ollama_host = config.get("ollama_host", "http://localhost:11434")
                    rules_message_id = config.get("rules_message_id")
                    ai_flag_channel_id = config.get("ai_flag_channel_id")

                    # Get server rules
                    server_rules = await ai_moderation.get_server_rules(message.guild, rules_message_id)

                    # Analyze message
                    result = await ai_moderation.analyze_message_with_ollama(
                        message.content,
                        server_rules,
                        ollama_host,
                        ai_model
                    )

                    # If analysis succeeded and score is above threshold, create flag
                    if result and result["score"] >= confidence_threshold:
                        flag_id = await ai_moderation.create_ai_flag(
                            guild_id,
                            message,
                            result["score"],
                            result["category"],
                            result["reason"]
                        )

                        # Post to AI flag channel
                        if flag_id and ai_flag_channel_id:
                            channel = message.guild.get_channel(int(ai_flag_channel_id))
                            if channel and isinstance(channel, discord.TextChannel):
                                embed = ai_moderation.create_ai_flag_embed(
                                    flag_id,
                                    message,
                                    result["score"],
                                    result["category"],
                                    result["reason"]
                                )
                                await channel.send(embed=embed)
                                logger.info(
                                    f"Message flagué par l'IA: {message.id} "
                                    f"(score: {result['score']}, catégorie: {result['category']})"
                                )

        except Exception as e:
            # Gracefully handle AI errors - don't let them break the bot
            logger.error(f"Erreur lors de l'analyse IA du message: {e}")

        # --- COUNTER GAME ---
        # Quand un message est envoyé dans le salon compteur du minijeux comparé avec le dernier chiffre
        from database import get_db_connection

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        try:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM counter_game WHERE guildId = ? AND channelId = ?",
                    (guild_id, channel_id),
                )
                is_counter_channel = cursor.fetchone() is not None
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du salon de comptage: {e}")
            return

        if not is_counter_channel:
            return

        # Only check if it's a digit before acquiring the lock
        if not (message.content.isdigit() and not str(message.content).isspace()):
            return

        # Validate the number is within reasonable bounds to prevent integer overflow
        try:
            number = int(message.content)
            if number < 0 or number > 1000000:
                return
        except ValueError:
            return

        # Acquire lock for this specific guild/channel to prevent race conditions
        lock = self._get_counter_lock(guild_id, channel_id)
        async with lock:
            conn = None
            try:
                # Re-read the database state under the lock to get fresh values
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM counter_game WHERE guildId = ? AND channelId = ?",
                    (guild_id, channel_id),
                )
                result = cursor.fetchone()

                if not result:
                    conn.close()
                    return

                # Si le message est envoyé dans le salon du minijeux compteur
                last_user_id = result["lastUserId"]
                last_count = result["count"]
                count = message.content

                if str(message.author.id) == last_user_id:
                    await self.reset_counter_game(
                        message,
                        cursor,
                        conn,
                        "Vous ne pouvez pas compter deux fois de suite !",
                    )
                    return
                if str(int(message.content)) == str(result["count"] + 1):
                    await message.add_reaction("✅")
                    # Mettre à jour le compteur
                    cursor.execute(
                        "UPDATE counter_game SET count = ?, lastUserId = ? WHERE guildId = ? AND channelId = ?",
                        (
                            count,
                            str(message.author.id),
                            guild_id,
                            channel_id,
                        ),
                    )
                    conn.commit()
                    conn.close()
                    return
                elif str(int(message.content)) == str(result["count"]):
                    await self.reset_counter_game(
                        message,
                        cursor,
                        conn,
                        f"Vous avez mis le même chiffre ! Le bon chiffre était {last_count + 1}",
                    )
                    return
                else:
                    # Mauvais chiffre (ni count+1, ni count)
                    await self.reset_counter_game(
                        message,
                        cursor,
                        conn,
                        f"Mauvais chiffre ! Le bon chiffre était {last_count + 1}, "
                        f"mais vous avez mis {message.content}.",
                    )
                    return
            except Exception as e:
                logger.error(f"Erreur lors du traitement du jeu de comptage: {e}")
                if conn:
                    conn.close()

    async def close(self):
        """Fermer proprement la session HTTP quand le bot se ferme."""
        logger.info("Démarrage de l'arrêt gracieux du bot...")

        # Arrêter la tâche de vérification des streams
        if hasattr(self, "stream_check_task") and not self.stream_check_task.done():
            logger.info("Arrêt de la tâche de vérification Twitch...")
            self.stream_check_task.cancel()
            try:
                await asyncio.wait_for(self.stream_check_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            logger.info("Tâche de vérification Twitch arrêtée")

        # Arrêter la tâche de vérification YouTube
        if hasattr(self, "youtube_check_task") and not self.youtube_check_task.done():
            logger.info("Arrêt de la tâche de vérification YouTube...")
            self.youtube_check_task.cancel()

        # Arrêter les tâches de modération
        if hasattr(self, "warning_decay_task"):
            self.warning_decay_task.cancel()

        if hasattr(self, "mute_expiration_task"):
            self.mute_expiration_task.cancel()

        # Arrêter la tâche de sauvegarde automatique
        if hasattr(self, "backup_task"):
            self.backup_task.cancel()

        # Arrêter la tâche de nettoyage du rate limiter
        if hasattr(self, "rate_limit_cleanup_task"):
            self.rate_limit_cleanup_task.cancel()

        if self.session:
            await self.session.close()
            logger.info("Session HTTP fermée")

        logger.info("Arrêt du bot...")
        await super().close()
        logger.info("Bot arrêté avec succès")

    async def on_ready(self):
        logger.info("Bot prêt!")
        if self.user:
            logger.info(f"Connecté en tant que {self.user} (ID: {self.user.id})")
            await self.change_presence(
                activity=discord.CustomActivity(name="Prêt à aider !", emoji="🤖")
            )
        else:
            logger.error("Erreur: Utilisateur non défini")


client = ISROBOT()

def signal_handler(sig, frame):
    """Gestionnaire de signal pour arrêt gracieux."""
    logger.warning(f"Signal {sig} reçu, arrêt gracieux du bot...")
    # Utiliser le loop pour planifier la fermeture du bot
    # au lieu de créer une tâche directement depuis le signal handler
    loop = client.loop
    if loop and loop.is_running():
        loop.create_task(client.close())
    else:
        # Si le loop n'est pas en cours, forcer l'arrêt
        sys.exit(0)

# Enregistrer les gestionnaires de signaux pour arrêt gracieux
if sys.platform != "win32":
    # Sur Unix/Linux, enregistrer SIGTERM et SIGINT
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
else:
    # Sur Windows, seulement SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)

if TOKEN:
    try:
        logger.info("Démarrage du bot...")
        client.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Interruption clavier détectée")
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du bot: {e}")
        raise
    finally:
        logger.info("Bot terminé")
else:
    logger.critical("TOKEN non trouvé dans le fichier .env")
    sys.exit(1)
