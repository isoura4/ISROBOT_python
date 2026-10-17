"""Système de traduction léger basé sur des fichiers JSON locaux.

Deux mécanismes complémentaires :

* :func:`t` traduit une chaîne à l'exécution en fonction de la locale de
  l'utilisateur (généralement ``interaction.locale``).
* :func:`tr` + :class:`JsonTranslator` permettent la localisation native des
  descriptions de commandes Discord (via ``app_commands.locale_str`` et le
  ``Translator`` de l'arbre de commandes).
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from discord import app_commands

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
DEFAULT_LOCALE = "fr"
SUPPORTED_LOCALES = ("fr", "en")


def base_locale(locale: Optional[str]) -> str:
    """Normalise une locale Discord (``en-US``) vers une locale supportée."""
    if not locale:
        return DEFAULT_LOCALE
    normalized = str(locale).replace("_", "-").lower()
    base = normalized.split("-")[0]
    return base if base in SUPPORTED_LOCALES else DEFAULT_LOCALE


@lru_cache(maxsize=None)
def _load(locale: str) -> Dict[str, Any]:
    path = _LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Impossible de charger les traductions {path}: {e}")
        return {}


def t(key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
    """Retourne la traduction de ``key`` pour ``locale`` (repli sur le défaut)."""
    loc = base_locale(locale)
    value = _load(loc).get(key)
    if value is None and loc != DEFAULT_LOCALE:
        value = _load(DEFAULT_LOCALE).get(key)
    if value is None:
        logger.debug(f"Clé de traduction manquante: {key} (locale={loc})")
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f"Formatage de traduction échoué pour '{key}': {e}")
            return value
    return value


def get_locale(interaction: Any) -> str:
    """Retourne la locale supportée d'une interaction Discord."""
    return base_locale(getattr(interaction, "locale", None))


def tr(key: str) -> app_commands.locale_str:
    """Marque une description de commande comme traduisible (côté Discord)."""
    return app_commands.locale_str(t(key, DEFAULT_LOCALE), key=key)


class JsonTranslator(app_commands.Translator):
    """Traduit les ``locale_str`` des commandes via les fichiers JSON."""

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: Any,
        context: Any,
    ) -> Optional[str]:
        key = (string.extras or {}).get("key")
        if not key:
            return None
        loc = base_locale(getattr(locale, "value", locale))
        if loc == DEFAULT_LOCALE:
            return None
        value = _load(loc).get(key)
        if value is None:
            return None
        return value


def clear_cache() -> None:
    """Vide le cache des traductions (utile en développement/tests)."""
    _load.cache_clear()
