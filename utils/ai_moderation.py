"""
AI-assisted message flagging using a configurable AI provider.
Helps moderators identify potentially problematic messages.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from dotenv import load_dotenv

import database
from utils import ai_provider
from utils.i18n import t

load_dotenv()

logger = logging.getLogger(__name__)


async def analyze_message(
    message_content: str,
    server_rules: Optional[str],
    model: Optional[str] = None,
    host: Optional[str] = None,
) -> Optional[dict]:
    """
    Analyze a message using the configured AI provider to detect violations.

    Args:
        message_content: texte du message à analyser.
        server_rules: règles du serveur (optionnel).
        model: modèle Ollama explicite (ignoré pour les providers externes).
        host: hôte Ollama explicite (ignoré pour les providers externes).

    Returns:
        dict with keys: 'score' (0-100), 'category', 'reason'
        None if analysis fails
    """
    prompt = _build_analysis_prompt(message_content, server_rules)

    kwargs: dict = {"temperature": 0.3, "timeout": 5.0}
    if ai_provider.get_provider() == "ollama":
        if model is not None:
            kwargs["model"] = model
        if host is not None:
            kwargs["host"] = host

    try:
        ai_response = await ai_provider.chat(
            [{"role": "user", "content": prompt}], **kwargs
        )
    except ai_provider.AIProviderError as e:
        logger.warning(f"Échec de l'analyse IA: {e}")
        return None

    if not ai_response:
        return None

    return _parse_ai_response(ai_response)


def _build_analysis_prompt(message_content: str, server_rules: Optional[str]) -> str:
    """Build the prompt for Ollama analysis."""
    # Truncate very long messages
    if len(message_content) > 1000:
        message_content = message_content[:1000] + "..."

    prompt = """You are a content moderation AI assistant for a Discord server. Your role is to help moderators identify potentially problematic messages. Be conservative and cautious - only flag messages that clearly violate rules or are harmful.

"""

    if server_rules:
        prompt += f"""Server Rules:
{server_rules}

"""

    prompt += f"""Message to analyze:
"{message_content}"

Analyze this message and provide:
1. A confidence score (0-100) indicating how likely this message violates the rules or is harmful
   - 0-30: No violation (normal conversation)
   - 30-50: Borderline (might be worth reviewing)
   - 50-70: Likely violation (should be reviewed)
   - 70-100: Clear violation (immediate attention needed)

2. A category if problematic:
   - Toxicity (insults, aggression, negativity)
   - Spam (repetitive, promotional, low-value content)
   - NSFW (adult content, inappropriate material)
   - Harassment (targeted attacks, bullying)
   - Misinformation (false or misleading information)
   - None (no violation detected)

3. A brief reason for your assessment (one sentence)

FORMAT YOUR RESPONSE EXACTLY AS:
SCORE: [number 0-100]
CATEGORY: [category from list above]
REASON: [brief explanation in one sentence]

Be very conservative. Most messages are normal conversation and should score below 30.
"""

    return prompt


def _parse_ai_response(ai_response: str) -> Optional[dict]:
    """Parse the AI response to extract score, category, and reason."""
    try:
        score = None
        category = None
        reason = None

        lines = ai_response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("SCORE:"):
                score_str = line.replace("SCORE:", "").strip()
                # Extract just the number
                import re

                match = re.search(r"\d+", score_str)
                if match:
                    score = int(match.group())
            elif line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip()
            elif line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()

        # Validate results
        if score is None or category is None or reason is None:
            logger.warning(f"Incomplete AI response: {ai_response[:200]}")
            return None

        # Clamp score to 0-100
        score = max(0, min(100, score))

        # Validate category
        valid_categories = [
            "Toxicity",
            "Spam",
            "NSFW",
            "Harassment",
            "Misinformation",
            "None",
        ]
        if category not in valid_categories:
            logger.warning(f"Invalid category from AI: {category}")
            category = "None"

        return {"score": score, "category": category, "reason": reason}

    except Exception as e:
        logger.error(f"Error parsing AI response: {e}")
        return None


async def create_ai_flag(
    guild_id: str,
    message: discord.Message,
    ai_score: int,
    ai_category: str,
    ai_reason: str,
) -> Optional[int]:
    """
    Create an AI flag in the database.

    Returns:
        Flag ID if successful, None if flag already exists for this message
    """
    # Truncate message content if too long
    message_content = message.content
    if len(message_content) > 2000:
        message_content = message_content[:2000] + "..."

    message_id = str(message.id)
    channel_id = str(message.channel.id)
    author_id = str(message.author.id)
    now = datetime.now(timezone.utc).isoformat()

    def _do() -> Optional[int]:
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()

            # Check if message already flagged
            cursor.execute(
                "SELECT id FROM ai_flags WHERE message_id = ?", (message_id,)
            )
            if cursor.fetchone():
                return None

            cursor.execute(
                """
                INSERT INTO ai_flags 
                (guild_id, message_id, channel_id, user_id, message_content, 
                 ai_score, ai_category, ai_reason, moderator_action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
                (
                    guild_id,
                    message_id,
                    channel_id,
                    author_id,
                    message_content,
                    ai_score,
                    ai_category,
                    ai_reason,
                    now,
                ),
            )

            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating AI flag: {e}")
            return None
        finally:
            conn.close()

    return await asyncio.to_thread(_do)


