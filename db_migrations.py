"""
Database migrations for the minigame system.

This module provides migration scripts to:
1. Backup and remove the legacy 'corners' column from users table
2. Create new tables for quests, shop, trades, and transactions
3. Add guild_settings table for per-guild configuration
4. Ensure all expected columns exist on existing tables
"""

import logging
import re
import os
import shutil
import sqlite3
from datetime import datetime

import dotenv

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

# Database path
_db_path = os.getenv("db_path")
if _db_path:
    if not os.path.isabs(_db_path):
        script_dir = os.path.dirname(__file__)
        DB_PATH = os.path.abspath(os.path.join(script_dir, _db_path))
    else:
        DB_PATH = _db_path
else:
    DB_PATH = None


def get_db_connection(db_path=None):
    """Create a database connection."""
    path = db_path or DB_PATH
    if not path:
        raise ValueError("Database path not defined in environment variables.")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def backup_database(db_path=None):
    """Create a backup of the database before migration."""
    path = db_path or DB_PATH
    if not path or not os.path.exists(path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{path}.{timestamp}.bak"
    shutil.copy2(path, backup_path)
    logger.info(f"Database backup created: {backup_path}")
    return backup_path


def remove_corners_column(db_path=None):
    """
    Remove the legacy 'corners' column from the users table.

    SQLite doesn't support DROP COLUMN directly in older versions,
    so we recreate the table without that column.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # Check if corners column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "corners" not in column_names:
            logger.info(
                "Column 'corners' does not exist in users table. Skipping."
            )
            return True

        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")

        # Create new table without corners column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users_new (
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                xp REAL DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                coins REAL DEFAULT 0,
                PRIMARY KEY (guildId, userId)
            )
        """)

        # Copy data from old table (excluding corners)
        cursor.execute("""
            INSERT INTO users_new (guildId, userId, xp, level, messages, coins)
            SELECT guildId, userId, xp, level, messages, coins FROM users
        """)

        # Drop old table and rename new one
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_new RENAME TO users")

        conn.commit()
        logger.info("Successfully removed 'corners' column from users table.")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error removing corners column: {e}")
        return False
    finally:
        conn.close()


def create_minigame_tables(db_path=None):
    """Create all new tables needed for the minigame system."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # Guild settings table for minigame channel configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guildId TEXT PRIMARY KEY,
                minigame_enabled INTEGER DEFAULT 1,
                minigame_channel_id TEXT,
                xp_trading_enabled INTEGER DEFAULT 1,
                trade_tax_percent REAL DEFAULT 10.0,
                duel_tax_percent REAL DEFAULT 10.0,
                daily_xp_transfer_cap_percent REAL DEFAULT 10.0,
                daily_xp_transfer_cap_max INTEGER DEFAULT 500,
                capture_cooldown_seconds INTEGER DEFAULT 60,
                duel_cooldown_seconds INTEGER DEFAULT 300,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Quest exception channels (for quests that can be done in other channels)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quest_exception_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                channelId TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guildId, channelId)
            )
        """)

        # Quests table (quest templates)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('daily', 'random', 'event')),
                target_type TEXT NOT NULL,
                target_value INTEGER NOT NULL DEFAULT 1,
                reward_coins INTEGER DEFAULT 0,
                reward_xp INTEGER DEFAULT 0,
                allow_other_channels INTEGER DEFAULT 0,
                rarity TEXT DEFAULT 'common' CHECK(
                    rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary')
                ),
                metadata TEXT DEFAULT '{}',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User quests (assigned quests to users)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                questId INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (questId) REFERENCES quests(id)
            )
        """)

        # User daily quest tracking (for streaks and limits)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_daily_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                last_daily_claim TEXT,
                streak INTEGER DEFAULT 0,
                daily_xp_transferred INTEGER DEFAULT 0,
                last_xp_transfer_reset TEXT,
                last_capture_at TEXT,
                last_duel_at TEXT,
                UNIQUE(guildId, userId)
            )
        """)

        # Shop items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price_coins INTEGER DEFAULT 0,
                price_xp INTEGER DEFAULT 0,
                consumable INTEGER DEFAULT 1,
                stock INTEGER DEFAULT -1,
                metadata TEXT DEFAULT '{}',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User inventory (for consumable items)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                itemId INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (itemId) REFERENCES shop_items(id),
                UNIQUE(guildId, userId, itemId)
            )
        """)

        # User active effects (from consumable items)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_active_effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                effect_data TEXT DEFAULT '{}',
                expires_at TEXT NOT NULL,
                UNIQUE(guildId, userId, effect_type)
            )
        """)

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                fromUserId TEXT NOT NULL,
                toUserId TEXT NOT NULL,
                coins INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending' CHECK(
                    status IN (
                        'pending', 'accepted', 'completed', 'canceled', 'expired'
                    )
                ),
                tax_coins INTEGER DEFAULT 0,
                tax_xp INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                accepted_at TEXT,
                escrow_release_at TEXT,
                completed_at TEXT
            )
        """)

        # Transactions ledger (for audit trail)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                kind TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'coins' CHECK(currency IN ('coins', 'xp')),
                balance_after REAL,
                metadata TEXT DEFAULT '{}',
                related_id INTEGER,
                related_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User cooldowns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_cooldowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                action_type TEXT NOT NULL,
                last_action_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guildId, userId, action_type)
            )
        """)

        conn.commit()
        logger.info("Successfully created all minigame tables.")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating minigame tables: {e}")
        return False
    finally:
        conn.close()


