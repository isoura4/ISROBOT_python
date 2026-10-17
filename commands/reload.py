import os
from pathlib import Path
from typing import List, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.feature_toggles import (
    FEATURES,
    feature_label,
    get_feature_rows,
    is_module_enabled,
    module_label,
    set_feature_enabled,
)
from utils.i18n import get_locale, t, tr
from utils.logging_config import get_logger

# Chargement du fichier .env
load_dotenv()

# Configure logging for this module
logger = get_logger(__name__)

# Récupération des variables d'environnement
SERVER_ID = int(os.getenv("server_id", "0"))


class Reload(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._env_path = Path(__file__).resolve().parents[1] / ".env"

    async def _sync_commands(self) -> bool:
        try:
            # Synchronisation globale (commandes sans scope de guilde)
            await self.bot.tree.sync()
            # Synchronisation sur la guilde (instantanée)
            await self.bot.tree.sync(guild=discord.Object(id=SERVER_ID))
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation: {e}")
            return False

    async def _reload_extensions(
        self, locale: str = None
    ) -> Tuple[List[str], List[str], List[str]]:
        reloaded_extensions: List[str] = []
        failed_extensions: List[str] = []
        disabled_extensions: List[str] = []

        commands_path = Path(__file__).resolve().parents[1] / "commands"
        for file in os.listdir(commands_path):
            if not file.endswith(".py") or file.startswith("_"):
                continue

            module_name = f"commands.{file[:-3]}"
            if not is_module_enabled(module_name):
                disabled_extensions.append(module_label(module_name, locale))
                if module_name in self.bot.extensions:
                    try:
                        await self.bot.unload_extension(module_name)
                    except Exception as e:
                        failed_extensions.append(f"{module_name}: {str(e)}")
                continue

            try:
                try:
                    await self.bot.reload_extension(module_name)
                    reloaded_extensions.append(module_name)
                    logger.debug(f"Extension {module_name} rechargée avec succès")
                except commands.ExtensionNotLoaded:
                    await self.bot.load_extension(module_name)
                    reloaded_extensions.append(module_name)
                    logger.debug(f"Extension {module_name} chargée avec succès")
            except Exception as e:
                failed_extensions.append(f"{module_name}: {str(e)}")
                logger.error(f"Erreur lors du rechargement de {module_name}: {e}")

        return reloaded_extensions, failed_extensions, disabled_extensions

    async def _feature_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        current_lower = current.lower()
        locale = get_locale(interaction)
        return [
            app_commands.Choice(name=f"{key} — {feature_label(key, locale)}", value=key)
            for key in FEATURES
            if current_lower in key.lower()
            or current_lower in feature_label(key, locale).lower()
        ][:25]

    async def _apply_feature_toggle(
        self, interaction: discord.Interaction, feature: str, enabled: bool
    ) -> None:
        locale = get_locale(interaction)
        if feature not in FEATURES:
            await interaction.response.send_message(
                t("reload.unknown_feature", locale, feature=feature), ephemeral=True
            )
            return

        set_feature_enabled(feature, enabled, self._env_path)
        module_name = FEATURES[feature]["module"]

        try:
            if enabled:
                if module_name in self.bot.extensions:
                    await self.bot.reload_extension(module_name)
                else:
                    await self.bot.load_extension(module_name)
            elif module_name in self.bot.extensions:
                await self.bot.unload_extension(module_name)
        except Exception as e:
            logger.error(f"Erreur lors de l'application du toggle {feature}: {e}")
            await interaction.response.send_message(
                t("reload.apply_failed", locale, feature=feature, error=e),
                ephemeral=True,
            )
            return

        sync_success = await self._sync_commands()
        state_label = t(
            "reload.state_enabled" if enabled else "reload.state_disabled", locale
        )
        sync_label = t("reload.sync_ok" if sync_success else "reload.sync_fail", locale)
        await interaction.response.send_message(
            t(
                "reload.toggle_success",
                locale,
                label=feature_label(feature, locale),
                state=state_label,
                sync=sync_label,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="reload", description=tr("cmd.reload.desc"))
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction):
        locale = get_locale(interaction)
        # Différer la réponse car le processus peut prendre du temps
        await interaction.response.defer()

        reloaded_extensions, failed_extensions, disabled_extensions = (
            await self._reload_extensions(locale)
        )
        sync_success = await self._sync_commands()

        # Préparer le message de réponse
        embed = discord.Embed(
            title=t("reload.title", locale),
            color=(
                discord.Color.green()
                if not failed_extensions
                else discord.Color.orange()
            ),
        )

        if reloaded_extensions:
            embed.add_field(
                name=t("reload.field_reloaded", locale),
                value="\n".join([f"• {ext}" for ext in reloaded_extensions]),
                inline=False,
            )

        if disabled_extensions:
            embed.add_field(
                name=t("reload.field_disabled", locale),
                value="\n".join([f"• {ext}" for ext in disabled_extensions]),
                inline=False,
            )

        if failed_extensions:
            embed.add_field(
                name=t("reload.field_failed", locale),
                value="\n".join([f"• {ext}" for ext in failed_extensions]),
                inline=False,
            )

        if sync_success:
            embed.add_field(
                name=t("reload.field_sync", locale),
                value=t("reload.sync_done", locale),
                inline=False,
            )
        else:
            embed.add_field(
                name=t("reload.field_sync_warn", locale),
                value=t("reload.sync_error", locale),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="feature_list",
        description=tr("cmd.feature_list.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    async def feature_list(self, interaction: discord.Interaction):
        locale = get_locale(interaction)
        rows = get_feature_rows(locale)

        embed = discord.Embed(
            title=t("reload.features_title", locale),
            color=discord.Color.blurple(),
        )
        for key, label, enabled, env_key in rows:
            status = t(
                "reload.feature_status_on" if enabled else "reload.feature_status_off",
                locale,
            )
            embed.add_field(
                name=f"{label} ({key})",
                value=f"{status}\n`{env_key}`",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="feature_enable",
        description=tr("cmd.feature_enable.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(feature=_feature_autocomplete)
    async def feature_enable(self, interaction: discord.Interaction, feature: str):
        await self._apply_feature_toggle(interaction, feature, True)

    @app_commands.command(
        name="feature_disable",
        description=tr("cmd.feature_disable.desc"),
    )
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(feature=_feature_autocomplete)
    async def feature_disable(self, interaction: discord.Interaction, feature: str):
        await self._apply_feature_toggle(interaction, feature, False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Reload(bot))
