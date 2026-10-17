import asyncio
import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.i18n import get_locale, t, tr
from utils.logging_config import get_logger
from utils.xp import calculate_level_from_xp, calculate_xp_for_level

# Chargement du fichier .env
load_dotenv()

# Configure logging for this module
logger = get_logger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))


class XPSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_cooldowns = {}  # Cooldown pour éviter le spam d'XP

    def get_db_connection(self):
        """Crée une connexion à la base de données SQLite."""
        import database

        return database.get_db_connection()

    def calculate_level_from_xp(self, xp):
        """Calcule le niveau basé sur l'XP."""
        return calculate_level_from_xp(xp)

    def calculate_xp_for_level(self, level):
        """Calcule l'XP nécessaire pour atteindre un niveau donné."""
        return calculate_xp_for_level(level)

    def add_user_xp(self, guild_id, user_id, xp_gain):
        """Ajoute de l'XP à un utilisateur et met à jour son niveau."""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Vérifier si l'utilisateur existe
        cursor.execute(
            "SELECT xp, level, messages FROM users WHERE guildId = ? AND userId = ?",
            (str(guild_id), str(user_id)),
        )
        result = cursor.fetchone()

        if result:
            # L'utilisateur existe, on met à jour ses stats
            old_xp = result["xp"]
            old_level = result["level"]
            old_messages = result["messages"]

            new_xp = old_xp + xp_gain
            new_level = self.calculate_level_from_xp(new_xp)
            new_messages = old_messages + 1

            cursor.execute(
                """
                UPDATE users
                SET xp = ?, level = ?, messages = ?
                WHERE guildId = ? AND userId = ?
            """,
                (new_xp, new_level, new_messages, str(guild_id), str(user_id)),
            )

            level_up = new_level > old_level
        else:
            # L'utilisateur n'existe pas, on le crée
            new_xp = xp_gain
            new_level = self.calculate_level_from_xp(new_xp)
            new_messages = 1

            cursor.execute(
                """
                INSERT INTO users (guildId, userId, xp, level, messages, coins)
                VALUES (?, ?, ?, ?, ?, 0)
            """,
                (str(guild_id), str(user_id), new_xp, new_level, new_messages),
            )

            level_up = new_level > 1

        conn.commit()
        conn.close()

        return {
            "new_xp": new_xp,
            "new_level": new_level,
            "level_up": level_up,
            "messages": new_messages,
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        """Écoute les messages et ajoute de l'XP."""
        # Ignorer les messages des bots
        if message.author.bot:
            return

        # Vérifier que le message est dans un serveur
        if not message.guild:
            return

        # Vérifier le serveur autorisé (optionnel)
        if message.guild.id != SERVER_ID:
            return

        user_id = message.author.id
        guild_id = message.guild.id

        # Système de cooldown pour éviter le spam (1 minute)
        cooldown_key = f"{guild_id}_{user_id}"
        current_time = discord.utils.utcnow().timestamp()

        if cooldown_key in self.user_cooldowns:
            if current_time - self.user_cooldowns[cooldown_key] < 60:  # 60 secondes
                return

        self.user_cooldowns[cooldown_key] = current_time

        # Bornage mémoire : purge les cooldowns expirés quand le dict grossit
        if len(self.user_cooldowns) > 1000:
            cutoff = current_time - 60
            self.user_cooldowns = {
                k: v for k, v in self.user_cooldowns.items() if v >= cutoff
            }

        # Ajouter de l'XP
        xp_gain = random.randint(15, 25)
        try:
            result = await asyncio.to_thread(
                self.add_user_xp, guild_id, user_id, xp_gain
            )

            # Si l'utilisateur a level up, envoyer un message privé à l'utilisateur
            if result["level_up"]:
                try:
                    embed = discord.Embed(
                        title=t("xp.levelup.title"),
                        description=t(
                            "xp.levelup.description", level=result["new_level"]
                        ),
                        color=discord.Color.gold(),
                    )
                    embed.add_field(
                        name=t("xp.field_total"),
                        value=f"{result['new_xp']} XP",
                        inline=True,
                    )
                    embed.add_field(
                        name=t("xp.field_messages"),
                        value=t("xp.messages_count", count=result["messages"]),
                        inline=True,
                    )

                    await message.author.send(embed=embed, silent=True)
                except discord.errors.Forbidden:
                    # L'utilisateur a désactivé les MP ou a bloqué le bot
                    logger.debug(
                        f"Cannot send DM to {message.author}: permission denied or blocked"
                    )
                except Exception as e:
                    logger.warning(
                        f"Erreur lors de l'envoi du message de level up à {message.author}: {e}"
                    )

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'XP pour {message.author}: {e}")

    @app_commands.command(name="level", description=tr("cmd.level.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def level(
        self, interaction: discord.Interaction, user: discord.Member = None
    ):
        """Affiche le niveau et l'XP d'un utilisateur."""
        locale = get_locale(interaction)
        target_user = user or interaction.user

        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT xp, level, messages FROM users WHERE guildId = ? AND userId = ?",
            (str(interaction.guild.id), str(target_user.id)),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            if target_user == interaction.user:
                await interaction.response.send_message(
                    t("xp.no_xp_self", locale),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    t("xp.no_xp_other", locale, user=target_user.mention),
                    ephemeral=True,
                )
            return

        current_xp = result["xp"]
        current_level = result["level"]
        messages = result["messages"]

        # Calculer l'XP nécessaire pour le niveau suivant
        xp_for_current_level = self.calculate_xp_for_level(current_level)
        xp_for_next_level = self.calculate_xp_for_level(current_level + 1)
        xp_progress = current_xp - xp_for_current_level
        xp_needed = xp_for_next_level - xp_for_current_level

        # Créer l'embed
        embed = discord.Embed(
            title=t("xp.level_title", locale, user=target_user.display_name),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(
            url=(
                target_user.avatar.url
                if target_user.avatar
                else target_user.default_avatar.url
            )
        )

        embed.add_field(
            name=t("xp.field_level", locale),
            value=f"**{current_level}**",
            inline=True,
        )
        embed.add_field(
            name=t("xp.field_xp", locale), value=f"**{current_xp}**", inline=True
        )
        embed.add_field(
            name=t("xp.field_messages_emoji", locale),
            value=f"**{messages}**",
            inline=True,
        )

        # Barre de progression
        progress_bar_length = 20
        progress = int((xp_progress / xp_needed) * progress_bar_length)
        progress_bar = "█" * progress + "░" * (progress_bar_length - progress)

        embed.add_field(
            name=t("xp.field_progress", locale),
            value=f"```{progress_bar}```\n{xp_progress}/{xp_needed} XP",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description=tr("cmd.leaderboard.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def leaderboard(self, interaction: discord.Interaction):
        """Affiche le leaderboard des niveaux."""
        locale = get_locale(interaction)
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT userId, xp, level, messages
            FROM users
            WHERE guildId = ?
            ORDER BY xp DESC
            LIMIT 10
        """,
            (str(interaction.guild.id),),
        )

        results = cursor.fetchall()
        conn.close()

        if not results:
            await interaction.response.send_message(
                t("xp.leaderboard_empty", locale), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=t("xp.leaderboard_title", locale), color=discord.Color.gold()
        )

        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7

        leaderboard_text = ""
        for i, row in enumerate(results):
            # Essayer de récupérer l'utilisateur dans le serveur
            if interaction.guild:
                user = interaction.guild.get_member(int(row["userId"]))
            else:
                user = None

            if user:
                # L'utilisateur est dans le serveur
                user_name = user.display_name
            else:
                # L'utilisateur n'est plus dans le serveur, utiliser son mention
                user_name = f"<@{row['userId']}>"

            leaderboard_text += (
                t(
                    "xp.leaderboard_entry",
                    locale,
                    medal=medals[i],
                    name=user_name,
                    level=row["level"],
                    xp=row["xp"],
                    messages=row["messages"],
                )
                + "\n\n"
            )

        embed.description = leaderboard_text
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(XPSystem(bot))
