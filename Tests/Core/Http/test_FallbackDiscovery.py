"""Fallback e2e con DISCOVERY REAL — el catch-all llega por la vía dinámica, no por monkeypatch.

A diferencia de `test_FallbackOrder` (que inyecta el catch-all monkeypatcheando
`iter_fallback_routes`), aquí montamos un MÓDULO sintético con un `@Controller` que trae un
`@Fallback @Get("/{path:path}")`, apuntamos `settings.modules_package` + `sys.path` hacia él y
dejamos que `create_app()` lo DESCUBRA solo (el mismo `iter_fallback_routes` real que corre en
producción, sin parcharlo). Cierra el lazo del release: el discovery libre importa TODO el árbol
del módulo, así que el `@Fallback` registra vivan donde vivan sus archivos — aquí en un `Http/`
anidado de nombre arbitrario.

Sin BD ni red. TestClient verifica el ORDEN: /status (health) y /static (asset real) GANAN su
match; el resto cae en el catch-all (el shell de la SPA). Limpiamos sys.path/sys.modules y el
`settings` en teardown para no contaminar la suite.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from milpa.Core.Config import settings
from milpa.Core.Http.Http import create_app

# El paquete sintético: un módulo `Spa` cuyo controller con @Fallback vive en un `Http/`
# anidado de nombre arbitrario (`puerta/entrada.py`), NO en un archivo de convención. El
# segmento `Modules` deja que el discovery (module_packages) lo cuente como módulo.
_ROOT = "milpa_fallback_probe"
_PKG = f"{_ROOT}.Modules"  # esto apunta settings.modules_package

# El @Controller("") con un @Fallback @Get("/{path:path}") es EXACTAMENTE la forma del shell de
# una SPA (ver Core/Http/Routing.Fallback): prefijo raíz + catch-all montado al final.
_CONTROLLER_SRC = '''"""Controller de SPA escrito en un Http/ anidado: el @Fallback se descubre igual."""

from __future__ import annotations

from fastapi.responses import HTMLResponse
from starlette.requests import Request

from milpa.Core.Http import Controller, Fallback, Get


@Controller("", tags=["spa-probe"])
class SpaProbeController:
    @Fallback
    @Get("/{path:path}")
    def shell(self, request: Request, path: str) -> HTMLResponse:
        return HTMLResponse(f"<html data-shell='{path}'></html>")
'''


def _write_module(root: Path) -> None:
    """Crea `<root>/milpa_fallback_probe/Modules/Spa/Http/puerta/entrada.py` con __init__ por nivel.

    El controller vive PROFUNDO (Http/puerta/) y con nombre libre (entrada.py): el discovery
    recursivo de iter_fallback_routes lo encuentra sin que esté en un archivo de convención.
    """
    http_nested = root / _ROOT / "Modules" / "Spa" / "Http" / "puerta"
    http_nested.mkdir(parents=True)
    for level in (
        root / _ROOT,
        root / _ROOT / "Modules",
        root / _ROOT / "Modules" / "Spa",
        root / _ROOT / "Modules" / "Spa" / "Http",
        http_nested,
    ):
        (level / "__init__.py").write_text("", encoding="utf-8")
    (http_nested / "entrada.py").write_text(_CONTROLLER_SRC, encoding="utf-8")


def _purge_modules(prefix: str) -> None:
    for name in [n for n in sys.modules if n == prefix or n.startswith(f"{prefix}.")]:
        del sys.modules[name]


@pytest.fixture
def _client_with_discovered_fallback(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[TestClient]:
    """create_app() descubriendo el @Fallback del módulo sintético + un /static real con un
    archivo. NADA se monkeypatchea del registro: es el iter_fallback_routes de verdad."""
    _write_module(tmp_path)
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setattr(settings, "modules_package", _PKG)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "app.css").write_text("body{color:red}", encoding="utf-8")
    monkeypatch.setattr(settings, "user_static_dir", str(static_dir))

    try:
        with TestClient(create_app()) as client:
            yield client
    finally:
        sys.path.remove(str(tmp_path))
        _purge_modules(_ROOT)


def test_status_gana_al_fallback_descubierto(_client_with_discovered_fallback: TestClient) -> None:
    """/status se montó ANTES del catch-all descubierto: lo atiende el health check, no el shell."""
    response = _client_with_discovered_fallback.get("/status")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "data-shell" not in response.text


def test_estaticos_ganan_al_fallback_descubierto(_client_with_discovered_fallback: TestClient) -> None:
    """El mount /static se montó ANTES del catch-all: sirve el archivo, no el shell de la SPA."""
    response = _client_with_discovered_fallback.get("/static/app.css")

    assert response.status_code == 200
    assert "color:red" in response.text
    assert "data-shell" not in response.text


def test_fallback_descubierto_atrapa_lo_demas(_client_with_discovered_fallback: TestClient) -> None:
    """Cualquier ruta sin dueño cae en el @Fallback que el discovery REAL montó al final."""
    response = _client_with_discovered_fallback.get("/cualquier/ruta/del/cliente")

    assert response.status_code == 200
    assert "data-shell='cualquier/ruta/del/cliente'" in response.text
