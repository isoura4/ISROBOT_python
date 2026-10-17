"""
Minigame system command handler.

This module provides Discord bot commands for:
- Channel configuration (admin)
- Daily quests
- Quest management
- Shop system
- Trading system
- Wallet and history
- Capture and duel games
"""

import logging
import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from db_helpers import (
    add_quest_exception_channel,
    get_guild_settings,
    get_quest_exception_channels,
    get_user_balance,
    get_user_transactions,
    is_minigame_enabled,
    is_quest_exception_channel,
    remove_quest_exception_channel,
    set_minigame_channel,
    set_minigame_enabled,
)
from minigame_engine import (
    arena_duel,
    capture_attempt,
    get_capture_stats,
    get_duel_stats,
)
from quests import (
    assign_daily_quests,
    claim_all_completed_quests,
    claim_quest,
    get_daily_status,
    get_streak_multiplier,
    get_user_active_quests,
    increment_quest_progress,
    update_streak,
)
from shop import (
    buy_item,
    get_shop_items,
    get_user_inventory,
    has_active_effect,
    use_item,
)
from trades import (
    accept_trade,
    cancel_trade,
    check_and_complete_ready_trades,
    create_trade_offer,
    get_pending_trades_for_user,
)
from utils.i18n import get_locale, t, tr
from utils.time_utils import utcnow

# Load environment variables
load_dotenv()
SERVER_ID = int(os.getenv("server_id", "0"))

# Global minigame toggle from .env (default: enabled)
MINIGAME_GLOBALLY_ENABLED = os.getenv("minigame_enabled", "true").lower() != "false"

# Set up logging
logger = logging.getLogger(__name__)


async def check_minigame_channel(
    interaction: discord.Interaction,
    allow_exceptions: bool = False,
) -> bool:
    """
    Check if the command is being run in the minigame channel.

    Returns True if allowed, False if not (sends error message).
    """
    locale = get_locale(interaction)

    # Check global toggle from .env
    if not MINIGAME_GLOBALLY_ENABLED:
        await interaction.response.send_message(
            t("minigame.disabled_global", locale),
            ephemeral=True,
        )
        return False

    if not interaction.guild:
        await interaction.response.send_message(
            t("minigame.common.guild_only", locale),
            ephemeral=True,
        )
        return False

    guild_id = str(interaction.guild.id)
    channel_id = str(interaction.channel_id)

    # Check if minigame is enabled for this guild
    if not is_minigame_enabled(guild_id):
        await interaction.response.send_message(
            t("minigame.disabled_guild", locale),
            ephemeral=True,
        )
        return False

    settings = get_guild_settings(guild_id)
    minigame_channel_id = settings.get("minigame_channel_id")

    # If no channel is set, only admins can proceed
    if not minigame_channel_id:
        await interaction.response.send_message(
            t("minigame.no_channel_set", locale),
            ephemeral=True,
        )
        return False

    # Check if in minigame channel
    if channel_id == minigame_channel_id:
        return True

    # Check exception channels if allowed
    if allow_exceptions and is_quest_exception_channel(guild_id, channel_id):
        return True

    # Not allowed - send error with channel mention
    channel_mention = f"<#{minigame_channel_id}>"
    await interaction.response.send_message(
        t("minigame.channel_restriction", locale, channel_mention=channel_mention),
        ephemeral=True,
    )
    return False


def _build_xp_warning_embed(
    warning: dict, locale: Optional[str] = None
) -> discord.Embed:
    """Construit l'embed d'avertissement de perte de niveau lors d'un transfert d'XP."""
    embed = discord.Embed(
        title=t("minigame.xp_warning.title", locale),
        description=t(
            "minigame.xp_warning.description",
            locale,
            current_xp=warning["current_xp"],
            xp_to_transfer=warning["xp_to_transfer"],
            remaining_xp=warning["remaining_xp"],
            current_level=warning["current_level"],
            new_level=warning["new_level"],
            levels_lost=warning["levels_lost"],
        ),
        color=discord.Color.orange(),
    )
    embed.set_footer(text=t("minigame.xp_warning.footer", locale))
    return embed


