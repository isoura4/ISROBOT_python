"""Utilitaires de temps partagés.

Fournit un remplaçant non déprécié de ``datetime.utcnow()`` qui conserve
le même comportement (datetime naïf en UTC), afin de ne pas casser le
stockage/comparaison des dates existantes en base.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Retourne la date/heure UTC naïve (sans tzinfo).

    Équivalent non déprécié de ``datetime.utcnow()``.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