def seed_default_quests(db_path=None):
    """Seed the database with default quest templates."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    default_quests = [
        # Daily quests
        (
            "Message Master",
            "Send 10 messages in the server",
            "daily",
            "messages_sent",
            10,
            50,
            25,
            0,
            "common",
            '{"channel_type": "any"}',
        ),
        (
            "Chatter",
            "Send 25 messages in the server",
            "daily",
            "messages_sent",
            25,
            100,
            50,
            0,
            "uncommon",
            '{"channel_type": "any"}',
        ),
        (
            "Counter Helper",
            "Participate in the counting minigame 5 times",
            "daily",
            "counting_participation",
            5,
            75,
            30,
            1,
            "common",
            '{"requires_counting_channel": true}',
        ),
        (
            "Lucky Coin",
            "Use coinflip 3 times",
            "daily",
            "coinflip_used",
            3,
            30,
            15,
            0,
            "common",
            "{}",
        ),
        # Random quests
        (
            "Capture Novice",
            "Attempt 3 captures",
            "random",
            "capture_attempt",
            3,
            100,
            50,
            0,
            "uncommon",
            "{}",
        ),
        (
            "Duel Challenger",
            "Challenge someone to a duel",
            "random",
            "duel_challenge",
            1,
            75,
            40,
            0,
            "uncommon",
            "{}",
        ),
        (
            "Big Spender",
            "Spend 100 coins in the shop",
            "random",
            "coins_spent",
            100,
            50,
            25,
            0,
            "rare",
            "{}",
        ),
        (
            "Social Butterfly",
            "Send 50 messages",
            "random",
            "messages_sent",
            50,
            200,
            100,
            0,
            "rare",
            "{}",
        ),
        (
            "Treasure Hunter",
            "Win 200 coins from captures",
            "random",
            "coins_won_capture",
            200,
            150,
            75,
            0,
            "epic",
            "{}",
        ),
    ]

    try:
        cursor.execute("SELECT COUNT(*) FROM quests")
        count = cursor.fetchone()[0]
        if count > 0:
            logger.info(f"Quests table already has {count} entries. Skipping seed.")
            return True

        cursor.executemany(
            """
            INSERT INTO quests (
                name, description, type, target_type, target_value,
                reward_coins, reward_xp, allow_other_channels, rarity, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            default_quests,
        )

        conn.commit()
        logger.info(f"Successfully seeded {len(default_quests)} default quests.")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error seeding default quests: {e}")
        return False
    finally:
        conn.close()


