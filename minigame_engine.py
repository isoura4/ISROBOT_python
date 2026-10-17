"""
Minigame engine for capture attempts and arena duels.

This module provides the core game logic for:
- Capture attempts (solo gamble)
- Arena duels (PvP gamble)
"""

import random

from database import get_db_connection
from db_helpers import (
    add_coins,
    add_xp,
    calculate_level_from_xp,
    check_cooldown,
    ensure_user_exists,
    get_guild_settings,
    set_cooldown,
    spend_coins,
)

# Multiplier applied to the fair payout cap (1 / odds) so the house keeps a
# small edge and the capture game is not a net source of coins over time.
CAPTURE_HOUSE_EDGE = 0.95

# Paramètres d'équilibrage du jeu de capture (externalisés en constantes).
CAPTURE_BASE_ODDS = 0.30
CAPTURE_XP_BONUS_PER_LEVEL = 0.01
CAPTURE_XP_BONUS_MAX = 0.20
CAPTURE_STAKE_BONUS_PER_COIN = 0.0003
CAPTURE_STAKE_BONUS_MAX = 0.15
CAPTURE_STAKE_CAP = 500
CAPTURE_MAX_ODDS = 0.65

# Paramètres d'équilibrage du duel d'arène.
DUEL_BASE_ODDS = 0.50
DUEL_ODDS_SHIFT_PER_LEVEL = 0.02
DUEL_ODDS_SHIFT_MAX = 0.20


def calculate_capture_odds(user_xp: float, stake_coins: float) -> float:
    """
    Calculate capture success odds based on user XP and stake.

    Higher XP and higher stake = better odds.
    Base odds: 30%
    XP bonus: up to +20% based on level
    Stake bonus: up to +15% based on stake (caps at 500 coins)
    Max total odds: 65%
    """
    level = calculate_level_from_xp(user_xp)

    # Base odds
    base_odds = CAPTURE_BASE_ODDS

    # XP bonus (1% per level, max 20%)
    xp_bonus = min(level * CAPTURE_XP_BONUS_PER_LEVEL, CAPTURE_XP_BONUS_MAX)

    # Stake bonus (higher stake = better odds, diminishing returns)
    # 0.03% per coin up to 500 coins = 15%
    stake_bonus = min(
        stake_coins * CAPTURE_STAKE_BONUS_PER_COIN, CAPTURE_STAKE_BONUS_MAX
    )

    total_odds = base_odds + xp_bonus + stake_bonus

    return min(total_odds, CAPTURE_MAX_ODDS)


