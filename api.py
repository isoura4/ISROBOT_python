"""
Flask API for ISROBOT V2 Dashboard.

This module provides REST endpoints for the web dashboard to:
- Get guild statistics
- Get/update guild configuration
- Manage challenges
- Handle Discord OAuth2 authentication
"""


import os
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database import get_db_connection
from utils.logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app, origins=os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000").split(","))

# API secret for authentication (should match dashboard)
API_SECRET = os.getenv("API_SECRET", "change-me-in-production")

# Warn if using default API secret
if API_SECRET == "change-me-in-production":
    logger.warning(
        "⚠️ SECURITY WARNING: Using default API_SECRET. "
        "Please set a secure API_SECRET in your environment variables for production."
    )


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != API_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# --- STATS ENDPOINTS ---

@app.route("/api/guilds/<guild_id>/stats", methods=["GET"])
@require_api_key
def get_guild_stats(guild_id: str):
    """
    Get statistics for a guild.

    Query params:
    - period: 7d, 30d, or all (default: 7d)
    """
    period = request.args.get("period", "7d")

    # Calculate date range
    if period == "7d":
        days = 7
    elif period == "30d":
        days = 30
    else:
        days = 365 * 10  # All time

    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Get member count and growth
        cursor.execute(
            """
            SELECT date, member_count, joins_today, leaves_today
            FROM member_growth
            WHERE guild_id = ? AND date >= ?
            ORDER BY date ASC
            """,
            (guild_id, start_date)
        )
        growth_data = [dict(row) for row in cursor.fetchall()]

        # Get top members by XP
        cursor.execute(
            """
            SELECT userId, xp, level, messages
            FROM users
            WHERE guildId = ?
            ORDER BY xp DESC
            LIMIT 10
            """,
            (guild_id,)
        )
        top_members = [dict(row) for row in cursor.fetchall()]

        # Get channel activity
        cursor.execute(
            """
            SELECT channel_id, date, message_count
            FROM channel_stats
            WHERE guild_id = ? AND date >= ?
            ORDER BY date ASC
            """,
            (guild_id, start_date)
        )
        channel_activity = [dict(row) for row in cursor.fetchall()]

        # Get aggregated channel stats
        cursor.execute(
            """
            SELECT channel_id, SUM(message_count) as total_messages
            FROM channel_stats
            WHERE guild_id = ? AND date >= ?
            GROUP BY channel_id
            ORDER BY total_messages DESC
            LIMIT 10
            """,
            (guild_id, start_date)
        )
        top_channels = [dict(row) for row in cursor.fetchall()]

        # Get total stats
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_users,
                SUM(xp) as total_xp,
                SUM(messages) as total_messages
            FROM users
            WHERE guildId = ?
            """,
            (guild_id,)
        )
        totals = dict(cursor.fetchone())

        # Get hourly activity distribution (mock data - would need message timestamps)
        # This would require tracking message hours in the database
        hourly_activity = [0] * 24  # Placeholder

        return jsonify({
            "guild_id": guild_id,
            "period": period,
            "totals": totals,
            "growth": growth_data,
            "top_members": top_members,
            "channel_activity": channel_activity,
            "top_channels": top_channels,
            "hourly_activity": hourly_activity,
        })

    except Exception as e:
        logger.error(f"Error getting guild stats: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/guilds/<guild_id>/leaderboard", methods=["GET"])
@require_api_key
def get_leaderboard(guild_id: str):
    """Get XP leaderboard for a guild."""
    limit = int(request.args.get("limit", 10))
    limit = min(limit, 100)  # Cap at 100

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT userId, xp, level, messages
            FROM users
            WHERE guildId = ?
            ORDER BY xp DESC
            LIMIT ?
            """,
            (guild_id, limit)
        )
        members = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "guild_id": guild_id,
            "leaderboard": members
        })
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# --- CONFIG ENDPOINTS ---

