"""Tests de QUEUE_NAMESPACE: ciudadanía en bus compartido.

Sin redis ni worker: solo se ejercita el resolvedor puro `qualified_queue` y el guard
de `task_default_queue` (que se setea en tiempo de import bajo el namespace). El namespace
se monkeypatchea sobre `settings.queue_namespace` (singleton module-level), mismo patrón
que el resto de la suite. Es el aislamiento que la feature debe garantizar: dos apps en el
MISMO redis db dejan de robarse tasks porque cada cola va prefijada `{ns}.<cola>`.
"""

from __future__ import annotations

import importlib

from pytest import MonkeyPatch

from milpa.Core.CeleryApp import qualified_queue
from milpa.Core.Config import settings


# ----------------------------------------------------------------- resolvedor puro
def test_qualified_queue_without_namespace_is_passthrough(monkeypatch: MonkeyPatch) -> None:
    """Sin namespace (default): devuelve el nombre tal cual = 100% retrocompatible."""
    monkeypatch.setattr(settings, "queue_namespace", "")
    assert qualified_queue("emails") == "emails"


def test_qualified_queue_none_passes_through_without_namespace(monkeypatch: MonkeyPatch) -> None:
    """None sin namespace pasa como None (la default la maneja task_default_queue)."""
    monkeypatch.setattr(settings, "queue_namespace", "")
    assert qualified_queue(None) is None


def test_qualified_queue_with_namespace_prefixes_explicit_name(monkeypatch: MonkeyPatch) -> None:
    """Con namespace: la cola explícita se prefija `{ns}.<cola>`."""
    monkeypatch.setattr(settings, "queue_namespace", "aqua")
    assert qualified_queue("emails") == "aqua.emails"


def test_qualified_queue_none_stays_none_with_namespace(monkeypatch: MonkeyPatch) -> None:
    """Con namespace, None SIGUE siendo None: la cola por defecto la prefija
    task_default_queue (a `{ns}.celery`), no este resolvedor."""
    monkeypatch.setattr(settings, "queue_namespace", "aqua")
    assert qualified_queue(None) is None


# ------------------------------------------------- task_default_queue del celery_app
def test_celery_default_queue_untouched_without_namespace() -> None:
    """Sin namespace (= el entorno de la suite), el módulo NO toca task_default_queue:
    Celery deja su 'celery' interno. Se lee el celery_app REAL ya importado."""
    from milpa.Core.CeleryApp import celery_app

    assert celery_app.conf.task_default_queue in (None, "celery")


def test_celery_default_queue_prefixed_with_namespace(monkeypatch: MonkeyPatch) -> None:
    """Con namespace, la cola por defecto pasa a `{ns}.celery`: events.handle/mail.send con
    queue=None y los jobs/crons sin cola explícita caen en una cola SOLO de esta app, no en
    la 'celery' compartida (la ejecución cruzada silenciosa que la feature mata).

    Recarga el MÓDULO CeleryApp con el namespace activo para ejercitar el guard de import-time
    REAL, y restaura (reload sin ns) en finally para devolver el `celery_app` global limpio al
    resto de la suite — otros tests comparten ese singleton."""
    import milpa.Core.CeleryApp.CeleryApp as celery_module

    monkeypatch.setattr(settings, "queue_namespace", "aqua")
    try:
        importlib.reload(celery_module)
        assert celery_module.celery_app.conf.task_default_queue == "aqua.celery"
    finally:
        monkeypatch.setattr(settings, "queue_namespace", "")
        importlib.reload(celery_module)
        assert celery_module.celery_app.conf.task_default_queue in (None, "celery")
