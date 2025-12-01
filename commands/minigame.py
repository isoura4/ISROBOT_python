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
    is_quest_exception_channel,
    remove_quest_exception_channel,
    set_minigame_channel,
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
    update_streak,
)
from shop import (
    buy_item,
    get_shop_items,
    get_user_inventory,
    has_active_effect,
)
from trades import (
    accept_trade,
    cancel_trade,
    check_and_complete_ready_trades,
    create_trade_offer,
    get_pending_trades_for_user,
    get_xp_transfer_warning,
)

# Load environment variables
load_dotenv()
SERVER_ID = int(os.getenv("server_id", "0"))

# Set up logging
logger = logging.getLogger(__name__)

# Channel restriction error message
CHANNEL_RESTRICTION_MSG = (
    "⚠️ **Mini-game Channel Required**\n\n"
    "This mini-game feature is only available in the designated "
    "Minigame channel for this server.\n\n"
    "Please run this command in {channel_mention} or ask an admin "
    "to set the channel with `/minigame set-channel`."
)

NO_CHANNEL_SET_MSG = (
    "⚠️ **No Minigame Channel Set**\n\n"
    "An administrator needs to set a minigame channel first.\n"
    "Use `/minigame set-channel #channel` to configure."
)


async def check_minigame_channel(
    interaction: discord.Interaction,
    allow_exceptions: bool = False,
) -> bool:
    """
    Check if the command is being run in the minigame channel.

    Returns True if allowed, False if not (sends error message).
    """
    if not interaction.guild:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return False

    guild_id = str(interaction.guild.id)
    channel_id = str(interaction.channel_id)

    settings = get_guild_settings(guild_id)
    minigame_channel_id = settings.get("minigame_channel_id")

    # If no channel is set, only admins can proceed
    if not minigame_channel_id:
        await interaction.response.send_message(
            NO_CHANNEL_SET_MSG,
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
        CHANNEL_RESTRICTION_MSG.format(channel_mention=channel_mention),
        ephemeral=True,
    )
    return False


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
        description="Minigame system commands",
    )

    @minigame_group.command(
        name="set-channel",
        description="Set the minigame channel for this server (Admin only)",
    )
    @app_commands.describe(channel="The channel to use for minigames")
    @app_commands.default_permissions(administrator=True)
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        """Set the minigame channel."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        set_minigame_channel(guild_id, str(channel.id))

        embed = discord.Embed(
            title="✅ Minigame Channel Set",
            description=f"Minigame commands will now only work in {channel.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @minigame_group.command(
        name="clear-channel",
        description="Clear the minigame channel setting (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def clear_channel(self, interaction: discord.Interaction):
        """Clear the minigame channel setting."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        set_minigame_channel(guild_id, None)

        embed = discord.Embed(
            title="✅ Minigame Channel Cleared",
            description="Minigame channel restriction has been removed.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @minigame_group.command(
        name="allow-channel",
        description="Add a quest exception channel (Admin only)",
    )
    @app_commands.describe(
        channel="Channel where quest actions can be completed"
    )
    @app_commands.default_permissions(administrator=True)
    async def allow_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        """Add a quest exception channel."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        added = add_quest_exception_channel(guild_id, str(channel.id))

        if added:
            embed = discord.Embed(
                title="✅ Exception Channel Added",
                description=(
                    f"{channel.mention} is now an exception channel.\n"
                    "Quest-related actions can be tracked here."
                ),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="ℹ️ Already Added",
                description=f"{channel.mention} is already an exception channel.",
                color=discord.Color.blue(),
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @minigame_group.command(
        name="remove-channel",
        description="Remove a quest exception channel (Admin only)",
    )
    @app_commands.describe(channel="Channel to remove from exceptions")
    @app_commands.default_permissions(administrator=True)
    async def remove_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        """Remove a quest exception channel."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        removed = remove_quest_exception_channel(guild_id, str(channel.id))

        if removed:
            embed = discord.Embed(
                title="✅ Exception Channel Removed",
                description=f"{channel.mention} removed from exception list.",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="ℹ️ Not Found",
                description=f"{channel.mention} was not an exception channel.",
                color=discord.Color.blue(),
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @minigame_group.command(
        name="stats",
        description="View minigame statistics (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction):
        """View minigame statistics."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        settings = get_guild_settings(guild_id)
        exception_channels = get_quest_exception_channels(guild_id)

        embed = discord.Embed(
            title="📊 Minigame Configuration",
            color=discord.Color.blue(),
        )

        # Channel settings
        mg_channel = settings.get("minigame_channel_id")
        if mg_channel:
            embed.add_field(
                name="Minigame Channel",
                value=f"<#{mg_channel}>",
                inline=True,
            )
        else:
            embed.add_field(
                name="Minigame Channel",
                value="Not set",
                inline=True,
            )

        embed.add_field(
            name="Exception Channels",
            value=str(len(exception_channels)),
            inline=True,
        )

        # Economy settings
        embed.add_field(
            name="XP Trading",
            value="✅ Enabled" if settings.get("xp_trading_enabled") else "❌ Disabled",
            inline=True,
        )

        embed.add_field(
            name="Trade Tax",
            value=f"{settings.get('trade_tax_percent', 10)}%",
            inline=True,
        )

        embed.add_field(
            name="Duel Tax",
            value=f"{settings.get('duel_tax_percent', 10)}%",
            inline=True,
        )

        embed.add_field(
            name="Daily XP Cap",
            value=(
                f"{settings.get('daily_xp_transfer_cap_percent', 10)}% "
                f"(max {settings.get('daily_xp_transfer_cap_max', 500)})"
            ),
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Daily Commands ====================

    daily_group = app_commands.Group(
        name="daily",
        description="Daily quest commands",
    )

    @daily_group.command(
        name="claim",
        description="Claim your daily quests",
    )
    async def daily_claim(self, interaction: discord.Interaction):
        """Claim daily quests."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        # Get or assign daily quests
        status = get_daily_status(guild_id, user_id)

        if not status["can_claim_new"] and status["quests"]:
            embed = discord.Embed(
                title="📋 Daily Quests",
                description="You already have daily quests. Complete them first!",
                color=discord.Color.orange(),
            )
            for quest in status["quests"]:
                status_icon = "✅" if quest["completed"] else "🔄"
                embed.add_field(
                    name=f"{status_icon} {quest['name']}",
                    value=(
                        f"{quest['description']}\n"
                        f"Progress: {quest['progress']}/{quest['target_value']}\n"
                        f"Rewards: 🪙 {quest['reward_coins']} | "
                        f"⭐ {quest['reward_xp']} XP"
                    ),
                    inline=False,
                )
            embed.set_footer(text=f"🔥 Streak: {status['streak']} days")
            await interaction.response.send_message(embed=embed)
            return

        # Assign new daily quests
        quests = assign_daily_quests(guild_id, user_id)

        if not quests:
            embed = discord.Embed(
                title="❌ No Quests Available",
                description="No daily quests are available right now.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)
            return

        # Update streak
        new_streak = update_streak(guild_id, user_id)
        multiplier = get_streak_multiplier(new_streak)

        embed = discord.Embed(
            title="🎯 Daily Quests Assigned!",
            description="Complete these quests to earn rewards!",
            color=discord.Color.green(),
        )

        for quest in quests:
            embed.add_field(
                name=f"🔄 {quest['name']}",
                value=(
                    f"{quest['description']}\n"
                    f"Rewards: 🪙 {quest['reward_coins']} | ⭐ {quest['reward_xp']} XP"
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"🔥 Streak: {new_streak} days | Multiplier: {multiplier}x"
        )
        await interaction.response.send_message(embed=embed)

    @daily_group.command(
        name="status",
        description="View your daily quest status",
    )
    async def daily_status(self, interaction: discord.Interaction):
        """View daily quest status."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        status = get_daily_status(guild_id, user_id)

        if not status["quests"]:
            embed = discord.Embed(
                title="📋 Daily Status",
                description="No daily quests yet. Use `/daily claim` to get some!",
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"🔥 Streak: {status['streak']} days")
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title="📋 Daily Quest Status",
            description=f"Progress: {status['completed']}/{status['total']} completed",
            color=(
                discord.Color.green()
                if status["all_completed"]
                else discord.Color.blue()
            ),
        )

        for quest in status["quests"]:
            if quest["completed"]:
                status_icon = "✅"
                status_text = "Completed!"
            else:
                status_icon = "🔄"
                progress_pct = (quest["progress"] / quest["target_value"]) * 100
                status_text = (
                    f"{quest['progress']}/{quest['target_value']} "
                    f"({progress_pct:.0f}%)"
                )

            embed.add_field(
                name=f"{status_icon} {quest['name']}",
                value=(
                    f"{quest['description']}\n"
                    f"Status: {status_text}\n"
                    f"Rewards: 🪙 {quest['reward_coins']} | "
                    f"⭐ {quest['reward_xp']} XP"
                ),
                inline=False,
            )

        embed.set_footer(text=f"🔥 Streak: {status['streak']} days")
        await interaction.response.send_message(embed=embed)

    # ==================== Quest Commands ====================

    quest_group = app_commands.Group(
        name="quest",
        description="Quest management commands",
    )

    @quest_group.command(
        name="list",
        description="List your active quests",
    )
    async def quest_list(self, interaction: discord.Interaction):
        """List active quests."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        quests = get_user_active_quests(guild_id, user_id)

        if not quests:
            embed = discord.Embed(
                title="📜 Active Quests",
                description="No active quests. Use `/daily claim` to get daily quests!",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title="📜 Active Quests",
            color=discord.Color.green(),
        )

        for quest in quests:
            status_icon = "✅" if quest["completed"] else "🔄"
            progress_pct = (quest["progress"] / quest["target_value"]) * 100

            embed.add_field(
                name=f"{status_icon} {quest['name']} (ID: {quest['id']})",
                value=(
                    f"{quest['description']}\n"
                    f"Progress: {quest['progress']}/{quest['target_value']} "
                    f"({progress_pct:.0f}%)\n"
                    f"Rewards: 🪙 {quest['reward_coins']} | "
                    f"⭐ {quest['reward_xp']} XP"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @quest_group.command(
        name="claim",
        description="Claim rewards for a completed quest",
    )
    @app_commands.describe(quest_id="Quest ID to claim (from /quest list)")
    async def quest_claim_cmd(
        self,
        interaction: discord.Interaction,
        quest_id: Optional[int] = None,
    ):
        """Claim quest rewards."""
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
                    title="ℹ️ No Quests to Claim",
                    description="No completed quests to claim rewards from.",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
                return

            embed = discord.Embed(
                title="🎉 Rewards Claimed!",
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
                name="📊 Total Rewards",
                value=f"🪙 {total_coins} coins | ⭐ {total_xp} XP",
                inline=False,
            )

            # Check for level up
            if any(r.get("level_up") for r in results):
                new_level = max(r.get("new_level", 0) for r in results)
                embed.add_field(
                    name="🎊 Level Up!",
                    value=f"You reached level **{new_level}**!",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Error",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Shop Commands ====================

    shop_group = app_commands.Group(
        name="shop",
        description="Shop commands",
    )

    @shop_group.command(
        name="list",
        description="View available shop items",
    )
    async def shop_list(self, interaction: discord.Interaction):
        """List shop items."""
        if not await check_minigame_channel(interaction):
            return

        items = get_shop_items()

        if not items:
            embed = discord.Embed(
                title="🏪 Shop",
                description="No items available.",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title="🏪 Shop",
            description="Use `/shop buy <id>` to purchase an item",
            color=discord.Color.green(),
        )

        for item in items:
            price_parts = []
            if item["price_coins"] > 0:
                price_parts.append(f"🪙 {item['price_coins']}")
            if item["price_xp"] > 0:
                price_parts.append(f"⭐ {item['price_xp']} XP")

            price_str = " + ".join(price_parts) if price_parts else "Free"
            stock_str = f" | Stock: {item['stock']}" if item["stock"] != -1 else ""

            embed.add_field(
                name=f"#{item['id']} - {item['name']}",
                value=f"{item['description']}\nPrice: {price_str}{stock_str}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @shop_group.command(
        name="buy",
        description="Purchase an item from the shop",
    )
    @app_commands.describe(
        item_id="Item ID to purchase",
        quantity="Number to purchase (default: 1)",
    )
    async def shop_buy(
        self,
        interaction: discord.Interaction,
        item_id: int,
        quantity: int = 1,
    ):
        """Buy a shop item."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = buy_item(guild_id, user_id, item_id, quantity)

            embed = discord.Embed(
                title="✅ Purchase Successful!",
                description=(
                    f"You bought **{result['quantity']}x {result['item_name']}**"
                ),
                color=discord.Color.green(),
            )

            cost_parts = []
            if result["coins_spent"] > 0:
                cost_parts.append(f"🪙 {result['coins_spent']}")
            if result["xp_spent"] > 0:
                cost_parts.append(f"⭐ {result['xp_spent']} XP")

            embed.add_field(
                name="Cost",
                value=" + ".join(cost_parts),
                inline=True,
            )

            if result["is_consumable"]:
                embed.add_field(
                    name="📦 Inventory",
                    value="Item added to your inventory. Use `/inventory` to view.",
                    inline=False,
                )

            if result.get("level_down"):
                embed.add_field(
                    name="⚠️ Level Changed",
                    value=f"You are now level {result['new_level']}",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Purchase Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Trade Commands ====================

    trade_group = app_commands.Group(
        name="trade",
        description="Trading commands",
    )

    @trade_group.command(
        name="offer",
        description="Offer a trade to another player",
    )
    @app_commands.describe(
        user="User to trade with",
        coins="Amount of coins to offer",
        xp="Amount of XP to offer",
    )
    async def trade_offer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        coins: int = 0,
        xp: int = 0,
    ):
        """Create a trade offer."""
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
                now = datetime.utcnow()

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
                            to_user_id, coins, xp, now
                        )
                        embed = discord.Embed(
                            title="⚠️ XP Transfer Warning",
                            description=(
                                f"**This trade will cause you to lose levels!**\n\n"
                                f"Current XP: {warning['current_xp']}\n"
                                f"XP to transfer: {xp}\n"
                                f"Remaining XP: {warning['remaining_xp']}\n\n"
                                f"**Level change:** {warning['current_level']} → "
                                f"{warning['new_level']}\n"
                                f"You will lose **{warning['levels_lost']}** "
                                f"level(s)!"
                            ),
                            color=discord.Color.orange(),
                        )
                        embed.set_footer(
                            text="Run the same command again within "
                                 "30 seconds to confirm"
                        )
                        await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )
                        return
                else:
                    # First attempt, store for confirmation
                    self._pending_xp_confirmations[confirm_key] = (
                        to_user_id, coins, xp, now
                    )
                    embed = discord.Embed(
                        title="⚠️ XP Transfer Warning",
                        description=(
                            f"**This trade will cause you to lose levels!**\n\n"
                            f"Current XP: {warning['current_xp']}\n"
                            f"XP to transfer: {xp}\n"
                            f"Remaining XP: {warning['remaining_xp']}\n\n"
                            f"**Level change:** {warning['current_level']} → "
                            f"{warning['new_level']}\n"
                            f"You will lose **{warning['levels_lost']}** level(s)!"
                        ),
                        color=discord.Color.orange(),
                    )
                    embed.set_footer(
                        text="Run the same command again within "
                             "30 seconds to confirm"
                    )
                    await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )
                    return

        try:
            result = create_trade_offer(
                guild_id, from_user_id, to_user_id, coins, xp
            )

            embed = discord.Embed(
                title="📤 Trade Offer Created",
                description=f"Trade offer sent to {user.mention}",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="Trade ID", value=str(result["trade_id"]), inline=True
            )

            offer_parts = []
            if result["coins"] > 0:
                offer_parts.append(f"🪙 {result['coins']} coins")
            if result["xp"] > 0:
                offer_parts.append(f"⭐ {result['xp']} XP")

            embed.add_field(
                name="Offering", value="\n".join(offer_parts), inline=True
            )

            net_parts = []
            if result["net_coins"] > 0:
                net_parts.append(f"🪙 {result['net_coins']} coins")
            if result["net_xp"] > 0:
                net_parts.append(f"⭐ {result['net_xp']} XP")

            tax_str = f"\n(Tax: {result['tax_coins']}🪙 {result['tax_xp']}⭐)"
            embed.add_field(
                name="After Tax",
                value="\n".join(net_parts) + tax_str,
                inline=True,
            )

            footer_text = (
                f"{user.display_name} can accept with "
                f"/trade accept {result['trade_id']}"
            )
            embed.set_footer(text=footer_text)
            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Trade Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @trade_group.command(
        name="accept",
        description="Accept a pending trade offer",
    )
    @app_commands.describe(trade_id="Trade ID to accept")
    async def trade_accept(
        self,
        interaction: discord.Interaction,
        trade_id: int,
    ):
        """Accept a trade."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = accept_trade(guild_id, user_id, trade_id)

            embed = discord.Embed(
                title="✅ Trade Accepted",
                description="Trade is now in escrow.",
                color=discord.Color.green(),
            )

            embed.add_field(name="Trade ID", value=str(result["trade_id"]), inline=True)
            embed.add_field(
                name="Escrow Release",
                value=f"In {result['minutes_until_release']} minutes",
                inline=True,
            )

            value_parts = []
            if result["coins"] > 0:
                net_coins = result['coins'] - result['tax_coins']
                value_parts.append(f"🪙 {net_coins} coins")
            if result["xp"] > 0:
                net_xp = result['xp'] - result['tax_xp']
                value_parts.append(f"⭐ {net_xp} XP")

            embed.add_field(
                name="You Will Receive",
                value="\n".join(value_parts),
                inline=False,
            )

            embed.set_footer(
                text="Sender can cancel during escrow. "
                     "Trade auto-completes after escrow."
            )
            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Accept Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @trade_group.command(
        name="cancel",
        description="Cancel a pending or escrowed trade",
    )
    @app_commands.describe(trade_id="Trade ID to cancel")
    async def trade_cancel(
        self,
        interaction: discord.Interaction,
        trade_id: int,
    ):
        """Cancel a trade."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        try:
            result = cancel_trade(guild_id, user_id, trade_id)

            embed = discord.Embed(
                title="✅ Trade Canceled",
                color=discord.Color.green(),
            )

            if result["refunded"]:
                embed.description = "Trade canceled. Funds have been refunded."
            else:
                embed.description = "Trade canceled."

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Cancel Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @trade_group.command(
        name="pending",
        description="View your pending trades",
    )
    async def trade_pending(self, interaction: discord.Interaction):
        """View pending trades."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        trades = get_pending_trades_for_user(guild_id, user_id)

        embed = discord.Embed(
            title="📋 Pending Trades",
            color=discord.Color.blue(),
        )

        if trades["sent"]:
            sent_text = ""
            for t in trades["sent"][:5]:
                sent_text += f"**#{t['id']}** → <@{t['toUserId']}>\n"
                sent_text += f"🪙 {t['coins']} | ⭐ {t['xp']} XP\n\n"
            embed.add_field(name="📤 Sent", value=sent_text or "None", inline=True)
        else:
            embed.add_field(name="📤 Sent", value="None", inline=True)

        if trades["received"]:
            recv_text = ""
            for t in trades["received"][:5]:
                recv_text += f"**#{t['id']}** ← <@{t['fromUserId']}>\n"
                recv_text += f"🪙 {t['coins']} | ⭐ {t['xp']} XP\n\n"
            embed.add_field(name="📥 Received", value=recv_text or "None", inline=True)
        else:
            embed.add_field(name="📥 Received", value="None", inline=True)

        if not trades["sent"] and not trades["received"]:
            embed.description = "No pending trades."

        await interaction.response.send_message(embed=embed)

    # ==================== Wallet & History ====================

    @app_commands.command(
        name="wallet",
        description="View your coins, XP, and level",
    )
    async def wallet(self, interaction: discord.Interaction):
        """View wallet."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        balance = get_user_balance(guild_id, user_id)

        embed = discord.Embed(
            title=f"👛 {interaction.user.display_name}'s Wallet",
            color=discord.Color.gold(),
        )

        embed.add_field(name="🪙 Coins", value=f"{balance['coins']:.0f}", inline=True)
        embed.add_field(name="⭐ XP", value=f"{balance['xp']:.0f}", inline=True)
        embed.add_field(name="📊 Level", value=str(balance["level"]), inline=True)

        # Get inventory count
        inventory = get_user_inventory(guild_id, user_id)
        if inventory:
            items_count = sum(i["quantity"] for i in inventory)
            embed.add_field(
                name="📦 Inventory",
                value=f"{items_count} item(s)",
                inline=True,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="history",
        description="View your recent transactions",
    )
    @app_commands.describe(
        type="Filter by transaction type",
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Quests", value="quest_reward"),
            app_commands.Choice(name="Shop", value="shop_purchase"),
            app_commands.Choice(name="Trades", value="trade"),
            app_commands.Choice(name="Captures", value="capture"),
            app_commands.Choice(name="Duels", value="duel"),
        ]
    )
    async def history(
        self,
        interaction: discord.Interaction,
        type: str = "all",
    ):
        """View transaction history."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        kind = None if type == "all" else type
        transactions = get_user_transactions(
            guild_id, user_id, limit=10, kind=kind
        )

        filter_text = f" ({type})" if type != "all" else ""
        embed = discord.Embed(
            title="📜 Transaction History",
            description=f"Last 10 transactions{filter_text}",
            color=discord.Color.blue(),
        )

        if not transactions:
            embed.description = "No transactions found."
            await interaction.response.send_message(embed=embed)
            return

        for tx in transactions:
            amount = tx["amount"]
            currency = tx["currency"]
            symbol = "🪙" if currency == "coins" else "⭐"

            if amount >= 0:
                amount_str = f"+{amount:.0f} {symbol}"
            else:
                amount_str = f"{amount:.0f} {symbol}"

            tx_timestamp = datetime.fromisoformat(tx['created_at']).timestamp()
            embed.add_field(
                name=f"{tx['kind'].replace('_', ' ').title()}",
                value=f"{amount_str}\n<t:{int(tx_timestamp)}:R>",
                inline=True,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="inventory",
        description="View your item inventory",
    )
    async def inventory(self, interaction: discord.Interaction):
        """View inventory."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        items = get_user_inventory(guild_id, user_id)

        embed = discord.Embed(
            title="📦 Inventory",
            color=discord.Color.blue(),
        )

        if not items:
            embed.description = "Your inventory is empty."
            await interaction.response.send_message(embed=embed)
            return

        for item in items:
            embed.add_field(
                name=f"{item['name']} x{item['quantity']}",
                value=f"{item['description']}\nID: {item['itemId']}",
                inline=False,
            )

        embed.set_footer(text="Use items with /use <item_id>")
        await interaction.response.send_message(embed=embed)

    # ==================== Game Commands ====================

    @app_commands.command(
        name="capture",
        description="Attempt to capture rewards by staking coins",
    )
    @app_commands.describe(stake="Amount of coins to stake (10-1000)")
    async def capture_cmd(
        self,
        interaction: discord.Interaction,
        stake: int,
    ):
        """Capture attempt command."""
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

            if result["success"]:
                embed = discord.Embed(
                    title="🎉 Capture Successful!",
                    description="You caught something valuable!",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Stake", value=f"🪙 {result['stake']}", inline=True
                )
                embed.add_field(
                    name="Winnings",
                    value=f"🪙 {result['winnings']}",
                    inline=True,
                )
                embed.add_field(
                    name="Net Gain",
                    value=f"+🪙 {result['net_gain']}",
                    inline=True,
                )
                embed.add_field(
                    name="XP Earned",
                    value=f"+⭐ {result['xp_gained']}",
                    inline=True,
                )
            else:
                embed = discord.Embed(
                    title="😔 Capture Failed",
                    description="It got away...",
                    color=discord.Color.red(),
                )
                embed.add_field(
                    name="Coins Lost",
                    value=f"-🪙 {result['coins_lost']}",
                    inline=True,
                )
                embed.add_field(
                    name="Consolation XP",
                    value=f"+⭐ {result['xp_gained']}",
                    inline=True,
                )

            odds_pct = result['odds'] * 100
            roll_pct = result['roll'] * 100
            embed.add_field(
                name="📊 Odds",
                value=f"Your odds: {odds_pct:.1f}% | Roll: {roll_pct:.1f}%",
                inline=False,
            )

            if result.get("level_up"):
                embed.add_field(
                    name="🎊 Level Up!",
                    value=f"You reached level **{result['new_level']}**!",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Capture Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="duel",
        description="Challenge another player to a duel",
    )
    @app_commands.describe(
        opponent="Player to challenge",
        bet="Amount each player bets (10-500)",
    )
    async def duel_cmd(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        bet: int,
    ):
        """Duel command."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user1_id = str(interaction.user.id)
        user2_id = str(opponent.id)

        try:
            result = arena_duel(guild_id, user1_id, user2_id, bet)

            winner_id = result["winner_id"]
            loser_id = result["loser_id"]

            winner_mention = f"<@{winner_id}>"
            loser_mention = f"<@{loser_id}>"

            embed = discord.Embed(
                title="⚔️ Duel Results!",
                description=f"{winner_mention} defeats {loser_mention}!",
                color=discord.Color.gold(),
            )

            embed.add_field(
                name="Bet", value=f"🪙 {result['bet']} each", inline=True
            )
            embed.add_field(
                name="Pot", value=f"🪙 {result['total_pot']}", inline=True
            )
            embed.add_field(
                name="Tax", value=f"🪙 {result['tax']}", inline=True
            )

            winner_value = (
                f"{winner_mention}\n+🪙 {result['net_gain']} | "
                f"+⭐ {result['winner_xp_gained']}"
            )
            embed.add_field(
                name="🏆 Winner",
                value=winner_value,
                inline=True,
            )
            loser_value = (
                f"{loser_mention}\n-🪙 {result['bet']} | "
                f"+⭐ {result['loser_xp_gained']}"
            )
            embed.add_field(
                name="💀 Loser",
                value=loser_value,
                inline=True,
            )

            user1_odds_pct = result['user1_odds'] * 100
            user2_odds_pct = result['user2_odds'] * 100
            odds_str = (
                f"<@{user1_id}>: {user1_odds_pct:.1f}% | "
                f"<@{user2_id}>: {user2_odds_pct:.1f}%"
            )
            embed.add_field(
                name="📊 Odds",
                value=odds_str,
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Duel Failed",
                description=str(e),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="stats",
        description="View your capture and duel statistics",
    )
    async def user_stats(self, interaction: discord.Interaction):
        """View user stats."""
        if not await check_minigame_channel(interaction):
            return

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        capture_stats = get_capture_stats(guild_id, user_id)
        duel_stats = get_duel_stats(guild_id, user_id)

        embed = discord.Embed(
            title=f"📊 {interaction.user.display_name}'s Stats",
            color=discord.Color.blue(),
        )

        # Capture stats
        embed.add_field(
            name="🎯 Captures",
            value=(
                f"Attempts: {capture_stats['attempts']}\n"
                f"Wins: {capture_stats['wins']} ({capture_stats['win_rate']}%)\n"
                f"Net: {capture_stats['net_profit']:+.0f} 🪙"
            ),
            inline=True,
        )

        # Duel stats
        embed.add_field(
            name="⚔️ Duels",
            value=(
                f"Fights: {duel_stats['duels']}\n"
                f"Wins: {duel_stats['wins']} ({duel_stats['win_rate']}%)\n"
                f"Net: {duel_stats['net_profit']:+.0f} 🪙"
            ),
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MinigameCommands(bot))
