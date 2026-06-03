"""Capa de templating del framework: el motor Jinja2 (`TemplateEngine`) + el helper
`view()` (render server-side a HTMLResponse). Lo consumen tanto los controllers
(vistas web) como el `Mailer` (correos)."""

from __future__ import annotations

from milpa.Core.View.TemplateEngine import TemplateEngine, template_engine
from milpa.Core.View.View import negotiate, prefers_html, view

__all__ = ["TemplateEngine", "negotiate", "prefers_html", "template_engine", "view"]
