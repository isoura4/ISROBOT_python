import logging
import os
import re
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils import ai_provider
from utils.i18n import get_locale, t, tr

# Chargement du fichier .env
load_dotenv()

# Logger pour ce module
logger = logging.getLogger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))

# Limites configurables via l'environnement
MAX_AI_QUESTION_LENGTH = int(os.getenv("ai_max_question_length", "500"))
MAX_AI_RESPONSE_LENGTH = int(os.getenv("ai_max_response_length", "1024"))

# Liste de mots-clés inappropriés (à adapter selon les besoins)
INAPPROPRIATE_KEYWORDS = [
    "porn",
    "nsfw",
    "sex",
    "nude",
    "naked",
    "explicit",
    "xxx",
    "drug",
    "cocaine",
    "heroin",
    "meth",
    "illegal",
    "kill",
    "murder",
    "suicide",
    "bomb",
    "weapon",
    "terrorist",
    "hack",
    "exploit",
    "malware",
    "virus",
    "ddos",
    # Mots français
    "pornographique",
    "sexuel",
    "nu",
    "explicite",
    "drogue",
    "cocaïne",
    "héroïne",
    "illégal",
    "illégale",
    "tuer",
    "meurtre",
    "suicide",
    "bombe",
    "arme",
    "terroriste",
    "piratage",
    "malveillant",
]

# Table de substitution « leetspeak » pour contrer les contournements simples
_LEET_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "!": "i",
    }
)

# Caractères invisibles retirés avant analyse
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)


def _normalize_for_filter(text: str) -> str:
    """Normalise un texte pour la détection de contenu inapproprié.

    Retire les caractères invisibles, les accents, applique les minuscules
    et remplace les substitutions leetspeak courantes.
    """
    text = text.translate(_ZERO_WIDTH)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().translate(_LEET_TRANSLATION)


# Motifs tolérant les répétitions de lettres (« ssseeeexxx ») et les
# séparateurs de ponctuation intercalés (« s.e.x », « s-e-x », « s_e_x »).
# L'espace n'est volontairement pas traité comme séparateur pour limiter
# les faux positifs sur des mots légitimes adjacents.
_FILTER_PATTERNS = [
    re.compile(
        r"\b" + "".join(f"{re.escape(ch)}+(?:[^\\w\\s]|_)*" for ch in keyword) + r"\b"
    )
    for keyword in {_normalize_for_filter(kw) for kw in INAPPROPRIATE_KEYWORDS}
    if keyword
]

# Prompt système pour guider le comportement de l'IA
SYSTEM_PROMPT = """Tu es un assistant IA respectueux et utile dans un serveur Discord.
Tu DOIS respecter les règles suivantes:
1. Ne jamais générer, décrire ou aider avec du contenu NSFW, explicite, pornographique ou sexuel
2. Ne jamais fournir d'instructions pour des activités illégales (drogue, piratage, violence, etc.)
3. Ne jamais générer de contenu offensant, haineux ou discriminatoire
4. Refuser poliment toute demande inappropriée
5. Toujours rester courtois et constructif

Si une question viole ces règles, réponds simplement: "Je ne peux pas répondre à cette question car elle viole les règles du serveur."
"""


class AI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def contains_inappropriate_content(self, text: str) -> bool:
        """Vérifie si le texte contient du contenu inapproprié.

        Le texte est normalisé (accents, leetspeak, caractères invisibles) et
        comparé à des motifs tolérant la répétition de lettres.
        """
        normalized = _normalize_for_filter(text)
        return any(pattern.search(normalized) for pattern in _FILTER_PATTERNS)

    @app_commands.command(name="ai", description=tr("cmd.ai.desc"))
    @app_commands.describe(question=tr("cmd.ai.question"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def ai(self, interaction: discord.Interaction, question: str):
        locale = get_locale(interaction)
        # Check if AI command is enabled
        from utils.ai_toggle import ai_manager, check_ai_enabled

        if not check_ai_enabled("command"):
            embed = discord.Embed(
                title=t("ai.disabled.title", locale),
                description=ai_manager.get_disabled_message("command", locale),
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Répondre immédiatement pour éviter le timeout
        await interaction.response.defer(thinking=True)

        try:
            # Validation de base
            if not question or not question.strip():
                await interaction.followup.send(
                    t("ai.empty_question", locale), ephemeral=True
                )
                return

            question = question.strip()

            # Limiter la longueur de la question pour éviter les abus
            if len(question) > MAX_AI_QUESTION_LENGTH:
                await interaction.followup.send(
                    t("ai.question_too_long", locale, max=MAX_AI_QUESTION_LENGTH),
                    ephemeral=True,
                )
                return

            # Vérifier si la question contient du contenu inapproprié
            if self.contains_inappropriate_content(question):
                error_embed = discord.Embed(
                    title=t("ai.inappropriate_title", locale),
                    description=t("ai.inappropriate_desc", locale),
                    color=discord.Color.red(),
                )
                error_embed.set_footer(text=t("ai.inappropriate_footer", locale))
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Préparer l'embed de réponse
            embed = discord.Embed(
                title=t("ai.response_title", locale), color=discord.Color.blue()
            )
            embed.add_field(
                name=t("ai.field_question", locale), value=question, inline=False
            )

            # Interroger le provider IA configuré (Ollama ou API compatible OpenAI)
            try:
                ai_response = await ai_provider.chat(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": question},
                    ],
                    temperature=0.7,
                )
            except ai_provider.AIProviderTimeoutError as e:
                logger.warning(f"Timeout IA: {e}")
                error_embed = discord.Embed(
                    title=t("ai.error_title", locale),
                    description=t("ai.timeout_error", locale),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            except ai_provider.AIProviderConnectionError as e:
                logger.warning(f"Erreur de connexion IA: {e}")
                error_embed = discord.Embed(
                    title=t("ai.error_title", locale),
                    description=t("ai.conn_error", locale),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            except ai_provider.AIProviderConfigError as e:
                logger.error(f"Configuration IA invalide: {e}")
                error_embed = discord.Embed(
                    title=t("ai.error_title", locale),
                    description=t("ai.config_error", locale, error=str(e)),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            except ai_provider.AIProviderError as e:
                logger.error(f"Erreur IA: {e}")
                error_embed = discord.Embed(
                    title=t("ai.error_title", locale),
                    description=t("ai.comm_error", locale, error=str(e)),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Vérifier si la réponse est valide
            if ai_response is None:
                error_embed = discord.Embed(
                    title=t("ai.error_title", locale),
                    description=t("ai.invalid_response", locale),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Vérifier si la réponse de l'IA contient du contenu inapproprié
            if self.contains_inappropriate_content(ai_response):
                error_embed = discord.Embed(
                    title=t("ai.filtered_title", locale),
                    description=t("ai.filtered_desc", locale),
                    color=discord.Color.red(),
                )
                error_embed.set_footer(text=t("ai.filtered_footer", locale))
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Limiter la réponse pour respecter la limite de champ Discord
            if len(ai_response) > MAX_AI_RESPONSE_LENGTH:
                ai_response = ai_response[: MAX_AI_RESPONSE_LENGTH - 3] + "..."

            embed.add_field(
                name=t("ai.field_response", locale), value=ai_response, inline=False
            )
            embed.set_footer(
                text=t(
                    "ai.footer",
                    locale,
                    model=ai_provider.get_active_model(),
                    user=interaction.user.display_name,
                )
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title=t("ai.error_title", locale),
                description=t("ai.generic_error", locale, error=str(e)),
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=error_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AI(bot))
