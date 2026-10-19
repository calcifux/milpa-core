"""Capa de vistas de milpa: el helper `view()` (render server-side a HTMLResponse), `negotiate()`,
Vite y la PWA. El motor de plantillas (`TemplateEngine`, `template_engine`) es el de tequio: uno solo
para vistas y correos, con las funciones web que milpa le suma (ver `TemplateGlobals.py`).

Los nombres se entregan al pedirlos y no al importar el paquete: tequio importa
`milpa.Core.View.TemplateGlobals` MIENTRAS arma su motor, y si este archivo importara el motor
arriba, cerraría un ciclo con tequio a medio cargar.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from milpa.Core.View import Pwa
    from milpa.Core.View.TemplateEngine import TemplateEngine, template_engine
    from milpa.Core.View.View import negotiate, prefers_html, view

__all__ = ["Pwa", "TemplateEngine", "negotiate", "prefers_html", "template_engine", "view"]

# nombre -> (módulo, atributo); atributo None = el módulo mismo
_LAZY: Final[dict[str, tuple[str, str | None]]] = {
    "Pwa": ("milpa.Core.View.Pwa", None),
    "TemplateEngine": ("milpa.Core.View.TemplateEngine", "TemplateEngine"),
    "template_engine": ("milpa.Core.View.TemplateEngine", "template_engine"),
    "negotiate": ("milpa.Core.View.View", "negotiate"),
    "prefers_html": ("milpa.Core.View.View", "prefers_html"),
    "view": ("milpa.Core.View.View", "view"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = _LAZY[name]
    module = import_module(module_name)
    return module if attribute is None else getattr(module, attribute)
