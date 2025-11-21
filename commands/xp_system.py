import math
import os
import random
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))
DB_PATH = os.getenv("db_path")

# Configuration du système d'XP
XP_PER_MESSAGE = random.randint(15, 25)  # XP aléatoire par message
LEVEL_MULTIPLIER = 125  # Multiplicateur pour calculer l'XP nécessaire par niveau


class XPSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_cooldowns = {}  # Cooldown pour éviter le spam d'XP

    def get_db_connection(self):
        """Crée une connexion à la base de données SQLite."""
        if not DB_PATH:
            raise ValueError("Le chemin de la base de données n'est pas défini.")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_level_from_xp(self, xp):
        """Calcule le niveau basé sur l'XP."""
        return int(math.sqrt(xp / LEVEL_MULTIPLIER)) + 1

    def calculate_xp_for_level(self, level):
        """Calcule l'XP nécessaire pour atteindre un niveau donné."""
        return ((level - 1) ** 2) * LEVEL_MULTIPLIER

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
                INSERT INTO users (guildId, userId, xp, level, messages, coins, corners)
                VALUES (?, ?, ?, ?, ?, 0, 0)
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

        # Ajouter de l'XP
        xp_gain = random.randint(15, 25)
        try:
            result = self.add_user_xp(guild_id, user_id, xp_gain)

            # Si l'utilisateur a level up, envoyer un message priver a l'utilisateur
            if result["level_up"]:
                embed = discord.Embed(
                    title="🎉 Level Up !",
                    description=f"Vous avez atteint le niveau **{result['new_level']}** !",
                    color=discord.Color.gold(),
                )
                embed.add_field(
                    name="XP Total", value=f"{result['new_xp']} XP", inline=True
                )
                embed.add_field(
                    name="Messages", value=f"{result['messages']} messages", inline=True
                )

                await message.author.send(embed=embed, silent=True)

        except Exception as e:
            print(f"Erreur lors de l'ajout d'XP pour {message.author}: {e}")

    @app_commands.command(name="level", description="Affiche votre niveau et votre XP")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def level(
        self, interaction: discord.Interaction, user: discord.Member = None
    ):
        """Affiche le niveau et l'XP d'un utilisateur."""
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
                    "Vous n'avez pas encore d'XP ! Envoyez des messages pour en gagner.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"{target_user.mention} n'a pas encore d'XP !", ephemeral=True
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
            title=f"📊 Niveau de {target_user.display_name}", color=discord.Color.blue()
        )
        embed.set_thumbnail(
            url=(
                target_user.avatar.url
                if target_user.avatar
                else target_user.default_avatar.url
            )
        )

        embed.add_field(name="🎯 Niveau", value=f"**{current_level}**", inline=True)
        embed.add_field(name="⭐ XP Total", value=f"**{current_xp}**", inline=True)
        embed.add_field(name="💬 Messages", value=f"**{messages}**", inline=True)

        # Barre de progression
        progress_bar_length = 20
        progress = int((xp_progress / xp_needed) * progress_bar_length)
        progress_bar = "█" * progress + "░" * (progress_bar_length - progress)

        embed.add_field(
            name="📈 Progression vers le niveau suivant",
            value=f"```{progress_bar}```\n{xp_progress}/{xp_needed} XP",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="leaderboard", description="Affiche le classement des niveaux"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def leaderboard(self, interaction: discord.Interaction):
        """Affiche le leaderboard des niveaux."""
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
                "Aucun utilisateur trouvé dans le classement !", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🏆 Classement des niveaux", color=discord.Color.gold()
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

            leaderboard_text += f"{medals[i]} **{user_name}**\n"
            leaderboard_text += f"   Niveau {row['level']} • {row['xp']} XP • {row['messages']} messages\n\n"

        embed.description = leaderboard_text
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(XPSystem(bot))
