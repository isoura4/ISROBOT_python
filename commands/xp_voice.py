import logging
import math
import os
import random
from typing import Dict, Optional, Tuple, Union

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Chargement du fichier .env
load_dotenv()

# Logger pour ce module
logger = logging.getLogger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))

# Configuration du système d'XP
LEVEL_MULTIPLIER = 125  # Doit matcher xp_system.py
VOICE_XP_MIN = 15  # XP min par heure en vocal
VOICE_XP_MAX = 25  # XP max par heure en vocal


class VoiceXP(commands.Cog):
    """Attribue de l'XP toutes les heures aux membres présents en vocal."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # sessions[(guild_id, user_id)] = last_award_timestamp (float, epoch seconds)
        self.sessions: Dict[Tuple[int, int], float] = {}
        # Lancer la boucle qui vérifie périodiquement et crédite l'XP (toutes les 5 minutes)
        self.voice_award_loop.start()

    async def cog_unload(self):
        # Arrêter proprement la tâche quand le cog est déchargé
        try:
            self.voice_award_loop.cancel()
        except Exception:
            pass

    # --- Utilitaires DB & calcul de niveau ---
    def get_db_connection(self):
        from database import get_db_connection

        return get_db_connection()

    def calculate_level_from_xp(self, xp: float) -> int:
        return int(math.sqrt(xp / LEVEL_MULTIPLIER)) + 1

    def add_voice_xp(self, guild_id: int, user_id: int, xp_gain: int):
        """Ajoute de l'XP de voix sans incrémenter le compteur de messages."""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT xp, level, messages FROM users WHERE guildId = ? AND userId = ?",
            (str(guild_id), str(user_id)),
        )
        result = cursor.fetchone()

        if result:
            old_xp = result["xp"]
            old_level = result["level"]
            messages = result["messages"]  # ne pas toucher aux messages

            new_xp = old_xp + xp_gain
            new_level = self.calculate_level_from_xp(new_xp)

            cursor.execute(
                """
                UPDATE users
                SET xp = ?, level = ?, messages = ?
                WHERE guildId = ? AND userId = ?
                """,
                (new_xp, new_level, messages, str(guild_id), str(user_id)),
            )

            level_up = new_level > old_level
        else:
            new_xp = xp_gain
            new_level = self.calculate_level_from_xp(new_xp)
            messages = 0
            cursor.execute(
                """
                INSERT INTO users (guildId, userId, xp, level, messages, coins, corners)
                VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (str(guild_id), str(user_id), new_xp, new_level, messages),
            )
            level_up = new_level > 1

        conn.commit()
        conn.close()

        return {
            "new_xp": new_xp,
            "new_level": new_level,
            "level_up": level_up,
            "messages": messages,
        }

    # --- Gestion des états vocaux ---
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        # Ignorer les bots et les autres serveurs si nécessaire
        if member.bot:
            return
        if SERVER_ID and member.guild.id != SERVER_ID:
            return

        key = (member.guild.id, member.id)
        afk_channel = member.guild.afk_channel

        def eligible(
            channel: Optional[Union[discord.VoiceChannel, discord.StageChannel]],
            state: discord.VoiceState,
        ) -> bool:
            if channel is None:
                return False
            if afk_channel and channel.id == afk_channel.id:
                return False
            # Optionnel: ignorer les utilisateurs sourds de leur côté
            # if state.self_deaf or state.deaf:
            #     return False
            return True

        # Si l'utilisateur rejoint/est dans un vocal éligible
        if eligible(after.channel, after):
            # Si on vient de rejoindre ou qu'on devient éligible, démarrer le timer d'une heure
            if key not in self.sessions:
                self.sessions[key] = discord.utils.utcnow().timestamp()
        else:
            # Si l'utilisateur quitte ou n'est plus éligible, retirer la session pour arrêter le comptage
            if key in self.sessions:
                del self.sessions[key]

    # --- Boucle d'attribution périodique ---
    @tasks.loop(minutes=5)
    async def voice_award_loop(self):
        """Toutes les 5 minutes, vérifier qui a atteint 1h (ou plus) en vocal et attribuer l'XP."""
        if not self.sessions:
            return

        now_ts = discord.utils.utcnow().timestamp()
        to_update: Dict[Tuple[int, int], float] = {}

        # Vérifier les sessions courantes
        for (guild_id, user_id), last_award_ts in list(self.sessions.items()):
            # Vérifier que l'utilisateur est toujours en vocal et éligible
            guild = self.bot.get_guild(guild_id)
            if not guild:
                # Nettoyage si le serveur n'est pas accessible
                del self.sessions[(guild_id, user_id)]
                continue

            member = guild.get_member(user_id)
            if not member:
                del self.sessions[(guild_id, user_id)]
                continue

            voice = member.voice
            if not voice or not voice.channel:
                del self.sessions[(guild_id, user_id)]
                continue

            if guild.afk_channel and voice.channel.id == guild.afk_channel.id:
                # AFK, pas d'XP
                continue

            elapsed = now_ts - last_award_ts
            full_hours = int(elapsed // 3600)
            if full_hours >= 1:
                # Attribuer l'XP pour chaque heure complète passée depuis la dernière attribution
                xp_per_hour = random.randint(VOICE_XP_MIN, VOICE_XP_MAX)
                total_xp = xp_per_hour * full_hours
                try:
                    self.add_voice_xp(guild_id, user_id, total_xp)
                except Exception as e:
                    logger.error(
                        "Erreur lors de l'attribution d'XP vocal à %s sur %s: %s",
                        user_id, guild_id, e
                    )
                    continue

                # Mettre à jour le timestamp d'attribution pour conserver la/les heure(s) restante(s)
                new_ts = last_award_ts + (full_hours * 3600)
                to_update[(guild_id, user_id)] = new_ts

        # Appliquer les mises à jour hors de la boucle principale pour éviter les mutations concurrentes
        for key, new_ts in to_update.items():
            # Toujours vérifier que la session existe encore (peut avoir été supprimée ci-dessus)
            if key in self.sessions:
                self.sessions[key] = new_ts

    @voice_award_loop.before_loop
    async def before_voice_award_loop(self):
        # Attendre que le bot soit prêt avant de démarrer la boucle
        await self.bot.wait_until_ready()
        # Enregistrer les membres déjà en vocal au démarrage
        for guild in self.bot.guilds:
            if SERVER_ID and guild.id != SERVER_ID:
                continue
            afk = guild.afk_channel
            now_ts = discord.utils.utcnow().timestamp()
            for member in guild.members:
                if member.bot:
                    continue
                voice = member.voice
                if voice and voice.channel:
                    if afk and voice.channel.id == afk.id:
                        continue
                    self.sessions[(guild.id, member.id)] = now_ts


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceXP(bot))
