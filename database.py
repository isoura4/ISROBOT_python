import os
import sqlite3

import dotenv

# Charger les variables d'environnement depuis le fichier .env
dotenv.load_dotenv()

# Chemin vers la base de données SQLite
DB_PATH = os.getenv("db_path")


def get_db_connection():
    """Crée une connexion à la base de données SQLite."""
    if not DB_PATH:
        raise ValueError(
            "Le chemin de la base de données n'est pas défini dans les variables d'environnement."
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    return conn


def create_database():
    """Crée la base de données et les tables nécessaires."""
    if not DB_PATH:
        raise ValueError(
            "Le chemin de la base de données n'est pas défini dans les variables d'environnement."
        )

    if os.path.exists(DB_PATH):
        print("La base de données existe déjà.")
    else:
        print("La base de données n'existe pas, elle va être créée.")

    # Créer les tables nécessaires (toujours exécuter cette partie)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Création de la table des utilisateurs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            guildId TEXT NOT NULL,
            userId TEXT NOT NULL,
            xp REAL DEFAULT 0,
            level INTEGER DEFAULT 1,
            messages INTEGER DEFAULT 0,
            coins REAL DEFAULT 0,
            corners INTEGER DEFAULT 0,
            PRIMARY KEY (guildId, userId)
        )
    """
    )

    # Création de la table des streamers
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS streamers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            streamerName TEXT NOT NULL,
            streamChannelId TEXT,
            roleId TEXT,
            announced INTEGER DEFAULT 0,
            startTime TEXT
        )
    """
    )

    # Création de la table des chaînes YouTube
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS youtube_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channelId TEXT NOT NULL,
            channelName TEXT NOT NULL,
            discordChannelId TEXT NOT NULL,
            roleId TEXT,
            lastVideoId TEXT,
            lastShortId TEXT,
            lastLiveId TEXT,
            notifyVideos INTEGER DEFAULT 1,
            notifyShorts INTEGER DEFAULT 1,
            notifyLive INTEGER DEFAULT 1
        )
    """
    )

    # Création de la table pour le jeu du compteur
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS counter_game (
            guildId TEXT NOT NULL,
            channelId TEXT NOT NULL,
            messageId TEXT DEFAULT '',
            userId TEXT NOT NULL,
            lastUserId TEXT DEFAULT '0',
            count INTEGER DEFAULT 0,
            PRIMARY KEY (guildId, channelId)
        )
    """
    )

    conn.commit()
    conn.close()
    print("Base de données et tables créées avec succès.")


if __name__ == "__main__":
    create_database()
