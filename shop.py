"""
Shop system module.

This module handles:
- Shop item listing
- Item purchases (coins and/or XP)
- Item effect application
- Inventory management
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from database import get_db_connection
from db_helpers import (
    get_user_balance,
    spend_coins,
    spend_xp,
)


def get_shop_items(
    active_only: bool = True,
    conn=None,
) -> list:
    """Get all shop items."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        if active_only:
            cursor.execute(
                """
                SELECT * FROM shop_items
                WHERE active = 1 AND (stock = -1 OR stock > 0)
                ORDER BY price_coins, price_xp
                """
            )
        else:
            cursor.execute("SELECT * FROM shop_items ORDER BY price_coins, price_xp")

        items = []
        for row in cursor.fetchall():
            item = dict(row)
            # Parse metadata JSON
            if item.get("metadata"):
                try:
                    item["metadata"] = json.loads(item["metadata"])
                except json.JSONDecodeError:
                    item["metadata"] = {}
            items.append(item)

        return items
    finally:
        if should_close:
            conn.close()


def get_shop_item(item_id: int, conn=None) -> Optional[dict]:
    """Get a specific shop item by ID."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM shop_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            return None

        item = dict(row)
        if item.get("metadata"):
            try:
                item["metadata"] = json.loads(item["metadata"])
            except json.JSONDecodeError:
                item["metadata"] = {}

        return item
    finally:
        if should_close:
            conn.close()


def buy_item(
    guild_id: str,
    user_id: str,
    item_id: int,
    quantity: int = 1,
    conn=None,
) -> dict:
    """
    Purchase an item from the shop.

    Args:
        guild_id: Guild ID
        user_id: User ID
        item_id: Shop item ID to purchase
        quantity: Number to purchase (default 1)

    Returns:
        dict with purchase results
    """
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")

    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Get item
        item = get_shop_item(item_id, conn)
        if not item:
            raise ValueError("Item not found")

        if not item["active"]:
            raise ValueError("Item is not available for purchase")

        # Check stock
        if item["stock"] != -1 and item["stock"] < quantity:
            raise ValueError(
                f"Not enough stock: only {item['stock']} available"
            )

        # Calculate total cost
        total_coins = item["price_coins"] * quantity
        total_xp = item["price_xp"] * quantity

        # Get user balance
        balance = get_user_balance(guild_id, user_id, conn)

        # Check if user can afford it
        if balance["coins"] < total_coins:
            raise ValueError(
                f"Not enough coins: have {balance['coins']}, need {total_coins}"
            )

        if total_xp > 0 and balance["xp"] < total_xp:
            raise ValueError(
                f"Not enough XP: have {balance['xp']}, need {total_xp}"
            )

        # Deduct costs
        if total_coins > 0:
            spend_coins(
                guild_id,
                user_id,
                total_coins,
                "shop_purchase",
                related_id=item_id,
                related_type="shop_item",
                conn=conn,
            )

        xp_result = None
        if total_xp > 0:
            xp_result = spend_xp(
                guild_id,
                user_id,
                total_xp,
                "shop_purchase",
                related_id=item_id,
                related_type="shop_item",
                conn=conn,
            )

        # Update stock if limited
        if item["stock"] != -1:
            cursor.execute(
                "UPDATE shop_items SET stock = stock - ? WHERE id = ?",
                (quantity, item_id),
            )

        # Add to inventory if consumable
        if item["consumable"]:
            cursor.execute(
                """
                INSERT INTO user_inventory (guildId, userId, itemId, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guildId, userId, itemId)
                DO UPDATE SET quantity = quantity + excluded.quantity
                """,
                (str(guild_id), str(user_id), item_id, quantity),
            )

        conn.commit()

        return {
            "item_name": item["name"],
            "quantity": quantity,
            "coins_spent": total_coins,
            "xp_spent": total_xp,
            "is_consumable": bool(item["consumable"]),
            "level_down": xp_result.get("level_down", False) if xp_result else False,
            "new_level": xp_result.get("new_level") if xp_result else None,
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def get_user_inventory(
    guild_id: str,
    user_id: str,
    conn=None,
) -> list:
    """Get user's inventory of consumable items."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT ui.*, si.name, si.description, si.metadata
            FROM user_inventory ui
            JOIN shop_items si ON ui.itemId = si.id
            WHERE ui.guildId = ? AND ui.userId = ? AND ui.quantity > 0
            ORDER BY ui.acquired_at DESC
            """,
            (str(guild_id), str(user_id)),
        )

        items = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("metadata"):
                try:
                    item["metadata"] = json.loads(item["metadata"])
                except json.JSONDecodeError:
                    item["metadata"] = {}
            items.append(item)

        return items
    finally:
        if should_close:
            conn.close()


def use_item(
    guild_id: str,
    user_id: str,
    item_id: int,
    conn=None,
) -> dict:
    """
    Use a consumable item from inventory.

    Args:
        guild_id: Guild ID
        user_id: User ID
        item_id: Shop item ID to use

    Returns:
        dict with item effect details
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Check if user has the item
        cursor.execute(
            """
            SELECT ui.quantity, si.name, si.metadata
            FROM user_inventory ui
            JOIN shop_items si ON ui.itemId = si.id
            WHERE ui.guildId = ? AND ui.userId = ? AND ui.itemId = ?
            """,
            (str(guild_id), str(user_id), item_id),
        )
        row = cursor.fetchone()

        if not row or row[0] < 1:
            raise ValueError("You don't have this item in your inventory")

        item_name = row[1]
        metadata = {}
        if row[2]:
            try:
                metadata = json.loads(row[2])
            except json.JSONDecodeError:
                pass

        # Decrement quantity
        cursor.execute(
            """
            UPDATE user_inventory
            SET quantity = quantity - 1
            WHERE guildId = ? AND userId = ? AND itemId = ?
            """,
            (str(guild_id), str(user_id), item_id),
        )

        # Store active effect
        effect = metadata.get("effect")
        if effect:
            duration = metadata.get("duration_minutes", 60)
            expires_at = datetime.utcnow() + timedelta(minutes=duration)

            cursor.execute(
                """
                INSERT INTO user_active_effects (
                    guildId, userId, effect_type, effect_data, expires_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guildId, userId, effect_type)
                DO UPDATE SET effect_data = excluded.effect_data,
                              expires_at = excluded.expires_at
                """,
                (
                    str(guild_id),
                    str(user_id),
                    effect,
                    json.dumps(metadata),
                    expires_at.isoformat(),
                ),
            )

        conn.commit()

        return {
            "item_name": item_name,
            "effect": effect,
            "metadata": metadata,
            "message": f"Used {item_name}!",
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def get_active_effects(
    guild_id: str,
    user_id: str,
    conn=None,
) -> list:
    """Get user's currently active effects."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        now = datetime.utcnow().isoformat()

        cursor.execute(
            """
            SELECT effect_type, effect_data, expires_at
            FROM user_active_effects
            WHERE guildId = ? AND userId = ? AND expires_at > ?
            """,
            (str(guild_id), str(user_id), now),
        )

        effects = []
        for row in cursor.fetchall():
            effect = {
                "effect_type": row[0],
                "effect_data": json.loads(row[1]) if row[1] else {},
                "expires_at": row[2],
            }
            effects.append(effect)

        return effects
    finally:
        if should_close:
            conn.close()


def has_active_effect(
    guild_id: str,
    user_id: str,
    effect_type: str,
    conn=None,
) -> Optional[dict]:
    """Check if user has a specific active effect."""
    effects = get_active_effects(guild_id, user_id, conn)

    for effect in effects:
        if effect["effect_type"] == effect_type:
            return effect

    return None
