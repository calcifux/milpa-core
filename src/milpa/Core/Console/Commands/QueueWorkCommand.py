"""Command `queue work`: arranca el TRABAJADOR (worker) de Celery.

El worker es el que EJECUTA las tareas en background (mandar correos, timbrar,
etc.). Por sí solo no agenda nada: solo procesa lo que se le despacha. El
"despertador" que dispara los crons va aparte (`schedule work`), a propósito,
para que una laptop de desarrollo nunca dispare crons sola. ≈ `php artisan
queue:work` de Laravel.
"""

from __future__ import annotations

import typer

from milpa.Core.CeleryApp import celery_app
from milpa.Core.Config import settings
from milpa.Core.Console import console_command


@console_command(
    name="work",
    group="queue",
    help="Arranca el worker de Celery (procesa las tareas en background). (≈ php artisan queue:work)",
)
def queue_work(
    queue: str | None = typer.Option(
        None,
        "--queue",
        help="Cola(s) a consumir, separadas por coma (ej: emails,reports). = `queue:work --queue=emails`. "
        "Si se omite, consume la cola por defecto.",
    ),
    concurrency: int | None = typer.Option(None, help="Número de procesos worker en paralelo (default: nº de CPUs)."),
    loglevel: str = typer.Option(settings.log_level, help="Nivel de log del worker."),
) -> None:
    """Lanza el worker (proceso de larga duración). Bloquea hasta Ctrl-C.

    NO embebe el scheduler (`-B`) de forma deliberada: el despertador se arranca
    aparte con `schedule work`, así dev no auto-dispara crons. Ver docs/11.
    """
    argv = ["worker", "--loglevel", loglevel]
    if queue is not None:
        argv += ["-Q", queue]  # = --queue=emails de Laravel; consume solo esa(s) cola(s)
    if concurrency is not None:
        argv += ["--concurrency", str(concurrency)]
    celery_app.worker_main(argv=argv)
