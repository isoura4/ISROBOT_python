import os
import sqlite3

import dotenv

# Charger les variables d'environnement depuis le fichier .env
dotenv.load_dotenv()

# Chemin vers la base de données SQLite
# Convertir en chemin absolu pour éviter les problèmes de localisation
_db_path = os.getenv("db_path")
if _db_path:
    # Si le chemin est relatif, le rendre absolu par rapport au répertoire du script
    if not os.path.isabs(_db_path):
        script_dir = os.path.dirname(__file__)
        DB_PATH = os.path.abspath(os.path.join(script_dir, _db_path))
    else:
        DB_PATH = _db_path
else:
    DB_PATH = None


def get_db_connection():
    """Crée une connexion à la base de données SQLite."""
    if not DB_PATH:
        raise ValueError(
            "Le chemin de la base de données n'est pas défini "
            "dans les variables d'environnement."
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    return conn


def create_database():
    """Crée la base de données et les tables nécessaires."""
    if not DB_PATH:
        raise ValueError(
            "Le chemin de la base de données n'est pas défini "
            "dans les variables d'environnement."
        )

    db_existed = os.path.exists(DB_PATH)
    if db_existed:
        print(
            f"La base de données existe déjà à l'emplacement: {DB_PATH}"
        )
    else:
        print(
            f"La base de données n'existe pas, elle va être créée "
            f"à l'emplacement: {DB_PATH}"
        )

    # Créer les tables nécessaires (toujours exécuter cette partie)
    # CREATE TABLE IF NOT EXISTS permet de créer uniquement si la table n'existe pas
    # et ne supprime PAS les données existantes
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

    if db_existed:
        print(
            "Tables vérifiées et créées si nécessaire "
            "(données existantes préservées)."
        )
    else:
        print("Base de données et tables créées avec succès.")


if __name__ == "__main__":
    create_database()
