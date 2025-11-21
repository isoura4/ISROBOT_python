import discord
from discord import app_commands
from discord.ext import commands


class PingBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping_bot", description="Mesure le ping entre discord et le bot."
    )
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000  # Convert to milliseconds
        await interaction.response.send_message(f"Pong! Latence: {latency:.2f} ms")


async def setup(bot: commands.Bot):
    await bot.add_cog(PingBot(bot))
    # Enregistrer la commande ping_bot dans le bot
