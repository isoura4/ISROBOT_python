import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database
from utils.i18n import get_locale, t, tr
from utils.time_utils import utcnow

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))

# API publique (AppView) Bluesky : lecture des profils et des flux sans auth.
BLUESKY_PUBLIC_API = os.getenv(
    "bluesky_public_api", "https://public.api.bsky.app"
).rstrip("/")

# Logger pour ce module
logger = logging.getLogger(__name__)

# Nombre maximal de posts annoncés par cycle et par compte (anti-spam).
MAX_ANNOUNCE_PER_CYCLE = 5

_HANDLE_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
_DID_RE = re.compile(r"^did:(?:plc|web):[a-zA-Z0-9._:%-]+$")


@asynccontextmanager
async def _http_session(bot: commands.Bot):
    """Réutilise la session HTTP partagée du bot si disponible.

    N'en crée une (temporaire, fermée en sortie) que si le bot n'en a pas.
    """
    session = getattr(bot, "session", None)
    if session is not None and not session.closed:
        yield session
        return

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as temp_session:
        yield temp_session


# --- Helpers purs (testables sans réseau) ---


def normalize_bluesky_identifier(identifier: str) -> str:
    """Retire les espaces et le ``@`` initial d'un handle Bluesky."""
    return identifier.strip().lstrip("@").strip()


def is_valid_bluesky_handle(handle: str) -> bool:
    """Valide un handle Bluesky (forme ``nom.domaine``)."""
    return bool(_HANDLE_RE.match(handle or ""))


def is_valid_bluesky_did(did: str) -> bool:
    """Valide un DID Bluesky (``did:plc:...`` ou ``did:web:...``)."""
    return bool(_DID_RE.match(did or ""))


def validate_bluesky_identifier(
    identifier: str, locale: Optional[str] = None
) -> tuple[bool, str]:
    """Valide un identifiant Bluesky (handle ou DID).

    Returns:
        tuple: ``(is_valid, error_message)``.
    """
    normalized = normalize_bluesky_identifier(identifier)
    if not normalized:
        return False, t("bluesky.empty_input", locale)
    if is_valid_bluesky_did(normalized) or is_valid_bluesky_handle(normalized):
        return True, ""
    return False, t("bluesky.invalid_handle", locale)


