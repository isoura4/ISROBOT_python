import asyncio
import logging
import os
import re

import discord
import ollama
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Chargement du fichier .env
load_dotenv()

# Logger pour ce module
logger = logging.getLogger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))
OLLAMA_HOST = os.getenv("ollama_host", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("ollama_model", "llama2")

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
        # Configurer le client Ollama avec l'host personnalisé
        self.ollama_client = ollama.Client(host=OLLAMA_HOST)

    def contains_inappropriate_content(self, text: str) -> bool:
        """Vérifie si le texte contient du contenu inapproprié."""
        # Convertir en minuscules pour la comparaison
        text_lower = text.lower()

        # Vérifier chaque mot-clé inapproprié
        for keyword in INAPPROPRIATE_KEYWORDS:
            # Utiliser des expressions régulières pour détecter le mot entier
            # \b signifie "word boundary" pour éviter les faux positifs
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text_lower):
                return True

        return False

    @app_commands.command(name="ai", description="Posez une question à l'IA")
    @app_commands.describe(question="La question que vous voulez poser à l'IA")
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def ai(self, interaction: discord.Interaction, question: str):
        # Check if AI command is enabled
        from utils.ai_toggle import check_ai_enabled, ai_manager
        
        if not check_ai_enabled("command"):
            embed = discord.Embed(
                title="Fonctionnalité désactivée",
                description=ai_manager.get_disabled_message("command"),
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Répondre immédiatement pour éviter le timeout
        await interaction.response.defer(thinking=True)

        try:
            # Validation de base
            if not question or not question.strip():
                await interaction.followup.send(
                    "❌ La question ne peut pas être vide.", ephemeral=True
                )
                return
            
            question = question.strip()
            
            # Limiter la longueur de la question pour éviter les abus
            if len(question) > 500:
                await interaction.followup.send(
                    "❌ Votre question est trop longue. Veuillez la limiter à 500 caractères.", 
                    ephemeral=True
                )
                return

            # Vérifier si la question contient du contenu inapproprié
            if self.contains_inappropriate_content(question):
                error_embed = discord.Embed(
                    title="❌ Contenu inapproprié détecté",
                    description="Votre question contient du contenu qui viole les règles du serveur. "
                    "Les questions obscènes, illégales ou NSFW ne sont pas autorisées.",
                    color=discord.Color.red(),
                )
                error_embed.set_footer(
                    text="Veuillez respecter les règles de la communauté"
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Préparer l'embed de réponse
            embed = discord.Embed(
                title="🤖 Réponse de l'IA", color=discord.Color.blue()
            )
            embed.add_field(name="❓ Question", value=question, inline=False)

            # Exécuter la requête Ollama dans un thread pour éviter de bloquer
            def get_ai_response():
                try:
                    response = self.ollama_client.chat(
                        model=OLLAMA_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": SYSTEM_PROMPT,
                            },
                            {
                                "role": "user",
                                "content": question,
                            },
                        ],
                    )
                    # Valider la structure de la réponse
                    if not response or "message" not in response or "content" not in response["message"]:
                        return None
                    return response["message"]["content"]
                except ConnectionError as e:
                    logger.warning(f"Erreur de connexion Ollama: {e}")
                    return "❌ Impossible de se connecter au serveur IA. Vérifiez que Ollama est en cours d'exécution."
                except TimeoutError as e:
                    logger.warning(f"Timeout Ollama: {e}")
                    return "❌ Le serveur IA a mis trop de temps à répondre. Réessayez plus tard."
                except Exception as e:
                    logger.error(f"Erreur Ollama: {e}")
                    return f"❌ Erreur lors de la communication avec l'IA: {str(e)}"

            # Exécuter dans un thread pour ne pas bloquer l'event loop
            loop = asyncio.get_event_loop()
            ai_response = await loop.run_in_executor(None, get_ai_response)
            
            # Vérifier si la réponse est valide
            if ai_response is None:
                error_embed = discord.Embed(
                    title="❌ Erreur",
                    description="La réponse de l'IA est invalide ou vide.",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            
            # Vérifier si c'est un message d'erreur
            if ai_response.startswith("❌"):
                error_embed = discord.Embed(
                    title="❌ Erreur",
                    description=ai_response,
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Vérifier si la réponse de l'IA contient du contenu inapproprié
            if self.contains_inappropriate_content(ai_response):
                error_embed = discord.Embed(
                    title="❌ Réponse filtrée",
                    description="La réponse générée par l'IA a été bloquée car elle pourrait violer les règles du serveur.",
                    color=discord.Color.red(),
                )
                error_embed.set_footer(text="Veuillez reformuler votre question")
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Limiter la réponse à 1024 caractères pour Discord
            if len(ai_response) > 1024:
                ai_response = ai_response[:1021] + "..."

            embed.add_field(name="💭 Réponse", value=ai_response, inline=False)
            embed.set_footer(
                text=f"Modèle: {OLLAMA_MODEL} | Demandé par {interaction.user.display_name}"
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Erreur",
                description=f"Une erreur est survenue: {str(e)}",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=error_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AI(bot))
