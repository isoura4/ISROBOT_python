import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv, set_key


def _parse_bool_env(value: Optional[str], default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


FEATURES: Dict[str, Dict[str, str]] = {
    "ai": {
        "module": "commands.ai",
        "label": "Commande IA",
    },
    "coinflip": {
        "module": "commands.coinflip",
        "label": "Coinflip",
    },
    "count": {
        "module": "commands.count",
        "label": "Compteur",
    },
    "minigame": {
        "module": "commands.minigame",
        "label": "Minigame",
    },
    "moderation": {
        "module": "commands.moderation",
        "label": "Modération",
    },
    "moderation_config": {
        "module": "commands.moderation_config",
        "label": "Configuration modération",
    },
    "moderation_context": {
        "module": "commands.moderation_context",
        "label": "Menu contextuel modération",
    },
    "ping": {
        "module": "commands.ping",
        "label": "Ping",
    },
    "ping_bot": {
        "module": "commands.ping_bot",
        "label": "Ping bot",
    },
    "stream": {
        "module": "commands.stream",
        "label": "Streams Twitch",
    },
    "user_moderation": {
        "module": "commands.user_moderation",
        "label": "Appels utilisateurs",
    },
    "xp_system": {
        "module": "commands.xp_system",
        "label": "XP texte",
    },
    "xp_voice": {
        "module": "commands.xp_voice",
        "label": "XP vocal",
    },
    "youtube": {
        "module": "commands.youtube",
        "label": "YouTube",
    },
}

_MODULE_TO_FEATURE = {data["module"]: key for key, data in FEATURES.items()}


def feature_env_key(feature_key: str) -> str:
    return f"COG_{feature_key.upper()}_ENABLED"


def module_to_feature_key(module_name: str) -> Optional[str]:
    return _MODULE_TO_FEATURE.get(module_name)


def module_label(module_name: str) -> str:
    feature_key = module_to_feature_key(module_name)
    if feature_key is None:
        return module_name
    return FEATURES[feature_key]["label"]


def feature_status(feature_key: str) -> bool:
    env_key = feature_env_key(feature_key)
    enabled = _parse_bool_env(os.getenv(env_key), default=True)

    if feature_key == "ai":
        enabled = (
            enabled
            and _parse_bool_env(os.getenv("AI_ENABLED"), default=True)
            and _parse_bool_env(os.getenv("AI_COMMAND_ENABLED"), default=True)
        )

    if feature_key == "minigame":
        enabled = enabled and _parse_bool_env(
            os.getenv("minigame_enabled"), default=True
        )

    return enabled


def is_module_enabled(module_name: str) -> bool:
    feature_key = module_to_feature_key(module_name)
    if feature_key is None:
        return True
    return feature_status(feature_key)


def get_feature_rows() -> List[Tuple[str, str, bool, str]]:
    rows: List[Tuple[str, str, bool, str]] = []
    for key, data in FEATURES.items():
        rows.append((key, data["label"], feature_status(key), feature_env_key(key)))
    return rows


def set_feature_enabled(feature_key: str, enabled: bool, env_path: Path) -> None:
    env_key = feature_env_key(feature_key)
    set_key(str(env_path), env_key, "true" if enabled else "false")
    load_dotenv(dotenv_path=env_path, override=True)
