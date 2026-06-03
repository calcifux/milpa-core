"""Celery central. Descubre tareas y crons de los módulos presentes."""

from __future__ import annotations

from typing import Any

from celery import Celery

from milpa.Core.Config import settings
from milpa.Core.Console import import_submodules
from milpa.Core.Logging import setup_logging
from milpa.Core.Registry import collect_beat_schedule, import_all_tasks

# Logging unificado (Loguru) también en worker/beat.
setup_logging()

celery_app = Celery(
    "app",  # nombre genérico (Core reutilizable); las tasks llevan su nombre explícito
    # Broker-agnostic: redis://, amqp:// (RabbitMQ), sqs://, ... Result backend OPCIONAL
    # (None por default; crons fire-and-forget). Ver docs/research/broker_agnostic_plan.md.
    broker=settings.effective_broker_url,
    backend=settings.effective_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    timezone=settings.timezone,
    enable_utc=True,
    worker_hijack_root_logger=False,  # el logging lo maneja Loguru
)

# visibility_timeout SOLO aplica a redis/SQS (RabbitMQ/AMQP lo ignora). Explícito para
# garantizar `lock_timeout > visibility_timeout` por construcción (ver Cron.py).
if settings.broker_uses_visibility_timeout:
    celery_app.conf.broker_transport_options = {"visibility_timeout": settings.redis_visibility_timeout}


@celery_app.on_after_configure.connect
def _discover_modules(sender: Celery, **_: Any) -> None:
    """Discovery DIFERIDO (no en tiempo de import) para evitar el ciclo de imports
    Cron → CeleryApp → import_all_tasks() → command del módulo → Cron (a medio
    inicializar). Se ejecuta cuando Celery finaliza su configuración (arranque de
    worker/beat), con `app.Core.Cron` ya completamente cargado.

    Registra las tareas (Jobs + Console/Commands) y arma el `beat_schedule` (crons)
    de TODOS los módulos presentes. Registrar tareas NO las dispara; el único
    disparo automático es `celery beat`, y cada cron respeta su guard
    `@cron_task(environments=[...])`.
    """
    import_all_tasks()
    import_submodules("milpa.Core.Mail")  # tasks de correo del framework (mail.send) para el worker
    import_submodules("milpa.Core.Events")  # task events.handle: el worker corre observers encolados
    sender.conf.beat_schedule = collect_beat_schedule()
