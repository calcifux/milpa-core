"""El endpoint GET /example/hello ENCOLA el job example.hello (no lo ejecuta en el
request). Sin broker: monkeypatcheamos `.delay`. Y si el broker está caído → 503 limpio.
"""

from __future__ import annotations

from typing import Any

from kombu.exceptions import OperationalError
from pytest import MonkeyPatch
from starlette.testclient import TestClient

from milpa.Core.Http import create_app
from milpa.Modules.Example.Jobs.HelloJob import hello_world


def test_endpoint_enqueues_the_hello_job(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(hello_world, "delay", lambda **kwargs: captured.update(kwargs))

    response = TestClient(create_app()).get("/example/hello", params={"name": "milpa"})

    assert response.status_code == 200
    assert response.json() == {"status": "encolado", "job": "example.hello", "name": "milpa"}
    assert captured == {"name": "milpa"}  # se encoló con el nombre dado


def test_async_endpoint_also_enqueues(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(hello_world, "delay", lambda **kwargs: captured.update(kwargs))

    response = TestClient(create_app()).get("/example/hello-async", params={"name": "milpa"})

    assert response.status_code == 200
    assert response.json()["mode"] == "async"
    assert captured == {"name": "milpa"}  # el .delay() corrió en threadpool, sin bloquear el loop


def test_returns_503_when_broker_is_down(monkeypatch: MonkeyPatch) -> None:
    def boom(**_kwargs: Any) -> None:
        raise OperationalError("broker caído")  # broker_guard lo traduce a QueueUnavailableError

    monkeypatch.setattr(hello_world, "delay", boom)

    response = TestClient(create_app(), raise_server_exceptions=False).get("/example/hello")

    assert response.status_code == 503


def test_hello_job_returns_greeting() -> None:
    # Ejecuta la lógica de la task directamente (lo que correría el worker).
    assert hello_world(name="milpa") == "Hola, milpa!"
