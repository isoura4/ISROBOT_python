"""
AI-assisted message flagging using Ollama.
Helps moderators identify potentially problematic messages.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import discord
from dotenv import load_dotenv

import database

load_dotenv()

logger = logging.getLogger(__name__)

# Default Ollama configuration
DEFAULT_OLLAMA_HOST = os.getenv("ollama_host", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("ollama_model", "llama2")


async def analyze_message_with_ollama(
    message_content: str,
    server_rules: Optional[str],
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    model: str = DEFAULT_OLLAMA_MODEL,
) -> Optional[dict]:
    """
    Analyze a message using Ollama AI to detect potential violations.

    Returns:
        dict with keys: 'score' (0-100), 'category', 'reason'
        None if analysis fails
    """
    prompt = _build_analysis_prompt(message_content, server_rules)

    try:
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(5):  # 5 second timeout
                async with session.post(
                    f"{ollama_host}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Conservative for consistency
                            "top_p": 0.9,
                        },
                    },
                ) as response:
                    if response.status != 200:
                        logger.error(
                            f"Ollama API returned status {response.status}"
                        )
                        return None

                    data = await response.json()
                    ai_response = data.get("response", "")

                    return _parse_ai_response(ai_response)

    except asyncio.TimeoutError:
        logger.warning("Ollama analysis timed out after 5 seconds")
        return None
    except aiohttp.ClientError as e:
        logger.warning(f"Ollama connection error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error analyzing message with Ollama: {e}")
        return None


def _build_analysis_prompt(
    message_content: str, server_rules: Optional[str]
) -> str:
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
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check if message already flagged
        cursor.execute(
            "SELECT id FROM ai_flags WHERE message_id = ?", (str(message.id),)
        )
        if cursor.fetchone():
            return None

        # Truncate message content if too long
        message_content = message.content
        if len(message_content) > 2000:
            message_content = message_content[:2000] + "..."

        cursor.execute(
            """
            INSERT INTO ai_flags 
            (guild_id, message_id, channel_id, user_id, message_content, 
             ai_score, ai_category, ai_reason, moderator_action, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
            (
                guild_id,
                str(message.id),
                str(message.channel.id),
                str(message.author.id),
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


async def get_server_rules(guild: discord.Guild, rules_message_id: Optional[str]) -> Optional[str]:
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

        logger.warning(f"Rules message {rules_message_id} not found in guild {guild.id}")
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
) -> discord.Embed:
    """Create an embed for an AI-flagged message."""
    # Risk level indicator
    if ai_score >= 80:
        risk = "🔴 ÉLEVÉ"
        color = discord.Color.dark_red()
    elif ai_score >= 60:
        risk = "🟠 MOYEN"
        color = discord.Color.orange()
    elif ai_score >= 40:
        risk = "🟡 FAIBLE"
        color = discord.Color.gold()
    else:
        risk = "🟢 INFO"
        color = discord.Color.blue()

    embed = discord.Embed(
        title=f"🤖 Message signalé par l'IA (Flag #{flag_id})",
        description=f"**Niveau de risque:** {risk} ({ai_score}/100)",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(name="Catégorie", value=ai_category, inline=True)
    embed.add_field(name="Score IA", value=f"{ai_score}/100", inline=True)
    embed.add_field(name="Raison IA", value=ai_reason, inline=False)

    # Message info
    embed.add_field(name="Auteur", value=message.author.mention, inline=True)
    embed.add_field(name="Canal", value=message.channel.mention, inline=True)
    embed.add_field(
        name="Lien",
        value=f"[Aller au message]({message.jump_url})",
        inline=True,
    )

    # Message content (truncated)
    content = message.content
    if len(content) > 500:
        content = content[:500] + "..."
    embed.add_field(name="Contenu du message", value=content or "*[Aucun texte]*", inline=False)

    embed.set_footer(text="IA assistant • Les modérateurs ont le dernier mot")

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


async def update_ai_flag_action(
    flag_id: int, action: str, moderator_id: str
) -> bool:
    """
    Update the moderator action for an AI flag.

    Args:
        flag_id: The flag ID
        action: 'warned', 'reviewed', 'ignored', or 'false_positive'
        moderator_id: ID of the moderator taking action

    Returns:
        True if successful, False otherwise
    """
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

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


async def get_pending_ai_flags(guild_id: str, limit: int = 10) -> list:
    """Get pending AI flags for a guild."""
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
