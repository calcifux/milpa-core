"""EL test de la LIBERTAD de encarpetado (estilo milpa): el discovery importa TODO el árbol de
cada módulo, así que los decoradores registran AUNQUE vivan en un archivo ANIDADO con nombre
arbitrario (aquí: `cosecha/maquinaria/trilladora.py`) O todos juntos de corrido en UN SOLO archivo
plano. No hay carpetas de convención obligatorias (Jobs/, Crons/, Console/Commands/, Observers/,
Handlers/, Policies/): las carpetas son la PROPUESTA que generan los make:*, jamás un requisito.

Sin BD ni red. Construimos en `tmp_path` un paquete de módulos SINTÉTICO, apuntamos
`settings.modules_package` y `sys.path` hacia él, y verificamos que tras `import_all_tasks()` /
`import_all_observers()` / `import_all_handlers()` / `import_all_policies()` / `iter_cli_apps()`
los decoradores quedaron registrados. Limpiamos TODO el estado global (registros de Console, Cron,
Observers, Handlers, Policies, Celery, sys.modules, sys.path) para no contaminar el resto de la suite.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from milpa.Core.Auth import Gate
from milpa.Core.Auth.Authorization import reset_policies
from milpa.Core.Config import settings
from milpa.Core.Console import registered_commands, reset_registry
from milpa.Core.Cron import reset_cron_registry
from milpa.Core.Events import reset_observers
from milpa.Core.Mediator import registered_handlers, reset_handlers
from milpa.Core.Registry import (
    import_all_handlers,
    import_all_observers,
    import_all_policies,
    import_all_tasks,
    iter_cli_apps,
)

# ---------------------------------------------------------------------------
# Caso 1: archivo ANIDADO de nombre arbitrario (port de tequio). El @console_command
# y el @job viven JUNTOS en un .py PROFUNDO; el discovery los encuentra igual, sin que
# estén en Jobs/ ni en Console/Commands/.
# ---------------------------------------------------------------------------
_NESTED_PKG = "libertad_layout_probe"
_NESTED_GROUP = "cosecha"

# El paquete NO contiene el segmento "Modules", así que la deducción de grupo no aplica: el
# @console_command declara `group=` explícito (lo mismo que exige el framework para commands
# fuera de app.Modules).
_NESTED_SRC = '''"""Archivo anidado de nombre arbitrario: prueba que el discovery desciende todo el árbol."""

from __future__ import annotations

from milpa.Core.Console import console_command
from milpa.Core.Jobs import job


@job(name="cosecha.trillar")
def trillar(parcela_id: int) -> int:
    return parcela_id


@console_command(name="trillar", group="cosecha", help="Trilla una parcela (vive ANIDADO).")
def trillar_command(parcela_id: int) -> None:
    ...
'''


def _write_nested_pkg(root: Path) -> None:
    """Crea `<root>/libertad_layout_probe/cosecha/maquinaria/trilladora.py` con __init__ por nivel."""
    nested_dir = root / _NESTED_PKG / "cosecha" / "maquinaria"
    nested_dir.mkdir(parents=True)
    for level in (root / _NESTED_PKG, root / _NESTED_PKG / "cosecha", nested_dir):
        (level / "__init__.py").write_text("", encoding="utf-8")
    (nested_dir / "trilladora.py").write_text(_NESTED_SRC, encoding="utf-8")


# ---------------------------------------------------------------------------
# Caso 2: TODO DE CORRIDO en un solo archivo plano (el test que protege el espíritu
# del release: "no vamos a luchar contra los devs que escriben todo de corrido sin
# encarpetar para pruebas de concepto"). job + cron + observer + handler + command +
# policy, todo junto, SIN carpetas — y el discovery registra TODO.
# ---------------------------------------------------------------------------
# El paquete sintético SÍ trae el segmento `Modules` para que la deducción de grupo del
# @console_command aplique (igual que en un proyecto real `app.Modules`): el grupo se deriva del
# nombre del módulo (`DeCorrido` → `decorrido`) sin declarar `group=` a mano.
_FLAT_ROOT = "milpa_synthetic_pkg"
_FLAT_PKG = f"{_FLAT_ROOT}.Modules"  # esto es lo que apunta settings.modules_package
_FLAT_MODULE = "DeCorrido"  # un módulo (paquete) cuyo ÚNICO contenido útil es un .py plano

_FLAT_SRC = '''"""Un módulo entero escrito DE CORRIDO en un solo archivo plano: job + cron + observer +
handler + command + policy, todo junto, sin Jobs/ ni Crons/ ni Observers/ ni nada. El discovery
recursivo importa el árbol y CADA decorador corre."""

from __future__ import annotations

from milpa.Core.Auth import policy
from milpa.Core.Console import console_command
from milpa.Core.Cron import cron_task, daily_at
from milpa.Core.Events import Observer
from milpa.Core.Jobs import job
from milpa.Core.Mediator import handles


@job(name="decorrido.exportar")
def exportar(user_id: int) -> int:
    return user_id


@cron_task(name="decorrido.barrer", schedule=daily_at("03:00"))
def barrer() -> None:
    ...


class NotaCreada:
    pass


class NotaObserver(Observer):
    observes = NotaCreada

    def handle(self, event: object) -> None:
        ...


class ArchivarNota:
    pass


@handles(ArchivarNota)
class ArchivarNotaHandler:
    def handle(self, command: ArchivarNota) -> str:
        return "archivada"


@console_command(name="archivar", help="Archiva una nota (vive DE CORRIDO).")  # grupo deducido: decorrido
def archivar_command() -> None:
    ...


@policy("decorrido.editar")
def puede_editar(user: object, recurso: object) -> bool:
    return True
'''


def _write_flat_pkg(root: Path) -> None:
    """Crea `<root>/milpa_synthetic_pkg/Modules/DeCorrido/__init__.py` (vacío) + un único `all.py`.

    El módulo `DeCorrido` es un paquete (carpeta con __init__) porque `module_packages()` solo
    cuenta sub-paquetes (`info.ispkg`); pero su contenido es UN SOLO archivo plano `all.py` con
    todos los decoradores juntos — cero carpetas de convención adentro. El segmento `Modules`
    intermedio deja que el @console_command deduzca su grupo (`DeCorrido` → `decorrido`).
    """
    module_dir = root / _FLAT_ROOT / "Modules" / _FLAT_MODULE
    module_dir.mkdir(parents=True)
    (root / _FLAT_ROOT / "__init__.py").write_text("", encoding="utf-8")
    (root / _FLAT_ROOT / "Modules" / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "all.py").write_text(_FLAT_SRC, encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures: cada uno escribe su paquete sintético, apunta settings + sys.path y limpia
# TODO el estado global en teardown (registros + sys.modules + sys.path).
# ---------------------------------------------------------------------------
def _reset_all_registries() -> None:
    reset_registry()
    reset_cron_registry()
    reset_observers()
    reset_handlers()
    reset_policies()


def _purge_modules(prefix: str) -> None:
    for name in [n for n in sys.modules if n == prefix or n.startswith(f"{prefix}.")]:
        del sys.modules[name]


@pytest.fixture
def _nested_modules(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[str]:
    """Paquete sintético con el archivo anidado + settings.modules_package y sys.path apuntados."""
    _reset_all_registries()
    _write_nested_pkg(tmp_path)
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setattr(settings, "modules_package", _NESTED_PKG)
    try:
        yield _NESTED_PKG
    finally:
        sys.path.remove(str(tmp_path))
        _purge_modules(_NESTED_PKG)
        _reset_all_registries()


@pytest.fixture
def _flat_modules(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[str]:
    """Paquete sintético con el módulo DE CORRIDO + settings.modules_package y sys.path apuntados."""
    _reset_all_registries()
    _write_flat_pkg(tmp_path)
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setattr(settings, "modules_package", _FLAT_PKG)
    try:
        yield _FLAT_PKG
    finally:
        sys.path.remove(str(tmp_path))
        _purge_modules(_FLAT_ROOT)
        _reset_all_registries()


# ---------------------------------------------------------------------------
# Caso 1 — archivo anidado de nombre arbitrario.
# ---------------------------------------------------------------------------
def test_console_command_in_nested_arbitrary_file_is_discovered(_nested_modules: str) -> None:
    """`iter_cli_apps()` importa todo el árbol y arma el sub-app: el command anidado queda registrado."""
    apps = {group: sub_app for group, sub_app in iter_cli_apps()}

    assert _NESTED_GROUP in apps  # el grupo 'cosecha' se montó desde un archivo anidado de nombre libre
    names = {command.name for command in registered_commands()[_NESTED_GROUP]}
    assert "trillar" in names


def test_job_in_nested_arbitrary_file_is_discovered(_nested_modules: str) -> None:
    """`import_all_tasks()` importa todo el árbol: el @job anidado registra su task de Celery."""
    from milpa.Core.CeleryApp import celery_app

    import_all_tasks()

    assert "cosecha.trillar" in celery_app.tasks  # el decorador @job corrió → task registrada


# ---------------------------------------------------------------------------
# Caso 2 — TODO DE CORRIDO en un solo archivo plano (el espíritu del release).
# ---------------------------------------------------------------------------
def test_de_corrido_single_flat_file_registers_everything(_flat_modules: str) -> None:
    """Un módulo escrito de corrido (job+cron+observer+handler+command+policy en UN .py) y el
    discovery registra TODO. Es la garantía del release: las carpetas son propuesta, no requisito."""
    from milpa.Core.CeleryApp import celery_app
    from milpa.Core.Cron import registered_crons
    from milpa.Core.Events import registered_observers

    # Un solo barrido recursivo (import_all_tasks) basta para cargar el árbol; las cinco
    # import_all_* delegan en el mismo _import_all_modules. Llamamos varias para reflejar el
    # arranque real (web/worker) y comprobar idempotencia.
    import_all_tasks()
    import_all_observers()
    import_all_handlers()
    import_all_policies()
    apps = {group: sub_app for group, sub_app in iter_cli_apps()}

    # job → task de Celery registrada
    assert "decorrido.exportar" in celery_app.tasks
    # cron → registrado en el sink de crons (lo agenda el beat)
    assert any(rc.name == "decorrido.barrer" for rc in registered_crons())
    # observer → subclase auto-registrada
    assert any(obs.__name__ == "NotaObserver" for obs in registered_observers())
    # handler → @handles registrado en el Mediator (por tipo de comando)
    assert any(cmd.__name__ == "ArchivarNota" for cmd in registered_handlers())
    # command → grupo deducido 'decorrido' (segmento tras Modules... aquí no hay Modules, ver abajo)
    assert "decorrido" in apps
    assert "archivar" in {command.name for command in registered_commands()["decorrido"]}
    # policy → registrada en el Gate (allows usa la fn registrada)
    assert Gate.allows("decorrido.editar", object()) is True
