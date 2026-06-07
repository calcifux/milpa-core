"""Tests del passthrough de `serve --workers` (sin levantar uvicorn de verdad).

Capturamos los kwargs con que `serve` llama a `uvicorn.run` (monkeypatch del módulo
uvicorn, que `serve` importa local). Lo que protegemos:
- workers>1 viaja como `workers=N` a uvicorn Y fuerza `reload=False` (incompatibles);
- workers=1 (default) NO pasa `workers=` (respeta el `--reload` de dev) y deja root_path
  derivado de ASSET_URL intacto.
"""

from __future__ import annotations

from typing import Any

import uvicorn
from pytest import MonkeyPatch

from milpa.Core.Console.Cli import serve


def _capture_uvicorn(monkeypatch: MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run(app_factory: str, **kwargs: Any) -> None:
        captured["app"] = app_factory
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    return captured


def test_workers_passa_a_uvicorn_y_fuerza_no_reload(monkeypatch: MonkeyPatch) -> None:
    captured = _capture_uvicorn(monkeypatch)

    serve(host="0.0.0.0", port=9000, reload=True, workers=4)

    assert captured["workers"] == 4  # workers>1 -> viaja a uvicorn
    assert captured["reload"] is False  # incompatibles: --workers fuerza no-reload
    assert captured["app"] == "milpa.Core.Http.Http:create_app"
    assert captured["factory"] is True


def test_un_solo_worker_pasa_none_y_respeta_reload(monkeypatch: MonkeyPatch) -> None:
    captured = _capture_uvicorn(monkeypatch)

    serve(host="127.0.0.1", port=8000, reload=True, workers=1)

    assert captured["workers"] is None  # N=1: None => default de uvicorn (dev), no fuerza nada
    assert captured["reload"] is True  # se respeta el modo --reload de siempre


def test_root_path_se_preserva_desde_asset_url(monkeypatch: MonkeyPatch) -> None:
    """El soporte reverse-proxy (ASSET_URL ruta -> root_path ASGI) NO se toca al añadir --workers."""
    from milpa.Core.Config import settings

    captured = _capture_uvicorn(monkeypatch)
    monkeypatch.setattr(settings, "asset_url", "/nombre-reverse/")

    serve(host="127.0.0.1", port=8000, reload=False, workers=2)

    assert captured["root_path"] == "/nombre-reverse"  # prefijo derivado, sin barra final
    assert captured["workers"] == 2
