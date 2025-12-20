# Importation des bibliothèques et modules
import asyncio
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
APP_ID = int(os.getenv("app_id", "0"))
TOKEN = os.getenv("secret_key")
SERVER_ID = int(os.getenv("server_id", "0"))
DB_PATH = os.getenv("db_path")

# Parametrage des logs
logging.basicConfig(
    filename="discord.log",
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

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

    async def setup_hook(self):
        # Créer une session HTTP pour les requêtes API
        self.session = aiohttp.ClientSession()

        # Lancer le script database.py pour créer la base de données
        print("Initialisation de la base de données...")
        try:
            import database

            database.create_database()
            print("Base de données initialisée avec succès.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation de la base de données: {e}")

        # Supprimer toutes les commandes /
        self.tree.clear_commands(guild=None)
        print("Commandes existantes vidées")

        # Parcourir les fichiers contenant des commandes
        commands_path = Path("commands/")
        for file in commands_path.glob("*.py"):
            if file.name.startswith("_"):
                continue
            # Charger le module comme extension
            module_name = f"commands.{file.stem}"
            try:
                await self.load_extension(module_name)
                print(f"Extension {module_name} chargée avec succès")
            except Exception as e:
                print(f"Erreur lors du chargement de {module_name}: {e}")

        # Synchroniser les commandes avec Discord
        try:
            # Synchronisation globale (peut prendre jusqu'à 1 heure)
            synced_global = await self.tree.sync()
            print(f"{len(synced_global)} commande(s) synchronisée(s) globalement")

            # Synchronisation sur le serveur spécifique (instantané)
            synced_guild = await self.tree.sync(guild=discord.Object(id=SERVER_ID))
            print(f"{len(synced_guild)} commande(s) synchronisée(s) avec le serveur")

        except Exception as e:
            print(f"Erreur lors de la synchronisation: {e}")
            import traceback

            traceback.print_exc()

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
                print("Le minijeux du compteur est déjà configuré.")
            else:
                print("Le minijeux du compteur n'est pas configuré.")
            conn.close()
        except Exception as e:
            print(f"Erreur lors de la vérification du minijeux du compteur: {e}")
            import traceback

            traceback.print_exc()

        # Démarrer la tâche de vérification des streams en arrière-plan
        self.stream_check_task = self.loop.create_task(self.check_streams_loop())

        # Démarrer la tâche de vérification YouTube en arrière-plan
        self.youtube_check_task = self.loop.create_task(self.check_youtube_loop())

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

                    print(f"🔍 [Twitch] Vérification de {len(streamers)} streamer(s)...")
                    logger.debug(
                        f"Vérification de {len(streamers)} streamer(s) Twitch"
                    )

                    for streamer in streamers:
                        try:
                            # Database schema: streamers table
                            # [0]=id, [1]=streamerName, [2]=streamChannelId,
                            # [3]=roleId, [4]=announced, [5]=startTime

                            streamer_id = streamer[0]
                            streamer_name = streamer[1]
                            stream_channel_id = streamer[2]
                            announced = streamer[4]

                            print(
                                f"  → Vérification du streamer Twitch: "
                                f"{streamer_name}"
                            )
                            logger.debug(
                                f"Vérification du statut de {streamer_name} "
                                f"sur Twitch"
                            )

                            # Vérifier si le streamer est en ligne
                            stream_data = await stream_checker.check_streamer_status(
                                streamer_name
                            )
                            if (
                                stream_data and len(stream_data) > 0
                            ):  # Si des données sont retournées, le streamer est en ligne
                                print(f"    ✓ {streamer_name} est en ligne !")
                                logger.debug(
                                    f"{streamer_name} est actuellement en ligne"
                                )
                                # Vérifier si on a déjà annoncé ce stream
                                if announced == 0:
                                    channel = self.get_channel(
                                        int(stream_channel_id)
                                    )
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
                                            streamer_name, channel, stream_title, category
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
                                    print(
                                        f"    ℹ {streamer_name} est déjà annoncé"
                                    )
                                    logger.debug(
                                        f"{streamer_name} est en ligne mais "
                                        f"déjà annoncé"
                                    )
                            else:
                                print(f"    ✗ {streamer_name} est hors ligne")
                                logger.debug(
                                    f"{streamer_name} n'est pas en ligne"
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
                        except Exception as e:
                            logger.error(
                                f"Erreur lors de la vérification du streamer {streamer[1]}: {e}"
                            )

            except Exception as e:
                logger.error(f"Erreur lors de la vérification des streams: {e}")

            # Attendre 5 minutes avant la prochaine vérification
            await asyncio.sleep(300)

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

                    print(f"🔍 [YouTube] Vérification de {len(channels)} chaîne(s)...")
                    logger.debug(
                        f"Vérification de {len(channels)} chaîne(s) YouTube"
                    )

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

                            print(
                                f"  → Vérification de la chaîne YouTube: "
                                f"{channel_name}"
                            )
                            print(
                                f"    ℹ Notifications activées: "
                                f"vidéos={bool(notify_videos)}, "
                                f"shorts={bool(notify_shorts)}"
                            )
                            logger.debug(
                                f"Vérification de {channel_name} "
                                f"(ID: {channel_id})"
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
                                print(
                                    f"    ⚠ Aucune notification activée pour "
                                    f"{channel_name} - ignorer"
                                )
                                logger.warning(
                                    f"Aucune notification activée pour {channel_name}"
                                )
                                continue

                            # Vérifier les nouvelles vidéos et shorts
                            if notify_videos or notify_shorts:
                                print(
                                    f"    → Vérification des vidéos/shorts "
                                    f"pour {channel_name}"
                                )
                                logger.debug(
                                    f"Vérification des uploads pour "
                                    f"{channel_name} (vidéos: {notify_videos}, "
                                    f"shorts: {notify_shorts})"
                                )
                                try:
                                    latest_uploads = (
                                        await youtube_checker.get_latest_uploads(
                                            channel_id, max_results=3
                                        )
                                    )

                                    # Track announced content in this cycle to prevent duplicates
                                    # Separate flags for videos and shorts since they're different content types
                                    announced_short_in_this_cycle = False
                                    announced_video_in_this_cycle = False

                                    if not latest_uploads:
                                        print(
                                            f"      ℹ Aucune vidéo trouvée pour "
                                            f"{channel_name}"
                                        )
                                        logger.debug(
                                            f"Aucune vidéo trouvée pour "
                                            f"{channel_name}"
                                        )
                                    else:
                                        print(
                                            f"      ℹ {len(latest_uploads)} vidéo(s) "
                                            f"trouvée(s) pour {channel_name}"
                                        )

                                    for upload in latest_uploads:
                                        video_id = upload["snippet"]["resourceId"][
                                            "videoId"
                                        ]

                                        # Récupérer les détails de la vidéo pour déterminer si c'est un short
                                        video_details = (
                                            await youtube_checker.get_video_details(
                                                video_id
                                            )
                                        )
                                        if not video_details:
                                            print(
                                                f"        ⚠ Impossible de récupérer "
                                                f"les détails de la vidéo {video_id}"
                                            )
                                            logger.warning(
                                                f"Impossible de récupérer les détails "
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
                                        content_type = "short" if is_short_video else "vidéo"

                                        print(
                                            f"        → Vérification: {content_type} "
                                            f"'{video_title[:50]}...' (ID: {video_id[:8]}...)"
                                        )

                                        # Annoncer les shorts
                                        if is_short_video and notify_shorts:
                                            if video_id != last_short_id and not announced_short_in_this_cycle:
                                                print(
                                                    f"          ✓ Nouveau short "
                                                    f"détecté: {video_title[:50]}..."
                                                )
                                                logger.debug(
                                                    f"Nouveau short détecté pour "
                                                    f"{channel_name}: {video_id}"
                                                )

                                                # Mettre à jour lastShortId AVANT d'annoncer
                                                # pour éviter les doublons en cas d'échec de l'annonce
                                                conn = database.get_db_connection()
                                                db_update_success = False
                                                try:
                                                    cursor = conn.cursor()
                                                    cursor.execute(
                                                        "UPDATE youtube_channels SET lastShortId = ? WHERE id = ?",
                                                        (video_id, channel_data[0]),
                                                    )
                                                    conn.commit()
                                                    # Update local variable only after successful commit
                                                    last_short_id = video_id
                                                    announced_short_in_this_cycle = True
                                                    db_update_success = True
                                                    logger.info(
                                                        f"lastShortId mis à jour pour {channel_name}: {video_id}"
                                                    )
                                                except Exception as e:
                                                    logger.error(
                                                        f"Erreur lors de la mise à jour de lastShortId pour {channel_name}: {e}"
                                                    )
                                                    # Skip this video but continue processing others
                                                    continue
                                                finally:
                                                    conn.close()

                                                # Only announce if database update succeeded
                                                if db_update_success:
                                                    # Annoncer le short après la mise à jour de la base de données
                                                    await announcer.announce_short(
                                                        channel_id,
                                                        channel_name,
                                                        discord_channel,
                                                        video_id,
                                                        video_title,
                                                        thumbnail_url,
                                                    )
                                                    logger.info(
                                                        f"Annonce short envoyée pour {channel_name}"
                                                    )
                                                    break  # Ne traiter qu'un seul nouveau short à la fois
                                            else:
                                                print(
                                                    f"          ℹ Short déjà connu "
                                                    f"(ID: {video_id[:8]}...)"
                                                )

                                        # Annoncer les vidéos normales
                                        elif not is_short_video and notify_videos:
                                            if video_id != last_video_id and not announced_video_in_this_cycle:
                                                print(
                                                    f"          ✓ Nouvelle vidéo "
                                                    f"détectée: {video_title[:50]}..."
                                                )
                                                logger.debug(
                                                    f"Nouvelle vidéo détectée pour "
                                                    f"{channel_name}: {video_id}"
                                                )

                                                # Mettre à jour lastVideoId AVANT d'annoncer
                                                # pour éviter les doublons en cas d'échec de l'annonce
                                                conn = database.get_db_connection()
                                                db_update_success = False
                                                try:
                                                    cursor = conn.cursor()
                                                    cursor.execute(
                                                        "UPDATE youtube_channels SET lastVideoId = ? WHERE id = ?",
                                                        (video_id, channel_data[0]),
                                                    )
                                                    conn.commit()
                                                    # Update local variable only after successful commit
                                                    last_video_id = video_id
                                                    announced_video_in_this_cycle = True
                                                    db_update_success = True
                                                    logger.info(
                                                        f"lastVideoId mis à jour pour {channel_name}: {video_id}"
                                                    )
                                                except Exception as e:
                                                    logger.error(
                                                        f"Erreur lors de la mise à jour de lastVideoId pour {channel_name}: {e}"
                                                    )
                                                    # Skip this video but continue processing others
                                                    continue
                                                finally:
                                                    conn.close()

                                                # Only announce if database update succeeded
                                                if db_update_success:
                                                    # Annoncer la vidéo après la mise à jour de la base de données
                                                    await announcer.announce_video(
                                                        channel_id,
                                                        channel_name,
                                                        discord_channel,
                                                        video_id,
                                                        video_title,
                                                        thumbnail_url,
                                                    )
                                                    logger.info(
                                                        f"Annonce vidéo envoyée pour {channel_name}"
                                                    )
                                                    break  # Ne traiter qu'une seule nouvelle vidéo à la fois
                                            else:
                                                print(
                                                    f"          ℹ Vidéo déjà connue "
                                                    f"(ID: {video_id[:8]}...)"
                                                )
                                        else:
                                            # Vidéo ignorée car les notifications sont désactivées pour ce type
                                            if is_short_video and not notify_shorts:
                                                print(
                                                    "          ⊗ Short ignoré "
                                                    "(notifications désactivées)"
                                                )
                                            elif not is_short_video and not notify_videos:
                                                print(
                                                    "          ⊗ Vidéo ignorée "
                                                    "(notifications désactivées)"
                                                )

                                except discord.errors.Forbidden as e:
                                    logger.error(
                                        f"Permission Discord refusée pour {channel_name} lors de l'annonce d'une vidéo/short: {e}"
                                    )

                                except Exception as e:
                                    logger.error(
                                        f"Erreur lors de la vérification des uploads pour {channel_name}: {e}"
                                    )

                        except Exception as e:
                            logger.error(
                                f"Erreur lors de la vérification de la chaîne {channel_data[2]}: {e}"
                            )

            except Exception as e:
                error_msg = str(e)
                # Détecter les erreurs de quota
                if "quota" in error_msg.lower() or "403" in error_msg:
                    logger.error(
                        f"⚠️ QUOTA API YOUTUBE DÉPASSÉ! Vérification ignorée. "
                        f"Le quota se réinitialise à minuit PST. Erreur: {e}"
                    )
                    print(
                        f"❌ [YouTube] Quota API dépassé! "
                        f"Prochaine tentative dans 30 minutes."
                    )
                else:
                    logger.error(f"Erreur lors de la vérification YouTube: {e}")

            # Attendre 10 minutes avant la prochaine vérification (optimisé pour ~9500 unités/jour)
            await asyncio.sleep(600)

    def _get_counter_lock(self, guild_id: str, channel_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific counter game channel."""
        key = (guild_id, channel_id)
        # Use setdefault for thread-safe lock creation
        return self._counter_locks.setdefault(key, asyncio.Lock())

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

        # Check if this is a counting game channel (quick check without lock)
        from database import get_db_connection

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM counter_game WHERE guildId = ? AND channelId = ?",
            (guild_id, channel_id),
        )
        is_counter_channel = cursor.fetchone() is not None
        conn.close()

        if not is_counter_channel:
            return

        # Only check if it's a digit before acquiring the lock
        if not (message.content.isdigit() and not str(message.content).isspace()):
            return

        # Acquire lock for this specific guild/channel to prevent race conditions
        lock = self._get_counter_lock(guild_id, channel_id)
        async with lock:
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

    async def close(self):
        """Fermer proprement la session HTTP quand le bot se ferme."""
        # Arrêter la tâche de vérification des streams
        if hasattr(self, "stream_check_task"):
            self.stream_check_task.cancel()

        # Arrêter la tâche de vérification YouTube
        if hasattr(self, "youtube_check_task"):
            self.youtube_check_task.cancel()

        if self.session:
            await self.session.close()
        await super().close()

    async def on_ready(self):
        print("Ready !")
        if self.user:
            print(f"Connecté en tant que {self.user} (ID: {self.user.id})")
            await self.change_presence(
                activity=discord.CustomActivity(name="Prêt à aider !", emoji="🤖")
            )
        else:
            print("Erreur: Utilisateur non défini")


client = ISROBOT()
if TOKEN:
    client.run(TOKEN)
else:
    print("Erreur: TOKEN non trouvé dans le fichier .env")
