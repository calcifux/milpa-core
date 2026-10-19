"""milpa = tequio + la capa web (ver milpa/Core/__init__.py y tequio/Core/Extensions.py).

Lo que estas pruebas cuidan:
  - lo compartido es EL MISMO objeto con el nombre de milpa y el de tequio (un registro, una clase);
  - hay UNA configuración en el proceso y es de la clase de milpa (con los campos web);
  - recargar un módulo por su nombre de milpa vuelve a correr el archivo de tequio;
  - el mapa de tipos (.pyi) para el editor y mypy está al día con tequio.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _sync_script() -> ModuleType:
    """El generador del mapa (scripts/ no es un paquete importable: se carga por su ruta)."""
    spec = importlib.util.spec_from_file_location("sync_tequio_stubs", _ROOT / "scripts" / "sync_tequio_stubs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("milpa_name", "tequio_name"),
    [
        ("milpa.Core.Database", "tequio.Core.Database"),
        ("milpa.Core.Database.Session", "tequio.Core.Database.Session"),
        ("milpa.Core.Errors.Errors", "tequio.Core.Errors.Errors"),
        ("milpa.Core.Console.Console", "tequio.Core.Console.Console"),
        ("milpa.Core.Translate.I18n", "tequio.Core.Translate.I18n"),
        ("milpa.Core.View.TemplateEngine", "tequio.Core.View.TemplateEngine"),
    ],
)
def test_shared_module_is_the_same_object(milpa_name: str, tequio_name: str) -> None:
    assert importlib.import_module(milpa_name) is importlib.import_module(tequio_name)


def test_web_modules_stay_in_milpa() -> None:
    from milpa.Core import tequio_name_of

    assert tequio_name_of("milpa.Core.Http.Http") is None
    assert tequio_name_of("milpa.Core.Errors.WebErrors") is None
    assert tequio_name_of("milpa.Core.Console.Commands.MakeCommands") is None


def test_one_settings_object_with_web_fields() -> None:
    from tequio.Core.Config import settings as worker_settings

    from milpa.Core.Config import Settings, settings

    assert settings is worker_settings
    assert isinstance(settings, Settings)
    assert hasattr(settings, "csp_nonce_enabled")


def test_web_errors_are_domain_errors() -> None:
    from tequio.Core.Errors import DomainError

    from milpa.Core.Errors import UnauthorizedError

    assert issubclass(UnauthorizedError, DomainError)


def test_template_engine_has_the_web_globals() -> None:
    from milpa.Core.View import template_engine

    assert {"asset", "vite", "env_script", "csp_nonce"} <= set(template_engine.environment.globals)


def test_reload_by_milpa_name_runs_the_tequio_file() -> None:
    """Las pruebas de la consola recargan los comandos para volver a registrarlos: tiene que servir."""
    from milpa.Core.Console import registered_commands, reset_registry

    reset_registry()
    import milpa.Core.Console.Commands.SeedCommands as seed_module

    importlib.reload(seed_module)
    try:
        assert "db" in registered_commands()
        assert seed_module.__spec__ is not None
        assert seed_module.__spec__.name == "tequio.Core.Console.Commands.SeedCommands"
    finally:
        reset_registry()


def test_type_map_matches_tequio() -> None:
    """Si truena: tequio cambió lo compartido. Corre `uv run python scripts/sync_tequio_stubs.py`."""
    script = _sync_script()
    expected = script.expected_stubs()
    stubs_on_disk = set(Path(_ROOT / "src" / "milpa" / "Core").rglob("*.pyi"))

    assert stubs_on_disk == set(expected), "el mapa .pyi no corresponde a lo compartido con tequio"
    # Se comparan los NOMBRES y no el texto: el orden y el formato los deja ruff al generar.
    for path, content in expected.items():
        assert script.exported_names_of_stub(path) == _names_in(content), f"{path.name} desfasado"


def _names_in(stub_text: str) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(stub_text).body:
        if isinstance(node, ast.ImportFrom) and node.module != "__future__":
            names.update(alias.asname or alias.name for alias in node.names)
    return names
