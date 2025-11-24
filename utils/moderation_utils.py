"""
Utility functions for the moderation system.
Handles database operations, notifications, and helper functions.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord

import database

logger = logging.getLogger(__name__)


# --- Database Helper Functions ---


def get_warning_count(guild_id: str, user_id: str) -> int:
    """Get current warning count for a user."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT warn_count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = cursor.fetchone()
        return result["warn_count"] if result else 0
    finally:
        conn.close()


def increment_warning(
    guild_id: str, user_id: str, moderator_id: str, reason: str
) -> int:
    """
    Increment warning count for a user and log the action.
    Returns the new warning count.
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Get current count
        cursor.execute(
            "SELECT warn_count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = cursor.fetchone()
        old_count = result["warn_count"] if result else 0
        new_count = old_count + 1

        # Update or insert warning record
        cursor.execute(
            """
            INSERT INTO warnings (guild_id, user_id, warn_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                warn_count = ?,
                updated_at = ?
        """,
            (guild_id, user_id, new_count, now, now, new_count, now),
        )

        # Log to history
        cursor.execute(
            """
            INSERT INTO warning_history 
            (guild_id, user_id, action, warn_count_before, warn_count_after, 
             moderator_id, reason, created_at)
            VALUES (?, ?, 'warn_issued', ?, ?, ?, ?, ?)
        """,
            (guild_id, user_id, old_count, new_count, moderator_id, reason, now),
        )

        conn.commit()
        return new_count
    finally:
        conn.close()


def decrement_warning(
    guild_id: str, user_id: str, moderator_id: Optional[str], reason: Optional[str]
) -> int:
    """
    Decrement warning count for a user and log the action.
    Returns the new warning count.
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Get current count
        cursor.execute(
            "SELECT warn_count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = cursor.fetchone()
        if not result or result["warn_count"] <= 0:
            return 0

        old_count = result["warn_count"]
        new_count = max(0, old_count - 1)

        # Update warning record
        cursor.execute(
            """
            UPDATE warnings 
            SET warn_count = ?, updated_at = ?
            WHERE guild_id = ? AND user_id = ?
        """,
            (new_count, now, guild_id, user_id),
        )

        # Log to history
        cursor.execute(
            """
            INSERT INTO warning_history 
            (guild_id, user_id, action, warn_count_before, warn_count_after, 
             moderator_id, reason, created_at)
            VALUES (?, ?, 'warn_decreased', ?, ?, ?, ?, ?)
        """,
            (guild_id, user_id, old_count, new_count, moderator_id, reason, now),
        )

        conn.commit()
        return new_count
    finally:
        conn.close()


def get_warning_history(guild_id: str, user_id: str) -> list:
    """Get complete warning history for a user."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM warning_history 
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC
        """,
            (guild_id, user_id),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def add_mute(
    guild_id: str,
    user_id: str,
    moderator_id: Optional[str],
    reason: str,
    duration_seconds: int,
) -> None:
    """Add an active mute record."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=duration_seconds)

        cursor.execute(
            """
            INSERT INTO active_mutes 
            (guild_id, user_id, moderator_id, reason, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                moderator_id = ?,
                reason = ?,
                expires_at = ?,
                created_at = ?
        """,
            (
                guild_id,
                user_id,
                moderator_id,
                reason,
                expires_at.isoformat(),
                now.isoformat(),
                moderator_id,
                reason,
                expires_at.isoformat(),
                now.isoformat(),
            ),
        )

        # Log to history
        cursor.execute(
            """
            INSERT INTO warning_history 
            (guild_id, user_id, action, warn_count_before, warn_count_after, 
             moderator_id, reason, created_at)
            VALUES (?, ?, 'mute_applied', 0, 0, ?, ?, ?)
        """,
            (guild_id, user_id, moderator_id, reason, now.isoformat()),
        )

        conn.commit()
    finally:
        conn.close()


def remove_mute(
    guild_id: str, user_id: str, moderator_id: Optional[str], reason: str
) -> bool:
    """
    Remove an active mute record.
    Returns True if a mute was removed, False otherwise.
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check if mute exists
        cursor.execute(
            "SELECT id FROM active_mutes WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = cursor.fetchone()
        if not result:
            return False

        # Remove mute
        cursor.execute(
            "DELETE FROM active_mutes WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )

        # Log to history
        cursor.execute(
            """
            INSERT INTO warning_history 
            (guild_id, user_id, action, warn_count_before, warn_count_after, 
             moderator_id, reason, created_at)
            VALUES (?, ?, 'mute_removed', 0, 0, ?, ?, ?)
        """,
            (guild_id, user_id, moderator_id, reason, now),
        )

        conn.commit()
        return True
    finally:
        conn.close()


def get_active_mute(guild_id: str, user_id: str) -> Optional[dict]:
    """Get active mute record for a user, if any."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM active_mutes WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = cursor.fetchone()
        return dict(result) if result else None
    finally:
        conn.close()


def get_expired_mutes() -> list:
    """Get all mutes that have expired."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("SELECT * FROM active_mutes WHERE expires_at <= ?", (now,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_moderation_config(guild_id: str) -> Optional[dict]:
    """Get moderation configuration for a guild."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM moderation_config WHERE guild_id = ?", (guild_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None
    finally:
        conn.close()


def set_moderation_config(guild_id: str, parameter: str, value: str) -> None:
    """Set a moderation configuration parameter for a guild."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check if config exists
        cursor.execute(
            "SELECT guild_id FROM moderation_config WHERE guild_id = ?", (guild_id,)
        )
        exists = cursor.fetchone()

        if not exists:
            # Create default config
            cursor.execute(
                "INSERT INTO moderation_config (guild_id, created_at) VALUES (?, ?)",
                (guild_id, now),
            )

        # Update the parameter
        cursor.execute(
            f"UPDATE moderation_config SET {parameter} = ? WHERE guild_id = ?",
            (value, guild_id),
        )

        conn.commit()
    finally:
        conn.close()


def calculate_decay_days(warn_count: int, config: Optional[dict]) -> int:
    """Calculate the number of days until next decay based on warn count."""
    if not config:
        # Default values
        decay_days = {1: 7, 2: 14, 3: 21}
        return decay_days.get(warn_count, 28)

    if warn_count == 1:
        return config.get("warn_1_decay_days", 7)
    elif warn_count == 2:
        return config.get("warn_2_decay_days", 14)
    elif warn_count == 3:
        return config.get("warn_3_decay_days", 21)
    else:
        return 28  # 4+ warns decay after 28 days


def get_users_for_decay() -> list:
    """Get all users whose warnings are ready to decay."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)

        # Get all users with warnings
        cursor.execute("SELECT * FROM warnings WHERE warn_count > 0")
        warnings = cursor.fetchall()

        users_to_decay = []
        for warning in warnings:
            guild_id = warning["guild_id"]
            user_id = warning["user_id"]
            warn_count = warning["warn_count"]
            updated_at = datetime.fromisoformat(warning["updated_at"])

            # Get config for this guild
            config = get_moderation_config(guild_id)
            decay_days = calculate_decay_days(warn_count, config)

            # Check if decay period has passed
            decay_deadline = updated_at + timedelta(days=decay_days)
            if now >= decay_deadline:
                users_to_decay.append(
                    {
                        "guild_id": guild_id,
                        "user_id": user_id,
                        "warn_count": warn_count,
                    }
                )

        return users_to_decay
    finally:
        conn.close()


def create_appeal(
    guild_id: str, user_id: str, appeal_reason: str
) -> Optional[int]:
    """
    Create a new appeal for a user.
    Returns the appeal ID if successful, None if user has no warnings
    or already has a pending appeal.
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check if user has warnings
        cursor.execute(
            "SELECT warn_count FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        result = cursor.fetchone()
        if not result or result["warn_count"] <= 0:
            return None

        # Check for existing pending appeal
        cursor.execute(
            """
            SELECT id FROM moderation_appeals 
            WHERE guild_id = ? AND user_id = ? AND status = 'pending'
        """,
            (guild_id, user_id),
        )
        if cursor.fetchone():
            return None

        # Create appeal
        cursor.execute(
            """
            INSERT INTO moderation_appeals 
            (guild_id, user_id, appeal_reason, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """,
            (guild_id, user_id, appeal_reason, now),
        )

        # Log to history
        cursor.execute(
            """
            INSERT INTO warning_history 
            (guild_id, user_id, action, warn_count_before, warn_count_after, 
             moderator_id, reason, created_at)
            VALUES (?, ?, 'appeal_created', 0, 0, NULL, ?, ?)
        """,
            (guild_id, user_id, appeal_reason, now),
        )

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_pending_appeals(guild_id: str) -> list:
    """Get all pending appeals for a guild."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM moderation_appeals 
            WHERE guild_id = ? AND status = 'pending'
            ORDER BY created_at ASC
        """,
            (guild_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def review_appeal(
    appeal_id: int, moderator_id: str, decision: str, moderator_decision: str
) -> bool:
    """
    Review an appeal (approve or deny).
    Returns True if successful, False if appeal not found.
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check if appeal exists
        cursor.execute(
            "SELECT guild_id, user_id FROM moderation_appeals WHERE id = ?",
            (appeal_id,),
        )
        result = cursor.fetchone()
        if not result:
            return False

        guild_id = result["guild_id"]
        user_id = result["user_id"]

        # Update appeal
        cursor.execute(
            """
            UPDATE moderation_appeals 
            SET status = ?, moderator_id = ?, moderator_decision = ?, reviewed_at = ?
            WHERE id = ?
        """,
            (decision, moderator_id, moderator_decision, now, appeal_id),
        )

        # Log to history
        cursor.execute(
            """
            INSERT INTO warning_history 
            (guild_id, user_id, action, warn_count_before, warn_count_after, 
             moderator_id, reason, created_at)
            VALUES (?, ?, 'appeal_reviewed', 0, 0, ?, ?, ?)
        """,
            (guild_id, user_id, moderator_id, moderator_decision, now),
        )

        conn.commit()
        return True
    finally:
        conn.close()


# --- Notification Functions ---


async def send_dm_notification(
    user: discord.Member, embed: discord.Embed
) -> bool:
    """
    Send a DM notification to a user.
    Returns True if successful, False if DMs are disabled.
    """
    try:
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        logger.warning(f"Cannot send DM to user {user.id} - DMs disabled")
        return False
    except Exception as e:
        logger.error(f"Error sending DM to user {user.id}: {e}")
        return False


def create_warning_embed(
    reason: str, warn_count: int, guild_name: str, rules_link: Optional[str] = None
) -> discord.Embed:
    """Create an embed for a warning notification."""
    embed = discord.Embed(
        title="⚠️ Avertissement reçu",
        description=f"Vous avez reçu un avertissement sur **{guild_name}**.",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Raison", value=reason, inline=False)
    embed.add_field(name="Nombre d'avertissements", value=str(warn_count), inline=True)

    if rules_link:
        embed.add_field(
            name="Règles du serveur", value=f"[Cliquez ici]({rules_link})", inline=False
        )

    embed.add_field(
        name="📝 Faire appel",
        value="Vous pouvez faire appel de cet avertissement en utilisant "
        "la commande `/appeal` avec votre raison.",
        inline=False,
    )

    embed.set_footer(text="Système de modération ISROBOT")
    return embed


def create_mute_embed(
    reason: str, duration_seconds: int, guild_name: str
) -> discord.Embed:
    """Create an embed for a mute notification."""
    duration_str = format_duration(duration_seconds)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

    embed = discord.Embed(
        title="🔇 Vous avez été muté",
        description=f"Vous avez été muté sur **{guild_name}**.",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Raison", value=reason, inline=False)
    embed.add_field(name="Durée", value=duration_str, inline=True)
    embed.add_field(
        name="Expire",
        value=f"<t:{int(expires_at.timestamp())}:R>",
        inline=True,
    )

    embed.set_footer(text="Système de modération ISROBOT")
    return embed


def create_decay_embed(
    new_warn_count: int, guild_name: str
) -> discord.Embed:
    """Create an embed for a warning decay notification."""
    embed = discord.Embed(
        title="✅ Avertissement expiré",
        description=f"Un de vos avertissements sur **{guild_name}** a expiré.",
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Nouveaux avertissements", value=str(new_warn_count), inline=True
    )

    embed.add_field(
        name="Continuez ainsi !",
        value="Continuez à respecter les règles du serveur.",
        inline=False,
    )

    embed.set_footer(text="Système de modération ISROBOT")
    return embed


def create_modlog_embed(
    action: str, user: discord.Member, moderator: Optional[discord.Member], **kwargs
) -> discord.Embed:
    """Create an embed for moderation log entries."""
    color_map = {
        "warn": discord.Color.orange(),
        "unwarn": discord.Color.blue(),
        "mute": discord.Color.red(),
        "unmute": discord.Color.green(),
        "decay": discord.Color.light_gray(),
        "appeal_created": discord.Color.purple(),
        "appeal_approved": discord.Color.green(),
        "appeal_denied": discord.Color.red(),
    }

    title_map = {
        "warn": "⚠️ Avertissement émis",
        "unwarn": "✅ Avertissement retiré",
        "mute": "🔇 Utilisateur muté",
        "unmute": "🔊 Utilisateur démuté",
        "decay": "⏰ Avertissement expiré",
        "appeal_created": "📝 Appel créé",
        "appeal_approved": "✅ Appel approuvé",
        "appeal_denied": "❌ Appel refusé",
    }

    embed = discord.Embed(
        title=title_map.get(action, "📋 Action de modération"),
        color=color_map.get(action, discord.Color.blue()),
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(name="Utilisateur", value=user.mention, inline=True)

    if moderator:
        embed.add_field(name="Modérateur", value=moderator.mention, inline=True)
    else:
        embed.add_field(name="Action", value="Automatique", inline=True)

    # Add additional fields from kwargs
    for key, value in kwargs.items():
        formatted_key = key.replace("_", " ").title()
        embed.add_field(name=formatted_key, value=str(value), inline=False)

    embed.set_footer(text="Système de modération ISROBOT")
    return embed


# --- Utility Functions ---


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds} seconde{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} heure{'s' if hours != 1 else ''}"
    else:
        days = seconds // 86400
        return f"{days} jour{'s' if days != 1 else ''}"


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse duration string to seconds.
    Examples: "1h", "30m", "1d", "2h30m"
    """
    duration_str = duration_str.lower().strip()
    total_seconds = 0

    import re

    # Parse days
    days_match = re.search(r"(\d+)d", duration_str)
    if days_match:
        total_seconds += int(days_match.group(1)) * 86400

    # Parse hours
    hours_match = re.search(r"(\d+)h", duration_str)
    if hours_match:
        total_seconds += int(hours_match.group(1)) * 3600

    # Parse minutes
    minutes_match = re.search(r"(\d+)m", duration_str)
    if minutes_match:
        total_seconds += int(minutes_match.group(1)) * 60

    # Parse seconds
    seconds_match = re.search(r"(\d+)s", duration_str)
    if seconds_match:
        total_seconds += int(seconds_match.group(1))

    return total_seconds if total_seconds > 0 else None