def capture_attempt(
    guild_id: str,
    user_id: str,
    stake_coins: float,
    luck_bonus: float = 0.0,
) -> dict:
    """
    Perform a capture attempt.

    Args:
        guild_id: Guild ID
        user_id: User ID
        stake_coins: Amount of coins to stake (min 10)
        luck_bonus: Additional luck from items (0.0-0.20)

    Returns:
        dict with success status, winnings, and updated balances
    """
    if stake_coins < 10:
        raise ValueError("Minimum stake is 10 coins")

    if stake_coins > 1000:
        raise ValueError("Maximum stake is 1000 coins")

    conn = get_db_connection()

    try:
        # Get guild settings for cooldown
        settings = get_guild_settings(guild_id, conn)
        cooldown_seconds = settings.get("capture_cooldown_seconds", 60)

        # Check cooldown
        on_cooldown, remaining = check_cooldown(
            guild_id, user_id, "capture", cooldown_seconds, conn
        )
        if on_cooldown:
            raise ValueError(f"Capture on cooldown. Wait {remaining} seconds.")

        # Get user data
        user = ensure_user_exists(guild_id, user_id, conn)

        # Check if user has enough coins
        if user["coins"] < stake_coins:
            raise ValueError(
                f"Insufficient coins: have {user['coins']}, need {stake_coins}"
            )

        # Calculate odds
        base_odds = calculate_capture_odds(user["xp"], stake_coins)
        total_odds = min(base_odds + luck_bonus, 0.75)  # Max 75% with luck

        # Roll for success
        roll = random.random()
        success = roll < total_odds

        # Set cooldown
        set_cooldown(guild_id, user_id, "capture", conn)

        if success:
            # Success: base payout of 2x stake plus a bonus that grows as the
            # odds get lower. To keep the game from being a money printer, the
            # total multiplier is capped so the expected value stays <= 0.
            #
            # With a total multiplier M, EV = stake * (odds * (M - 1) - (1 - odds)).
            # EV <= 0 requires M <= 1 / odds. We apply a small house edge so the
            # economy deflates on average regardless of the player's odds.
            fair_multiplier_cap = (1.0 / total_odds) * CAPTURE_HOUSE_EDGE
            multiplier = min(
                2.0 + (1 - total_odds), fair_multiplier_cap
            )  # Lower odds = higher multiplier
            winnings = int(stake_coins * multiplier)
            xp_gain = int(stake_coins * 0.1)  # 10% of stake as XP

            # Credit winnings (net gain = winnings - stake)
            add_coins(
                guild_id,
                user_id,
                winnings - stake_coins,
                "capture_win",
                conn=conn,
            )

            # Add XP
            xp_result = add_xp(
                guild_id,
                user_id,
                xp_gain,
                "capture_win",
                conn=conn,
            )

            conn.commit()

            return {
                "success": True,
                "roll": round(roll, 3),
                "odds": round(total_odds, 3),
                "stake": stake_coins,
                "winnings": winnings,
                "net_gain": winnings - stake_coins,
                "xp_gained": xp_gain,
                "level_up": xp_result.get("level_up", False),
                "new_level": xp_result.get("new_level"),
            }
        else:
            # Failure: Lose stake, gain small XP consolation
            xp_consolation = max(1, int(stake_coins * 0.02))  # 2% of stake as XP

            # Debit stake
            spend_coins(
                guild_id,
                user_id,
                stake_coins,
                "capture_loss",
                conn=conn,
            )

            # Add consolation XP
            xp_result = add_xp(
                guild_id,
                user_id,
                xp_consolation,
                "capture_consolation",
                conn=conn,
            )

            conn.commit()

            return {
                "success": False,
                "roll": round(roll, 3),
                "odds": round(total_odds, 3),
                "stake": stake_coins,
                "coins_lost": stake_coins,
                "xp_gained": xp_consolation,
                "level_up": xp_result.get("level_up", False),
                "new_level": xp_result.get("new_level"),
            }

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def calculate_duel_odds(user1_xp: float, user2_xp: float) -> tuple[float, float]:
    """
    Calculate duel win odds for both players.

    Higher XP gives advantage, but randomness keeps it fair.
    Base odds: 50/50
    XP difference bonus: up to +/- 20%
    """
    level1 = calculate_level_from_xp(user1_xp)
    level2 = calculate_level_from_xp(user2_xp)

    level_diff = level1 - level2

    # Each level difference = 2% odds shift, max 20%
    odds_shift = min(abs(level_diff) * DUEL_ODDS_SHIFT_PER_LEVEL, DUEL_ODDS_SHIFT_MAX)

    if level_diff > 0:
        user1_odds = DUEL_BASE_ODDS + odds_shift
        user2_odds = DUEL_BASE_ODDS - odds_shift
    elif level_diff < 0:
        user1_odds = DUEL_BASE_ODDS - odds_shift
        user2_odds = DUEL_BASE_ODDS + odds_shift
    else:
        user1_odds = DUEL_BASE_ODDS
        user2_odds = DUEL_BASE_ODDS

    return user1_odds, user2_odds


