"""Lo que milpa le suma a tequio. tequio lee este módulo solo (ver `tequio/Core/Extensions.py`).

Se anuncia en el pyproject de milpa:

    [project.entry-points."tequio.extensions"]
    milpa = "milpa.Core.TequioExtension"

Cada nombre de aquí lo lee tequio al arrancar; ninguno se llama desde milpa.

OJO: este archivo se importa MIENTRAS tequio arma su configuración y su motor de plantillas. Por
eso no importa nada pesado arriba: lo que necesita lo importa dentro de cada función, cuando tequio
la llama (importarlo aquí arriba cerraría un ciclo con tequio a medio cargar).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from milpa.Core.Config.Settings import Settings

# La carpeta Resources del paquete milpa: sus layouts web (index.html.j2) y los textos de sus correos de prueba.
RESOURCES_DIR: Final = Path(__file__).resolve().parents[1] / "Resources"

# Los registros de la web que también van a loguru (tequio ya encauza celery).
INTERCEPTED_LOGGERS: Final = ("uvicorn", "uvicorn.error", "uvicorn.access", "httpx")

# El título de `jornal list`.
CONSOLE_TITLE: Final = "🌽 Labores de la milpa"


def settings_class() -> type[Settings]:
    """La configuración de milpa: la de tequio más los campos de la web."""
    from milpa.Core.Config.Settings import Settings

    return Settings


def template_globals() -> dict[str, Any]:
    """Las funciones de las vistas web: `asset()`, `vite()`, `env_script()`, `csp_nonce()`…"""
    from milpa.Core.View.TemplateGlobals import web_template_globals

    return web_template_globals()