def seed_default_shop_items(db_path=None):
    """Seed the database with default shop items."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    default_items = [
        (
            "XP Boost (Small)",
            "Gain 25% more XP from messages for 1 hour",
            100,
            0,
            1,
            -1,
            '{"effect": "xp_boost", "multiplier": 1.25, "duration_minutes": 60}',
        ),
        (
            "XP Boost (Large)",
            "Gain 50% more XP from messages for 1 hour",
            250,
            0,
            1,
            -1,
            '{"effect": "xp_boost", "multiplier": 1.50, "duration_minutes": 60}',
        ),
        (
            "Capture Luck Charm",
            "Increase capture success rate by 10% for 30 minutes",
            150,
            0,
            1,
            -1,
            '{"effect": "capture_luck", "bonus": 0.10, "duration_minutes": 30}',
        ),
        (
            "Quest Reroll Token",
            "Reroll one of your daily quests",
            200,
            0,
            1,
            -1,
            '{"effect": "quest_reroll", "uses": 1}',
        ),
        (
            "Trade Fee Waiver",
            "Waive tax on your next trade",
            300,
            0,
            1,
            -1,
            '{"effect": "trade_fee_waiver", "uses": 1}',
        ),
        (
            "XP Shield",
            "Protect your XP from loss in the next failed capture",
            100,
            50,
            1,
            -1,
            '{"effect": "xp_shield", "uses": 1}',
        ),
    ]

    try:
        cursor.execute("SELECT COUNT(*) FROM shop_items")
        count = cursor.fetchone()[0]
        if count > 0:
            logger.info(
                f"Shop items table already has {count} entries. Skipping seed."
            )
            return True

        cursor.executemany(
            """
            INSERT INTO shop_items (
                name, description, price_coins, price_xp, consumable, stock, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            default_items,
        )

        conn.commit()
        logger.info(f"Successfully seeded {len(default_items)} default shop items.")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error seeding default shop items: {e}")
        return False
    finally:
        conn.close()


