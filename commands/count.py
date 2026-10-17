import asyncio
import os

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


def _configure_counter(guild_id: str, channel_id: str, user_id: str) -> bool:
    """Enregistre la configuration du compteur.

    Retourne ``True`` si la configuration vient d'être créée, ``False`` si
    elle existait déjà. Exécuté dans un thread pour ne pas bloquer l'event loop.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM counter_game WHERE guildId = ? AND channelId = ?",
            (guild_id, channel_id),
        )
        if cursor.fetchone():
            return False

        cursor.execute(
            """
            INSERT INTO counter_game
            (guildId, channelId, messageId, userId, lastUserId, count)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (guild_id, channel_id, "", user_id, "0", 0),
        )
        conn.commit()
        return True
    finally:
        conn.close()


class Count(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="count", description=tr("cmd.count.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def count(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Configure le salon pour le minijeux du compteur."""
        locale = get_locale(interaction)
        # Vérifier que la commande est exécutée dans un serveur
        if not interaction.guild:
            await interaction.response.send_message(
                t("count.guild_only", locale),
                ephemeral=True,
            )
            return

        if not database.DB_PATH:
            await interaction.response.send_message(
                t("count.no_db", locale),
                ephemeral=True,
            )
            return

        # Enregistrer la configuration dans la base de données
        created = await asyncio.to_thread(
            _configure_counter,
            str(interaction.guild.id),
            str(channel.id),
            str(interaction.user.id),
        )

        if not created:
            await interaction.response.send_message(
                t("count.already", locale, channel=channel.mention),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            t("count.configured", locale, channel=channel.mention),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Count(bot))
