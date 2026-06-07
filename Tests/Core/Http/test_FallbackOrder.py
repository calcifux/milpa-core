"""Tests del ORDEN de montaje de las rutas @Fallback en create_app (Core/Http/Http.py) — sin BD.

La promesa de @Fallback: un catch-all en la RAÍZ (`@Get("/{path:path}")` con prefijo "") se
monta DESPUÉS de los routers, los estáticos, /vite y /status, así que NO se los come. En
Starlette gana el PRIMER match, y create_app monta el catch-all al final a propósito.

Inyectamos un endpoint de prueba monkeypatcheando el discovery (`iter_fallback_routes` que ve
create_app) — sin depender de un módulo real ni del Demo. Verificamos con TestClient que las
rutas registradas ANTES (status, estáticos) ganan, y que el resto cae en el catch-all.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import milpa.Core.Http.Http as http_module
from milpa.Core.Config import settings
from milpa.Core.Http.Http import create_app
from milpa.Core.Http.Routing import FallbackRoute


def _shell(path: str) -> HTMLResponse:
    """Endpoint catch-all de prueba: devuelve el 'shell' marcado, para distinguirlo de
    /status y de los estáticos cuando ganan ELLOS el match."""
    return HTMLResponse(f"<html data-shell='{path}'></html>")


def _fake_discovery() -> Iterator[FallbackRoute]:
    yield (_shell, "/{path:path}", ["GET"], {})


@pytest.fixture
def _client_with_root_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """create_app con un catch-all RAÍZ inyectado + un /static real con un archivo, para
    probar que ni el health check ni los estáticos los atrapa el catch-all."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "app.css").write_text("body{color:red}", encoding="utf-8")
    monkeypatch.setattr(settings, "user_static_dir", str(static_dir))
    # El catch-all raíz: lo ve create_app al montar al final (el discovery real es dinámico).
    monkeypatch.setattr(http_module, "iter_fallback_routes", _fake_discovery)
    with TestClient(create_app()) as client:
        yield client


def test_status_gana_al_catch_all(_client_with_root_fallback: TestClient) -> None:
    # /status se registró ANTES del catch-all: lo atiende el health check, NO el shell.
    response = _client_with_root_fallback.get("/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_estaticos_ganan_al_catch_all(_client_with_root_fallback: TestClient) -> None:
    # El mount /static se registró ANTES del catch-all: sirve el archivo, no el shell.
    response = _client_with_root_fallback.get("/static/app.css")
    assert response.status_code == 200
    assert "color:red" in response.text
    assert "data-shell" not in response.text


def test_catch_all_atrapa_lo_demas(_client_with_root_fallback: TestClient) -> None:
    # Cualquier otra ruta sin dueño cae en el catch-all (el shell de la SPA). El
    # {path:path} captura SIN la barra inicial (cómo lo entrega FastAPI/Starlette).
    response = _client_with_root_fallback.get("/cualquier/ruta/del/cliente")
    assert response.status_code == 200
    assert "data-shell='cualquier/ruta/del/cliente'" in response.text
