"""
Database helper functions for the minigame system.

This module provides atomic operations for user balances,
transaction logging, and safe database operations.
"""

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from database import get_db_connection

# XP-to-level configuration
LEVEL_MULTIPLIER = 125


def calculate_level_from_xp(xp: float) -> int:
    """Calculate level from XP."""
    if xp < 0:
        xp = 0
    return int(math.sqrt(xp / LEVEL_MULTIPLIER)) + 1


def calculate_xp_for_level(level: int) -> float:
    """Calculate XP required to reach a given level."""
    return ((level - 1) ** 2) * LEVEL_MULTIPLIER


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Context manager for database transactions."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def ensure_user_exists(
    guild_id: str,
    user_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> dict:
    """
    Ensure a user exists in the database.
    Returns user data dictionary.
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT guildId, userId, xp, level, messages, coins
            FROM users WHERE guildId = ? AND userId = ?
            """,
            (str(guild_id), str(user_id)),
        )
        result = cursor.fetchone()

        if result:
            return dict(result)

        # Create new user
        cursor.execute(
            """
            INSERT INTO users (guildId, userId, xp, level, messages, coins)
            VALUES (?, ?, 0, 1, 0, 0)
            """,
            (str(guild_id), str(user_id)),
        )
        conn.commit()

        return {
            "guildId": str(guild_id),
            "userId": str(user_id),
            "xp": 0,
            "level": 1,
            "messages": 0,
            "coins": 0,
        }
    finally:
        if should_close:
            conn.close()


