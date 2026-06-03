"""Helper `view()` — render server-side de una vista a `HTMLResponse` (= `view()` de Laravel).

El controller no toca el motor Jinja ni el sufijo del archivo, solo pide la vista
por nombre. Vive en Core/View para que cualquier módulo lo reuse.

COMO NOMBRAR LA VISTA (para quien viene de Laravel)
---------------------------------------------------
Usamos la convencion NATIVA de Jinja: ruta con `/` (NO el `::` ni los puntos de
Laravel). Mapeo mental:

    Laravel                       milpa (Jinja)                  archivo en disco
    view('index')              -> view('index')               -> app/Resources/Views/index.html.j2
    view('emails.x')           -> view('Emails/x')            -> app/Resources/Views/Emails/x.html.j2
    view('example::welcome')   -> view('example/welcome')     -> app/Modules/Example/Resources/Views/welcome.html.j2

Reglas:
  • Vista COMPARTIDA (vive en app/Resources/Views) -> ruta relativa, SIN prefijo.
  • Vista de un MODULO (app/Modules/<X>/Resources/Views) -> prefijo = nombre del
    modulo en minusculas: "example/...". El prefijo lo descubre solo el
    TemplateEngine (ver `_module_views_dirs`); no se registra a mano.
  • El sufijo `.html.j2` es opcional aqui (lo agrega `view()`).
"""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.requests import Request

from milpa.Core.View.TemplateEngine import template_engine


def view(template: str, context: dict[str, object] | None = None) -> HTMLResponse:
    """Renderiza `template` con `context` y lo devuelve como `HTMLResponse`.

    Acepta el nombre con o sin sufijo `.html.j2` y namespaced por módulo
    ("example/welcome") o de la raíz compartida ("index"). El context es opcional.
    """
    name = template if template.endswith(".html.j2") else f"{template}.html.j2"
    return HTMLResponse(template_engine.render(name, context or {}))


def prefers_html(request: Request) -> bool:
    """¿El cliente prefiere HTML sobre JSON? (negociación de contenido por `Accept`).

    Heurística KISS por POSICIÓN (no parsea q-values completos, suficiente en la práctica): hay
    HTML solo si `text/html` está presente Y (no hay `application/json` O `text/html` aparece
    antes). Un navegador manda `text/html,...` primero → HTML; un fetch con `application/json` o un
    cliente con `*/*` (curl) → JSON. Así una sola ruta sirve los dos carriles con buenos defaults.
    """
    accept = request.headers.get("accept", "").lower()
    if "text/html" not in accept:
        return False
    if "application/json" not in accept:
        return True
    return accept.index("text/html") < accept.index("application/json")


def negotiate(
    request: Request,
    data: Any,
    template: str,
    *,
    context: dict[str, object] | None = None,
    data_key: str = "data",
) -> Response:
    """Negociación de contenido (≈ DRF): MISMA ruta, HTML o JSON según `Accept`.

    Si el cliente prefiere HTML (`prefers_html`), renderiza `template` con `data` bajo `data_key`
    (+ `context` extra); si no, devuelve `data` como JSON (`jsonable_encoder`, soporta Pydantic/
    dataclasses/dict). Evita duplicar la lógica en dos controllers cuando una ruta sirve ambos.

        @Get("/notes")
        def notes(self, request: Request) -> Response:
            data = [note_dict(n) for n in NoteRepository().all()]
            return negotiate(request, data, "demo/notes", data_key="notes")
    """
    if prefers_html(request):
        return view(template, {data_key: data, **(context or {})})
    return JSONResponse(jsonable_encoder(data))
