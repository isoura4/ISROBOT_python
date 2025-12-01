"""
Quest system module.

This module handles:
- Daily quest assignment
- Quest progress tracking
- Quest completion and reward claiming
- Random quest generation
"""

import random
from datetime import datetime

from database import get_db_connection
from db_helpers import add_coins, add_xp, get_daily_tracking


def get_available_quests(
    quest_type: str = "daily",
    conn=None,
) -> list:
    """Get all active quest templates of a given type."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT * FROM quests
            WHERE type = ? AND active = 1
            ORDER BY rarity, name
            """,
            (quest_type,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def get_user_active_quests(
    guild_id: str,
    user_id: str,
    conn=None,
) -> list:
    """Get all active (unclaimed) quests for a user."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT uq.*, q.name, q.description, q.target_type, q.target_value,
                   q.reward_coins, q.reward_xp, q.rarity, q.allow_other_channels
            FROM user_quests uq
            JOIN quests q ON uq.questId = q.id
            WHERE uq.guildId = ? AND uq.userId = ? AND uq.claimed = 0
            ORDER BY uq.assigned_at DESC
            """,
            (str(guild_id), str(user_id)),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def get_user_daily_quests(
    guild_id: str,
    user_id: str,
    conn=None,
) -> list:
    """Get today's daily quests for a user."""
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Get quests assigned today
        today = datetime.utcnow().date().isoformat()

        cursor.execute(
            """
            SELECT uq.*, q.name, q.description, q.target_type, q.target_value,
                   q.reward_coins, q.reward_xp, q.rarity, q.type,
                   q.allow_other_channels
            FROM user_quests uq
            JOIN quests q ON uq.questId = q.id
            WHERE uq.guildId = ? AND uq.userId = ?
              AND date(uq.assigned_at) = ?
              AND q.type = 'daily'
            ORDER BY uq.assigned_at
            """,
            (str(guild_id), str(user_id), today),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def assign_daily_quests(
    guild_id: str,
    user_id: str,
    num_guaranteed: int = 1,
    num_random: int = 2,
    conn=None,
) -> list:
    """
    Assign daily quests to a user.

    Args:
        guild_id: Guild ID
        user_id: User ID
        num_guaranteed: Number of guaranteed daily quests
        num_random: Number of random quests to potentially add

    Returns:
        list of assigned quest dictionaries
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Check if user already has daily quests today
        existing = get_user_daily_quests(guild_id, user_id, conn)
        if existing:
            return existing

        # Get available daily quests
        daily_quests = get_available_quests("daily", conn)
        if not daily_quests:
            return []

        assigned = []

        # Assign guaranteed daily quests
        if daily_quests and num_guaranteed > 0:
            # Prioritize common quests for guaranteed slots
            common_quests = [q for q in daily_quests if q["rarity"] == "common"]
            pool = common_quests if common_quests else daily_quests

            selected = random.sample(pool, min(num_guaranteed, len(pool)))
            for quest in selected:
                cursor.execute(
                    """
                    INSERT INTO user_quests (
                        guildId, userId, questId, progress, completed, claimed
                    ) VALUES (?, ?, ?, 0, 0, 0)
                    """,
                    (str(guild_id), str(user_id), quest["id"]),
                )
                quest["user_quest_id"] = cursor.lastrowid
                quest["progress"] = 0
                quest["completed"] = 0
                assigned.append(quest)

        # Potentially assign random bonus quests (50% chance each)
        remaining_quests = [q for q in daily_quests if q not in assigned]
        for _ in range(num_random):
            if remaining_quests and random.random() < 0.5:
                quest = random.choice(remaining_quests)
                remaining_quests.remove(quest)

                cursor.execute(
                    """
                    INSERT INTO user_quests (
                        guildId, userId, questId, progress, completed, claimed
                    ) VALUES (?, ?, ?, 0, 0, 0)
                    """,
                    (str(guild_id), str(user_id), quest["id"]),
                )
                quest["user_quest_id"] = cursor.lastrowid
                quest["progress"] = 0
                quest["completed"] = 0
                assigned.append(quest)

        conn.commit()
        return assigned

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def increment_quest_progress(
    guild_id: str,
    user_id: str,
    target_type: str,
    amount: int = 1,
    conn=None,
) -> list:
    """
    Increment progress on all matching quests for a user.

    Args:
        guild_id: Guild ID
        user_id: User ID
        target_type: The type of action (e.g., 'messages_sent', 'capture_attempt')
        amount: Amount to increment by

    Returns:
        list of quests that were completed by this increment
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Find matching active quests
        cursor.execute(
            """
            SELECT uq.id, uq.progress, q.target_value, q.name
            FROM user_quests uq
            JOIN quests q ON uq.questId = q.id
            WHERE uq.guildId = ? AND uq.userId = ?
              AND q.target_type = ?
              AND uq.completed = 0 AND uq.claimed = 0
            """,
            (str(guild_id), str(user_id), target_type),
        )
        quests = cursor.fetchall()

        completed_quests = []

        for quest in quests:
            quest_id = quest[0]
            current_progress = quest[1]
            target_value = quest[2]
            quest_name = quest[3]

            new_progress = min(current_progress + amount, target_value)
            is_complete = new_progress >= target_value

            if is_complete:
                cursor.execute(
                    """
                    UPDATE user_quests
                    SET progress = ?, completed = 1, completed_at = ?
                    WHERE id = ?
                    """,
                    (new_progress, datetime.utcnow().isoformat(), quest_id),
                )
                completed_quests.append({
                    "id": quest_id,
                    "name": quest_name,
                    "progress": new_progress,
                    "target": target_value,
                })
            else:
                cursor.execute(
                    "UPDATE user_quests SET progress = ? WHERE id = ?",
                    (new_progress, quest_id),
                )

        conn.commit()
        return completed_quests

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def claim_quest(
    guild_id: str,
    user_id: str,
    user_quest_id: int,
    conn=None,
) -> dict:
    """
    Claim rewards for a completed quest.

    Args:
        guild_id: Guild ID
        user_id: User ID
        user_quest_id: The user_quests.id to claim

    Returns:
        dict with claim results and rewards
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Get the quest
        cursor.execute(
            """
            SELECT uq.*, q.name, q.reward_coins, q.reward_xp
            FROM user_quests uq
            JOIN quests q ON uq.questId = q.id
            WHERE uq.id = ? AND uq.guildId = ? AND uq.userId = ?
            """,
            (user_quest_id, str(guild_id), str(user_id)),
        )
        quest = cursor.fetchone()

        if not quest:
            raise ValueError("Quest not found")

        quest = dict(quest)

        if not quest["completed"]:
            raise ValueError("Quest not yet completed")

        if quest["claimed"]:
            raise ValueError("Quest already claimed")

        # Award rewards
        reward_coins = quest["reward_coins"]
        reward_xp = quest["reward_xp"]

        if reward_coins > 0:
            add_coins(
                guild_id,
                user_id,
                reward_coins,
                "quest_reward",
                related_id=user_quest_id,
                related_type="quest",
                conn=conn,
            )

        xp_result = None
        if reward_xp > 0:
            xp_result = add_xp(
                guild_id,
                user_id,
                reward_xp,
                "quest_reward",
                related_id=user_quest_id,
                related_type="quest",
                conn=conn,
            )

        # Mark as claimed
        cursor.execute(
            "UPDATE user_quests SET claimed = 1 WHERE id = ?",
            (user_quest_id,),
        )

        conn.commit()

        return {
            "quest_name": quest["name"],
            "coins_rewarded": reward_coins,
            "xp_rewarded": reward_xp,
            "level_up": xp_result.get("level_up", False) if xp_result else False,
            "new_level": xp_result.get("new_level") if xp_result else None,
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def claim_all_completed_quests(
    guild_id: str,
    user_id: str,
    conn=None,
) -> list:
    """
    Claim all completed but unclaimed quests for a user.

    Returns:
        list of claim results
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        # Find all completed unclaimed quests
        cursor.execute(
            """
            SELECT uq.id FROM user_quests uq
            WHERE uq.guildId = ? AND uq.userId = ?
              AND uq.completed = 1 AND uq.claimed = 0
            """,
            (str(guild_id), str(user_id)),
        )
        quests = cursor.fetchall()

        results = []
        for quest in quests:
            try:
                result = claim_quest(guild_id, user_id, quest[0], conn)
                results.append(result)
            except ValueError:
                continue

        return results

    finally:
        if should_close:
            conn.close()


def get_daily_status(
    guild_id: str,
    user_id: str,
    conn=None,
) -> dict:
    """
    Get daily quest status including streak information.

    Returns:
        dict with daily quests, streak, and claim status
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    try:
        # Get today's quests
        daily_quests = get_user_daily_quests(guild_id, user_id, conn)

        # Get tracking data
        tracking = get_daily_tracking(guild_id, user_id, conn)

        # Calculate if eligible for new daily
        last_claim = tracking.get("last_daily_claim")
        can_claim_new = True
        if last_claim:
            last_claim_date = datetime.fromisoformat(last_claim).date()
            today = datetime.utcnow().date()
            can_claim_new = last_claim_date < today

        # Count completed/total
        total = len(daily_quests)
        completed = sum(1 for q in daily_quests if q["completed"])
        claimed = sum(1 for q in daily_quests if q.get("claimed"))

        return {
            "quests": daily_quests,
            "total": total,
            "completed": completed,
            "claimed": claimed,
            "streak": tracking.get("streak", 0),
            "can_claim_new": can_claim_new and total == 0,
            "all_completed": completed == total and total > 0,
        }
    finally:
        if should_close:
            conn.close()


def update_streak(
    guild_id: str,
    user_id: str,
    conn=None,
) -> int:
    """
    Update streak when user completes daily quests.

    Returns:
        new streak value
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cursor = conn.cursor()
    try:
        tracking = get_daily_tracking(guild_id, user_id, conn)

        last_claim = tracking.get("last_daily_claim")
        current_streak = tracking.get("streak", 0)
        now = datetime.utcnow()
        today = now.date()

        new_streak = 1  # Default: reset to 1

        if last_claim:
            last_claim_date = datetime.fromisoformat(last_claim).date()
            days_diff = (today - last_claim_date).days

            if days_diff == 1:
                # Consecutive day: increment streak
                new_streak = current_streak + 1
            elif days_diff == 0:
                # Same day: keep streak
                new_streak = current_streak
            # else: gap > 1 day, reset to 1

        cursor.execute(
            """
            UPDATE user_daily_tracking
            SET streak = ?, last_daily_claim = ?
            WHERE guildId = ? AND userId = ?
            """,
            (new_streak, now.isoformat(), str(guild_id), str(user_id)),
        )
        conn.commit()

        return new_streak

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def get_streak_multiplier(streak: int) -> float:
    """
    Calculate reward multiplier based on streak.

    7-day streak = 1.5x rewards
    14-day streak = 2.0x rewards
    30-day streak = 2.5x rewards
    """
    if streak >= 30:
        return 2.5
    elif streak >= 14:
        return 2.0
    elif streak >= 7:
        return 1.5
    else:
        return 1.0
