"""
Engagement System Cog for ISROBOT V2.

Handles:
- Priority 1: XP Recognition System (enhanced)
- Priority 2: Automated Onboarding
- Priority 3: Weekly Challenges
- Priority 4: Event Reminders
"""

import os
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database import get_db_connection
from utils.logging_config import get_logger

# Load environment variables
load_dotenv()

SERVER_ID = int(os.getenv("server_id", "0"))
logger = get_logger(__name__)


class EngagementSystem(commands.Cog):
    """Cog for community engagement features."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_cooldowns = {}  # Anti-spam for welcome detection
        self.message_cooldowns = {}  # Anti-spam for XP gain

    async def cog_load(self):
        """Called when the cog is loaded."""
        # Start scheduled tasks
        self.check_temp_roles.start()
        self.check_event_reminders.start()
        self.weekly_challenge_task.start()
        logger.info("Engagement system cog loaded")

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        self.check_temp_roles.cancel()
        self.check_event_reminders.cancel()
        self.weekly_challenge_task.cancel()
        logger.info("Engagement system cog unloaded")

    # --- HELPER METHODS ---

    def get_engagement_config(self, guild_id: str) -> dict:
        """Get or create engagement configuration for a guild."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM engagement_config WHERE guild_id = ?",
                (guild_id,)
            )
            result = cursor.fetchone()

            if result:
                return dict(result)

            # Create default config
            cursor.execute(
                """
                INSERT INTO engagement_config (guild_id, created_at)
                VALUES (?, ?)
                """,
                (guild_id, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()

            return {
                "guild_id": guild_id,
                "xp_per_message": 1,
                "welcome_bonus_xp": 10,
                "welcome_detection_enabled": 1,
                "announcements_channel_id": None,
                "ambassador_role_id": None,
                "new_member_role_id": None,
                "new_member_role_duration_days": 7,
                "welcome_dm_enabled": 1,
                "welcome_dm_text": """Bienvenue sur le serveur ! 🎉

**Guide de démarrage:**
1. 📋 Consultez les règles du serveur
2. 🎭 Choisissez vos rôles
3. 👋 Présentez-vous dans le salon approprié
4. 🔍 Explorez les différents salons

N'hésitez pas à poser des questions !""",
                "welcome_public_text": "Bienvenue {user} sur le serveur ! 🎉",
            }
        finally:
            conn.close()

    def get_xp_thresholds(self, guild_id: str) -> list:
        """Get XP thresholds for a guild."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM xp_thresholds
                WHERE guild_id = ?
                ORDER BY threshold_points ASC
                """,
                (guild_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def add_xp_to_user(
        self, guild_id: str, user_id: str, xp_amount: int, reason: str = "message"
    ) -> dict:
        """Add XP to a user and check for milestone achievements."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Get current user data
            cursor.execute(
                "SELECT xp, level FROM users WHERE guildId = ? AND userId = ?",
                (guild_id, user_id)
            )
            result = cursor.fetchone()

            if result:
                old_xp = result["xp"]
                new_xp = old_xp + xp_amount
            else:
                # Create user
                old_xp = 0
                new_xp = xp_amount
                cursor.execute(
                    """
                    INSERT INTO users (guildId, userId, xp, level, messages, coins)
                    VALUES (?, ?, ?, 1, 0, 0)
                    """,
                    (guild_id, user_id, new_xp)
                )

            # Update XP
            cursor.execute(
                "UPDATE users SET xp = ? WHERE guildId = ? AND userId = ?",
                (new_xp, guild_id, user_id)
            )
            conn.commit()

            # Check thresholds
            thresholds = self.get_xp_thresholds(guild_id)
            new_threshold = None
            for threshold in thresholds:
                if old_xp < threshold["threshold_points"] <= new_xp:
                    new_threshold = threshold
                    break

            return {
                "old_xp": old_xp,
                "new_xp": new_xp,
                "xp_added": xp_amount,
                "new_threshold": new_threshold,
            }
        finally:
            conn.close()

    # --- PRIORITY 1: XP RECOGNITION SYSTEM ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain on message and welcome detection."""
        # Ignore bots
        if message.author.bot:
            return

        # Ignore DMs
        if not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        config = self.get_engagement_config(guild_id)

        # --- Anti-spam XP check (1 message per minute) ---
        cooldown_key = f"{guild_id}_{user_id}"
        current_time = datetime.now(timezone.utc).timestamp()

        if cooldown_key in self.message_cooldowns:
            if current_time - self.message_cooldowns[cooldown_key] < 60:
                # Still on cooldown, check for welcome detection only
                pass
            else:
                # Add XP for message
                self.message_cooldowns[cooldown_key] = current_time
                xp_amount = config.get("xp_per_message", 1)
                result = self.add_xp_to_user(guild_id, user_id, xp_amount, "message")

                # Check for milestone achievement
                if result.get("new_threshold"):
                    await self._handle_threshold_reached(
                        message, result["new_threshold"], result["new_xp"]
                    )
        else:
            # First message, add XP
            self.message_cooldowns[cooldown_key] = current_time
            xp_amount = config.get("xp_per_message", 1)
            result = self.add_xp_to_user(guild_id, user_id, xp_amount, "message")

            # Check for milestone achievement
            if result.get("new_threshold"):
                await self._handle_threshold_reached(
                    message, result["new_threshold"], result["new_xp"]
                )

        # --- Welcome detection ---
        if config.get("welcome_detection_enabled", 1):
            await self._check_welcome_message(message, config)

    async def _check_welcome_message(
        self, message: discord.Message, config: dict
    ):
        """Check if message is a welcome message and reward accordingly."""
        content_lower = message.content.lower()

        # Check for "bienvenue" or "welcome" with a mention
        welcome_patterns = ["bienvenue", "welcome", "bvn"]
        has_welcome = any(pattern in content_lower for pattern in welcome_patterns)

        if has_welcome and message.mentions:
            # Anti-spam: limit to one welcome bonus per minute
            cooldown_key = f"welcome_{message.guild.id}_{message.author.id}"
            current_time = datetime.now(timezone.utc).timestamp()

            if cooldown_key in self.welcome_cooldowns:
                if current_time - self.welcome_cooldowns[cooldown_key] < 60:
                    return

            self.welcome_cooldowns[cooldown_key] = current_time

            # Add reaction
            try:
                await message.add_reaction("🙏")
            except discord.errors.Forbidden:
                pass

            # Give XP bonus
            bonus_xp = config.get("welcome_bonus_xp", 10)
            guild_id = str(message.guild.id)
            user_id = str(message.author.id)

            result = self.add_xp_to_user(guild_id, user_id, bonus_xp, "accueil_nouveau")

            logger.info(
                f"Welcome bonus: {message.author} earned {bonus_xp} XP for welcoming"
            )

            # Check for milestone
            if result.get("new_threshold"):
                await self._handle_threshold_reached(
                    message, result["new_threshold"], result["new_xp"]
                )

    async def _handle_threshold_reached(
        self, message: discord.Message, threshold: dict, current_xp: int
    ):
        """Handle when a user reaches a new XP threshold."""
        # Announce in channel
        embed = discord.Embed(
            title="🎉 Nouveau Palier Atteint !",
            description=(
                f"Félicitations {message.author.mention} !\n"
                f"Vous avez atteint **{threshold['threshold_points']} points** !"
            ),
            color=discord.Color.gold()
        )
        embed.add_field(name="XP Total", value=f"{int(current_xp)}", inline=True)
        embed.set_thumbnail(
            url=message.author.avatar.url if message.author.avatar else
            message.author.default_avatar.url
        )

        try:
            await message.channel.send(embed=embed)
        except discord.errors.Forbidden:
            pass

        # Assign role if configured
        if threshold.get("role_id"):
            try:
                role = message.guild.get_role(int(threshold["role_id"]))
                if role and message.author:
                    member = message.guild.get_member(message.author.id)
                    if member:
                        await member.add_roles(role, reason="XP threshold reached")
                        logger.info(
                            f"Assigned role {role.name} to {member} for reaching "
                            f"{threshold['threshold_points']} XP"
                        )
            except Exception as e:
                logger.error(f"Error assigning threshold role: {e}")

    # --- PRIORITY 2: AUTOMATED ONBOARDING ---

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member join for onboarding."""
        if member.bot:
            return

        guild_id = str(member.guild.id)
        config = self.get_engagement_config(guild_id)

        # 1. Send public welcome message
        await self._send_public_welcome(member, config)

        # 2. Send private DM
        if config.get("welcome_dm_enabled", 1):
            await self._send_welcome_dm(member, config)

        # 3. Assign temporary "Nouveau" role
        if config.get("new_member_role_id"):
            await self._assign_temp_role(member, config)

        # 4. Ping random Ambassador
        if config.get("ambassador_role_id"):
            await self._notify_ambassador(member, config)

        # Track member growth
        await self._track_member_join(member.guild)

    async def _send_public_welcome(self, member: discord.Member, config: dict):
        """Send public welcome message."""
        # Find system channel or announcements channel
        channel = None
        if config.get("announcements_channel_id"):
            channel = member.guild.get_channel(
                int(config["announcements_channel_id"])
            )
        if not channel:
            channel = member.guild.system_channel

        if not channel:
            return

        # Format welcome message
        welcome_text = config.get(
            "welcome_public_text",
            "Bienvenue {user} sur le serveur ! 🎉"
        )
        welcome_text = welcome_text.replace("{user}", member.mention)

        embed = discord.Embed(
            title="👋 Nouveau Membre !",
            description=welcome_text,
            color=discord.Color.green()
        )
        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.add_field(
            name="Membre #",
            value=str(member.guild.member_count),
            inline=True
        )

        try:
            await channel.send(embed=embed)
        except discord.errors.Forbidden:
            logger.warning(f"Cannot send welcome message to {channel.name}")

    async def _send_welcome_dm(self, member: discord.Member, config: dict):
        """Send welcome DM to new member."""
        dm_text = config.get(
            "welcome_dm_text",
            """Bienvenue sur le serveur ! 🎉

**Guide de démarrage:**
1. 📋 Consultez les règles du serveur
2. 🎭 Choisissez vos rôles
3. 👋 Présentez-vous dans le salon approprié
4. 🔍 Explorez les différents salons

N'hésitez pas à poser des questions !"""
        )

        embed = discord.Embed(
            title=f"Bienvenue sur {member.guild.name} !",
            description=dm_text,
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(
            url=member.guild.icon.url if member.guild.icon else None
        )

        try:
            await member.send(embed=embed)
        except discord.errors.Forbidden:
            logger.debug(f"Cannot send DM to {member} (DMs disabled)")

    async def _assign_temp_role(self, member: discord.Member, config: dict):
        """Assign temporary role to new member."""
        role_id = config.get("new_member_role_id")
        if not role_id:
            return

        role = member.guild.get_role(int(role_id))
        if not role:
            return

        try:
            await member.add_roles(role, reason="New member onboarding")

            # Record in database for scheduled removal
            duration_days = config.get("new_member_role_duration_days", 7)
            expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO temp_member_roles
                    (guild_id, user_id, role_id, assigned_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(member.guild.id),
                        str(member.id),
                        str(role_id),
                        datetime.now(timezone.utc).isoformat(),
                        expires_at.isoformat()
                    )
                )
                conn.commit()
            finally:
                conn.close()

            logger.info(
                f"Assigned temp role {role.name} to {member} for {duration_days} days"
            )
        except discord.errors.Forbidden:
            logger.warning(f"Cannot assign temp role to {member}")

    async def _notify_ambassador(self, member: discord.Member, config: dict):
        """Notify a random ambassador about new member."""
        ambassador_role_id = config.get("ambassador_role_id")
        if not ambassador_role_id:
            return

        role = member.guild.get_role(int(ambassador_role_id))
        if not role or not role.members:
            return

        # Select random ambassador
        ambassador = random.choice(role.members)

        embed = discord.Embed(
            title="👋 Nouveau Membre à Accueillir !",
            description=(
                f"Un nouveau membre vient de rejoindre **{member.guild.name}** !\n\n"
                f"**Membre:** {member.mention} ({member.name})\n\n"
                f"En tant qu'Ambassadeur, n'hésitez pas à lui souhaiter la bienvenue !"
            ),
            color=discord.Color.blue()
        )
        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )

        try:
            await ambassador.send(embed=embed)
            logger.info(f"Notified ambassador {ambassador} about new member {member}")
        except discord.errors.Forbidden:
            logger.debug(f"Cannot send DM to ambassador {ambassador}")

    async def _track_member_join(self, guild: discord.Guild):
        """Track member join for analytics."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            cursor.execute(
                """
                INSERT INTO member_growth (guild_id, date, member_count, joins_today)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(guild_id, date) DO UPDATE SET
                    member_count = excluded.member_count,
                    joins_today = member_growth.joins_today + 1
                """,
                (str(guild.id), today, guild.member_count)
            )
            conn.commit()
        finally:
            conn.close()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Track member leave for analytics."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            cursor.execute(
                """
                INSERT INTO member_growth (guild_id, date, member_count, leaves_today)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(guild_id, date) DO UPDATE SET
                    member_count = excluded.member_count,
                    leaves_today = member_growth.leaves_today + 1
                """,
                (str(member.guild.id), today, member.guild.member_count)
            )
            conn.commit()
        finally:
            conn.close()

    # --- PRIORITY 3: WEEKLY CHALLENGES ---

    @tasks.loop(time=datetime.strptime("09:00", "%H:%M").time())
    async def weekly_challenge_task(self):
        """Post weekly challenge every Monday at 9h."""
        # Check if today is Monday
        if datetime.now(timezone.utc).weekday() != 0:
            return

        # Get all guilds with challenges configured
        for guild in self.bot.guilds:
            await self._post_weekly_challenge(guild)

    async def _post_weekly_challenge(self, guild: discord.Guild):
        """Post a random weekly challenge."""
        guild_id = str(guild.id)
        config = self.get_engagement_config(guild_id)

        # Get announcements channel
        channel = None
        if config.get("announcements_channel_id"):
            channel = guild.get_channel(int(config["announcements_channel_id"]))
        if not channel:
            channel = guild.system_channel

        if not channel:
            return

        # Get random active challenge
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM weekly_challenges
                WHERE guild_id = ? AND is_active = 1
                ORDER BY RANDOM() LIMIT 1
                """,
                (guild_id,)
            )
            challenge = cursor.fetchone()

            if not challenge:
                # Create default challenges if none exist
                await self._create_default_challenges(guild_id)
                cursor.execute(
                    """
                    SELECT * FROM weekly_challenges
                    WHERE guild_id = ? AND is_active = 1
                    ORDER BY RANDOM() LIMIT 1
                    """,
                    (guild_id,)
                )
                challenge = cursor.fetchone()

            if not challenge:
                return

            challenge = dict(challenge)

            # Create embed
            embed = discord.Embed(
                title="🎯 Challenge de la Semaine !",
                description=f"**{challenge['name']}**\n\n{challenge['description']}",
                color=discord.Color.purple()
            )
            embed.add_field(
                name="🏆 Récompense",
                value=f"{challenge['reward_xp']} XP",
                inline=True
            )
            if challenge.get("reward_role_id"):
                role = guild.get_role(int(challenge["reward_role_id"]))
                if role:
                    embed.add_field(
                        name="🎭 Rôle",
                        value=role.mention,
                        inline=True
                    )
            embed.set_footer(
                text="Bonne chance à tous ! Participez pour gagner des récompenses."
            )

            try:
                message = await channel.send(embed=embed)

                # Record in history
                cursor.execute(
                    """
                    INSERT INTO challenge_history
                    (guild_id, challenge_id, started_at, message_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        challenge["id"],
                        datetime.now(timezone.utc).isoformat(),
                        str(message.id)
                    )
                )
                conn.commit()

                logger.info(f"Posted weekly challenge '{challenge['name']}' in {guild}")
            except discord.errors.Forbidden:
                logger.warning(f"Cannot post challenge in {channel.name}")
        finally:
            conn.close()

    async def _create_default_challenges(self, guild_id: str):
        """Create default challenges for a guild."""
        default_challenges = [
            {
                "name": "📸 Meme Week",
                "description": (
                    "Créez et partagez vos meilleurs mèmes dans le salon approprié. "
                    "Le mème le plus drôle (plus de réactions) gagne !"
                ),
                "reward_xp": 100,
            },
            {
                "name": "💻 Setup Showcase",
                "description": (
                    "Montrez votre setup gaming/travail ! "
                    "Partagez une photo de votre bureau et inspirez la communauté."
                ),
                "reward_xp": 150,
            },
            {
                "name": "🎨 Art Challenge",
                "description": (
                    "Créez une œuvre artistique liée à notre communauté. "
                    "Dessin, digital art, musique... Tout est permis !"
                ),
                "reward_xp": 200,
            },
            {
                "name": "💬 Entraide Communautaire",
                "description": (
                    "Aidez au moins 3 membres cette semaine. "
                    "Répondez aux questions, donnez des conseils !"
                ),
                "reward_xp": 100,
            },
            {
                "name": "🎮 Gaming Night",
                "description": (
                    "Participez à au moins 2 sessions de jeu avec d'autres membres. "
                    "Jouez ensemble et amusez-vous !"
                ),
                "reward_xp": 120,
            },
        ]

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            for challenge in default_challenges:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO weekly_challenges
                    (guild_id, name, description, reward_xp, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (
                        guild_id,
                        challenge["name"],
                        challenge["description"],
                        challenge["reward_xp"],
                        datetime.now(timezone.utc).isoformat()
                    )
                )
            conn.commit()
        finally:
            conn.close()

    # --- PRIORITY 4: EVENT REMINDERS ---

    @tasks.loop(hours=1)
    async def check_event_reminders(self):
        """Check for upcoming events and send reminders."""
        for guild in self.bot.guilds:
            await self._check_guild_events(guild)

    async def _check_guild_events(self, guild: discord.Guild):
        """Check events for a specific guild."""
        config = self.get_engagement_config(str(guild.id))

        # Get announcements channel
        channel = None
        if config.get("announcements_channel_id"):
            channel = guild.get_channel(int(config["announcements_channel_id"]))
        if not channel:
            channel = guild.system_channel

        if not channel:
            return

        try:
            events = await guild.fetch_scheduled_events()
        except Exception as e:
            logger.error(f"Error fetching events for {guild}: {e}")
            return

        now = datetime.now(timezone.utc)

        for event in events:
            if event.status != discord.EventStatus.scheduled:
                continue

            time_until = event.start_time - now
            hours_until = time_until.total_seconds() / 3600

            # 24h reminder
            if 23 <= hours_until <= 25:
                await self._send_event_reminder(
                    guild, event, channel, "24h"
                )

            # 1h reminder
            if 0.5 <= hours_until <= 1.5:
                await self._send_event_reminder(
                    guild, event, channel, "1h"
                )

    async def _send_event_reminder(
        self,
        guild: discord.Guild,
        event: discord.ScheduledEvent,
        channel: discord.TextChannel,
        reminder_type: str
    ):
        """Send event reminder if not already sent."""
        guild_id = str(guild.id)
        event_id = str(event.id)

        # Check if already sent
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM event_reminders_sent
                WHERE guild_id = ? AND event_id = ? AND reminder_type = ?
                """,
                (guild_id, event_id, reminder_type)
            )
            if cursor.fetchone():
                return  # Already sent

            # Create embed
            if reminder_type == "24h":
                title = "📅 Événement dans 24h !"
                description = (
                    f"**{event.name}**\n\n"
                    f"{event.description or 'Pas de description'}\n\n"
                    "Réagissez avec ✅ si vous comptez participer !"
                )
            else:
                title = "⏰ Événement dans 1h !"
                description = (
                    f"**{event.name}**\n\n"
                    f"L'événement commence bientôt !"
                )

            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📍 Lieu",
                value=event.location or (
                    event.channel.mention if event.channel else "Non spécifié"
                ),
                inline=True
            )
            embed.add_field(
                name="🕐 Date",
                value=f"<t:{int(event.start_time.timestamp())}:F>",
                inline=True
            )

            if event.cover_image:
                embed.set_image(url=event.cover_image.url)

            try:
                message = await channel.send(embed=embed)

                if reminder_type == "24h":
                    await message.add_reaction("✅")

                # Record reminder sent
                cursor.execute(
                    """
                    INSERT INTO event_reminders_sent
                    (guild_id, event_id, reminder_type, sent_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (guild_id, event_id, reminder_type, datetime.now(timezone.utc).isoformat())
                )
                conn.commit()

                logger.info(f"Sent {reminder_type} reminder for event {event.name}")
            except discord.errors.Forbidden:
                logger.warning(f"Cannot send event reminder in {channel.name}")
        finally:
            conn.close()

    # --- SCHEDULED TASKS ---

    @tasks.loop(hours=1)
    async def check_temp_roles(self):
        """Check and remove expired temporary roles."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                SELECT * FROM temp_member_roles WHERE expires_at <= ?
                """,
                (now,)
            )
            expired_roles = cursor.fetchall()

            for entry in expired_roles:
                entry = dict(entry)
                guild = self.bot.get_guild(int(entry["guild_id"]))
                if not guild:
                    continue

                member = guild.get_member(int(entry["user_id"]))
                if not member:
                    # Member left, just remove from database
                    cursor.execute(
                        "DELETE FROM temp_member_roles WHERE id = ?",
                        (entry["id"],)
                    )
                    conn.commit()
                    continue

                role = guild.get_role(int(entry["role_id"]))
                if role and role in member.roles:
                    try:
                        await member.remove_roles(
                            role, reason="Temporary role expired"
                        )
                        logger.info(
                            f"Removed expired temp role {role.name} from {member}"
                        )
                    except discord.errors.Forbidden:
                        logger.warning(
                            f"Cannot remove temp role from {member}"
                        )

                # Remove from database
                cursor.execute(
                    "DELETE FROM temp_member_roles WHERE id = ?",
                    (entry["id"],)
                )
                conn.commit()
        finally:
            conn.close()

    # Wait for bot to be ready before starting tasks
    @check_temp_roles.before_loop
    async def before_check_temp_roles(self):
        await self.bot.wait_until_ready()

    @check_event_reminders.before_loop
    async def before_check_event_reminders(self):
        await self.bot.wait_until_ready()

    @weekly_challenge_task.before_loop
    async def before_weekly_challenge_task(self):
        await self.bot.wait_until_ready()

    # --- COMMANDS ---

    @app_commands.command(
        name="xp_thresholds",
        description="Configure les paliers XP et les rôles associés"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.describe(
        action="Action à effectuer",
        points="Nombre de points pour le palier",
        role="Rôle à assigner"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Ajouter", value="add"),
        app_commands.Choice(name="Supprimer", value="remove"),
        app_commands.Choice(name="Liste", value="list"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def xp_thresholds(
        self,
        interaction: discord.Interaction,
        action: str,
        points: int = None,
        role: discord.Role = None
    ):
        """Configure XP thresholds and associated roles."""
        guild_id = str(interaction.guild.id)

        if action == "list":
            thresholds = self.get_xp_thresholds(guild_id)
            if not thresholds:
                await interaction.response.send_message(
                    "Aucun palier XP configuré. Utilisez `/xp_thresholds add` pour en créer.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🎯 Paliers XP",
                color=discord.Color.blue()
            )
            for t in thresholds:
                role = interaction.guild.get_role(int(t["role_id"]))
                role_name = role.mention if role else f"Rôle {t['role_id']}"
                embed.add_field(
                    name=f"{t['threshold_points']} points",
                    value=role_name,
                    inline=True
                )
            await interaction.response.send_message(embed=embed)

        elif action == "add":
            if not points or not role:
                await interaction.response.send_message(
                    "Veuillez spécifier les points et le rôle.",
                    ephemeral=True
                )
                return

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO xp_thresholds
                    (guild_id, threshold_points, role_id, role_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        points,
                        str(role.id),
                        role.name,
                        datetime.now(timezone.utc).isoformat()
                    )
                )
                conn.commit()
            finally:
                conn.close()

            await interaction.response.send_message(
                f"✅ Palier ajouté : {points} points → {role.mention}",
                ephemeral=True
            )

        elif action == "remove":
            if not points:
                await interaction.response.send_message(
                    "Veuillez spécifier les points du palier à supprimer.",
                    ephemeral=True
                )
                return

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM xp_thresholds
                    WHERE guild_id = ? AND threshold_points = ?
                    """,
                    (guild_id, points)
                )
                conn.commit()
            finally:
                conn.close()

            await interaction.response.send_message(
                f"✅ Palier {points} points supprimé.",
                ephemeral=True
            )

    @app_commands.command(
        name="challenge",
        description="Gère les challenges hebdomadaires"
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.describe(
        action="Action à effectuer",
        name="Nom du challenge",
        description="Description du challenge",
        reward_xp="Récompense en XP"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Ajouter", value="add"),
        app_commands.Choice(name="Liste", value="list"),
        app_commands.Choice(name="Lancer maintenant", value="launch"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def challenge(
        self,
        interaction: discord.Interaction,
        action: str,
        name: str = None,
        description: str = None,
        reward_xp: int = 100
    ):
        """Manage weekly challenges."""
        guild_id = str(interaction.guild.id)

        if action == "list":
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM weekly_challenges
                    WHERE guild_id = ? AND is_active = 1
                    """,
                    (guild_id,)
                )
                challenges = [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

            if not challenges:
                await interaction.response.send_message(
                    "Aucun challenge actif. Des challenges par défaut seront créés.",
                    ephemeral=True
                )
                await self._create_default_challenges(guild_id)
                return

            embed = discord.Embed(
                title="🎯 Challenges Hebdomadaires",
                color=discord.Color.purple()
            )
            for c in challenges:
                embed.add_field(
                    name=c["name"],
                    value=f"{c['description'][:100]}...\n**Récompense:** {c['reward_xp']} XP",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action == "add":
            if not name or not description:
                await interaction.response.send_message(
                    "Veuillez spécifier le nom et la description.",
                    ephemeral=True
                )
                return

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO weekly_challenges
                    (guild_id, name, description, reward_xp, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (
                        guild_id,
                        name,
                        description,
                        reward_xp,
                        datetime.now(timezone.utc).isoformat()
                    )
                )
                conn.commit()
            finally:
                conn.close()

            await interaction.response.send_message(
                f"✅ Challenge '{name}' ajouté avec {reward_xp} XP de récompense.",
                ephemeral=True
            )

        elif action == "launch":
            await interaction.response.defer(ephemeral=True)
            await self._post_weekly_challenge(interaction.guild)
            await interaction.followup.send(
                "✅ Challenge hebdomadaire lancé !",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(EngagementSystem(bot))