def ensure_table_columns(db_path=None):
    """
    Ensure all expected columns exist on existing tables.

    Compares actual table schemas with expected schemas and adds any
    missing columns using ALTER TABLE ADD COLUMN. This prevents errors
    when upgrading between versions that add new columns.
    """
    # Define expected columns for each table: (column_name, column_definition)
    expected_columns = {
        "users": [
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("xp", "REAL DEFAULT 0"),
            ("level", "INTEGER DEFAULT 1"),
            ("messages", "INTEGER DEFAULT 0"),
            ("coins", "REAL DEFAULT 0"),
        ],
        "streamers": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("streamerName", "TEXT NOT NULL"),
            ("streamChannelId", "TEXT"),
            ("roleId", "TEXT"),
            ("announced", "INTEGER DEFAULT 0"),
            ("startTime", "TEXT"),
        ],
        "youtube_channels": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("channelId", "TEXT NOT NULL"),
            ("channelName", "TEXT NOT NULL"),
            ("discordChannelId", "TEXT NOT NULL"),
            ("roleId", "TEXT"),
            ("lastVideoId", "TEXT"),
            ("lastShortId", "TEXT"),
            ("lastLiveId", "TEXT"),
            ("notifyVideos", "INTEGER DEFAULT 1"),
            ("notifyShorts", "INTEGER DEFAULT 1"),
            ("notifyLive", "INTEGER DEFAULT 1"),
        ],
        "counter_game": [
            ("guildId", "TEXT NOT NULL"),
            ("channelId", "TEXT NOT NULL"),
            ("messageId", "TEXT DEFAULT ''"),
            ("userId", "TEXT NOT NULL"),
            ("lastUserId", "TEXT DEFAULT '0'"),
            ("count", "INTEGER DEFAULT 0"),
        ],
        "warnings": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guild_id", "TEXT NOT NULL"),
            ("user_id", "TEXT NOT NULL"),
            ("warn_count", "INTEGER DEFAULT 0"),
            ("created_at", "TEXT NOT NULL"),
            ("updated_at", "TEXT NOT NULL"),
        ],
        "warning_history": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guild_id", "TEXT NOT NULL"),
            ("user_id", "TEXT NOT NULL"),
            ("action", "TEXT NOT NULL"),
            ("warn_count_before", "INTEGER NOT NULL"),
            ("warn_count_after", "INTEGER NOT NULL"),
            ("moderator_id", "TEXT"),
            ("reason", "TEXT"),
            ("created_at", "TEXT NOT NULL"),
        ],
        "moderation_appeals": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guild_id", "TEXT NOT NULL"),
            ("user_id", "TEXT NOT NULL"),
            ("warning_history_id", "INTEGER"),
            ("appeal_reason", "TEXT NOT NULL"),
            ("moderator_id", "TEXT"),
            ("status", "TEXT DEFAULT 'pending'"),
            ("moderator_decision", "TEXT"),
            ("created_at", "TEXT NOT NULL"),
            ("reviewed_at", "TEXT"),
        ],
        "moderation_config": [
            ("guild_id", "TEXT PRIMARY KEY"),
            ("log_channel_id", "TEXT"),
            ("appeal_channel_id", "TEXT"),
            ("ai_enabled", "INTEGER DEFAULT 1"),
            ("ai_confidence_threshold", "INTEGER DEFAULT 60"),
            ("ai_flag_channel_id", "TEXT"),
            ("ai_model", "TEXT DEFAULT 'llama2'"),
            ("ollama_host", "TEXT DEFAULT 'http://localhost:11434'"),
            ("decay_multiplier", "REAL DEFAULT 1.0"),
            ("warn_1_decay_days", "INTEGER DEFAULT 7"),
            ("warn_2_decay_days", "INTEGER DEFAULT 14"),
            ("warn_3_decay_days", "INTEGER DEFAULT 21"),
            ("mute_duration_warn_2", "INTEGER DEFAULT 3600"),
            ("mute_duration_warn_3", "INTEGER DEFAULT 86400"),
            ("rules_message_id", "TEXT"),
            ("created_at", "TEXT NOT NULL"),
        ],
        "ai_flags": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guild_id", "TEXT NOT NULL"),
            ("message_id", "TEXT NOT NULL"),
            ("channel_id", "TEXT NOT NULL"),
            ("user_id", "TEXT NOT NULL"),
            ("message_content", "TEXT NOT NULL"),
            ("ai_score", "INTEGER NOT NULL"),
            ("ai_category", "TEXT NOT NULL"),
            ("ai_reason", "TEXT NOT NULL"),
            ("moderator_action", "TEXT DEFAULT 'pending'"),
            ("moderator_id", "TEXT"),
            ("created_at", "TEXT NOT NULL"),
            ("reviewed_at", "TEXT"),
        ],
        "active_mutes": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guild_id", "TEXT NOT NULL"),
            ("user_id", "TEXT NOT NULL"),
            ("moderator_id", "TEXT"),
            ("reason", "TEXT NOT NULL"),
            ("expires_at", "TEXT NOT NULL"),
            ("created_at", "TEXT NOT NULL"),
        ],
        "guild_settings": [
            ("guildId", "TEXT PRIMARY KEY"),
            ("minigame_enabled", "INTEGER DEFAULT 1"),
            ("minigame_channel_id", "TEXT"),
            ("xp_trading_enabled", "INTEGER DEFAULT 1"),
            ("trade_tax_percent", "REAL DEFAULT 10.0"),
            ("duel_tax_percent", "REAL DEFAULT 10.0"),
            ("daily_xp_transfer_cap_percent", "REAL DEFAULT 10.0"),
            ("daily_xp_transfer_cap_max", "INTEGER DEFAULT 500"),
            ("capture_cooldown_seconds", "INTEGER DEFAULT 60"),
            ("duel_cooldown_seconds", "INTEGER DEFAULT 300"),
            ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
        "quests": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("name", "TEXT NOT NULL"),
            ("description", "TEXT NOT NULL"),
            ("type", "TEXT NOT NULL"),
            ("target_type", "TEXT NOT NULL"),
            ("target_value", "INTEGER NOT NULL DEFAULT 1"),
            ("reward_coins", "INTEGER DEFAULT 0"),
            ("reward_xp", "INTEGER DEFAULT 0"),
            ("allow_other_channels", "INTEGER DEFAULT 0"),
            ("rarity", "TEXT DEFAULT 'common'"),
            ("metadata", "TEXT DEFAULT '{}'"),
            ("active", "INTEGER DEFAULT 1"),
            ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
        "user_quests": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("questId", "INTEGER NOT NULL"),
            ("progress", "INTEGER DEFAULT 0"),
            ("completed", "INTEGER DEFAULT 0"),
            ("claimed", "INTEGER DEFAULT 0"),
            ("assigned_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("completed_at", "TEXT"),
        ],
        "user_daily_tracking": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("last_daily_claim", "TEXT"),
            ("streak", "INTEGER DEFAULT 0"),
            ("daily_xp_transferred", "INTEGER DEFAULT 0"),
            ("last_xp_transfer_reset", "TEXT"),
            ("last_capture_at", "TEXT"),
            ("last_duel_at", "TEXT"),
        ],
        "shop_items": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("name", "TEXT NOT NULL"),
            ("description", "TEXT NOT NULL"),
            ("price_coins", "INTEGER DEFAULT 0"),
            ("price_xp", "INTEGER DEFAULT 0"),
            ("consumable", "INTEGER DEFAULT 1"),
            ("stock", "INTEGER DEFAULT -1"),
            ("metadata", "TEXT DEFAULT '{}'"),
            ("active", "INTEGER DEFAULT 1"),
            ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
        "user_inventory": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("itemId", "INTEGER NOT NULL"),
            ("quantity", "INTEGER DEFAULT 1"),
            ("acquired_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
        "user_active_effects": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("effect_type", "TEXT NOT NULL"),
            ("effect_data", "TEXT DEFAULT '{}'"),
            ("expires_at", "TEXT NOT NULL"),
        ],
        "trades": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("fromUserId", "TEXT NOT NULL"),
            ("toUserId", "TEXT NOT NULL"),
            ("coins", "INTEGER DEFAULT 0"),
            ("xp", "INTEGER DEFAULT 0"),
            ("status", "TEXT DEFAULT 'pending'"),
            ("tax_coins", "INTEGER DEFAULT 0"),
            ("tax_xp", "INTEGER DEFAULT 0"),
            ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("accepted_at", "TEXT"),
            ("escrow_release_at", "TEXT"),
            ("completed_at", "TEXT"),
        ],
        "transactions": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("kind", "TEXT NOT NULL"),
            ("amount", "REAL NOT NULL"),
            ("currency", "TEXT DEFAULT 'coins'"),
            ("balance_after", "REAL"),
            ("metadata", "TEXT DEFAULT '{}'"),
            ("related_id", "INTEGER"),
            ("related_type", "TEXT"),
            ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
        "user_cooldowns": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("userId", "TEXT NOT NULL"),
            ("action_type", "TEXT NOT NULL"),
            ("last_action_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
        "quest_exception_channels": [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("guildId", "TEXT NOT NULL"),
            ("channelId", "TEXT NOT NULL"),
            ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ],
    }

    # Regex pattern for valid SQLite identifiers (alphanumeric + underscore)
    _valid_identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    added_columns = []

    try:
        for table_name, columns in expected_columns.items():
            # Validate table name to prevent SQL injection
            if not _valid_identifier.match(table_name):
                logger.warning(f"Skipping invalid table name: {table_name}")
                continue

            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                continue

            # Get existing columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_cols = {row[1] for row in cursor.fetchall()}

            # Add missing columns
            for col_name, col_def in columns:
                if col_name not in existing_cols:
                    # Validate column name to prevent SQL injection
                    if not _valid_identifier.match(col_name):
                        logger.warning(
                            f"Skipping invalid column name: {col_name}"
                        )
                        continue

                    # Remove PRIMARY KEY / NOT NULL / UNIQUE constraints
                    # for ALTER TABLE ADD COLUMN (SQLite limitation)
                    safe_def = col_def.replace("PRIMARY KEY AUTOINCREMENT", "")
                    safe_def = safe_def.replace("PRIMARY KEY", "")
                    safe_def = safe_def.replace("NOT NULL", "")
                    safe_def = safe_def.strip()
                    if not safe_def:
                        safe_def = "TEXT"
                    try:
                        cursor.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {col_name} {safe_def}"
                        )
                        added_columns.append(f"{table_name}.{col_name}")
                        logger.info(
                            f"Added missing column '{col_name}' to table '{table_name}'"
                        )
                    except sqlite3.OperationalError as e:
                        logger.warning(
                            f"Could not add column '{col_name}' to "
                            f"'{table_name}': {e}"
                        )

        conn.commit()

        if added_columns:
            logger.info(
                f"Column migration complete: {len(added_columns)} column(s) added"
            )
        else:
            logger.debug("Column migration: all columns are up to date")

        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error during column migration: {e}")
        return False
    finally:
        conn.close()


def run_all_migrations(db_path=None):
    """Run all migrations in order."""
    logger.info("Starting database migrations...")

    # Create backup first
    backup = backup_database(db_path)
    if backup:
        logger.info(f"Backup created at: {backup}")

    # Run migrations
    success = True

    if not remove_corners_column(db_path):
        logger.warning("corners column removal failed or skipped")

    if not create_minigame_tables(db_path):
        logger.error("Failed to create minigame tables")
        success = False

    if success:
        # Seed default data
        seed_default_quests(db_path)
        seed_default_shop_items(db_path)

    # Ensure all expected columns exist on existing tables
    if not ensure_table_columns(db_path):
        logger.warning("Column migration encountered issues")

    if success:
        logger.info("All migrations completed successfully!")
    else:
        logger.error("Some migrations failed. Check logs above.")

    return success


if __name__ == "__main__":
    # Configure basic logging when running as script
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_all_migrations()
