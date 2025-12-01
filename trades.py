"""
Player-to-player trade system.

This module handles:
- Trade offers (coins and XP)
- Trade acceptance with escrow
- Escrow release and completion
- XP transfer safety checks and caps
"""

from datetime import datetime, timedelta
from typing import Optional

from database import get_db_connection
from db_helpers import (
    add_coins,
    add_xp,
    calculate_level_from_xp,
    check_daily_xp_limit,
    ensure_user_exists,
    get_guild_settings,
    record_xp_transfer,
    spend_coins,
    spend_xp,
)


# Default escrow duration in minutes
ESCROW_DURATION_MINUTES = 5


def create_trade_offer(
    guild_id: str,
    from_user_id: str,
    to_user_id: str,
    coins: int = 0,
    xp: int = 0,
    conn=None,
) -> dict:
    """
    Create a trade offer from one user to another.

    Args:
        guild_id: Guild ID
        from_user_id: User offering the trade
        to_user_id: User receiving the offer
        coins: Amount of coins to trade
        xp: Amount of XP to trade

    Returns:
        dict with trade details
    """
    if from_user_id == to_user_id:
        raise ValueError("Cannot trade with yourself")

    if coins <= 0 and xp <= 0:
        raise ValueError("Must offer at least some coins or XP")

    if coins < 0 or xp < 0:
        raise ValueError("Cannot offer negative amounts")

    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Check guild settings for XP trading
        settings = get_guild_settings(guild_id, conn)
        if xp > 0 and not settings.get("xp_trading_enabled", 1):
            raise ValueError("XP trading is disabled on this server")

        # Check if sender has enough balance
        sender = ensure_user_exists(guild_id, from_user_id, conn)

        if sender["coins"] < coins:
            raise ValueError(
                f"Not enough coins: have {sender['coins']}, offering {coins}"
            )

        if sender["xp"] < xp:
            raise ValueError(
                f"Not enough XP: have {sender['xp']}, offering {xp}"
            )

        # Check XP daily limit
        if xp > 0:
            can_transfer, current, limit = check_daily_xp_limit(
                guild_id, from_user_id, xp, conn
            )
            if not can_transfer:
                remaining = limit - current
                raise ValueError(
                    f"Daily XP transfer limit reached. "
                    f"You can transfer {remaining} more XP today "
                    f"(limit: {limit})"
                )

        # Check for existing pending trades
        cursor.execute(
            """
            SELECT COUNT(*) FROM trades
            WHERE guildId = ? AND fromUserId = ? AND toUserId = ?
              AND status = 'pending'
            """,
            (str(guild_id), str(from_user_id), str(to_user_id)),
        )
        if cursor.fetchone()[0] > 0:
            raise ValueError(
                "You already have a pending trade with this user"
            )

        # Calculate tax preview
        tax_percent = settings.get("trade_tax_percent", 10.0)
        tax_coins = int(coins * (tax_percent / 100))
        tax_xp = int(xp * (tax_percent / 100))

        # Create trade record
        cursor.execute(
            """
            INSERT INTO trades (
                guildId, fromUserId, toUserId, coins, xp,
                status, tax_coins, tax_xp, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                str(guild_id),
                str(from_user_id),
                str(to_user_id),
                coins,
                xp,
                tax_coins,
                tax_xp,
                datetime.utcnow().isoformat(),
            ),
        )
        trade_id = cursor.lastrowid

        conn.commit()

        return {
            "trade_id": trade_id,
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "coins": coins,
            "xp": xp,
            "tax_coins": tax_coins,
            "tax_xp": tax_xp,
            "net_coins": coins - tax_coins,
            "net_xp": xp - tax_xp,
            "status": "pending",
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def get_trade(trade_id: int, conn=None) -> Optional[dict]:
    """Get trade details by ID."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return dict(row)
    finally:
        if should_close:
            conn.close()


def get_pending_trades_for_user(
    guild_id: str,
    user_id: str,
    conn=None,
) -> dict:
    """Get all pending trades involving a user (sent and received)."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Sent trades
        cursor.execute(
            """
            SELECT * FROM trades
            WHERE guildId = ? AND fromUserId = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (str(guild_id), str(user_id)),
        )
        sent = [dict(row) for row in cursor.fetchall()]

        # Received trades
        cursor.execute(
            """
            SELECT * FROM trades
            WHERE guildId = ? AND toUserId = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (str(guild_id), str(user_id)),
        )
        received = [dict(row) for row in cursor.fetchall()]

        return {
            "sent": sent,
            "received": received,
        }
    finally:
        if should_close:
            conn.close()


def calculate_xp_level_change(current_xp: float, xp_change: int) -> dict:
    """Calculate level changes from XP modification."""
    old_level = calculate_level_from_xp(current_xp)
    new_xp = current_xp + xp_change
    new_level = calculate_level_from_xp(max(0, new_xp))

    return {
        "old_xp": current_xp,
        "new_xp": new_xp,
        "old_level": old_level,
        "new_level": new_level,
        "level_change": new_level - old_level,
    }


def accept_trade(
    guild_id: str,
    user_id: str,
    trade_id: int,
    conn=None,
) -> dict:
    """
    Accept a pending trade.

    This moves funds into escrow and sets a release timer.

    Args:
        guild_id: Guild ID
        user_id: User accepting (must be the toUserId)
        trade_id: Trade ID to accept

    Returns:
        dict with acceptance details
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Get trade
        trade = get_trade(trade_id, conn)
        if not trade:
            raise ValueError("Trade not found")

        if trade["guildId"] != str(guild_id):
            raise ValueError("Trade not found in this guild")

        if trade["toUserId"] != str(user_id):
            raise ValueError("You are not the recipient of this trade")

        if trade["status"] != "pending":
            raise ValueError(f"Trade is not pending (status: {trade['status']})")

        # Check sender still has funds
        sender = ensure_user_exists(guild_id, trade["fromUserId"], conn)

        if sender["coins"] < trade["coins"]:
            # Cancel trade - sender no longer has funds
            cursor.execute(
                "UPDATE trades SET status = 'canceled' WHERE id = ?",
                (trade_id,),
            )
            conn.commit()
            raise ValueError(
                "Trade canceled: sender no longer has enough coins"
            )

        if sender["xp"] < trade["xp"]:
            cursor.execute(
                "UPDATE trades SET status = 'canceled' WHERE id = ?",
                (trade_id,),
            )
            conn.commit()
            raise ValueError(
                "Trade canceled: sender no longer has enough XP"
            )

        # Debit sender (into escrow)
        if trade["coins"] > 0:
            spend_coins(
                guild_id,
                trade["fromUserId"],
                trade["coins"],
                "trade_escrow",
                related_id=trade_id,
                related_type="trade",
                conn=conn,
            )

        if trade["xp"] > 0:
            spend_xp(
                guild_id,
                trade["fromUserId"],
                trade["xp"],
                "trade_escrow",
                related_id=trade_id,
                related_type="trade",
                conn=conn,
            )

        # Set escrow release time
        escrow_release = datetime.utcnow() + timedelta(
            minutes=ESCROW_DURATION_MINUTES
        )

        cursor.execute(
            """
            UPDATE trades
            SET status = 'accepted', accepted_at = ?, escrow_release_at = ?
            WHERE id = ?
            """,
            (
                datetime.utcnow().isoformat(),
                escrow_release.isoformat(),
                trade_id,
            ),
        )

        conn.commit()

        return {
            "trade_id": trade_id,
            "status": "accepted",
            "escrow_release_at": escrow_release.isoformat(),
            "minutes_until_release": ESCROW_DURATION_MINUTES,
            "coins": trade["coins"],
            "xp": trade["xp"],
            "tax_coins": trade["tax_coins"],
            "tax_xp": trade["tax_xp"],
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def complete_trade(
    trade_id: int,
    conn=None,
) -> dict:
    """
    Complete a trade after escrow period.

    This transfers funds to the recipient minus tax.

    Args:
        trade_id: Trade ID to complete

    Returns:
        dict with completion details
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        trade = get_trade(trade_id, conn)
        if not trade:
            raise ValueError("Trade not found")

        if trade["status"] != "accepted":
            raise ValueError(f"Trade cannot be completed (status: {trade['status']})")

        # Check escrow period
        escrow_release = datetime.fromisoformat(trade["escrow_release_at"])
        if datetime.utcnow() < escrow_release:
            remaining = (escrow_release - datetime.utcnow()).seconds
            raise ValueError(
                f"Escrow period not over. {remaining} seconds remaining."
            )

        guild_id = trade["guildId"]
        recipient_id = trade["toUserId"]
        sender_id = trade["fromUserId"]

        # Calculate net amounts after tax
        net_coins = trade["coins"] - trade["tax_coins"]
        net_xp = trade["xp"] - trade["tax_xp"]

        # Credit recipient
        if net_coins > 0:
            add_coins(
                guild_id,
                recipient_id,
                net_coins,
                "trade_received",
                related_id=trade_id,
                related_type="trade",
                conn=conn,
            )

        recipient_xp_result = None
        if net_xp > 0:
            recipient_xp_result = add_xp(
                guild_id,
                recipient_id,
                net_xp,
                "trade_received",
                related_id=trade_id,
                related_type="trade",
                conn=conn,
            )

            # Record XP transfer against daily limit
            record_xp_transfer(guild_id, sender_id, trade["xp"], conn)

        # Update trade status
        cursor.execute(
            """
            UPDATE trades
            SET status = 'completed', completed_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow().isoformat(), trade_id),
        )

        conn.commit()

        return {
            "trade_id": trade_id,
            "status": "completed",
            "recipient_id": recipient_id,
            "sender_id": sender_id,
            "coins_received": net_coins,
            "xp_received": net_xp,
            "tax_coins": trade["tax_coins"],
            "tax_xp": trade["tax_xp"],
            "recipient_level_up": (
                recipient_xp_result.get("level_up", False)
                if recipient_xp_result
                else False
            ),
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def cancel_trade(
    guild_id: str,
    user_id: str,
    trade_id: int,
    conn=None,
) -> dict:
    """
    Cancel a trade.

    Can be canceled by either party if pending.
    Can be canceled by sender during escrow period (refund).

    Args:
        guild_id: Guild ID
        user_id: User canceling
        trade_id: Trade ID to cancel

    Returns:
        dict with cancellation details
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        trade = get_trade(trade_id, conn)
        if not trade:
            raise ValueError("Trade not found")

        if trade["guildId"] != str(guild_id):
            raise ValueError("Trade not found in this guild")

        # Check if user is involved in trade
        is_sender = trade["fromUserId"] == str(user_id)
        is_recipient = trade["toUserId"] == str(user_id)

        if not is_sender and not is_recipient:
            raise ValueError("You are not involved in this trade")

        if trade["status"] == "completed":
            raise ValueError("Cannot cancel a completed trade")

        if trade["status"] == "canceled":
            raise ValueError("Trade is already canceled")

        # Refund if in escrow (accepted status)
        if trade["status"] == "accepted":
            # Only sender can cancel during escrow
            if not is_sender:
                raise ValueError(
                    "Only the sender can cancel during escrow period"
                )

            # Refund sender
            if trade["coins"] > 0:
                add_coins(
                    guild_id,
                    trade["fromUserId"],
                    trade["coins"],
                    "trade_refund",
                    related_id=trade_id,
                    related_type="trade",
                    conn=conn,
                )

            if trade["xp"] > 0:
                add_xp(
                    guild_id,
                    trade["fromUserId"],
                    trade["xp"],
                    "trade_refund",
                    related_id=trade_id,
                    related_type="trade",
                    conn=conn,
                )

        # Update status
        cursor.execute(
            "UPDATE trades SET status = 'canceled' WHERE id = ?",
            (trade_id,),
        )

        conn.commit()

        return {
            "trade_id": trade_id,
            "status": "canceled",
            "refunded": trade["status"] == "accepted",
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def check_and_complete_ready_trades(conn=None) -> list:
    """
    Check for trades ready to complete and complete them.

    This should be called periodically (e.g., every minute).

    Returns:
        list of completed trade IDs
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        now = datetime.utcnow().isoformat()

        # Find trades ready for completion
        cursor.execute(
            """
            SELECT id FROM trades
            WHERE status = 'accepted' AND escrow_release_at <= ?
            """,
            (now,),
        )
        ready_trades = cursor.fetchall()

        completed = []
        for trade_row in ready_trades:
            try:
                complete_trade(trade_row[0], conn)
                completed.append(trade_row[0])
            except Exception as e:
                print(f"Failed to complete trade {trade_row[0]}: {e}")
                continue

        return completed
    finally:
        if should_close:
            conn.close()


def get_xp_transfer_warning(
    guild_id: str,
    user_id: str,
    xp_amount: int,
    conn=None,
) -> dict:
    """
    Generate a warning message for XP transfer.

    Returns info about old XP, new XP, and level changes.
    """
    user = ensure_user_exists(guild_id, user_id, conn)
    level_info = calculate_xp_level_change(user["xp"], -xp_amount)

    return {
        "current_xp": user["xp"],
        "xp_to_transfer": xp_amount,
        "remaining_xp": level_info["new_xp"],
        "current_level": level_info["old_level"],
        "new_level": level_info["new_level"],
        "will_level_down": level_info["level_change"] < 0,
        "levels_lost": abs(level_info["level_change"]) if level_info["level_change"] < 0 else 0,  # noqa: E501
    }
