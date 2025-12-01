"""
Unit tests for the minigame system.

This module tests:
- DB helpers (ensure_user_exists, add_coins, spend_coins, add_xp, spend_xp)
- Migration script
- Quest logic
- Trade lifecycle
- Channel enforcement
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

# Set up test environment
os.environ["db_path"] = ":memory:"

# Import modules to test
from db_helpers import (  # noqa: E402
    add_coins,
    add_xp,
    calculate_level_from_xp,
    calculate_xp_for_level,
    check_cooldown,
    ensure_user_exists,
    get_guild_settings,
    get_user_balance,
    is_minigame_channel,
    set_cooldown,
    set_minigame_channel,
    spend_coins,
    spend_xp,
)
from db_migrations import (  # noqa: E402
    create_minigame_tables,
    remove_corners_column,
)
from minigame_engine import (  # noqa: E402
    arena_duel,
    calculate_capture_odds,
    calculate_duel_odds,
    capture_attempt,
)
from quests import (  # noqa: E402
    assign_daily_quests,
    claim_quest,
    get_daily_status,
    increment_quest_progress,
)
from trades import (  # noqa: E402
    accept_trade,
    cancel_trade,
    create_trade_offer,
    get_pending_trades_for_user,
)


@pytest.fixture
def test_db():
    """Create a test database with all tables."""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create connection and tables
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create users table (with corners for migration test)
    cursor.execute("""
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
    """)

    conn.commit()
    conn.close()

    # Run migrations
    create_minigame_tables(db_path)

    # Seed test quests
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO quests (name, description, type, target_type, target_value,
                           reward_coins, reward_xp, allow_other_channels, rarity)
        VALUES ('Test Quest', 'Send 5 messages', 'daily', 'messages_sent', 5,
                100, 50, 0, 'common')
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def mock_db_connection(test_db):
    """Mock get_db_connection to use test database."""

    def patched_get_db():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn

    with patch("db_helpers.get_db_connection", patched_get_db), \
         patch("minigame_engine.get_db_connection", patched_get_db), \
         patch("quests.get_db_connection", patched_get_db), \
         patch("trades.get_db_connection", patched_get_db), \
         patch("shop.get_db_connection", patched_get_db):
        yield patched_get_db


class TestDbHelpers:
    """Tests for database helper functions."""

    def test_ensure_user_exists_new_user(self, mock_db_connection):
        """Test creating a new user."""
        user = ensure_user_exists("guild1", "user1")

        assert user["guildId"] == "guild1"
        assert user["userId"] == "user1"
        assert user["xp"] == 0
        assert user["coins"] == 0
        assert user["level"] == 1

    def test_ensure_user_exists_existing_user(self, mock_db_connection):
        """Test getting an existing user."""
        # Create user first
        ensure_user_exists("guild1", "user1")

        # Get again
        user = ensure_user_exists("guild1", "user1")

        assert user["guildId"] == "guild1"
        assert user["userId"] == "user1"

    def test_add_coins(self, mock_db_connection):
        """Test adding coins to a user."""
        ensure_user_exists("guild1", "user1")

        result = add_coins("guild1", "user1", 100, "test")

        assert result["old_balance"] == 0
        assert result["new_balance"] == 100
        assert result["amount_added"] == 100

    def test_spend_coins_success(self, mock_db_connection):
        """Test spending coins when user has enough."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 100, "test")

        result = spend_coins("guild1", "user1", 50, "test")

        assert result["old_balance"] == 100
        assert result["new_balance"] == 50
        assert result["amount_spent"] == 50

    def test_spend_coins_insufficient(self, mock_db_connection):
        """Test spending coins when user doesn't have enough."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 50, "test")

        with pytest.raises(ValueError, match="Insufficient coins"):
            spend_coins("guild1", "user1", 100, "test")

    def test_add_xp_and_level_up(self, mock_db_connection):
        """Test adding XP and level calculation."""
        ensure_user_exists("guild1", "user1")

        # Add enough XP to level up (level 2 requires 125 XP)
        result = add_xp("guild1", "user1", 130, "test")

        assert result["old_xp"] == 0
        assert result["new_xp"] == 130
        assert result["old_level"] == 1
        assert result["new_level"] == 2
        assert result["level_up"] is True

    def test_spend_xp_insufficient(self, mock_db_connection):
        """Test spending XP when user doesn't have enough."""
        ensure_user_exists("guild1", "user1")
        add_xp("guild1", "user1", 50, "test")

        with pytest.raises(ValueError, match="Insufficient XP"):
            spend_xp("guild1", "user1", 100, "test")

    def test_calculate_level_from_xp(self):
        """Test XP-to-level calculation."""
        # Level 1: 0-124 XP
        assert calculate_level_from_xp(0) == 1
        assert calculate_level_from_xp(124) == 1

        # Level 2: 125-499 XP
        assert calculate_level_from_xp(125) == 2
        assert calculate_level_from_xp(499) == 2

        # Level 3: 500-1124 XP
        assert calculate_level_from_xp(500) == 3

    def test_calculate_xp_for_level(self):
        """Test level-to-XP calculation."""
        assert calculate_xp_for_level(1) == 0
        assert calculate_xp_for_level(2) == 125
        assert calculate_xp_for_level(3) == 500
        assert calculate_xp_for_level(4) == 1125


