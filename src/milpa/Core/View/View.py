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

from fastapi.responses import HTMLResponse

from milpa.Core.View.TemplateEngine import template_engine


def view(template: str, context: dict[str, object] | None = None) -> HTMLResponse:
    """Renderiza `template` con `context` y lo devuelve como `HTMLResponse`.

    Acepta el nombre con o sin sufijo `.html.j2` y namespaced por módulo
    ("example/welcome") o de la raíz compartida ("index"). El context es opcional.
    """
    name = template if template.endswith(".html.j2") else f"{template}.html.j2"
    return HTMLResponse(template_engine.render(name, context or {}))
