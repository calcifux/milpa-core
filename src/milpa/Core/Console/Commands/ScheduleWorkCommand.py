"""Command `schedule work`: arranca el DESPERTADOR (beat) de Celery.

beat solo MARCA LA HORA: cada cierto tiempo despacha los crons al worker (que es
quien hace el trabajo). NO ejecuta nada por sí mismo. Debe correr UNA sola
instancia (si hubiera varias, cada cron se dispararía varias veces).

⚠️ Arrancar esto SÍ dispara los crons, según el guard `@cron_task(environments=
[...])` de cada uno. En dev normalmente NO lo corres: pruebas a mano con el
command directo (p. ej. el command de un módulo). En prod corre como su propio servicio,
separado de los workers (best practice de Celery).
"""

from __future__ import annotations

import typer

from milpa.Core.CeleryApp import celery_app
from milpa.Core.Config import settings
from milpa.Core.Console import console_command


@console_command(
    name="work",
    group="schedule",
    help="Arranca el scheduler/beat (despacha los crons). (≈ php artisan schedule:work)",
)
def schedule_work(
    loglevel: str = typer.Option(settings.log_level, help="Nivel de log del scheduler."),
) -> None:
    """Lanza beat (proceso de larga duración). Bloquea hasta Ctrl-C. El
    beat_schedule lo arma el Registry al configurarse Celery, fusionando DOS
    fuentes: los `@cron_task` descubiertos (convertidos a crontab) MÁS los
    `beat_schedule` declarados en cada `Console/Kernel.py` (estos con precedencia)."""
    celery_app.start(argv=["beat", "--loglevel", loglevel])