class TestMigrations:
    """Tests for database migrations."""

    def test_remove_corners_column(self, test_db):
        """Test removing corners column from users table."""
        # First, verify corners exists
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()

        assert "corners" in columns

        # Run migration
        result = remove_corners_column(test_db)
        assert result is True

        # Verify corners is removed
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()

        assert "corners" not in columns

    def test_create_minigame_tables(self, test_db):
        """Test that all minigame tables are created."""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Check for expected tables
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = [
            "guild_settings",
            "quest_exception_channels",
            "quests",
            "user_quests",
            "user_daily_tracking",
            "shop_items",
            "user_inventory",
            "trades",
            "transactions",
            "user_cooldowns",
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"


class TestGuildSettings:
    """Tests for guild settings and channel enforcement."""

    def test_set_minigame_channel(self, mock_db_connection):
        """Test setting minigame channel."""
        set_minigame_channel("guild1", "channel123")
        settings = get_guild_settings("guild1")

        assert settings["minigame_channel_id"] == "channel123"

    def test_is_minigame_channel(self, mock_db_connection):
        """Test channel enforcement check."""
        set_minigame_channel("guild1", "channel123")

        assert is_minigame_channel("guild1", "channel123") is True
        assert is_minigame_channel("guild1", "other_channel") is False

    def test_clear_minigame_channel(self, mock_db_connection):
        """Test clearing minigame channel."""
        set_minigame_channel("guild1", "channel123")
        set_minigame_channel("guild1", None)

        settings = get_guild_settings("guild1")
        assert settings["minigame_channel_id"] is None


class TestQuests:
    """Tests for quest system."""

    def test_assign_daily_quests(self, mock_db_connection):
        """Test assigning daily quests."""
        quests = assign_daily_quests("guild1", "user1")

        assert len(quests) > 0
        assert quests[0]["progress"] == 0
        assert quests[0]["completed"] == 0

    def test_increment_quest_progress(self, mock_db_connection):
        """Test incrementing quest progress."""
        assign_daily_quests("guild1", "user1")

        # Increment progress
        completed = increment_quest_progress("guild1", "user1", "messages_sent", 3)

        assert len(completed) == 0  # Not completed yet

        # Check status
        status = get_daily_status("guild1", "user1")
        assert status["quests"][0]["progress"] == 3

    def test_complete_quest(self, mock_db_connection):
        """Test completing a quest."""
        assign_daily_quests("guild1", "user1")

        # Complete the quest
        completed = increment_quest_progress("guild1", "user1", "messages_sent", 5)

        assert len(completed) == 1
        assert completed[0]["name"] == "Test Quest"

    def test_claim_quest(self, mock_db_connection):
        """Test claiming quest rewards."""
        quests = assign_daily_quests("guild1", "user1")
        increment_quest_progress("guild1", "user1", "messages_sent", 5)

        # Claim the quest
        result = claim_quest("guild1", "user1", quests[0]["id"])

        assert result["quest_name"] == "Test Quest"
        assert result["coins_rewarded"] == 100
        assert result["xp_rewarded"] == 50

        # Verify rewards were added
        balance = get_user_balance("guild1", "user1")
        assert balance["coins"] == 100
        assert balance["xp"] == 50


class TestTrades:
    """Tests for trade system."""

    def test_create_trade_offer(self, mock_db_connection):
        """Test creating a trade offer."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 100, "test")

        trade = create_trade_offer("guild1", "user1", "user2", coins=50)

        assert trade["trade_id"] > 0
        assert trade["coins"] == 50
        assert trade["status"] == "pending"

    def test_accept_trade(self, mock_db_connection):
        """Test accepting a trade."""
        ensure_user_exists("guild1", "user1")
        ensure_user_exists("guild1", "user2")
        add_coins("guild1", "user1", 100, "test")

        trade = create_trade_offer("guild1", "user1", "user2", coins=50)
        result = accept_trade("guild1", "user2", trade["trade_id"])

        assert result["status"] == "accepted"
        assert "escrow_release_at" in result

    def test_cancel_pending_trade(self, mock_db_connection):
        """Test canceling a pending trade."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 100, "test")

        trade = create_trade_offer("guild1", "user1", "user2", coins=50)
        result = cancel_trade("guild1", "user1", trade["trade_id"])

        assert result["status"] == "canceled"
        assert result["refunded"] is False

    def test_trade_insufficient_funds(self, mock_db_connection):
        """Test trade with insufficient funds."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 30, "test")

        with pytest.raises(ValueError, match="Not enough coins"):
            create_trade_offer("guild1", "user1", "user2", coins=50)

    def test_trade_xp_disabled(self, mock_db_connection):
        """Test XP trading when disabled."""
        ensure_user_exists("guild1", "user1")
        add_xp("guild1", "user1", 1000, "test")
        # This test is a placeholder - XP trading disable test
        # would require more complex setup

    def test_pending_trades_for_user(self, mock_db_connection):
        """Test getting pending trades."""
        ensure_user_exists("guild1", "user1")
        ensure_user_exists("guild1", "user2")
        add_coins("guild1", "user1", 100, "test")

        create_trade_offer("guild1", "user1", "user2", coins=25)

        trades = get_pending_trades_for_user("guild1", "user1")
        assert len(trades["sent"]) == 1
        assert len(trades["received"]) == 0

        trades = get_pending_trades_for_user("guild1", "user2")
        assert len(trades["sent"]) == 0
        assert len(trades["received"]) == 1


class TestMinigameEngine:
    """Tests for capture and duel mechanics."""

    def test_calculate_capture_odds(self):
        """Test capture odds calculation."""
        # Base odds with low stake, low XP
        odds = calculate_capture_odds(0, 10)
        assert 0.30 <= odds <= 0.35

        # Higher XP = better odds
        odds_high_xp = calculate_capture_odds(1000, 10)
        assert odds_high_xp > odds

        # Higher stake = better odds
        odds_high_stake = calculate_capture_odds(0, 500)
        assert odds_high_stake > odds

        # Max odds cap
        odds_max = calculate_capture_odds(10000, 1000)
        assert odds_max <= 0.65

    def test_calculate_duel_odds(self):
        """Test duel odds calculation."""
        # Equal XP = 50/50
        odds1, odds2 = calculate_duel_odds(100, 100)
        assert odds1 == 0.50
        assert odds2 == 0.50

        # Higher XP = advantage
        odds1, odds2 = calculate_duel_odds(1000, 100)
        assert odds1 > odds2

        # Lower XP = disadvantage
        odds1, odds2 = calculate_duel_odds(100, 1000)
        assert odds1 < odds2

    def test_capture_minimum_stake(self, mock_db_connection):
        """Test capture with stake below minimum."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 100, "test")

        with pytest.raises(ValueError, match="Minimum stake"):
            capture_attempt("guild1", "user1", 5)

    def test_capture_maximum_stake(self, mock_db_connection):
        """Test capture with stake above maximum."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 2000, "test")

        with pytest.raises(ValueError, match="Maximum stake"):
            capture_attempt("guild1", "user1", 1500)

    def test_duel_same_user(self, mock_db_connection):
        """Test duel with self."""
        ensure_user_exists("guild1", "user1")
        add_coins("guild1", "user1", 100, "test")

        with pytest.raises(ValueError, match="Cannot duel yourself"):
            arena_duel("guild1", "user1", "user1", 50)


class TestCooldowns:
    """Tests for cooldown system."""

    def test_set_and_check_cooldown(self, mock_db_connection):
        """Test cooldown mechanics."""
        # Set cooldown
        set_cooldown("guild1", "user1", "capture")

        # Check immediately - should be on cooldown
        on_cooldown, remaining = check_cooldown(
            "guild1", "user1", "capture", 60
        )
        assert on_cooldown is True
        assert remaining > 0

    def test_cooldown_expired(self, mock_db_connection):
        """Test expired cooldown."""
        # Set cooldown
        set_cooldown("guild1", "user1", "capture")

        # Check with 0 second cooldown - should not be on cooldown
        on_cooldown, remaining = check_cooldown(
            "guild1", "user1", "capture", 0
        )
        assert on_cooldown is False
        assert remaining == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
