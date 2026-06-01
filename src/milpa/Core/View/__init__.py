"""Capa de templating del framework: el motor Jinja2 (`TemplateEngine`) + el helper
`view()` (render server-side a HTMLResponse). Lo consumen tanto los controllers
(vistas web) como el `Mailer` (correos)."""

from milpa.Core.View.TemplateEngine import TemplateEngine, template_engine
from milpa.Core.View.View import view

__all__ = ["TemplateEngine", "template_engine", "view"]
