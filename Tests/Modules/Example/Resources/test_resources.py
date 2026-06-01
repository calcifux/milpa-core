"""Resources POR MÓDULO auto-descubiertos: la vista y los catálogos de Example se
montan solos (sin listarlos), namespaced. Prueba el ChoiceLoader/PrefixLoader (Views)
y el load_path agregado (Lang). Base del aislamiento microservicio-ready.
"""

from __future__ import annotations

from milpa.Core.Translate import t
from milpa.Core.View.TemplateEngine import TemplateEngine


def test_module_view_auto_discovered_and_uses_module_lang() -> None:
    html = TemplateEngine().render("example/welcome.html.j2", {})
    assert "Hola desde el módulo Example" in html


def test_module_lang_namespace_resolves_per_locale() -> None:
    assert t("example.Greeting.hello", locale="es") == "Hola desde el módulo Example"
    assert t("example.Greeting.hello", locale="en") == "Hello from the Example module"