def get_user_balance(
    guild_id: str,
    user_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Get user's current balance (coins and xp)."""
    user = ensure_user_exists(guild_id, user_id, conn)
    return {
        "coins": user["coins"],
        "xp": user["xp"],
        "level": user["level"],
    }


def add_coins(
    guild_id: str,
    user_id: str,
    amount: float,
    reason: str = "unknown",
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """
    Add coins to a user's balance.
    Returns updated balance info.
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        user = ensure_user_exists(guild_id, user_id, conn)
        new_balance = user["coins"] + amount

        cursor.execute(
            "UPDATE users SET coins = ? WHERE guildId = ? AND userId = ?",
            (new_balance, str(guild_id), str(user_id)),
        )

        # Log transaction
        log_transaction(
            guild_id=guild_id,
            user_id=user_id,
            kind=reason,
            amount=amount,
            currency="coins",
            balance_after=new_balance,
            related_id=related_id,
            related_type=related_type,
            conn=conn,
        )

        conn.commit()

        return {
            "old_balance": user["coins"],
            "new_balance": new_balance,
            "amount_added": amount,
        }
    finally:
        if should_close:
            conn.close()


def spend_coins(
    guild_id: str,
    user_id: str,
    amount: float,
    reason: str = "unknown",
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """
    Spend coins from a user's balance.
    Raises ValueError if insufficient funds.
    Returns updated balance info.
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        user = ensure_user_exists(guild_id, user_id, conn)

        if user["coins"] < amount:
            raise ValueError(
                f"Insufficient coins: have {user['coins']}, need {amount}"
            )

        new_balance = user["coins"] - amount

        cursor.execute(
            "UPDATE users SET coins = ? WHERE guildId = ? AND userId = ?",
            (new_balance, str(guild_id), str(user_id)),
        )

        # Log transaction
        log_transaction(
            guild_id=guild_id,
            user_id=user_id,
            kind=reason,
            amount=-amount,
            currency="coins",
            balance_after=new_balance,
            related_id=related_id,
            related_type=related_type,
            conn=conn,
        )

        conn.commit()

        return {
            "old_balance": user["coins"],
            "new_balance": new_balance,
            "amount_spent": amount,
        }
    finally:
        if should_close:
            conn.close()


def add_xp(
    guild_id: str,
    user_id: str,
    amount: float,
    reason: str = "unknown",
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """
    Add XP to a user's balance and update level.
    Returns updated balance info and level change data.
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        user = ensure_user_exists(guild_id, user_id, conn)
        new_xp = user["xp"] + amount
        old_level = user["level"]
        new_level = calculate_level_from_xp(new_xp)

        cursor.execute(
            "UPDATE users SET xp = ?, level = ? WHERE guildId = ? AND userId = ?",
            (new_xp, new_level, str(guild_id), str(user_id)),
        )

        # Log transaction
        log_transaction(
            guild_id=guild_id,
            user_id=user_id,
            kind=reason,
            amount=amount,
            currency="xp",
            balance_after=new_xp,
            related_id=related_id,
            related_type=related_type,
            conn=conn,
        )

        conn.commit()

        return {
            "old_xp": user["xp"],
            "new_xp": new_xp,
            "old_level": old_level,
            "new_level": new_level,
            "level_up": new_level > old_level,
            "level_down": new_level < old_level,
            "amount_added": amount,
        }
    finally:
        if should_close:
            conn.close()


def spend_xp(
    guild_id: str,
    user_id: str,
    amount: float,
    reason: str = "unknown",
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """
    Spend XP from a user's balance and update level.
    Raises ValueError if insufficient XP.
    Returns updated balance info and level change data.
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        user = ensure_user_exists(guild_id, user_id, conn)

        if user["xp"] < amount:
            raise ValueError(f"Insufficient XP: have {user['xp']}, need {amount}")

        new_xp = user["xp"] - amount
        old_level = user["level"]
        new_level = calculate_level_from_xp(new_xp)

        cursor.execute(
            "UPDATE users SET xp = ?, level = ? WHERE guildId = ? AND userId = ?",
            (new_xp, new_level, str(guild_id), str(user_id)),
        )

        # Log transaction
        log_transaction(
            guild_id=guild_id,
            user_id=user_id,
            kind=reason,
            amount=-amount,
            currency="xp",
            balance_after=new_xp,
            related_id=related_id,
            related_type=related_type,
            conn=conn,
        )

        conn.commit()

        return {
            "old_xp": user["xp"],
            "new_xp": new_xp,
            "old_level": old_level,
            "new_level": new_level,
            "level_up": new_level > old_level,
            "level_down": new_level < old_level,
            "amount_spent": amount,
        }
    finally:
        if should_close:
            conn.close()


def log_transaction(
    guild_id: str,
    user_id: str,
    kind: str,
    amount: float,
    currency: str = "coins",
    balance_after: Optional[float] = None,
    metadata: Optional[dict] = None,
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """Log a transaction to the ledger. Returns transaction ID."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        meta_json = json.dumps(metadata) if metadata else "{}"

        cursor.execute(
            """
            INSERT INTO transactions (
                guildId, userId, kind, amount, currency, balance_after,
                metadata, related_id, related_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(guild_id),
                str(user_id),
                kind,
                amount,
                currency,
                balance_after,
                meta_json,
                related_id,
                related_type,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        if should_close:
            conn.close()


def get_user_transactions(
    guild_id: str,
    user_id: str,
    limit: int = 20,
    kind: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> list:
    """Get recent transactions for a user."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        if kind:
            cursor.execute(
                """
                SELECT * FROM transactions
                WHERE guildId = ? AND userId = ? AND kind = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (str(guild_id), str(user_id), kind, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM transactions
                WHERE guildId = ? AND userId = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (str(guild_id), str(user_id), limit),
            )

        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


# Guild settings helpers


def get_guild_settings(
    guild_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Get or create guild settings."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM guild_settings WHERE guildId = ?",
            (str(guild_id),),
        )
        result = cursor.fetchone()

        if result:
            return dict(result)

        # Create default settings
        cursor.execute(
            """
            INSERT INTO guild_settings (guildId) VALUES (?)
            """,
            (str(guild_id),),
        )
        conn.commit()

        return {
            "guildId": str(guild_id),
            "minigame_enabled": 1,
            "minigame_channel_id": None,
            "xp_trading_enabled": 1,
            "trade_tax_percent": 10.0,
            "duel_tax_percent": 10.0,
            "daily_xp_transfer_cap_percent": 10.0,
            "daily_xp_transfer_cap_max": 500,
            "capture_cooldown_seconds": 60,
            "duel_cooldown_seconds": 300,
        }
    finally:
        if should_close:
            conn.close()


def set_minigame_enabled(
    guild_id: str,
    enabled: bool,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Enable or disable the minigame system for a guild."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Ensure settings exist
        get_guild_settings(guild_id, conn)

        cursor.execute(
            """
            UPDATE guild_settings SET minigame_enabled = ?, updated_at = ?
            WHERE guildId = ?
            """,
            (1 if enabled else 0, datetime.utcnow().isoformat(), str(guild_id)),
        )
        conn.commit()
        return True
    finally:
        if should_close:
            conn.close()


def is_minigame_enabled(
    guild_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Check if the minigame system is enabled for a guild."""
    settings = get_guild_settings(guild_id, conn)
    return bool(settings.get("minigame_enabled", 1))


def set_minigame_channel(
    guild_id: str,
    channel_id: Optional[str],
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Set the minigame channel for a guild."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Ensure settings exist
        get_guild_settings(guild_id, conn)

        cursor.execute(
            """
            UPDATE guild_settings SET minigame_channel_id = ?, updated_at = ?
            WHERE guildId = ?
            """,
            (channel_id, datetime.utcnow().isoformat(), str(guild_id)),
        )
        conn.commit()
        return True
    finally:
        if should_close:
            conn.close()


def add_quest_exception_channel(
    guild_id: str,
    channel_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Add a channel to the quest exception list."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO quest_exception_channels (guildId, channelId)
            VALUES (?, ?)
            """,
            (str(guild_id), str(channel_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if should_close:
            conn.close()


def remove_quest_exception_channel(
    guild_id: str,
    channel_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Remove a channel from the quest exception list."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            DELETE FROM quest_exception_channels
            WHERE guildId = ? AND channelId = ?
            """,
            (str(guild_id), str(channel_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        if should_close:
            conn.close()


def get_quest_exception_channels(
    guild_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> list:
    """Get all quest exception channels for a guild."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT channelId FROM quest_exception_channels WHERE guildId = ?",
            (str(guild_id),),
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def is_minigame_channel(
    guild_id: str,
    channel_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Check if a channel is the designated minigame channel."""
    settings = get_guild_settings(guild_id, conn)
    return settings.get("minigame_channel_id") == str(channel_id)


def is_quest_exception_channel(
    guild_id: str,
    channel_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    """Check if a channel is a quest exception channel."""
    exception_channels = get_quest_exception_channels(guild_id, conn)
    return str(channel_id) in exception_channels


# Cooldown helpers


def check_cooldown(
    guild_id: str,
    user_id: str,
    action_type: str,
    cooldown_seconds: int,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[bool, int]:
    """
    Check if user is on cooldown for an action.
    Returns (is_on_cooldown, seconds_remaining).
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT last_action_at FROM user_cooldowns
            WHERE guildId = ? AND userId = ? AND action_type = ?
            """,
            (str(guild_id), str(user_id), action_type),
        )
        result = cursor.fetchone()

        if not result:
            return False, 0

        last_action = datetime.fromisoformat(result[0])
        now = datetime.utcnow()
        elapsed = (now - last_action).total_seconds()

        if elapsed >= cooldown_seconds:
            return False, 0

        remaining = int(cooldown_seconds - elapsed)
        return True, remaining
    finally:
        if should_close:
            conn.close()


def set_cooldown(
    guild_id: str,
    user_id: str,
    action_type: str,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Set/update cooldown for a user action."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO user_cooldowns (guildId, userId, action_type, last_action_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guildId, userId, action_type)
            DO UPDATE SET last_action_at = excluded.last_action_at
            """,
            (
                str(guild_id),
                str(user_id),
                action_type,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        if should_close:
            conn.close()


# Daily tracking helpers


def get_daily_tracking(
    guild_id: str,
    user_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """Get or create daily tracking data for a user."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT * FROM user_daily_tracking
            WHERE guildId = ? AND userId = ?
            """,
            (str(guild_id), str(user_id)),
        )
        result = cursor.fetchone()

        if result:
            return dict(result)

        # Create new tracking record
        cursor.execute(
            """
            INSERT INTO user_daily_tracking (guildId, userId)
            VALUES (?, ?)
            """,
            (str(guild_id), str(user_id)),
        )
        conn.commit()

        return {
            "guildId": str(guild_id),
            "userId": str(user_id),
            "last_daily_claim": None,
            "streak": 0,
            "daily_xp_transferred": 0,
            "last_xp_transfer_reset": None,
        }
    finally:
        if should_close:
            conn.close()


def update_daily_tracking(
    guild_id: str,
    user_id: str,
    updates: dict,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Update daily tracking data for a user."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    # Ensure record exists
    get_daily_tracking(guild_id, user_id, conn)

    # Whitelist of allowed column names to prevent SQL injection
    allowed_columns = {
        "last_daily_claim",
        "streak",
        "daily_xp_transferred",
        "last_xp_transfer_reset",
        "last_capture_at",
        "last_duel_at",
    }

    # Validate all column names
    for key in updates.keys():
        if key not in allowed_columns:
            raise ValueError(f"Invalid column name: {key}")

    cursor = conn.cursor()
    try:
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [str(guild_id), str(user_id)]

        cursor.execute(
            f"""
            UPDATE user_daily_tracking SET {set_clause}
            WHERE guildId = ? AND userId = ?
            """,
            values,
        )
        conn.commit()
    finally:
        if should_close:
            conn.close()


def check_daily_xp_limit(
    guild_id: str,
    user_id: str,
    xp_amount: int,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[bool, int, int]:
    """
    Check if user can transfer XP within daily limits.
    Returns (can_transfer, current_transferred, limit).
    """
    settings = get_guild_settings(guild_id, conn)
    user = ensure_user_exists(guild_id, user_id, conn)
    tracking = get_daily_tracking(guild_id, user_id, conn)

    # Calculate daily limit (10% of XP or max cap, whichever is lower)
    percent_cap = user["xp"] * (settings["daily_xp_transfer_cap_percent"] / 100)
    max_cap = settings["daily_xp_transfer_cap_max"]
    daily_limit = int(min(percent_cap, max_cap))

    # Reset daily counter if needed
    now = datetime.utcnow()
    last_reset = tracking.get("last_xp_transfer_reset")
    if last_reset:
        last_reset_dt = datetime.fromisoformat(last_reset)
        if (now - last_reset_dt).days >= 1:
            # Reset counter
            update_daily_tracking(
                guild_id,
                user_id,
                {
                    "daily_xp_transferred": 0,
                    "last_xp_transfer_reset": now.isoformat(),
                },
                conn,
            )
            tracking["daily_xp_transferred"] = 0

    current_transferred = tracking.get("daily_xp_transferred", 0)
    remaining = daily_limit - current_transferred

    can_transfer = remaining >= xp_amount
    return can_transfer, current_transferred, daily_limit


def record_xp_transfer(
    guild_id: str,
    user_id: str,
    xp_amount: int,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Record XP transfer against daily limit."""
    tracking = get_daily_tracking(guild_id, user_id, conn)
    current = tracking.get("daily_xp_transferred", 0)

    updates = {"daily_xp_transferred": current + xp_amount}

    if not tracking.get("last_xp_transfer_reset"):
        updates["last_xp_transfer_reset"] = datetime.utcnow().isoformat()

    update_daily_tracking(guild_id, user_id, updates, conn)