def post_web_url(handle: str, uri: str) -> str:
    """Construit l'URL web publique d'un post à partir de son AT-URI."""
    rkey = (uri or "").rstrip("/").split("/")[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def extract_post_text(post: dict) -> str:
    """Extrait le texte d'un post (chaîne vide si absent)."""
    record = post.get("record") or {}
    text = record.get("text") or ""
    return text.strip()


def extract_post_image(post: dict) -> Optional[str]:
    """Retourne l'URL de la première image/aperçu d'un post, si présente."""
    embed = post.get("embed") or {}
    embed_type = embed.get("$type", "")

    # Post avec images
    if "images" in embed and embed["images"]:
        image = embed["images"][0]
        return image.get("fullsize") or image.get("thumb")

    # Post avec lien externe (carte)
    external = embed.get("external") or {}
    if external.get("thumb"):
        return external["thumb"]

    # Post avec média + citation imbriqués
    media = embed.get("media") or {}
    if "images" in media and media["images"]:
        return media["images"][0].get("fullsize") or media["images"][0].get("thumb")

    return None


def extract_post_created_at(post: dict) -> Optional[str]:
    """Retourne l'horodatage ISO 8601 de création d'un post."""
    record = post.get("record") or {}
    return record.get("createdAt") or post.get("indexedAt")


def select_new_posts(feed: list, last_post_uri: Optional[str]) -> list:
    """Sélectionne les nouveaux posts d'un flux ``getAuthorFeed``.

    Le flux est trié du plus récent au plus ancien. On collecte les posts
    jusqu'à retrouver ``last_post_uri`` (exclu), en ignorant les reposts
    (champ ``reason``). Le résultat est renvoyé dans l'ordre chronologique.
    """
    new_posts = []
    for item in feed:
        post = item.get("post", {})
        if last_post_uri and post.get("uri") == last_post_uri:
            break
        if item.get("reason"):
            continue
        new_posts.append(post)
    new_posts.reverse()
    return new_posts


# --- Accès base de données ---


def _db_bluesky_exists(handle: str, discord_channel_id: str) -> bool:
    """Indique si le compte Bluesky est déjà surveillé dans ce salon."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM bluesky_accounts "
            "WHERE handle = ? AND discordChannelId = ?",
            (handle, discord_channel_id),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def _db_add_bluesky_account(
    handle: str,
    did: Optional[str],
    display_name: Optional[str],
    discord_channel_id: str,
    role_id: Optional[str],
    last_post_uri: Optional[str],
    last_post_cid: Optional[str],
) -> None:
    """Insère un nouveau compte Bluesky à surveiller."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO bluesky_accounts
               (handle, did, displayName, discordChannelId, roleId,
                lastPostUri, lastPostCid, createdAt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                handle,
                did,
                display_name,
                discord_channel_id,
                role_id,
                last_post_uri,
                last_post_cid,
                utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _db_list_bluesky_accounts() -> list:
    """Retourne la liste des comptes Bluesky surveillés."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, handle, did, displayName, discordChannelId, roleId,
                   lastPostUri, lastPostCid
            FROM bluesky_accounts
            ORDER BY handle ASC
            """)
        return cursor.fetchall()
    finally:
        conn.close()


def _db_remove_bluesky_account(handle: str) -> int:
    """Supprime un compte par son handle, retourne le nombre de lignes."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bluesky_accounts WHERE handle = ?",
            (handle,),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _db_update_last_post(
    account_id: int, last_post_uri: Optional[str], last_post_cid: Optional[str]
) -> None:
    """Met à jour le dernier post connu d'un compte."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE bluesky_accounts SET lastPostUri = ?, lastPostCid = ? "
            "WHERE id = ?",
            (last_post_uri, last_post_cid, account_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- API Bluesky ---


class CheckBlueskyAccount:
    """Classe pour interroger l'API publique Bluesky."""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_profile(self, actor: str) -> Optional[dict]:
        """Récupère le profil public d'un compte (handle ou DID)."""
        url = f"{BLUESKY_PUBLIC_API}/xrpc/app.bsky.actor.getProfile"
        params = {"actor": actor}
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            if response.status in (400, 404):
                logger.debug(f"Profil Bluesky introuvable: {actor} ({response.status})")
                return None
            raise Exception(f"Erreur API Bluesky (profil): {response.status}")

    async def get_author_feed(self, actor: str, limit: int = 20) -> list:
        """Récupère les derniers posts d'un compte (sans réponses)."""
        url = f"{BLUESKY_PUBLIC_API}/xrpc/app.bsky.feed.getAuthorFeed"
        params = {"actor": actor, "limit": limit, "filter": "posts_no_replies"}
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("feed", [])
            if response.status in (400, 404):
                logger.warning(
                    f"Flux Bluesky introuvable pour {actor} ({response.status})"
                )
                return []
            raise Exception(f"Erreur API Bluesky (flux): {response.status}")


class AnnounceBluesky:
    """Classe pour annoncer les nouveaux posts Bluesky."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_role(self, account_id: int):
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT roleId FROM bluesky_accounts WHERE id = ?",
                (account_id,),
            )
            return cursor.fetchone()
        finally:
            conn.close()

    async def get_role(self, account_id: int):
        """Récupère le rôle à mentionner pour les annonces."""
        result = await asyncio.to_thread(self._get_role, account_id)
        if result and result[0]:
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if guild is not None:
                return discord.utils.get(guild.roles, id=int(result[0]))
        return None

    async def announce_post(
        self,
        account_id: int,
        handle: str,
        display_name: Optional[str],
        discord_channel: discord.TextChannel,
        post_text: str,
        post_url: str,
        thumbnail_url: Optional[str] = None,
        created_at: Optional[str] = None,
        discord_role: Optional[discord.Role] = None,
    ):
        """Annonce un nouveau post Bluesky dans un salon Discord."""
        if discord_role is None:
            discord_role = await self.get_role(account_id)

        author = display_name or handle
        text = post_text or t("bluesky.no_text", None)

        embed = discord.Embed(
            title=t("bluesky.new_post_title", None, author=author),
            description=t(
                "bluesky.new_post_desc",
                None,
                text=text,
                url=post_url,
            ),
            color=discord.Color.from_rgb(0, 133, 255),
            url=post_url,
        )
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)

        timestamp = _parse_timestamp(created_at)
        if timestamp is not None:
            embed.timestamp = timestamp

        footer = t("bluesky.footer", None, handle=handle)
        embed.set_footer(text=footer)

        if discord_role is not None:
            await discord_channel.send(content=discord_role.mention, embed=embed)
        else:
            await discord_channel.send(embed=embed)


async def announce_posts_with_checkpoint(
    announcer: "AnnounceBluesky",
    account_id: int,
    handle: str,
    display_name: Optional[str],
    discord_channel: discord.TextChannel,
    new_posts: list,
) -> int:
    """Annonce des posts et avance le marqueur après chaque envoi réussi.

    Le marqueur ``lastPostUri`` est mis à jour post par post : ainsi, en cas
    d'échec d'un envoi (permission, réseau...), seuls les posts déjà annoncés
    avec succès sont marqués comme traités. Les posts restants seront réessayés
    au cycle suivant, sans doublon.

    Returns:
        Le nombre de posts annoncés avec succès.
    """
    announced = 0
    for post in new_posts:
        try:
            await announcer.announce_post(
                account_id,
                handle,
                display_name,
                discord_channel,
                extract_post_text(post),
                post_web_url(handle, post.get("uri", "")),
                thumbnail_url=extract_post_image(post),
                created_at=extract_post_created_at(post),
            )
        except discord.HTTPException as e:
            logger.error(
                f"Échec de l'annonce Bluesky de {handle} "
                f"(post {post.get('uri')}): {e}"
            )
            break

        await asyncio.to_thread(
            _db_update_last_post,
            account_id,
            post.get("uri"),
            post.get("cid"),
        )
        announced += 1

    return announced


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Convertit un horodatage ISO 8601 en datetime, si possible."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class Bluesky(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="bluesky_add",
        description=tr("cmd.bluesky_add.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def bluesky_add(
        self,
        interaction: discord.Interaction,
        account: str,
        channel: discord.TextChannel,
        ping_role: discord.Role = None,
    ):
        """Ajouter un compte Bluesky à surveiller (handle ou DID)."""
        locale = get_locale(interaction)

        is_valid, error_msg = validate_bluesky_identifier(account, locale)
        if not is_valid:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        handle = normalize_bluesky_identifier(account)

        try:
            async with _http_session(self.bot) as session:
                checker = CheckBlueskyAccount(session)
                profile = await checker.get_profile(handle)
                if not profile:
                    await interaction.response.send_message(
                        t("bluesky.not_found", locale, account=handle)
                    )
                    return

                actual_handle = profile.get("handle", handle)
                did = profile.get("did")
                display_name = profile.get("displayName") or actual_handle

                exists = await asyncio.to_thread(
                    _db_bluesky_exists, actual_handle, str(channel.id)
                )
                if exists:
                    await interaction.response.send_message(
                        t("bluesky.already", locale, name=display_name)
                    )
                    return

                # Initialiser le dernier post connu pour ne pas annoncer l'ancien contenu
                last_post_uri = None
                last_post_cid = None
                feed = await checker.get_author_feed(did, limit=1)
                if feed:
                    post = feed[0].get("post", {})
                    last_post_uri = post.get("uri")
                    last_post_cid = post.get("cid")
        except Exception as e:
            logger.warning(f"Impossible d'initialiser le compte Bluesky {handle}: {e}")
            await interaction.response.send_message(
                t("bluesky.check_error", locale, error=str(e))
            )
            return

        await asyncio.to_thread(
            _db_add_bluesky_account,
            actual_handle,
            did,
            display_name,
            str(channel.id),
            str(ping_role.id) if ping_role else None,
            last_post_uri,
            last_post_cid,
        )

        tracking_text = (
            t("bluesky.tracking_init", locale)
            if last_post_uri
            else t("bluesky.tracking_none", locale)
        )

        await interaction.response.send_message(
            t(
                "bluesky.added",
                locale,
                name=display_name,
                channel=channel.mention,
                tracking=tracking_text,
            )
        )
        if ping_role is not None:
            await interaction.followup.send(
                t("stream.role_announce", locale, role=ping_role.mention)
            )

    @app_commands.command(
        name="bluesky_remove",
        description=tr("cmd.bluesky_remove.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def bluesky_remove(self, interaction: discord.Interaction, account: str):
        """Retirer un compte Bluesky de la liste de surveillance."""
        locale = get_locale(interaction)
        handle = normalize_bluesky_identifier(account)

        if not handle:
            rows = await asyncio.to_thread(_db_list_bluesky_accounts)
            if not rows:
                await interaction.response.send_message(
                    t("bluesky.remove_none", locale)
                )
                return
            account_list = "\n".join([row[1] for row in rows])
            await interaction.response.send_message(
                t("bluesky.remove_specify", locale, list=account_list)
            )
            return

        rows_affected = await asyncio.to_thread(_db_remove_bluesky_account, handle)
        if rows_affected > 0:
            await interaction.response.send_message(
                t("bluesky.removed", locale, name=handle)
            )
        else:
            await interaction.response.send_message(
                t("bluesky.remove_not_found", locale, name=handle)
            )

    @app_commands.command(
        name="bluesky_list",
        description=tr("cmd.bluesky_list.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def bluesky_list(self, interaction: discord.Interaction):
        """Afficher la liste des comptes Bluesky suivis."""
        locale = get_locale(interaction)
        rows = await asyncio.to_thread(_db_list_bluesky_accounts)

        if not rows:
            await interaction.response.send_message(
                f"ℹ️ {t('bluesky.list_title', locale)}: {t('bluesky.chan_none', locale)}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=t("bluesky.list_title", locale),
            color=discord.Color.from_rgb(0, 133, 255),
        )

        for _id, handle, _did, display_name, channel_id, role_id, *_ in rows:
            name = display_name or handle
            channel_mention = (
                f"<#{channel_id}>" if channel_id else t("bluesky.chan_none", locale)
            )
            role_mention = (
                f"<@&{role_id}>" if role_id else t("bluesky.role_none", locale)
            )
            embed.add_field(
                name=name,
                value=t(
                    "bluesky.field_value",
                    locale,
                    handle=handle,
                    channel=channel_mention,
                    role=role_mention,
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Bluesky(bot))
