"""Cron AGENDADO: resumen diario de notas (el PRIMER ejemplo de cron en milpa).

Demuestra `@cron_task` (≠ job): lo AGENDA el scheduler — `schedule run` (que el crontab del SO
dispara cada minuto) lo manda al worker cuando toca (8:00 AM). `output="demo_digest"` rutea sus
logs a `logs/cron_demo_digest.log` (diario). Aquí solo cuenta + loguea; en un caso real mandaría
el resumen por correo al admin.
"""

from __future__ import annotations

from loguru import logger

from milpa.Core.Cron import cron_task, daily_at
from milpa.Modules.Demo.Repositories.NoteRepository import NoteRepository


@cron_task(
    name="demo.daily_digest",
    schedule=daily_at("08:00"),
    environments=("local", "development"),
    output="demo_digest",
)
def daily_digest() -> None:
    """Corre en el WORKER cada día a las 8:00 (lo despacha `schedule run`)."""
    total = len(NoteRepository().all())
    logger.info("demo.daily_digest | {n} notas en total (resumen diario)", n=total)
