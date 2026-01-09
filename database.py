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
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
        return conn
    except sqlite3.Error as e:
        # Fermer la connexion si elle a été créée mais que la configuration a échoué
        if conn:
            conn.close()
        raise RuntimeError(f"Impossible de se connecter à la base de données {DB_PATH}: {e}")


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

    # --- MODERATION SYSTEM TABLES ---

    # Table des avertissements (warnings)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            warn_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(guild_id, user_id)
        )
    """
    )

    # Index pour les recherches fréquentes
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_warnings_guild_user 
        ON warnings(guild_id, user_id)
    """
    )

    # Historique des avertissements (audit trail immuable)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS warning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            warn_count_before INTEGER NOT NULL,
            warn_count_after INTEGER NOT NULL,
            moderator_id TEXT,
            reason TEXT,
            created_at TEXT NOT NULL
        )
    """
    )

    # Index pour les recherches d'historique
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_history_guild_user 
        ON warning_history(guild_id, user_id)
    """
    )

    # Table des appels (appeals)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS moderation_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            warning_history_id INTEGER,
            appeal_reason TEXT NOT NULL,
            moderator_id TEXT,
            status TEXT DEFAULT 'pending',
            moderator_decision TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            FOREIGN KEY(warning_history_id) REFERENCES warning_history(id)
        )
    """
    )

    # Index pour les appels en attente
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_appeals_status 
        ON moderation_appeals(guild_id, status)
    """
    )

    # Configuration de modération par serveur
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS moderation_config (
            guild_id TEXT PRIMARY KEY,
            log_channel_id TEXT,
            appeal_channel_id TEXT,
            ai_enabled INTEGER DEFAULT 1,
            ai_confidence_threshold INTEGER DEFAULT 60,
            ai_flag_channel_id TEXT,
            ai_model TEXT DEFAULT 'llama2',
            ollama_host TEXT DEFAULT 'http://localhost:11434',
            decay_multiplier REAL DEFAULT 1.0,
            warn_1_decay_days INTEGER DEFAULT 7,
            warn_2_decay_days INTEGER DEFAULT 14,
            warn_3_decay_days INTEGER DEFAULT 21,
            mute_duration_warn_2 INTEGER DEFAULT 3600,
            mute_duration_warn_3 INTEGER DEFAULT 86400,
            rules_message_id TEXT,
            created_at TEXT NOT NULL
        )
    """
    )

    # Table des messages signalés par l'IA
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            message_content TEXT NOT NULL,
            ai_score INTEGER NOT NULL,
            ai_category TEXT NOT NULL,
            ai_reason TEXT NOT NULL,
            moderator_action TEXT DEFAULT 'pending',
            moderator_id TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(message_id)
        )
    """
    )

    # Index pour les flags en attente
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_flags_status 
        ON ai_flags(guild_id, moderator_action)
    """
    )

    # Table des mutes actifs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS active_mutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            moderator_id TEXT,
            reason TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(guild_id, user_id)
        )
    """
    )

    # Index pour les recherches d'expiration
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_mutes_expires 
        ON active_mutes(expires_at)
    """
    )

    # --- ENGAGEMENT SYSTEM TABLES ---

    # Configuration d'engagement par serveur
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS engagement_config (
            guild_id TEXT PRIMARY KEY,
            xp_per_message INTEGER DEFAULT 1,
            welcome_bonus_xp INTEGER DEFAULT 10,
            welcome_detection_enabled INTEGER DEFAULT 1,
            announcements_channel_id TEXT,
            ambassador_role_id TEXT,
            new_member_role_id TEXT,
            new_member_role_duration_days INTEGER DEFAULT 7,
            welcome_dm_enabled INTEGER DEFAULT 1,
            welcome_dm_text TEXT DEFAULT 'Bienvenue sur le serveur ! 🎉

**Guide de démarrage:**
1. 📋 Consultez les règles du serveur
2. 🎭 Choisissez vos rôles
3. 👋 Présentez-vous dans le salon approprié
4. 🔍 Explorez les différents salons

N''hésitez pas à poser des questions !',
            welcome_public_text TEXT DEFAULT 'Bienvenue {user} sur le serveur ! 🎉',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Paliers XP et rôles associés
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS xp_thresholds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            threshold_points INTEGER NOT NULL,
            role_id TEXT NOT NULL,
            role_name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, threshold_points)
        )
    """
    )

    # Index pour les seuils XP
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_xp_thresholds_guild 
        ON xp_thresholds(guild_id, threshold_points)
    """
    )

    # Challenges hebdomadaires
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            reward_xp INTEGER DEFAULT 100,
            reward_role_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Historique des challenges lancés
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS challenge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            challenge_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            message_id TEXT,
            FOREIGN KEY(challenge_id) REFERENCES weekly_challenges(id)
        )
    """
    )

    # Membres temporaires (pour le rôle "Nouveau")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS temp_member_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            UNIQUE(guild_id, user_id, role_id)
        )
    """
    )

    # Index pour les rôles temporaires expirés
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_temp_roles_expires 
        ON temp_member_roles(expires_at)
    """
    )

    # Rappels d'événements envoyés
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS event_reminders_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            reminder_type TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(guild_id, event_id, reminder_type)
        )
    """
    )

    # Statistiques de messages par canal (pour analytics)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            date TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            UNIQUE(guild_id, channel_id, date)
        )
    """
    )

    # Index pour les stats de canaux
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_channel_stats_guild_date 
        ON channel_stats(guild_id, date)
    """
    )

    # Historique de croissance des membres
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS member_growth (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            date TEXT NOT NULL,
            member_count INTEGER NOT NULL,
            joins_today INTEGER DEFAULT 0,
            leaves_today INTEGER DEFAULT 0,
            UNIQUE(guild_id, date)
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
