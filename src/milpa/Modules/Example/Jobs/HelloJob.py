"""Job de ejemplo: corre en el WORKER (background), no en el request.

Se auto-registra (lo importa el Registry desde Modules/<X>/Jobs). Dispáralo desde un
controller con `hello_world.delay(...)` / `.apply_async(...)`. Es el "hola mundo" que
demuestra encolar trabajo desde un endpoint y procesarlo en `queue work`.
"""

from __future__ import annotations

from loguru import logger

from milpa.Core.CeleryApp import celery_app


@celery_app.task(name="example.hello")
def hello_world(name: str = "mundo") -> str:
    """Tarea tonta: saluda. Se ejecuta en el worker; el log sale en su terminal."""
    logger.info("example.hello | ¡Hola, {name}! (ejecutado en el worker, en background)", name=name)
    return f"Hola, {name}!"
