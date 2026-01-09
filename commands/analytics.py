"""
Analytics Command for ISROBOT V2.

Handles Priority 5: Analytics Command (!stats)
- Owner-only command
- Top active members
- Event participation rate
- Member growth
- Most active channels
"""

import os
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import get_db_connection
from utils.logging_config import get_logger

# Load environment variables
load_dotenv()

SERVER_ID = int(os.getenv("server_id", "0"))
logger = get_logger(__name__)


class Analytics(commands.Cog):
    """Cog for analytics commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="stats")
    @commands.is_owner()
    async def stats_command(self, ctx: commands.Context, period: str = "7d"):
        """
        Generate analytics report (Owner only).

        Usage: !stats <period>
        Period options: 7d (7 days), 30d (30 days), all
        """
        await ctx.message.add_reaction("⏳")

        try:
            # Parse period
            if period == "7d":
                days = 7
                period_name = "7 derniers jours"
            elif period == "30d":
                days = 30
                period_name = "30 derniers jours"
            elif period == "all":
                days = 365 * 10  # Effectively all time
                period_name = "Tout le temps"
            else:
                await ctx.send(
                    "❌ Période invalide. Utilisez: `7d`, `30d`, ou `all`"
                )
                return

            guild = ctx.guild
            if not guild:
                await ctx.send("❌ Cette commande doit être utilisée dans un serveur.")
                return

            guild_id = str(guild.id)
            start_date = (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).strftime("%Y-%m-%d")

            # Generate report
            report_embed = await self._generate_report(guild, guild_id, start_date, period_name)

            # Send to DM
            try:
                await ctx.author.send(embed=report_embed)
                await ctx.message.remove_reaction("⏳", self.bot.user)
                await ctx.message.add_reaction("✅")
                await ctx.send("📊 Rapport envoyé en DM !", delete_after=5)
            except discord.errors.Forbidden:
                # Can't DM, send in channel
                await ctx.send(embed=report_embed)
                await ctx.message.remove_reaction("⏳", self.bot.user)
                await ctx.message.add_reaction("✅")

        except Exception as e:
            logger.error(f"Error generating analytics: {e}")
            await ctx.message.remove_reaction("⏳", self.bot.user)
            await ctx.message.add_reaction("❌")
            await ctx.send(f"❌ Erreur lors de la génération du rapport: {e}")

    async def _generate_report(
        self, guild: discord.Guild, guild_id: str, start_date: str, period_name: str
    ) -> discord.Embed:
        """Generate analytics report embed."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Top active members (by XP)
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
            top_members = cursor.fetchall()

            # 2. Member growth statistics
            cursor.execute(
                """
                SELECT
                    SUM(joins_today) as total_joins,
                    SUM(leaves_today) as total_leaves,
                    MAX(member_count) as peak_members,
                    MIN(member_count) as min_members
                FROM member_growth
                WHERE guild_id = ? AND date >= ?
                """,
                (guild_id, start_date)
            )
            growth_stats = cursor.fetchone()

            # 3. Most active channels
            cursor.execute(
                """
                SELECT channel_id, SUM(message_count) as total_messages
                FROM channel_stats
                WHERE guild_id = ? AND date >= ?
                GROUP BY channel_id
                ORDER BY total_messages DESC
                LIMIT 5
                """,
                (guild_id, start_date)
            )
            active_channels = cursor.fetchall()

            # 4. Total messages
            cursor.execute(
                """
                SELECT SUM(messages) as total_messages
                FROM users
                WHERE guildId = ?
                """,
                (guild_id,)
            )
            total_messages_result = cursor.fetchone()
            total_messages = total_messages_result[0] if total_messages_result else 0

            # 5. Event participation (reminders sent)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT event_id) as events_reminded
                FROM event_reminders_sent
                WHERE guild_id = ? AND sent_at >= ?
                """,
                (guild_id, start_date)
            )
            events_result = cursor.fetchone()
            events_reminded = events_result[0] if events_result else 0

        finally:
            conn.close()

        # Build embed
        embed = discord.Embed(
            title=f"📊 Rapport Analytics - {guild.name}",
            description=f"**Période:** {period_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Server overview
        online_count = sum(
            1 for m in guild.members if m.status != discord.Status.offline
        )
        embed.add_field(
            name="👥 Vue d'ensemble",
            value=(
                f"**Membres actuels:** {guild.member_count}\n"
                f"**En ligne:** {online_count}\n"
                f"**Bots:** {sum(1 for m in guild.members if m.bot)}"
            ),
            inline=True
        )

        # Growth stats
        if growth_stats and growth_stats["total_joins"]:
            total_joins = growth_stats["total_joins"] or 0
            total_leaves = growth_stats["total_leaves"] or 0
            net_growth = total_joins - total_leaves
            if net_growth > 0:
                growth_emoji = "📈"
            elif net_growth < 0:
                growth_emoji = "📉"
            else:
                growth_emoji = "➡️"
            embed.add_field(
                name="📊 Croissance",
                value=(
                    f"**Nouveaux:** {growth_stats['total_joins'] or 0}\n"
                    f"**Départs:** {growth_stats['total_leaves'] or 0}\n"
                    f"**Net:** {growth_emoji} {net_growth:+d}"
                ),
                inline=True
            )
        else:
            embed.add_field(
                name="📊 Croissance",
                value="Pas de données disponibles",
                inline=True
            )

        # Messages stats
        embed.add_field(
            name="💬 Messages",
            value=(
                f"**Total:** {total_messages or 0:,}\n"
                f"**Événements rappelés:** {events_reminded}"
            ),
            inline=True
        )

        # Top members
        if top_members:
            top_text = ""
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i, member in enumerate(top_members[:5]):
                user = guild.get_member(int(member["userId"]))
                name = user.display_name if user else f"User {member['userId']}"
                xp_val = int(member['xp'])
                lvl = member['level']
                msgs = member['messages']
                top_text += (
                    f"{medals[i]} **{name}**\n"
                    f"   {xp_val:,} XP | Nv.{lvl} | {msgs} msgs\n"
                )
            embed.add_field(
                name="🏆 Top Membres Actifs",
                value=top_text or "Aucun membre",
                inline=False
            )

        # Active channels
        if active_channels:
            channels_text = ""
            for i, ch in enumerate(active_channels):
                channel = guild.get_channel(int(ch["channel_id"]))
                channel_name = channel.mention if channel else f"#{ch['channel_id']}"
                channels_text += f"**{i+1}.** {channel_name} - {ch['total_messages']:,} msgs\n"
            embed.add_field(
                name="📢 Canaux les Plus Actifs",
                value=channels_text or "Aucune donnée",
                inline=False
            )

        embed.set_footer(
            text=f"Généré par ISROBOT • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )

        return embed

    @stats_command.error
    async def stats_error(self, ctx: commands.Context, error):
        """Handle errors for stats command."""
        if isinstance(error, commands.NotOwner):
            await ctx.send(
                "❌ Cette commande est réservée au propriétaire du bot.",
                delete_after=5
            )
        else:
            logger.error(f"Stats command error: {error}")
            await ctx.send(f"❌ Erreur: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Analytics(bot))