def arena_duel(
    guild_id: str,
    user1_id: str,
    user2_id: str,
    bet_coins: float,
) -> dict:
    """
    Perform an arena duel between two players.

    Both players stake the same amount. Winner takes pot minus tax.

    Args:
        guild_id: Guild ID
        user1_id: Challenger user ID
        user2_id: Opponent user ID
        bet_coins: Amount each player bets

    Returns:
        dict with winner, loser, winnings, tax, etc.
    """
    if user1_id == user2_id:
        raise ValueError("Cannot duel yourself")

    if bet_coins < 10:
        raise ValueError("Minimum bet is 10 coins")

    if bet_coins > 500:
        raise ValueError("Maximum bet is 500 coins")

    conn = get_db_connection()

    try:
        # Get guild settings
        settings = get_guild_settings(guild_id, conn)
        tax_percent = settings.get("duel_tax_percent", 10.0)
        cooldown_seconds = settings.get("duel_cooldown_seconds", 300)

        # Check cooldown for challenger
        on_cooldown, remaining = check_cooldown(
            guild_id, user1_id, "duel", cooldown_seconds, conn
        )
        if on_cooldown:
            raise ValueError(
                f"Duel on cooldown for challenger. Wait {remaining} seconds."
            )

        # Get user data
        user1 = ensure_user_exists(guild_id, user1_id, conn)
        user2 = ensure_user_exists(guild_id, user2_id, conn)

        # Check if both users have enough coins
        if user1["coins"] < bet_coins:
            raise ValueError(
                f"Challenger has insufficient coins: "
                f"have {user1['coins']}, need {bet_coins}"
            )
        if user2["coins"] < bet_coins:
            raise ValueError(
                f"Opponent has insufficient coins: "
                f"have {user2['coins']}, need {bet_coins}"
            )

        # Calculate odds
        user1_odds, user2_odds = calculate_duel_odds(user1["xp"], user2["xp"])

        # Roll for winner
        roll = random.random()
        user1_wins = roll < user1_odds

        # Calculate pot and tax
        total_pot = bet_coins * 2
        tax = int(total_pot * (tax_percent / 100))
        winnings = total_pot - tax
        net_gain = winnings - bet_coins  # Winner's net gain

        # Set cooldown for challenger
        set_cooldown(guild_id, user1_id, "duel", conn)

        if user1_wins:
            winner_id = user1_id
            loser_id = user2_id
        else:
            winner_id = user2_id
            loser_id = user1_id

        # Debit loser
        spend_coins(
            guild_id,
            loser_id,
            bet_coins,
            "duel_loss",
            conn=conn,
        )

        # Credit winner (net gain)
        add_coins(
            guild_id,
            winner_id,
            net_gain,
            "duel_win",
            metadata={"tax": tax, "opponent": loser_id},
            conn=conn,
        )

        # XP rewards
        winner_xp = int(bet_coins * 0.1)  # 10% of bet
        loser_xp = max(1, int(bet_coins * 0.02))  # 2% consolation

        winner_xp_result = add_xp(guild_id, winner_id, winner_xp, "duel_win", conn=conn)
        loser_xp_result = add_xp(
            guild_id, loser_id, loser_xp, "duel_consolation", conn=conn
        )

        conn.commit()

        return {
            "winner_id": winner_id,
            "loser_id": loser_id,
            "roll": round(roll, 3),
            "user1_odds": round(user1_odds, 3),
            "user2_odds": round(user2_odds, 3),
            "bet": bet_coins,
            "total_pot": total_pot,
            "tax": tax,
            "winnings": winnings,
            "net_gain": net_gain,
            "winner_xp_gained": winner_xp,
            "loser_xp_gained": loser_xp,
            "winner_level_up": winner_xp_result.get("level_up", False),
            "loser_level_up": loser_xp_result.get("level_up", False),
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_game_stats(
    guild_id: str,
    user_id: str,
    win_kind: str,
    loss_kind: str,
    count_key: str,
) -> dict:
    """Agrège les statistiques d'un jeu à partir de la table transactions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN kind = ? THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN kind = ? THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN kind = ? THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN kind = ? THEN ABS(amount) ELSE 0 END), 0)
            FROM transactions
            WHERE guildId = ? AND userId = ? AND kind IN (?, ?)
            """,
            (
                win_kind,
                loss_kind,
                win_kind,
                loss_kind,
                str(guild_id),
                str(user_id),
                win_kind,
                loss_kind,
            ),
        )
        wins, losses, total_winnings, total_losses = cursor.fetchone()

        wins = int(wins)
        losses = int(losses)
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0

        return {
            count_key: total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_winnings": total_winnings,
            "total_losses": total_losses,
            "net_profit": total_winnings - total_losses,
        }
    finally:
        conn.close()


def get_capture_stats(guild_id: str, user_id: str) -> dict:
    """Get capture statistics for a user."""
    return _get_game_stats(guild_id, user_id, "capture_win", "capture_loss", "attempts")


def get_duel_stats(guild_id: str, user_id: str) -> dict:
    """Get duel statistics for a user."""
    return _get_game_stats(guild_id, user_id, "duel_win", "duel_loss", "duels")
