import asyncio
import logging
import os
import re
import time
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

# Logger pour ce module
logger = logging.getLogger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))
TWITCH_CLIENT_ID = os.getenv("twitch_client_id")
TWITCH_CLIENT_SECRET = os.getenv("twitch_client_secret")


def _db_streamer_exists(streamer_name: str, channel_id: str) -> bool:
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM streamers " "WHERE streamerName = ? AND streamChannelId = ?",
            (streamer_name, channel_id),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def _db_add_streamer(
    streamer_name: str, channel_id: str, role_id: Optional[str]
) -> None:
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO streamers (streamerName, streamChannelId, roleId) "
            "VALUES (?, ?, ?)",
            (streamer_name, channel_id, role_id),
        )
        conn.commit()
    finally:
        conn.close()


def _db_remove_streamer(streamer_name: str) -> int:
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM streamers WHERE streamerName = ?", (streamer_name,))
        rows = cursor.rowcount
        conn.commit()
        return rows
    finally:
        conn.close()


def _db_list_streamers() -> list:
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT streamerName, streamChannelId, roleId, announced
            FROM streamers
            ORDER BY streamerName ASC
            """)
        return cursor.fetchall()
    finally:
        conn.close()


def _db_get_streamer_role(streamer_name: str):
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT roleId FROM streamers WHERE streamerName = ?",
            (streamer_name,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


class Stream(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stream_add", description=tr("cmd.stream_add.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def stream(
        self,
        interaction: discord.Interaction,
        streamer_name: str,
        channel: discord.TextChannel,
        ping_role: discord.Role = None,
    ):
        locale = get_locale(interaction)
        # Validation des entrées
        if not streamer_name or not streamer_name.strip():
            await interaction.response.send_message(
                t("stream.empty_name", locale), ephemeral=True
            )
            return

        # Nettoyer le nom du streamer (enlever les espaces et convertir en minuscules)
        streamer_name = streamer_name.strip().lower()

        # Valider que le nom respecte les règles Twitch (4-25 caractères, alphanumériques, underscores et tirets)
        if not re.match(r"^[a-zA-Z0-9_-]{4,25}$", streamer_name):
            await interaction.response.send_message(
                t("stream.invalid_name", locale),
                ephemeral=True,
            )
            return

        # Logique pour ajouter le streamer à la base de données
        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
            await interaction.response.send_message(
                t("stream.no_creds", locale), ephemeral=True
            )
            return

        try:
            # Connexion à la base de données SQLite:
            # Vérifier si le streamer existe déjà dans la base de données
            exists = await asyncio.to_thread(
                _db_streamer_exists, streamer_name, str(channel.id)
            )

            if exists:
                await interaction.response.send_message(
                    t("stream.already", locale, name=streamer_name),
                    ephemeral=True,
                )
                return

            # Ajouter le streamer et le channel id sélectionné à la base de données
            await asyncio.to_thread(
                _db_add_streamer,
                streamer_name,
                str(channel.id),
                str(ping_role.id) if ping_role else None,
            )

            # Envoyer un message de confirmation
            await interaction.response.send_message(
                t("stream.added", locale, name=streamer_name, channel=channel.mention)
            )
            if ping_role is not None:
                await interaction.followup.send(
                    t("stream.role_announce", locale, role=ping_role.mention)
                )
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du streamer {streamer_name}: {e}")
            await interaction.response.send_message(
                t("stream.add_error", locale, error=str(e)), ephemeral=True
            )

    @app_commands.command(
        name="stream_remove",
        description=tr("cmd.stream_remove.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def stream_remove(self, interaction: discord.Interaction, streamer_name: str):
        """Retirer un streamer de la liste des streamers."""
        locale = get_locale(interaction)
        # Validation des entrées
        if not streamer_name or not streamer_name.strip():
            await interaction.response.send_message(
                t("stream.empty_name", locale), ephemeral=True
            )
            return

        streamer_name = streamer_name.strip().lower()

        try:
            # Logique pour retirer le streamer de la base de données
            rows_deleted = await asyncio.to_thread(_db_remove_streamer, streamer_name)

            if rows_deleted > 0:
                await interaction.response.send_message(
                    t("stream.removed", locale, name=streamer_name)
                )
            else:
                await interaction.response.send_message(
                    t("stream.not_found", locale, name=streamer_name),
                    ephemeral=True,
                )
        except Exception as e:
            logger.error(
                f"Erreur lors de la suppression du streamer {streamer_name}: {e}"
            )
            await interaction.response.send_message(
                t("stream.remove_error", locale, error=str(e)),
                ephemeral=True,
            )

    @app_commands.command(
        name="stream_list",
        description=tr("cmd.stream_list.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def stream_list(self, interaction: discord.Interaction):
        locale = get_locale(interaction)
        try:
            rows = await asyncio.to_thread(_db_list_streamers)

            if not rows:
                await interaction.response.send_message(
                    f"ℹ️ {t('stream.list_title', locale)}: {t('stream.chan_none', locale)}",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=t("stream.list_title", locale),
                color=discord.Color.purple(),
            )

            for streamer_name, channel_id, role_id, announced in rows:
                channel_mention = (
                    f"<#{channel_id}>" if channel_id else t("stream.chan_none", locale)
                )
                role_mention = (
                    f"<@&{role_id}>" if role_id else t("stream.role_none", locale)
                )
                live_status = (
                    t("stream.live", locale)
                    if announced
                    else t("stream.offline", locale)
                )
                embed.add_field(
                    name=streamer_name,
                    value=t(
                        "stream.field_value",
                        locale,
                        channel=channel_mention,
                        role=role_mention,
                        status=live_status,
                    ),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erreur lors de l'affichage des streamers: {e}")
            await interaction.response.send_message(
                t("stream.list_error", locale, error=str(e)),
                ephemeral=True,
            )


class GetTwitchOAuth:
    """Classe pour gérer l'authentification avec l'API Twitch."""

    # Cache de token au niveau classe pour être réutilisé entre les instances
    # (une nouvelle instance est créée à chaque cycle de vérification).
    _cached_token: Optional[str] = None
    _token_expiry: float = 0.0

    def __init__(self, session: aiohttp.ClientSession):
        self.client_id = TWITCH_CLIENT_ID
        self.client_secret = TWITCH_CLIENT_SECRET
        self.session = session

    async def get_auth_token(self, retry_count: int = 3):
        """Obtenir un token d'authentification Twitch (avec cache + retry)."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Les identifiants Twitch ne sont pas configurés.")

        # Réutiliser le token en cache s'il est encore valide
        if (
            GetTwitchOAuth._cached_token
            and time.monotonic() < GetTwitchOAuth._token_expiry
        ):
            return GetTwitchOAuth._cached_token

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
                        token = data["access_token"]
                        # expires_in (secondes) ; marge de sécurité de 60 s
                        expires_in = data.get("expires_in", 3600)
                        GetTwitchOAuth._cached_token = token
                        GetTwitchOAuth._token_expiry = time.monotonic() + max(
                            60, expires_in - 60
                        )
                        return token
                    elif response.status >= 500:
                        # Erreur serveur, réessayer
                        last_error = f"Erreur serveur Twitch: {response.status}"
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2**attempt)  # Backoff exponentiel
                            continue
                    else:
                        # Erreur client (4xx), ne pas réessayer
                        raise Exception(
                            f"Erreur lors de la récupération du token OAuth: {response.status}"
                        )
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    logger.warning(
                        f"Tentative {attempt + 1}/{retry_count} échouée pour l'authentification Twitch: {e}"
                    )
                    await asyncio.sleep(2**attempt)
                    continue

        raise Exception(
            f"Échec de l'authentification Twitch après {retry_count} tentatives: {last_error}"
        )


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
                headers = {
                    "Client-ID": TWITCH_CLIENT_ID,
                    "Authorization": f"Bearer {token}",
                }
                url = f"https://api.twitch.tv/helix/streams?user_login={streamer_name}"

                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    elif response.status >= 500:
                        # Erreur serveur, réessayer
                        last_error = f"Erreur serveur Twitch: {response.status}"
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2**attempt)
                            continue
                    else:
                        # Erreur client, ne pas réessayer
                        raise Exception(
                            f"Erreur lors de la vérification du statut du streamer: {response.status}"
                        )
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    logger.warning(
                        f"Tentative {attempt + 1}/{retry_count} échouée pour {streamer_name}: {e}"
                    )
                    await asyncio.sleep(2**attempt)
                    continue

        raise Exception(
            f"Échec de la vérification du streamer {streamer_name} après {retry_count} tentatives: {last_error}"
        )


class AnnounceStream:
    """Classe pour annoncer le début d'un stream."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_role(self, streamer_name: str):
        """Récupérer le rôle à mentionner pour les annonces."""
        result = await asyncio.to_thread(_db_get_streamer_role, streamer_name)
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
            description=t(
                "stream.announce_desc",
                None,
                name=streamer_name,
                category=category,
                url=f"https://www.twitch.tv/{streamer_name}",
            ),
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
