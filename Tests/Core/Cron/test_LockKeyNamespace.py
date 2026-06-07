"""Test de la KEY del lock anti-overlap bajo QUEUE_NAMESPACE.

`without_overlapping` toma un lock en redis con key `cron-lock:{name}`. En bus compartido
(varias apps sobre el mismo redis db) dos apps con un cron del MISMO nombre se pisarían el
lock; con namespace la key va `cron-lock:{ns}:{name}` y cada app aísla su lock. Sin namespace
la key actual queda INTACTA (retrocompatible).

Sin redis real: fakeamos `_get_redis()` con un cliente que CAPTURA la key y devuelve un lock
trivial (adquiere siempre, no bloquea), así se ejercita el wrapper completo sin tocar la red.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pytest import MonkeyPatch

from milpa.Core.Config import settings
from milpa.Core.Cron import Cron as CronModule
from milpa.Core.Cron import cron_task


class _FakeLock:
    """Lock trivial: siempre adquiere, nunca bloquea, no toca redis."""

    def acquire(self, blocking: bool = False) -> bool:
        return True

    def release(self) -> None:
        return None


class _CapturingRedis:
    """Cliente redis fake: registra la key con la que se pide el lock."""

    def __init__(self, sink: dict[str, Any]) -> None:
        self._sink = sink

    def lock(self, key: str, **kwargs: Any) -> _FakeLock:
        self._sink["key"] = key
        return _FakeLock()


@pytest.fixture(autouse=True)
def _reset_redis_client() -> Iterator[None]:
    CronModule._redis_client = None
    yield
    CronModule._redis_client = None


def _patch_redis(monkeypatch: MonkeyPatch) -> dict[str, Any]:
    sink: dict[str, Any] = {}
    monkeypatch.setattr(CronModule, "_get_redis", lambda: _CapturingRedis(sink))
    return sink


def test_lock_key_unprefixed_without_namespace(monkeypatch: MonkeyPatch) -> None:
    """Sin namespace, la key del lock es la actual `cron-lock:{name}` (INTACTA)."""
    monkeypatch.setattr(settings, "queue_namespace", "")
    sink = _patch_redis(monkeypatch)

    @cron_task(name="test.cron.lockkey.plain", without_overlapping=True)
    def task() -> str:
        return "ran"

    task()

    assert sink["key"] == "cron-lock:test.cron.lockkey.plain"


def test_lock_key_namespaced_with_namespace(monkeypatch: MonkeyPatch) -> None:
    """Con namespace, la key va `cron-lock:{ns}:{name}` para aislar el lock entre apps."""
    monkeypatch.setattr(settings, "queue_namespace", "aqua")
    sink = _patch_redis(monkeypatch)

    @cron_task(name="test.cron.lockkey.ns", without_overlapping=True)
    def task() -> str:
        return "ran"

    task()

    assert sink["key"] == "cron-lock:aqua:test.cron.lockkey.ns"
