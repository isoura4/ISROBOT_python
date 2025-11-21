import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))
DB_PATH = os.getenv("db_path")


class count(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="count", description="Paramétré le salon du minijeux du compteur."
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def count(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Configure le salon pour le minijeux du compteur."""
        # Vérifier que la commande est exécutée dans un serveur
        if not interaction.guild:
            await interaction.response.send_message(
                "Cette commande ne peut être utilisée qu'dans un serveur.",
                ephemeral=True,
            )
            return

        if not DB_PATH:
            await interaction.response.send_message(
                "Le chemin de la base de données n'est pas défini dans les variables d'environnement.",
                ephemeral=True,
            )
            return

        # Vérifier si le salon est valide
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Veuillez spécifier un salon texte valide.", ephemeral=True
            )
            return

        # Créer la base de données et les tables si elles n'existent pas
        database.create_database()

        # Enregistrer la configuration dans la base de données
        conn = database.get_db_connection()
        cursor = conn.cursor()

        # Vérifier si une configuration existe déjà pour ce serveur et ce canal
        cursor.execute(
            "SELECT * FROM counter_game WHERE guildId = ? AND channelId = ?",
            (str(interaction.guild.id), str(channel.id)),
        )
        existing = cursor.fetchone()

        if existing:
            await interaction.response.send_message(
                f"Le minijeux du compteur est déjà configuré dans le salon {channel.mention}.",
                ephemeral=True,
            )
            conn.close()
            return

        # Insérer la nouvelle configuration
        cursor.execute(
            """
            INSERT INTO counter_game (guildId, channelId, messageId, userId, lastUserId, count)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                str(interaction.guild.id),
                str(channel.id),
                "",
                str(interaction.user.id),
                "0",
                0,
            ),
        )

        conn.commit()
        conn.close()

        await interaction.response.send_message(
            f"Le minijeux du compteur a été configuré dans le salon {channel.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(count(bot))
