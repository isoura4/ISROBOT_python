"""
Couche d'abstraction pour les providers d'IA.

Deux providers sont supportés, sélectionnés via la variable d'environnement
``AI_PROVIDER`` :

- ``ollama`` (défaut) : serveur local Ollama (``ollama_host``, ``ollama_model``).
- ``openai`` : toute API compatible OpenAI (OpenRouter, OpenAI, Mistral, ...)
  via ``openai_base_url``, ``openai_api_key`` et ``openai_model``.

L'interface publique est volontairement minimale :

- :func:`get_provider` : provider courant.
- :func:`get_active_model` : modèle résolu pour le provider courant.
- :func:`chat` : envoie une liste de messages et renvoie le texte de la réponse.

Les erreurs réseau/configuration lèvent une sous-classe de
:class:`AIProviderError` afin que les appelants puissent réagir.
"""

import asyncio
import logging
import os
from typing import List, Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --- Valeurs par défaut ------------------------------------------------------
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama2"
DEFAULT_OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENAI_MODEL = "openai/gpt-4o-mini"
DEFAULT_TIMEOUT = 30.0


class AIProviderError(Exception):
    """Erreur générique d'un provider IA."""


class AIProviderConfigError(AIProviderError):
    """Configuration du provider invalide ou incomplète."""


class AIProviderConnectionError(AIProviderError):
    """Le provider IA est injoignable."""


class AIProviderTimeoutError(AIProviderError):
    """Le provider IA n'a pas répondu dans les temps."""


def get_provider() -> str:
    """Retourne le provider IA configuré (``ollama`` par défaut)."""
    value = os.getenv("AI_PROVIDER", "ollama") or "ollama"
    return value.strip().lower()


def _openai_settings() -> tuple:
    """Retourne (base_url, api_key, model) pour le provider OpenAI-compatible."""
    base_url = (
        os.getenv("openai_base_url", DEFAULT_OPENAI_BASE_URL) or DEFAULT_OPENAI_BASE_URL
    ).strip()
    base_url = base_url.rstrip("/")
    api_key = (os.getenv("openai_api_key", "") or "").strip()
    model = (
        os.getenv("openai_model", DEFAULT_OPENAI_MODEL) or DEFAULT_OPENAI_MODEL
    ).strip()
    return base_url, api_key, model


def get_active_model() -> str:
    """Modèle résolu pour le provider courant."""
    if get_provider() == "openai":
        return _openai_settings()[2]
    return (
        os.getenv("ollama_model", DEFAULT_OLLAMA_MODEL) or DEFAULT_OLLAMA_MODEL
    ).strip()


def _parse_ollama_response(data: dict) -> Optional[str]:
    """Extrait le contenu texte d'une réponse Ollama ``/api/chat``."""
    if not isinstance(data, dict):
        return None
    message = data.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not content or not str(content).strip():
        return None
    return str(content)


def _parse_openai_response(data: dict) -> Optional[str]:
    """Extrait le contenu texte d'une réponse compatible OpenAI."""
    if not isinstance(data, dict):
        return None
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not content or not str(content).strip():
        return None
    return str(content)


async def _request_json(url: str, *, headers: dict, body: dict, timeout: float) -> dict:
    """Effectue une requête POST JSON et renvoie le corps décodé.

    Traduit les erreurs réseau/HTTP en exceptions du module.
    """
    try:
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(url, json=body, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    raise AIProviderError(
                        f"HTTP {response.status} depuis {url}: {text[:200]}"
                    )
                return await response.json()
    except (asyncio.TimeoutError, TimeoutError) as exc:
        raise AIProviderTimeoutError(f"Délai dépassé pour {url}") from exc
    except aiohttp.ClientError as exc:
        raise AIProviderConnectionError(f"Connexion impossible à {url}") from exc


async def _chat_ollama(
    messages: List[dict],
    *,
    model: str,
    host: str,
    temperature: Optional[float],
    timeout: float,
) -> Optional[str]:
    body = {"model": model, "messages": messages, "stream": False}
    if temperature is not None:
        body["options"] = {"temperature": temperature}

    url = f"{host.rstrip('/')}/api/chat"
    data = await _request_json(url, headers={}, body=body, timeout=timeout)
    return _parse_ollama_response(data)


async def _chat_openai(
    messages: List[dict],
    *,
    model: str,
    temperature: Optional[float],
    max_tokens: Optional[int],
    timeout: float,
) -> Optional[str]:
    base_url, api_key, default_model = _openai_settings()
    if not api_key:
        raise AIProviderConfigError(
            "openai_api_key est requis lorsque AI_PROVIDER=openai"
        )
    model = model or default_model

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    url = f"{base_url}/chat/completions"
    data = await _request_json(url, headers=headers, body=body, timeout=timeout)
    return _parse_openai_response(data)


async def chat(
    messages: List[dict],
    *,
    model: Optional[str] = None,
    host: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """Envoie une conversation au provider IA et renvoie le texte de la réponse.

    Args:
        messages: liste de messages ``{"role": ..., "content": ...}``.
        model: modèle explicite (défaut : modèle du provider).
        host: hôte Ollama explicite (ignoré pour les providers externes).
        temperature: température d'échantillonnage.
        max_tokens: nombre maximal de tokens générés (providers externes).
        timeout: délai maximal en secondes.

    Returns:
        Le texte de la réponse, ou ``None`` si la structure est invalide.

    Raises:
        AIProviderConfigError: configuration manquante/invalide.
        AIProviderConnectionError: provider injoignable.
        AIProviderTimeoutError: délai dépassé.
        AIProviderError: autre erreur du provider.
    """
    provider = get_provider()

    if provider == "openai":
        return await _chat_openai(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    if provider == "ollama":
        resolved_model = (
            model
            or (
                os.getenv("ollama_model", DEFAULT_OLLAMA_MODEL) or DEFAULT_OLLAMA_MODEL
            ).strip()
        )
        resolved_host = (
            host
            or (
                os.getenv("ollama_host", DEFAULT_OLLAMA_HOST) or DEFAULT_OLLAMA_HOST
            ).strip()
        )
        return await _chat_ollama(
            messages,
            model=resolved_model,
            host=resolved_host,
            temperature=temperature,
            timeout=timeout,
        )

    raise AIProviderConfigError(f"Provider IA inconnu: {provider!r}")
