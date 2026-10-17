"""Shared XP-to-level configuration and helpers.

Ce module centralise la formule de calcul de niveau pour éviter les
définitions dupliquées (xp_system, xp_voice, db_helpers, minigame_engine).
"""

import math

# Multiplicateur pour calculer l'XP nécessaire par niveau
LEVEL_MULTIPLIER = 125


def calculate_level_from_xp(xp: float) -> int:
    """Calcule le niveau à partir de l'XP."""
    if xp < 0:
        xp = 0
    return int(math.sqrt(xp / LEVEL_MULTIPLIER)) + 1


def calculate_xp_for_level(level: int) -> float:
    """Calcule l'XP nécessaire pour atteindre un niveau donné."""
    return ((level - 1) ** 2) * LEVEL_MULTIPLIER
