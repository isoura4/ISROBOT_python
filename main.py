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

        # Démarrer les tâches de modération en arrière-plan
        self.warning_decay_task = self.loop.create_task(self.warning_decay_loop())
        self.mute_expiration_task = self.loop.create_task(self.mute_expiration_loop())

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
        """Vérifier périodiquement les nouvelles vidéos, shorts et lives YouTube."""
        await self.wait_until_ready()  # Attendre que le bot soit prêt
        logger.info("Démarrage de la boucle de vérification YouTube")
        
        # Compteur pour vérifier les lives moins souvent (toutes les 2 boucles = ~20 min)
        live_check_counter = 0

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
                            last_live_id = channel_data[7]  # lastLiveId
                            notify_videos = channel_data[8]  # notifyVideos
                            notify_shorts = channel_data[9]  # notifyShorts
                            notify_live = channel_data[10]  # notifyLive

                            print(
                                f"  → Vérification de la chaîne YouTube: "
                                f"{channel_name}"
                            )
                            print(
                                f"    ℹ Notifications activées: "
                                f"vidéos={bool(notify_videos)}, "
                                f"shorts={bool(notify_shorts)}, "
                                f"live={bool(notify_live)}"
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
                            if not notify_videos and not notify_shorts and not notify_live:
                                print(
                                    f"    ⚠ Aucune notification activée pour "
                                    f"{channel_name} - ignorer"
                                )
                                logger.warning(
                                    f"Aucune notification activée pour {channel_name}"
                                )
                                continue
                            
                            # Ne vérifier les lives que toutes les 2 boucles (économiser le quota API - 100 unités par vérification!)
                            should_check_live = (live_check_counter % 2 == 0)

                            # Vérifier les lives (seulement si activé et si c'est le bon cycle)
                            if notify_live and should_check_live:
                                print(
                                    f"    → Vérification des lives pour "
                                    f"{channel_name}"
                                )
                                try:
                                    live_videos = (
                                        await youtube_checker.check_live_status(
                                            channel_id
                                        )
                                    )
                                    if live_videos and len(live_videos) > 0:
                                        latest_live = live_videos[0]
                                        live_id = latest_live["id"]["videoId"]

                                        print(
                                            f"      ✓ Live détecté: "
                                            f"{latest_live['snippet']['title']}"
                                        )
                                        logger.debug(
                                            f"Live détecté pour {channel_name}: "
                                            f"{live_id}"
                                        )

                                        # Si c'est un nouveau live
                                        if live_id != last_live_id:
                                            live_title = latest_live["snippet"]["title"]
                                            thumbnail_url = latest_live["snippet"][
                                                "thumbnails"
                                            ]["high"]["url"]
                                            await announcer.announce_live(
                                                channel_id,
                                                channel_name,
                                                discord_channel,
                                                live_id,
                                                live_title,
                                                thumbnail_url,
                                            )

                                            # Mettre à jour lastLiveId
                                            conn = database.get_db_connection()
                                            try:
                                                cursor = conn.cursor()
                                                cursor.execute(
                                                    "UPDATE youtube_channels SET lastLiveId = ? WHERE id = ?",
                                                    (live_id, channel_data[0]),
                                                )
                                                conn.commit()
                                                logger.info(
                                                    f"Annonce live envoyée pour {channel_name}"
                                                )
                                            finally:
                                                conn.close()
                                    else:
                                        print(
                                            f"      ✗ Pas de live en cours pour "
                                            f"{channel_name}"
                                        )
                                        logger.debug(
                                            f"Aucun live en cours pour "
                                            f"{channel_name}"
                                        )
                                        # Pas de live en cours, réinitialiser lastLiveId
                                        if last_live_id:
                                            conn = database.get_db_connection()
                                            try:
                                                cursor = conn.cursor()
                                                cursor.execute(
                                                    "UPDATE youtube_channels SET lastLiveId = NULL WHERE id = ?",
                                                    (channel_data[0],),
                                                )
                                                conn.commit()
                                                logger.debug(
                                                    f"Réinitialisation lastLiveId pour {channel_name}"
                                                )
                                            finally:
                                                conn.close()
                                except discord.errors.Forbidden as e:
                                    logger.error(
                                        f"Permission Discord refusée pour {channel_name} lors de l'annonce du live: {e}"
                                    )

                                except Exception as e:
                                    logger.error(
                                        f"Erreur lors de la vérification du live pour {channel_name}: {e}"
                                    )
                            elif notify_live and not should_check_live:
                                print(
                                    f"    ⊗ Vérification des lives ignorée pour {channel_name} "
                                    f"(économie du quota API - vérification 1x/2 cycles)"
                                )

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
                                            if video_id != last_short_id:
                                                print(
                                                    f"          ✓ Nouveau short "
                                                    f"détecté: {video_title[:50]}..."
                                                )
                                                logger.debug(
                                                    f"Nouveau short détecté pour "
                                                    f"{channel_name}: {video_id}"
                                                )
                                                await announcer.announce_short(
                                                    channel_id,
                                                    channel_name,
                                                    discord_channel,
                                                    video_id,
                                                    video_title,
                                                    thumbnail_url,
                                                )

                                                # Mettre à jour lastShortId
                                                conn = database.get_db_connection()
                                                try:
                                                    cursor = conn.cursor()
                                                    cursor.execute(
                                                        "UPDATE youtube_channels SET lastShortId = ? WHERE id = ?",
                                                        (video_id, channel_data[0]),
                                                    )
                                                    conn.commit()
                                                    logger.info(
                                                        f"Annonce short envoyée pour {channel_name}"
                                                    )
                                                finally:
                                                    conn.close()
                                                break  # Ne traiter qu'un seul nouveau short à la fois
                                            else:
                                                print(
                                                    f"          ℹ Short déjà connu "
                                                    f"(ID: {video_id[:8]}...)"
                                                )

                                        # Annoncer les vidéos normales
                                        elif not is_short_video and notify_videos:
                                            if video_id != last_video_id:
                                                print(
                                                    f"          ✓ Nouvelle vidéo "
                                                    f"détectée: {video_title[:50]}..."
                                                )
                                                logger.debug(
                                                    f"Nouvelle vidéo détectée pour "
                                                    f"{channel_name}: {video_id}"
                                                )
                                                await announcer.announce_video(
                                                    channel_id,
                                                    channel_name,
                                                    discord_channel,
                                                    video_id,
                                                    video_title,
                                                    thumbnail_url,
                                                )

                                                # Mettre à jour lastVideoId
                                                conn = database.get_db_connection()
                                                try:
                                                    cursor = conn.cursor()
                                                    cursor.execute(
                                                        "UPDATE youtube_channels SET lastVideoId = ? WHERE id = ?",
                                                        (video_id, channel_data[0]),
                                                    )
                                                    conn.commit()
                                                    logger.info(
                                                        f"Annonce vidéo envoyée pour {channel_name}"
                                                    )
                                                finally:
                                                    conn.close()
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
            
            # Incrémenter le compteur de vérification live
            live_check_counter += 1

            # Attendre 10 minutes avant la prochaine vérification (optimisé pour ~9500 unités/jour)
            await asyncio.sleep(600)

    async def warning_decay_loop(self):
        """Vérifier périodiquement et faire expirer les avertissements."""
        await self.wait_until_ready()
        logger.info("Démarrage de la boucle d'expiration des avertissements")

        while not self.is_closed():
            try:
                from utils import moderation_utils

                # Get users whose warnings should decay
                users_to_decay = moderation_utils.get_users_for_decay()

                print(f"🔍 [Modération] Vérification de {len(users_to_decay)} utilisateur(s) pour expiration...")
                logger.debug(f"Vérification de {len(users_to_decay)} utilisateurs pour expiration")

                for user_data in users_to_decay:
                    try:
                        guild_id = user_data["guild_id"]
                        user_id = user_data["user_id"]
                        warn_count = user_data["warn_count"]

                        # Decrement warning
                        new_count = moderation_utils.decrement_warning(
                            guild_id, user_id, None, "Expiration automatique"
                        )

                        print(f"  ✓ Avertissement expiré pour l'utilisateur {user_id} dans le serveur {guild_id}")
                        logger.info(f"Avertissement expiré: {user_id} @ {guild_id} ({warn_count} -> {new_count})")

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
                    print(f"🔍 [Modération] {len(expired_mutes)} mute(s) expiré(s) détecté(s)")
                    logger.debug(f"Traitement de {len(expired_mutes)} mutes expirés")

                for mute in expired_mutes:
                    try:
                        guild_id = mute["guild_id"]
                        user_id = mute["user_id"]
                        reason = mute["reason"]

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
                            print(f"  ✓ Mute expiré pour {member.display_name} dans {guild.name}")
                            logger.info(f"Mute expiré: {user_id} @ {guild_id}")
                        except Exception as e:
                            logger.error(f"Erreur lors du retrait du timeout: {e}")

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

        # --- AI MODERATION ---
        # Analyze message with AI if enabled and not in counter game
        try:
            from utils import ai_moderation, moderation_utils

            guild_id = str(message.guild.id)
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

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM counter_game WHERE guildId = ? AND channelId = ?",
            (str(message.guild.id), str(message.channel.id)),
        )
        result = cursor.fetchone()
        if result:
            # Si le message est envoyé dans le salon du minijeux compteur
            last_user_id = result["lastUserId"]
            last_count = result["count"]
            count = message.content
            if (
                message.content.isdigit() and not str(message.content).isspace()
            ):  # Vérifie si le message est un chiffre
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
                            str(message.guild.id),
                            str(message.channel.id),
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
            else:
                conn.close()
                return
        else:
            conn.close()

    async def close(self):
        """Fermer proprement la session HTTP quand le bot se ferme."""
        # Arrêter la tâche de vérification des streams
        if hasattr(self, "stream_check_task"):
            self.stream_check_task.cancel()

        # Arrêter la tâche de vérification YouTube
        if hasattr(self, "youtube_check_task"):
            self.youtube_check_task.cancel()

        # Arrêter les tâches de modération
        if hasattr(self, "warning_decay_task"):
            self.warning_decay_task.cancel()

        if hasattr(self, "mute_expiration_task"):
            self.mute_expiration_task.cancel()

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
