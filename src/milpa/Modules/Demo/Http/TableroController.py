"""Carril del surco `tablero` (vanilla JS) — el patrón "cada equipo declara su ruta".

Cada surco se monta DONDE su equipo decida, con SU template Jinja: aquí se declara
explícito (al usuario no le molesta — es el mismo gesto que en Laravel):

    Laravel:  Route::get('/{path?}', ...)->where('path', '.*');
    milpa:    @Get("/{path:path}")   ← `:path` ES el where('.*') de Starlette
                                       (matchea cualquier cosa, incluyendo '/').

El shell inyecta runtime-config (window.__ENV) igual que el surco React: la
convención es del FRAMEWORK, no de la tecnología del frontend.
"""

from __future__ import annotations

from fastapi.responses import HTMLResponse
from starlette.requests import Request

from milpa.Core.Http import Controller, Get
from milpa.Core.Http.Shell import shell_context
from milpa.Core.View import view


@Controller("/tablero", tags=["demo-tablero"])
class TableroController:
    @Get("")
    def shell(self, request: Request) -> HTMLResponse:
        """`shell_context()` (Core/Http/Shell) trae el window.__ENV con BASE_PATH:
        la convención runtime es del FRAMEWORK, no de la tecnología del frontend."""
        return view("demo/tablero", shell_context(request))

    @Get("/{path:path}")
    def shell_subruta(self, request: Request, path: str) -> HTMLResponse:
        """Catch-all del surco (= `->where('path', '.*')` de Laravel)."""
        del path  # solo participa en el routing
        return view("demo/tablero", shell_context(request))
