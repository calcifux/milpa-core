"""Tests del discovery del worker: las tasks del FRAMEWORK quedan registradas.

Guardrail (regresión): `_discover_modules` arma el registro de Celery del worker/beat.
Importa los árboles de tasks de los módulos Y, explícitamente, `Core/Mail` y `Core/Events`
para que `mail.send` y `events.handle` queden registradas. Sin ese import, un mensaje
encolado a `mail.send` se DESCARTA en silencio ("Received unregistered task of type
'mail.send'") aunque para el remitente el encolado haya sido exitoso. Este test fija ese
contrato para que un refactor futuro no deje de importarlas.
"""

from __future__ import annotations

from milpa.Core.CeleryApp import celery_app
from milpa.Core.CeleryApp.CeleryApp import _discover_modules


def test_worker_discovery_registers_framework_tasks() -> None:
    """Tras el discovery del arranque (worker/beat), las tasks del framework
    existen en el registro de Celery: sin esto, un mensaje encolado a `mail.send`
    o `events.handle` se descarta con "unregistered task"."""
    _discover_modules(celery_app)

    assert "mail.send" in celery_app.tasks  # Core/Mail/Tasks.py
    assert "events.handle" in celery_app.tasks  # Core/Events/Tasks.py


def test_worker_discovery_registers_demo_module_tasks() -> None:
    """Las tasks de los MÓDULOS también entran por el mismo discovery (Jobs/ y Crons/
    de cada módulo): el job y el cron del Demo quedan ejecutables en el worker."""
    _discover_modules(celery_app)

    assert "demo.export_notes" in celery_app.tasks
    assert "demo.daily_digest" in celery_app.tasks