class MinigameCommands(commands.Cog):
    """Main minigame command cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.trade_checker.start()
        # Pending XP trade confirmations:
        # {(guild_id, user_id): (to_user_id, coins, xp, timestamp)}
        self._pending_xp_confirmations: dict = {}

    def cog_unload(self):
        self.trade_checker.cancel()

    @tasks.loop(minutes=1)
    async def trade_checker(self):
        """Background task to complete ready trades."""
        try:
            completed = check_and_complete_ready_trades()
            if completed:
                logger.info(f"Auto-completed {len(completed)} trade(s)")
        except Exception as e:
            logger.error(f"Trade checker error: {e}")

    @trade_checker.before_loop
    async def before_trade_checker(self):
        await self.bot.wait_until_ready()

    # ==================== Admin Commands ====================

    minigame_group = app_commands.Group(
        name="minigame",
        description=tr("cmd.minigame.desc"),
    )

    @minigame_group.command(
        name="enable",
        description=tr("cmd.minigame.enable.desc"),
    )
    @app_commands.default_permissions(administrator=True)
    async def enable_minigame(self, interaction: discord.Interaction):
        """Enable the minigame system for this guild."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        # Check global toggle
        if not MINIGAME_GLOBALLY_ENABLED:
            await interaction.response.send_message(
                t("minigame.disabled_global", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        set_minigame_enabled(guild_id, True)

        embed = discord.Embed(
            title=t("minigame.enable.title", locale),
            description=t("minigame.enable.description", locale),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @minigame_group.command(
        name="disable",
        description=tr("cmd.minigame.disable.desc"),
    )
    @app_commands.default_permissions(administrator=True)
    async def disable_minigame(self, interaction: discord.Interaction):
        """Disable the minigame system for this guild."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        set_minigame_enabled(guild_id, False)

        embed = discord.Embed(
            title=t("minigame.disable.title", locale),
            description=t("minigame.disable.description", locale),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @minigame_group.command(
        name="set-channel",
        description=tr("cmd.minigame.set_channel.desc"),
    )
    @app_commands.describe(channel=tr("cmd.minigame.set_channel.param"))
    @app_commands.default_permissions(administrator=True)
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        """Set the minigame channel."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        set_minigame_channel(guild_id, str(channel.id))

        embed = discord.Embed(
            title=t("minigame.set_channel.title", locale),
            description=t(
                "minigame.set_channel.description",
                locale,
                channel_mention=channel.mention,
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @minigame_group.command(
        name="clear-channel",
        description=tr("cmd.minigame.clear_channel.desc"),
    )
    @app_commands.default_permissions(administrator=True)
    async def clear_channel(self, interaction: discord.Interaction):
        """Clear the minigame channel setting."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        set_minigame_channel(guild_id, None)

        embed = discord.Embed(
            title=t("minigame.clear_channel.title", locale),
            description=t("minigame.clear_channel.description", locale),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @minigame_group.command(
        name="allow-channel",
        description=tr("cmd.minigame.allow_channel.desc"),
    )
    @app_commands.describe(channel=tr("cmd.minigame.allow_channel.param"))
    @app_commands.default_permissions(administrator=True)
    async def allow_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        """Add a quest exception channel."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        added = add_quest_exception_channel(guild_id, str(channel.id))

        if added:
            embed = discord.Embed(
                title=t("minigame.allow_channel.added_title", locale),
                description=t(
                    "minigame.allow_channel.added_description",
                    locale,
                    channel_mention=channel.mention,
                ),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title=t("minigame.allow_channel.exists_title", locale),
                description=t(
                    "minigame.allow_channel.exists_description",
                    locale,
                    channel_mention=channel.mention,
                ),
                color=discord.Color.blue(),
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @minigame_group.command(
        name="remove-channel",
        description=tr("cmd.minigame.remove_channel.desc"),
    )
    @app_commands.describe(channel=tr("cmd.minigame.remove_channel.param"))
    @app_commands.default_permissions(administrator=True)
    async def remove_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        """Remove a quest exception channel."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        removed = remove_quest_exception_channel(guild_id, str(channel.id))

        if removed:
            embed = discord.Embed(
                title=t("minigame.remove_channel.removed_title", locale),
                description=t(
                    "minigame.remove_channel.removed_description",
                    locale,
                    channel_mention=channel.mention,
                ),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title=t("minigame.remove_channel.not_found_title", locale),
                description=t(
                    "minigame.remove_channel.not_found_description",
                    locale,
                    channel_mention=channel.mention,
                ),
                color=discord.Color.blue(),
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @minigame_group.command(
        name="stats",
        description=tr("cmd.minigame.stats.desc"),
    )
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction):
        """View minigame statistics."""
        locale = get_locale(interaction)
        if not interaction.guild:
            await interaction.response.send_message(
                t("minigame.common.guild_only", locale),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        settings = get_guild_settings(guild_id)
        exception_channels = get_quest_exception_channels(guild_id)

        embed = discord.Embed(
            title=t("minigame.config.title", locale),
            color=discord.Color.blue(),
        )

        # System status
        minigame_enabled = settings.get("minigame_enabled", 1)
        if not MINIGAME_GLOBALLY_ENABLED:
            system_status = t("minigame.config.disabled_global", locale)
        elif not minigame_enabled:
            system_status = t("minigame.config.disabled_guild", locale)
        else:
            system_status = t("minigame.config.enabled", locale)
        embed.add_field(
            name=t("minigame.config.system_status", locale),
            value=system_status,
            inline=True,
        )

        # Channel settings
        mg_channel = settings.get("minigame_channel_id")
        if mg_channel:
            channel_value = f"<#{mg_channel}>"
        else:
            channel_value = t("minigame.config.channel_not_set", locale)
        embed.add_field(
            name=t("minigame.config.channel", locale),
            value=channel_value,
            inline=True,
        )

        embed.add_field(
            name=t("minigame.config.exception_channels", locale),
            value=str(len(exception_channels)),
            inline=True,
        )

        # Economy settings
        if settings.get("xp_trading_enabled"):
            xp_trading_value = t("minigame.config.enabled", locale)
        else:
            xp_trading_value = t("minigame.config.disabled", locale)
        embed.add_field(
            name=t("minigame.config.xp_trading", locale),
            value=xp_trading_value,
            inline=True,
        )

        embed.add_field(
            name=t("minigame.config.trade_tax", locale),
            value=f"{settings.get('trade_tax_percent', 10)}%",
            inline=True,
        )

        embed.add_field(
            name=t("minigame.config.duel_tax", locale),
            value=f"{settings.get('duel_tax_percent', 10)}%",
            inline=True,
        )

        embed.add_field(
            name=t("minigame.config.daily_xp_cap", locale),
            value=t(
                "minigame.config.daily_xp_cap_value",
                locale,
                percent=settings.get("daily_xp_transfer_cap_percent", 10),
                limit=settings.get("daily_xp_transfer_cap_max", 500),
            ),
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Daily Commands ====================

    daily_group = app_commands.Group(
        name="daily",
        description=tr("cmd.daily.desc"),
    )

    @daily_group.command(
        name="claim",
        description=tr("cmd.daily.claim.desc"),
    )
    async def daily_claim(self, interaction: discord.Interaction):
        """Claim daily quests."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # Get or assign daily quests
        status = get_daily_status(guild_id, user_id)

        if not status["can_claim_new"] and status["quests"]:
            embed = discord.Embed(
                title=t("minigame.daily.quests_title", locale),
                description=t("minigame.daily.already", locale),
                color=discord.Color.orange(),
            )
            for quest in status["quests"]:
                if quest["completed"]:
                    status_icon = "✅"
                else:
                    status_icon = "🔄"
                progress_line = t(
                    "minigame.quest.progress",
                    locale,
                    progress=quest["progress"],
                    target=quest["target_value"],
                )
                rewards_line = t(
                    "minigame.quest.rewards",
                    locale,
                    coins=quest["reward_coins"],
                    xp=quest["reward_xp"],
                )
                embed.add_field(
                    name=f"{status_icon} {quest['name']}",
                    value=f"{quest['description']}\n{progress_line}\n{rewards_line}",
                    inline=False,
                )
            embed.set_footer(
                text=t("minigame.common.streak", locale, streak=status["streak"])
            )
            await interaction.response.send_message(embed=embed)
            return

        # Assign new daily quests
        quests = assign_daily_quests(guild_id, user_id)

        if not quests:
            embed = discord.Embed(
                title=t("minigame.daily.none_title", locale),
                description=t("minigame.daily.none_description", locale),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)
            return

        # Update streak
        new_streak = update_streak(guild_id, user_id)
        multiplier = get_streak_multiplier(new_streak)

        embed = discord.Embed(
            title=t("minigame.daily.assigned_title", locale),
            description=t("minigame.daily.assigned_description", locale),
            color=discord.Color.green(),
        )

        for quest in quests:
            rewards_line = t(
                "minigame.quest.rewards",
                locale,
                coins=quest["reward_coins"],
                xp=quest["reward_xp"],
            )
            embed.add_field(
                name=f"🔄 {quest['name']}",
                value=f"{quest['description']}\n{rewards_line}",
                inline=False,
            )

        embed.set_footer(
            text=t(
                "minigame.common.streak_multiplier",
                locale,
                streak=new_streak,
                multiplier=multiplier,
            )
        )
        await interaction.response.send_message(embed=embed)

    @daily_group.command(
        name="status",
        description=tr("cmd.daily.status.desc"),
    )
    async def daily_status(self, interaction: discord.Interaction):
        """View daily quest status."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        status = get_daily_status(guild_id, user_id)

        if not status["quests"]:
            embed = discord.Embed(
                title=t("minigame.daily.status_empty_title", locale),
                description=t("minigame.daily.status_empty_description", locale),
                color=discord.Color.blue(),
            )
            embed.set_footer(
                text=t("minigame.common.streak", locale, streak=status["streak"])
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=t("minigame.daily.status_title", locale),
            description=t(
                "minigame.daily.status_description",
                locale,
                completed=status["completed"],
                total=status["total"],
            ),
            color=(
                discord.Color.green()
                if status["all_completed"]
                else discord.Color.blue()
            ),
        )

        for quest in status["quests"]:
            if quest["completed"]:
                status_icon = "✅"
                status_text = t("minigame.daily.completed", locale)
            else:
                status_icon = "🔄"
                progress_pct = (quest["progress"] / quest["target_value"]) * 100
                status_text = t(
                    "minigame.daily.progress_value",
                    locale,
                    progress=quest["progress"],
                    target=quest["target_value"],
                    percent=f"{progress_pct:.0f}",
                )

            status_line = t("minigame.quest.status", locale, status=status_text)
            rewards_line = t(
                "minigame.quest.rewards",
                locale,
                coins=quest["reward_coins"],
                xp=quest["reward_xp"],
            )
            embed.add_field(
                name=f"{status_icon} {quest['name']}",
                value=f"{quest['description']}\n{status_line}\n{rewards_line}",
                inline=False,
            )

        embed.set_footer(
            text=t("minigame.common.streak", locale, streak=status["streak"])
        )
        await interaction.response.send_message(embed=embed)

    # ==================== Quest Commands ====================

    quest_group = app_commands.Group(
        name="quest",
        description=tr("cmd.quest.desc"),
    )

    @quest_group.command(
        name="list",
        description=tr("cmd.quest.list.desc"),
    )
    async def quest_list(self, interaction: discord.Interaction):
        """List active quests."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        quests = get_user_active_quests(guild_id, user_id)

        if not quests:
            embed = discord.Embed(
                title=t("minigame.quest.list_title", locale),
                description=t("minigame.quest.list_empty", locale),
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=t("minigame.quest.list_title", locale),
            color=discord.Color.green(),
        )

        for quest in quests:
            if quest["completed"]:
                status_icon = "✅"
            else:
                status_icon = "🔄"
            progress_pct = (quest["progress"] / quest["target_value"]) * 100

            field_name = t(
                "minigame.quest.field_name",
                locale,
                icon=status_icon,
                name=quest["name"],
                id=quest["id"],
            )
            progress_line = t(
                "minigame.quest.progress_pct",
                locale,
                progress=quest["progress"],
                target=quest["target_value"],
                percent=f"{progress_pct:.0f}",
            )
            rewards_line = t(
                "minigame.quest.rewards",
                locale,
                coins=quest["reward_coins"],
                xp=quest["reward_xp"],
            )

            embed.add_field(
                name=field_name,
                value=f"{quest['description']}\n{progress_line}\n{rewards_line}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @quest_group.command(
        name="claim",
        description=tr("cmd.quest.claim.desc"),
    )
    @app_commands.describe(quest_id=tr("cmd.quest.claim.param"))
    async def quest_claim_cmd(
        self,
        interaction: discord.Interaction,
        quest_id: Optional[int] = None,
    ):
        """Claim quest rewards."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            if quest_id:
                # Claim specific quest
                result = claim_quest(guild_id, user_id, quest_id)
                results = [result]
            else:
                # Claim all completed quests
                results = claim_all_completed_quests(guild_id, user_id)

            if not results:
                embed = discord.Embed(
                    title=t("minigame.quest.claim_none_title", locale),
                    description=t("minigame.quest.claim_none_description", locale),
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
                return

            embed = discord.Embed(
                title=t("minigame.quest.claim_title", locale),
                color=discord.Color.gold(),
            )

            total_coins = 0
            total_xp = 0

            for result in results:
                total_coins += result["coins_rewarded"]
                total_xp += result["xp_rewarded"]
                embed.add_field(
                    name=f"✅ {result['quest_name']}",
                    value=(
                        f"🪙 {result['coins_rewarded']} | "
                        f"⭐ {result['xp_rewarded']} XP"
                    ),
                    inline=True,
                )

            embed.add_field(
                name=t("minigame.quest.total_rewards", locale),
                value=t(
                    "minigame.quest.total_rewards_value",
                    locale,
                    coins=total_coins,
                    xp=total_xp,
                ),
                inline=False,
            )

            # Check for level up
            if any(r.get("level_up") for r in results):
                new_level = max(
                    (r["new_level"] for r in results if r.get("new_level") is not None),
                    default=0,
                )
                embed.add_field(
                    name=t("minigame.common.level_up_title", locale),
                    value=t("minigame.common.level_up_value", locale, level=new_level),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.common.error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Shop Commands ====================

    shop_group = app_commands.Group(
        name="shop",
        description=tr("cmd.shop.desc"),
    )

    @shop_group.command(
        name="list",
        description=tr("cmd.shop.list.desc"),
    )
    async def shop_list(self, interaction: discord.Interaction):
        """List shop items."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        items = get_shop_items()

        if not items:
            embed = discord.Embed(
                title=t("minigame.shop.title", locale),
                description=t("minigame.shop.empty", locale),
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=t("minigame.shop.title", locale),
            description=t("minigame.shop.usage", locale),
            color=discord.Color.green(),
        )

        for item in items:
            price_parts = []
            if item["price_coins"] > 0:
                price_parts.append(f"🪙 {item['price_coins']}")
            if item["price_xp"] > 0:
                price_parts.append(f"⭐ {item['price_xp']} XP")

            if price_parts:
                price_str = " + ".join(price_parts)
            else:
                price_str = t("minigame.shop.free", locale)
            if item["stock"] != -1:
                stock_str = " | " + t(
                    "minigame.shop.stock", locale, stock=item["stock"]
                )
            else:
                stock_str = ""

            embed.add_field(
                name=f"#{item['id']} - {item['name']}",
                value=t(
                    "minigame.shop.field_value",
                    locale,
                    description=item["description"],
                    price=price_str,
                    stock=stock_str,
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @shop_group.command(
        name="buy",
        description=tr("cmd.shop.buy.desc"),
    )
    @app_commands.describe(
        item_id=tr("cmd.shop.buy.item_id"),
        quantity=tr("cmd.shop.buy.quantity"),
    )
    async def shop_buy(
        self,
        interaction: discord.Interaction,
        item_id: int,
        quantity: int = 1,
    ):
        """Buy a shop item."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = buy_item(guild_id, user_id, item_id, quantity)

            try:
                if result["coins_spent"] > 0:
                    increment_quest_progress(
                        guild_id, user_id, "coins_spent", result["coins_spent"]
                    )
            except Exception as e:
                logger.error(f"Erreur lors de la progression de quête (shop): {e}")

            embed = discord.Embed(
                title=t("minigame.shop.buy_success_title", locale),
                description=t(
                    "minigame.shop.buy_success_description",
                    locale,
                    quantity=result["quantity"],
                    item=result["item_name"],
                ),
                color=discord.Color.green(),
            )

            cost_parts = []
            if result["coins_spent"] > 0:
                cost_parts.append(f"🪙 {result['coins_spent']}")
            if result["xp_spent"] > 0:
                cost_parts.append(f"⭐ {result['xp_spent']} XP")

            embed.add_field(
                name=t("minigame.shop.cost", locale),
                value=" + ".join(cost_parts),
                inline=True,
            )

            if result["is_consumable"]:
                embed.add_field(
                    name=t("minigame.common.inventory_field", locale),
                    value=t("minigame.shop.inventory_value", locale),
                    inline=False,
                )

            if result.get("level_down"):
                embed.add_field(
                    name=t("minigame.shop.level_changed_title", locale),
                    value=t(
                        "minigame.shop.level_changed_value",
                        locale,
                        level=result["new_level"],
                    ),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.shop.buy_error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Trade Commands ====================

    trade_group = app_commands.Group(
        name="trade",
        description=tr("cmd.trade.desc"),
    )

    @trade_group.command(
        name="offer",
        description=tr("cmd.trade.offer.desc"),
    )
    @app_commands.describe(
        user=tr("cmd.trade.offer.user"),
        coins=tr("cmd.trade.offer.coins"),
        xp=tr("cmd.trade.offer.xp"),
    )
    async def trade_offer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        coins: int = 0,
        xp: int = 0,
    ):
        """Create a trade offer."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        from_user_id = str(interaction.user.id)
        to_user_id = str(user.id)

        # Show XP warning if transferring XP
        if xp > 0:
            warning = get_xp_transfer_warning(guild_id, from_user_id, xp)

            if warning["will_level_down"]:
                confirm_key = (guild_id, from_user_id)
                now = utcnow()

                # Purge opportuniste des confirmations expirées (> 30 s)
                if len(self._pending_xp_confirmations) > 100:
                    self._pending_xp_confirmations = {
                        k: v
                        for k, v in self._pending_xp_confirmations.items()
                        if (now - v[3]).total_seconds() <= 30
                    }

                # Check if there's a pending confirmation
                pending = self._pending_xp_confirmations.get(confirm_key)
                if pending:
                    p_to_user, p_coins, p_xp, p_time = pending
                    # Check if same trade and within 30 seconds
                    time_diff = (now - p_time).total_seconds()
                    if (
                        p_to_user == to_user_id
                        and p_coins == coins
                        and p_xp == xp
                        and time_diff <= 30
                    ):
                        # Confirmation received, clear and proceed
                        del self._pending_xp_confirmations[confirm_key]
                        # Fall through to create the trade
                    else:
                        # Different trade or expired, update pending
                        self._pending_xp_confirmations[confirm_key] = (
                            to_user_id,
                            coins,
                            xp,
                            now,
                        )
                        embed = _build_xp_warning_embed(warning, locale=locale)
                        await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )
                        return
                else:
                    # First attempt, store for confirmation
                    self._pending_xp_confirmations[confirm_key] = (
                        to_user_id,
                        coins,
                        xp,
                        now,
                    )
                    embed = _build_xp_warning_embed(warning, locale=locale)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

        try:
            result = create_trade_offer(guild_id, from_user_id, to_user_id, coins, xp)

            embed = discord.Embed(
                title=t("minigame.trade.offer_title", locale),
                description=t(
                    "minigame.trade.offer_description",
                    locale,
                    mention=user.mention,
                ),
                color=discord.Color.green(),
            )

            embed.add_field(
                name=t("minigame.trade.trade_id", locale),
                value=str(result["trade_id"]),
                inline=True,
            )

            offer_parts = []
            if result["coins"] > 0:
                offer_parts.append(
                    t("minigame.trade.coins_part", locale, coins=result["coins"])
                )
            if result["xp"] > 0:
                offer_parts.append(f"⭐ {result['xp']} XP")

            embed.add_field(
                name=t("minigame.trade.offering", locale),
                value="\n".join(offer_parts),
                inline=True,
            )

            net_parts = []
            if result["net_coins"] > 0:
                net_parts.append(
                    t("minigame.trade.coins_part", locale, coins=result["net_coins"])
                )
            if result["net_xp"] > 0:
                net_parts.append(f"⭐ {result['net_xp']} XP")

            tax_str = t(
                "minigame.trade.tax_line",
                locale,
                coins=result["tax_coins"],
                xp=result["tax_xp"],
            )
            embed.add_field(
                name=t("minigame.trade.after_tax", locale),
                value="\n".join(net_parts) + tax_str,
                inline=True,
            )

            footer_text = t(
                "minigame.trade.offer_footer",
                locale,
                user=user.display_name,
                trade_id=result["trade_id"],
            )
            embed.set_footer(text=footer_text)
            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.trade.offer_error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @trade_group.command(
        name="accept",
        description=tr("cmd.trade.accept.desc"),
    )
    @app_commands.describe(trade_id=tr("cmd.trade.accept.param"))
    async def trade_accept(
        self,
        interaction: discord.Interaction,
        trade_id: int,
    ):
        """Accept a trade."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = accept_trade(guild_id, user_id, trade_id)

            embed = discord.Embed(
                title=t("minigame.trade.accepted_title", locale),
                description=t("minigame.trade.accepted_description", locale),
                color=discord.Color.green(),
            )

            embed.add_field(
                name=t("minigame.trade.trade_id", locale),
                value=str(result["trade_id"]),
                inline=True,
            )
            embed.add_field(
                name=t("minigame.trade.escrow_release", locale),
                value=t(
                    "minigame.trade.escrow_release_value",
                    locale,
                    minutes=result["minutes_until_release"],
                ),
                inline=True,
            )

            value_parts = []
            if result["coins"] > 0:
                net_coins = result["coins"] - result["tax_coins"]
                value_parts.append(
                    t("minigame.trade.coins_part", locale, coins=net_coins)
                )
            if result["xp"] > 0:
                net_xp = result["xp"] - result["tax_xp"]
                value_parts.append(f"⭐ {net_xp} XP")

            embed.add_field(
                name=t("minigame.trade.will_receive", locale),
                value="\n".join(value_parts),
                inline=False,
            )

            embed.set_footer(text=t("minigame.trade.accepted_footer", locale))
            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.trade.accept_error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @trade_group.command(
        name="cancel",
        description=tr("cmd.trade.cancel.desc"),
    )
    @app_commands.describe(trade_id=tr("cmd.trade.cancel.param"))
    async def trade_cancel(
        self,
        interaction: discord.Interaction,
        trade_id: int,
    ):
        """Cancel a trade."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = cancel_trade(guild_id, user_id, trade_id)

            embed = discord.Embed(
                title=t("minigame.trade.canceled_title", locale),
                color=discord.Color.green(),
            )

            if result["refunded"]:
                embed.description = t("minigame.trade.canceled_refunded", locale)
            else:
                embed.description = t("minigame.trade.canceled", locale)

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.trade.cancel_error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @trade_group.command(
        name="pending",
        description=tr("cmd.trade.pending.desc"),
    )
    async def trade_pending(self, interaction: discord.Interaction):
        """View pending trades."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        trades = get_pending_trades_for_user(guild_id, user_id)

        embed = discord.Embed(
            title=t("minigame.trade.pending_title", locale),
            color=discord.Color.blue(),
        )

        if trades["sent"]:
            sent_text = ""
            for trd in trades["sent"][:5]:
                sent_text += f"**#{trd['id']}** → <@{trd['toUserId']}>\n"
                sent_text += f"🪙 {trd['coins']} | ⭐ {trd['xp']} XP\n\n"
            embed.add_field(
                name=t("minigame.trade.sent_field", locale),
                value=sent_text or t("minigame.trade.none", locale),
                inline=True,
            )
        else:
            embed.add_field(
                name=t("minigame.trade.sent_field", locale),
                value=t("minigame.trade.none", locale),
                inline=True,
            )

        if trades["received"]:
            recv_text = ""
            for trd in trades["received"][:5]:
                recv_text += f"**#{trd['id']}** ← <@{trd['fromUserId']}>\n"
                recv_text += f"🪙 {trd['coins']} | ⭐ {trd['xp']} XP\n\n"
            embed.add_field(
                name=t("minigame.trade.received_field", locale),
                value=recv_text or t("minigame.trade.none", locale),
                inline=True,
            )
        else:
            embed.add_field(
                name=t("minigame.trade.received_field", locale),
                value=t("minigame.trade.none", locale),
                inline=True,
            )

        if not trades["sent"] and not trades["received"]:
            embed.description = t("minigame.trade.pending_empty", locale)

        await interaction.response.send_message(embed=embed)

    # ==================== Wallet & History ====================

    @app_commands.command(
        name="wallet",
        description=tr("cmd.wallet.desc"),
    )
    async def wallet(self, interaction: discord.Interaction):
        """View wallet."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        balance = get_user_balance(guild_id, user_id)

        embed = discord.Embed(
            title=t(
                "minigame.wallet.title", locale, user=interaction.user.display_name
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name=t("minigame.wallet.coins", locale),
            value=f"{balance['coins']:.0f}",
            inline=True,
        )
        embed.add_field(
            name=t("minigame.wallet.xp", locale),
            value=f"{balance['xp']:.0f}",
            inline=True,
        )
        embed.add_field(
            name=t("minigame.wallet.level", locale),
            value=str(balance["level"]),
            inline=True,
        )

        # Get inventory count
        inventory = get_user_inventory(guild_id, user_id)
        if inventory:
            items_count = sum(i["quantity"] for i in inventory)
            embed.add_field(
                name=t("minigame.common.inventory_field", locale),
                value=t("minigame.wallet.inventory_value", locale, count=items_count),
                inline=True,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="history",
        description=tr("cmd.history.desc"),
    )
    @app_commands.describe(
        type=tr("cmd.history.param"),
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name=tr("cmd.history.choice.all"), value="all"),
            app_commands.Choice(
                name=tr("cmd.history.choice.quests"), value="quest_reward"
            ),
            app_commands.Choice(
                name=tr("cmd.history.choice.shop"), value="shop_purchase"
            ),
            app_commands.Choice(name=tr("cmd.history.choice.trades"), value="trade"),
            app_commands.Choice(
                name=tr("cmd.history.choice.captures"), value="capture"
            ),
            app_commands.Choice(name=tr("cmd.history.choice.duels"), value="duel"),
        ]
    )
    async def history(
        self,
        interaction: discord.Interaction,
        type: str = "all",
    ):
        """View transaction history."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        kind = type
        if type == "all":
            kind = None
        transactions = get_user_transactions(guild_id, user_id, limit=10, kind=kind)

        filter_text = ""
        if type != "all":
            filter_text = f" ({type})"
        embed = discord.Embed(
            title=t("minigame.history.title", locale),
            description=t("minigame.history.description", locale, filter=filter_text),
            color=discord.Color.blue(),
        )

        if not transactions:
            embed.description = t("minigame.history.empty", locale)
            await interaction.response.send_message(embed=embed)
            return

        for tx in transactions:
            amount = tx["amount"]
            currency = tx["currency"]
            if currency == "coins":
                symbol = "🪙"
            else:
                symbol = "⭐"

            if amount >= 0:
                amount_str = f"+{amount:.0f} {symbol}"
            else:
                amount_str = f"{amount:.0f} {symbol}"

            tx_timestamp = datetime.fromisoformat(tx["created_at"]).timestamp()
            embed.add_field(
                name=f"{tx['kind'].replace('_', ' ').title()}",
                value=f"{amount_str}\n<t:{int(tx_timestamp)}:R>",
                inline=True,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="inventory",
        description=tr("cmd.inventory.desc"),
    )
    async def inventory(self, interaction: discord.Interaction):
        """View inventory."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        items = get_user_inventory(guild_id, user_id)

        embed = discord.Embed(
            title=t("minigame.common.inventory_field", locale),
            color=discord.Color.blue(),
        )

        if not items:
            embed.description = t("minigame.inventory.empty", locale)
            await interaction.response.send_message(embed=embed)
            return

        for item in items:
            embed.add_field(
                name=f"{item['name']} x{item['quantity']}",
                value=f"{item['description']}\nID: {item['itemId']}",
                inline=False,
            )

        embed.set_footer(text=t("minigame.inventory.footer", locale))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="use",
        description=tr("cmd.use.desc"),
    )
    @app_commands.describe(item_id=tr("cmd.use.param"))
    async def use_item_cmd(
        self,
        interaction: discord.Interaction,
        item_id: int,
    ):
        """Use a consumable item."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = use_item(guild_id, user_id, item_id)

            embed = discord.Embed(
                title=t("minigame.use.title", locale),
                description=result["message"],
                color=discord.Color.green(),
            )

            if result.get("effect"):
                duration = result["metadata"].get("duration_minutes", 60)
                embed.add_field(
                    name=t("minigame.use.effect_field", locale),
                    value=t(
                        "minigame.use.effect_value",
                        locale,
                        effect=result["effect"],
                        duration=duration,
                    ),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.use.error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Game Commands ====================

    @app_commands.command(
        name="capture",
        description=tr("cmd.capture.desc"),
    )
    @app_commands.describe(stake=tr("cmd.capture.param"))
    async def capture_cmd(
        self,
        interaction: discord.Interaction,
        stake: int,
    ):
        """Capture attempt command."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # Check for luck boost
        luck_effect = has_active_effect(guild_id, user_id, "capture_luck")
        luck_bonus = 0.0
        if luck_effect:
            luck_bonus = luck_effect["effect_data"].get("bonus", 0.0)

        try:
            result = capture_attempt(guild_id, user_id, stake, luck_bonus)

            try:
                increment_quest_progress(guild_id, user_id, "capture_attempt", 1)
                if result["success"]:
                    increment_quest_progress(
                        guild_id, user_id, "coins_won_capture", result["net_gain"]
                    )
            except Exception as e:
                logger.error(f"Erreur lors de la progression de quête (capture): {e}")

            if result["success"]:
                embed = discord.Embed(
                    title=t("minigame.capture.success_title", locale),
                    description=t("minigame.capture.success_description", locale),
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name=t("minigame.capture.stake", locale),
                    value=f"🪙 {result['stake']}",
                    inline=True,
                )
                embed.add_field(
                    name=t("minigame.capture.winnings", locale),
                    value=f"🪙 {result['winnings']}",
                    inline=True,
                )
                embed.add_field(
                    name=t("minigame.capture.net_gain", locale),
                    value=f"+🪙 {result['net_gain']}",
                    inline=True,
                )
                embed.add_field(
                    name=t("minigame.capture.xp_earned", locale),
                    value=f"+⭐ {result['xp_gained']}",
                    inline=True,
                )
            else:
                embed = discord.Embed(
                    title=t("minigame.capture.fail_title", locale),
                    description=t("minigame.capture.fail_description", locale),
                    color=discord.Color.red(),
                )
                embed.add_field(
                    name=t("minigame.capture.coins_lost", locale),
                    value=f"-🪙 {result['coins_lost']}",
                    inline=True,
                )
                embed.add_field(
                    name=t("minigame.capture.consolation_xp", locale),
                    value=f"+⭐ {result['xp_gained']}",
                    inline=True,
                )

            odds_pct = result["odds"] * 100
            roll_pct = result["roll"] * 100
            embed.add_field(
                name=t("minigame.common.odds_field", locale),
                value=t(
                    "minigame.capture.odds_value",
                    locale,
                    odds=f"{odds_pct:.1f}",
                    roll=f"{roll_pct:.1f}",
                ),
                inline=False,
            )

            if result.get("level_up"):
                embed.add_field(
                    name=t("minigame.common.level_up_title", locale),
                    value=t(
                        "minigame.common.level_up_value",
                        locale,
                        level=result["new_level"],
                    ),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.capture.error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="duel",
        description=tr("cmd.duel.desc"),
    )
    @app_commands.describe(
        opponent=tr("cmd.duel.opponent"),
        bet=tr("cmd.duel.bet"),
    )
    async def duel_cmd(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        bet: int,
    ):
        """Duel command."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user1_id = str(interaction.user.id)
        user2_id = str(opponent.id)

        try:
            result = arena_duel(guild_id, user1_id, user2_id, bet)

            try:
                increment_quest_progress(guild_id, user1_id, "duel_challenge", 1)
            except Exception as e:
                logger.error(f"Erreur lors de la progression de quête (duel): {e}")

            winner_id = result["winner_id"]
            loser_id = result["loser_id"]

            winner_mention = f"<@{winner_id}>"
            loser_mention = f"<@{loser_id}>"

            embed = discord.Embed(
                title=t("minigame.duel.results_title", locale),
                description=t(
                    "minigame.duel.results_description",
                    locale,
                    winner=winner_mention,
                    loser=loser_mention,
                ),
                color=discord.Color.gold(),
            )

            embed.add_field(
                name=t("minigame.duel.bet_field", locale),
                value=t("minigame.duel.bet_value", locale, amount=result["bet"]),
                inline=True,
            )
            embed.add_field(
                name=t("minigame.duel.pot", locale),
                value=f"🪙 {result['total_pot']}",
                inline=True,
            )
            embed.add_field(
                name=t("minigame.duel.tax", locale),
                value=f"🪙 {result['tax']}",
                inline=True,
            )

            winner_value = (
                f"{winner_mention}\n+🪙 {result['net_gain']} | "
                f"+⭐ {result['winner_xp_gained']}"
            )
            embed.add_field(
                name=t("minigame.duel.winner", locale),
                value=winner_value,
                inline=True,
            )
            loser_value = (
                f"{loser_mention}\n-🪙 {result['bet']} | "
                f"+⭐ {result['loser_xp_gained']}"
            )
            embed.add_field(
                name=t("minigame.duel.loser", locale),
                value=loser_value,
                inline=True,
            )

            user1_odds_pct = result["user1_odds"] * 100
            user2_odds_pct = result["user2_odds"] * 100
            odds_str = (
                f"<@{user1_id}>: {user1_odds_pct:.1f}% | "
                f"<@{user2_id}>: {user2_odds_pct:.1f}%"
            )
            embed.add_field(
                name=t("minigame.common.odds_field", locale),
                value=odds_str,
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title=t("minigame.duel.error_title", locale),
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="stats",
        description=tr("cmd.stats.desc"),
    )
    async def user_stats(self, interaction: discord.Interaction):
        """View user stats."""
        locale = get_locale(interaction)
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        capture_stats = get_capture_stats(guild_id, user_id)
        duel_stats = get_duel_stats(guild_id, user_id)

        embed = discord.Embed(
            title=t("minigame.stats.title", locale, user=interaction.user.display_name),
            color=discord.Color.blue(),
        )

        # Capture stats
        capture_attempts = t(
            "minigame.stats.attempts",
            locale,
            attempts=capture_stats["attempts"],
        )
        capture_wins = t(
            "minigame.stats.wins",
            locale,
            wins=capture_stats["wins"],
            rate=capture_stats["win_rate"],
        )
        capture_net = t(
            "minigame.stats.net",
            locale,
            net=f"{capture_stats['net_profit']:+.0f}",
        )
        embed.add_field(
            name=t("minigame.stats.captures_field", locale),
            value=f"{capture_attempts}\n{capture_wins}\n{capture_net}",
            inline=True,
        )

        # Duel stats
        duel_fights = t(
            "minigame.stats.fights",
            locale,
            fights=duel_stats["duels"],
        )
        duel_wins = t(
            "minigame.stats.wins",
            locale,
            wins=duel_stats["wins"],
            rate=duel_stats["win_rate"],
        )
        duel_net = t(
            "minigame.stats.net",
            locale,
            net=f"{duel_stats['net_profit']:+.0f}",
        )
        embed.add_field(
            name=t("minigame.stats.duels_field", locale),
            value=f"{duel_fights}\n{duel_wins}\n{duel_net}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MinigameCommands(bot))
