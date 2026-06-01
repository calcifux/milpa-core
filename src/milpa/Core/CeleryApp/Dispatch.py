"""Encolar con error LIMPIO si el broker (redis) no está disponible.

Cuando se despacha una task (`.delay()` / `.apply_async()`) y redis no responde,
Celery/kombu lanzan un error de bajo nivel poco claro. `broker_guard()` lo convierte
en un `QueueUnavailableError` con un mensaje que explica qué falta (redis + worker) y
recuerda que existe el camino síncrono (p. ej. `Mail.send`).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import redis.exceptions
from kombu.exceptions import OperationalError

from milpa.Core.Config import settings


class QueueUnavailableError(RuntimeError):
    """No se pudo encolar porque el broker (redis) no está disponible."""


@contextmanager
def broker_guard() -> Iterator[None]:
    """Envuelve un despacho a la cola y traduce fallos de conexión al broker en un
    `QueueUnavailableError` con mensaje accionable."""
    try:
        yield
    except (OperationalError, redis.exceptions.ConnectionError, OSError) as error:
        raise QueueUnavailableError(
            f"No se pudo encolar: el broker no responde en {settings.effective_broker_url!r}. "
            "Las operaciones ENCOLADAS necesitan el broker corriendo (BROKER_URL en .env, default redis) "
            "y un worker consumiendo (`queue work`). Si no quieres encolar, usa el camino SÍNCRONO "
            "(p. ej. `Mail.send` en vez de `Mail.queue`)."
        ) from error