async def get_server_rules(
    guild: discord.Guild, rules_message_id: Optional[str]
) -> Optional[str]:
    """
    Fetch server rules from a configured message.

    Returns:
        Rules text if found, None otherwise
    """
    if not rules_message_id:
        return None

    try:
        # Try to find the message in all text channels
        for channel in guild.text_channels:
            try:
                if not channel.permissions_for(guild.me).read_message_history:
                    continue

                message = await channel.fetch_message(int(rules_message_id))
                if message:
                    return message.content or (
                        message.embeds[0].description if message.embeds else None
                    )
            except (discord.NotFound, discord.Forbidden, ValueError):
                continue

        logger.warning(
            f"Rules message {rules_message_id} not found in guild {guild.id}"
        )
        return None

    except Exception as e:
        logger.error(f"Error fetching server rules: {e}")
        return None


def create_ai_flag_embed(
    flag_id: int,
    message: discord.Message,
    ai_score: int,
    ai_category: str,
    ai_reason: str,
    locale: Optional[str] = None,
) -> discord.Embed:
    """Create an embed for an AI-flagged message."""
    # Risk level indicator
    if ai_score >= 80:
        risk = t("ai.risk_high", locale)
        color = discord.Color.dark_red()
    elif ai_score >= 60:
        risk = t("ai.risk_medium", locale)
        color = discord.Color.orange()
    elif ai_score >= 40:
        risk = t("ai.risk_low", locale)
        color = discord.Color.gold()
    else:
        risk = t("ai.risk_info", locale)
        color = discord.Color.blue()

    embed = discord.Embed(
        title=t("ai.flag_title", locale, flag_id=flag_id),
        description=t("ai.flag_risk", locale, risk=risk, score=ai_score),
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(name=t("ai.field_category", locale), value=ai_category, inline=True)
    embed.add_field(
        name=t("ai.field_score", locale), value=f"{ai_score}/100", inline=True
    )
    embed.add_field(name=t("ai.field_reason", locale), value=ai_reason, inline=False)

    # Message info
    embed.add_field(
        name=t("ai.field_author", locale), value=message.author.mention, inline=True
    )
    embed.add_field(
        name=t("ai.field_channel", locale), value=message.channel.mention, inline=True
    )
    embed.add_field(
        name=t("ai.field_link", locale),
        value=t("ai.field_link_value", locale, url=message.jump_url),
        inline=True,
    )

    # Message content (truncated)
    content = message.content
    if len(content) > 500:
        content = content[:500] + "..."
    embed.add_field(
        name=t("ai.field_content", locale),
        value=content or t("ai.no_text", locale),
        inline=False,
    )

    embed.set_footer(text=t("ai.flag_footer", locale))

    return embed


def get_risk_level_emoji(score: int) -> str:
    """Get emoji for risk level."""
    if score >= 80:
        return "🔴"
    elif score >= 60:
        return "🟠"
    elif score >= 40:
        return "🟡"
    else:
        return "🟢"


async def update_ai_flag_action(flag_id: int, action: str, moderator_id: str) -> bool:
    """
    Update the moderator action for an AI flag.

    Args:
        flag_id: The flag ID
        action: 'warned', 'reviewed', 'ignored', or 'false_positive'
        moderator_id: ID of the moderator taking action

    Returns:
        True if successful, False otherwise
    """
    now = datetime.now(timezone.utc).isoformat()

    def _do() -> bool:
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE ai_flags 
                SET moderator_action = ?, moderator_id = ?, reviewed_at = ?
                WHERE id = ?
            """,
                (action, moderator_id, now, flag_id),
            )

            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating AI flag action: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(_do)


async def get_pending_ai_flags(guild_id: str, limit: int = 10) -> list:
    """Get pending AI flags for a guild."""

    def _do() -> list:
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM ai_flags 
                WHERE guild_id = ? AND moderator_action = 'pending'
                ORDER BY ai_score DESC, created_at ASC
                LIMIT ?
            """,
                (guild_id, limit),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    return await asyncio.to_thread(_do)