@app.route("/api/guilds/<guild_id>/config", methods=["GET"])
@require_api_key
def get_guild_config(guild_id: str):
    """Get configuration for a guild."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Get engagement config
        cursor.execute(
            "SELECT * FROM engagement_config WHERE guild_id = ?",
            (guild_id,)
        )
        engagement = cursor.fetchone()
        engagement_config = dict(engagement) if engagement else {}

        # Get moderation config
        cursor.execute(
            "SELECT * FROM moderation_config WHERE guild_id = ?",
            (guild_id,)
        )
        moderation = cursor.fetchone()
        moderation_config = dict(moderation) if moderation else {}

        # Get XP thresholds
        cursor.execute(
            """
            SELECT threshold_points, role_id, role_name
            FROM xp_thresholds
            WHERE guild_id = ?
            ORDER BY threshold_points ASC
            """,
            (guild_id,)
        )
        xp_thresholds = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "guild_id": guild_id,
            "engagement": engagement_config,
            "moderation": moderation_config,
            "xp_thresholds": xp_thresholds,
        })
    except Exception as e:
        logger.error(f"Error getting guild config: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/guilds/<guild_id>/config", methods=["POST"])
@require_api_key
def update_guild_config(guild_id: str):
    """Update configuration for a guild."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Update engagement config if provided
        if "engagement" in data:
            engagement = data["engagement"]

            # Validate fields
            allowed_fields = {
                "xp_per_message", "welcome_bonus_xp", "welcome_detection_enabled",
                "announcements_channel_id", "ambassador_role_id", "new_member_role_id",
                "new_member_role_duration_days", "welcome_dm_enabled",
                "welcome_dm_text", "welcome_public_text"
            }

            # Filter to allowed fields only
            safe_engagement = {k: v for k, v in engagement.items() if k in allowed_fields}

            if safe_engagement:
                # Ensure record exists
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO engagement_config (guild_id, created_at)
                    VALUES (?, ?)
                    """,
                    (guild_id, datetime.now(timezone.utc).isoformat())
                )

                # Build update query safely
                set_clauses = []
                values = []
                for key, value in safe_engagement.items():
                    set_clauses.append(f"{key} = ?")
                    values.append(value)

                values.append(guild_id)
                cursor.execute(
                    f"UPDATE engagement_config SET {', '.join(set_clauses)} WHERE guild_id = ?",
                    values
                )

        # Update moderation config if provided
        if "moderation" in data:
            moderation = data["moderation"]

            allowed_fields = {
                "log_channel_id", "appeal_channel_id", "ai_enabled",
                "ai_confidence_threshold", "ai_flag_channel_id", "ai_model",
                "ollama_host", "decay_multiplier", "warn_1_decay_days",
                "warn_2_decay_days", "warn_3_decay_days", "mute_duration_warn_2",
                "mute_duration_warn_3", "rules_message_id"
            }

            safe_moderation = {k: v for k, v in moderation.items() if k in allowed_fields}

            if safe_moderation:
                # Ensure record exists
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO moderation_config (guild_id, created_at)
                    VALUES (?, ?)
                    """,
                    (guild_id, datetime.now(timezone.utc).isoformat())
                )

                set_clauses = []
                values = []
                for key, value in safe_moderation.items():
                    set_clauses.append(f"{key} = ?")
                    values.append(value)

                values.append(guild_id)
                cursor.execute(
                    f"UPDATE moderation_config SET {', '.join(set_clauses)} WHERE guild_id = ?",
                    values
                )

        # Update XP thresholds if provided
        if "xp_thresholds" in data:
            thresholds = data["xp_thresholds"]

            # Replace all thresholds
            cursor.execute(
                "DELETE FROM xp_thresholds WHERE guild_id = ?",
                (guild_id,)
            )

            for threshold in thresholds:
                if "threshold_points" in threshold and "role_id" in threshold:
                    cursor.execute(
                        """
                        INSERT INTO xp_thresholds
                        (guild_id, threshold_points, role_id, role_name, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            guild_id,
                            threshold["threshold_points"],
                            threshold["role_id"],
                            threshold.get("role_name", ""),
                            datetime.now(timezone.utc).isoformat()
                        )
                    )

        conn.commit()
        return jsonify({"success": True, "message": "Configuration updated"})

    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating guild config: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# --- CHALLENGES ENDPOINTS ---

@app.route("/api/guilds/<guild_id>/challenges", methods=["GET"])
@require_api_key
def get_challenges(guild_id: str):
    """Get all challenges for a guild."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, reward_xp, reward_role_id, is_active, created_at
            FROM weekly_challenges
            WHERE guild_id = ?
            ORDER BY created_at DESC
            """,
            (guild_id,)
        )
        challenges = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "guild_id": guild_id,
            "challenges": challenges
        })
    except Exception as e:
        logger.error(f"Error getting challenges: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/guilds/<guild_id>/challenges", methods=["POST"])
@require_api_key
def create_challenge(guild_id: str):
    """Create a new challenge."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    name = data.get("name")
    description = data.get("description")
    reward_xp = data.get("reward_xp", 100)
    reward_role_id = data.get("reward_role_id")

    if not name or not description:
        return jsonify({"error": "Name and description are required"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO weekly_challenges
            (guild_id, name, description, reward_xp, reward_role_id, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                guild_id,
                name,
                description,
                reward_xp,
                reward_role_id,
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()

        return jsonify({
            "success": True,
            "challenge_id": cursor.lastrowid,
            "message": "Challenge created"
        })
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating challenge: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/guilds/<guild_id>/challenges/<int:challenge_id>", methods=["PUT"])
@require_api_key
def update_challenge(guild_id: str, challenge_id: int):
    """Update a challenge."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed_fields = {"name", "description", "reward_xp", "reward_role_id", "is_active"}
    safe_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not safe_data:
        return jsonify({"error": "No valid fields to update"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        set_clauses = []
        values = []
        for key, value in safe_data.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.extend([guild_id, challenge_id])
        cursor.execute(
            f"UPDATE weekly_challenges SET {', '.join(set_clauses)} WHERE guild_id = ? AND id = ?",
            values
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Challenge not found"}), 404

        return jsonify({"success": True, "message": "Challenge updated"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating challenge: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/guilds/<guild_id>/challenges/<int:challenge_id>", methods=["DELETE"])
@require_api_key
def delete_challenge(guild_id: str, challenge_id: int):
    """Delete a challenge."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM weekly_challenges WHERE guild_id = ? AND id = ?",
            (guild_id, challenge_id)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Challenge not found"}), 404

        return jsonify({"success": True, "message": "Challenge deleted"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting challenge: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# --- HEALTH CHECK ---

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# --- API SERVER RUNNER ---

def run_api_server(host: str = "0.0.0.0", port: int = 5000):
    """Run the Flask API server in a separate thread."""
    def run():
        app.run(host=host, port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info(f"API server started on {host}:{port}")
    return thread


if __name__ == "__main__":
    # Run standalone for testing
    app.run(host="0.0.0.0", port=5000, debug=True)
