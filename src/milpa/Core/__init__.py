"""El kernel de milpa = el kernel de tequio + la capa web.

milpa nació primero y tequio salió de él quitándole la web. Mientras cada uno tuvo su copia del
kernel, lo que se arreglaba en uno no llegaba al otro. Ahora milpa INSTALA tequio: aquí solo vive
lo web (Http, Auth, vistas/Vite/PWA, `serve`, `make controller`…) y lo demás es de tequio.

El PUENTE de abajo existe para no romper a nadie: los proyectos importan rutas como
`from milpa.Core.Database import Repository` (Tamiz lo hace más de cien veces) y milpa 1.x promete que
siguen valiendo. Cuando alguien pide un módulo compartido por su nombre de milpa, el puente le
entrega EL MISMO módulo de tequio, no una copia: una sola clase `DomainError`, un solo registro de
comandos, un solo `celery_app`. Por eso un `monkeypatch` en una prueba, o un `isinstance`, se
comporta igual con el nombre de milpa que con el de tequio.

OJO, trampa pagada al diseñarlo: un archivo «puente» por módulo (`from tequio.Core.Jobs import *`)
NO sirve. Crea un segundo módulo con los mismos nombres, y lo que la prueba parcha en él no lo ve
tequio. Por eso el puente devuelve el módulo original.

Lo que se comparte: carpetas completas (`SHARED_PACKAGES`) y, dentro de las carpetas que milpa
extiende (Console), los archivos que son iguales (`SHARED_MODULES`). Para compartir algo más, se
agrega aquí y se borra la copia de milpa.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Sequence
from types import ModuleType
from typing import Final

# Carpetas de milpa.Core que son 100 % de tequio (milpa.Core.Database.Session = tequio.Core.Database.Session).
SHARED_PACKAGES: Final = frozenset(
    {
        "CeleryApp",
        "Clock",
        "Cron",
        "Database",
        "Discovery",
        "Events",
        "Jobs",
        "Logging",
        "Mail",
        "Mediator",
        "Pipeline",
    }
)

# Archivos sueltos de tequio dentro de carpetas que milpa extiende con lo suyo (lo de milpa vive al lado:
# Errors/WebErrors.py, Registry/WebRegistry.py, Translate/AcceptLanguage.py, View/TemplateGlobals.py…).
SHARED_MODULES: Final = frozenset(
    {
        "Errors.Errors",
        "Registry.Registry",
        "Translate.I18n",
        "View.TemplateEngine",
        "Console.Console",
        "Console.Commands.DbCommands",
        "Console.Commands.MigrateCommands",
        "Console.Commands.QueueWorkCommand",
        "Console.Commands.ScheduleRunCommand",
        "Console.Commands.ScheduleWorkCommand",
        "Console.Commands.SeedCommands",
    }
)

_MILPA_CORE: Final = "milpa.Core."
_TEQUIO_CORE: Final = "tequio.Core."


def tequio_name_of(milpa_name: str) -> str | None:
    """El nombre en tequio de un módulo de milpa.Core que es compartido, o None si es de milpa."""
    if not milpa_name.startswith(_MILPA_CORE):
        return None
    relative = milpa_name.removeprefix(_MILPA_CORE)
    if relative.split(".", 1)[0] in SHARED_PACKAGES or relative in SHARED_MODULES:
        return _TEQUIO_CORE + relative
    return None


class _TequioBridge(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Contesta las importaciones de milpa.Core.<compartido> con el módulo de tequio ya cargado."""

    def __init__(self) -> None:
        # La «ficha» (`__spec__`) original de cada módulo de tequio entregado, por id del módulo.
        self._original_specs: dict[int, importlib.machinery.ModuleSpec | None] = {}

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if tequio_name_of(fullname) is None:
            return None
        return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        # Devuelve el módulo de tequio TAL CUAL: Python lo guarda también con el nombre de milpa, así
        # que es el mismo objeto con dos nombres (no le cambia `__name__`: ya lo trae).
        tequio_name = tequio_name_of(spec.name)
        if tequio_name is None:  # find_spec ya lo filtró; esto solo protege de un uso directo
            raise ImportError(f"{spec.name} no es un módulo compartido con tequio")
        module = importlib.import_module(tequio_name)
        self._original_specs[id(module)] = module.__spec__
        return module

    def exec_module(self, module: ModuleType) -> None:
        """Nada que correr (tequio ya ejecutó el módulo), salvo regresarle su ficha.

        OJO, trampa pagada: entre `create_module` y aquí, Python SIEMPRE le pone al módulo la ficha
        (`__spec__`) del puente. Con esa ficha, `importlib.reload` (las pruebas lo usan para volver a
        registrar comandos) recargaba «el puente», que no corre nada, y el módulo quedaba sin registrar.
        Con la suya de vuelta, recargar con el nombre de milpa recarga el archivo de tequio."""
        if id(module) in self._original_specs:
            module.__spec__ = self._original_specs.pop(id(module))


def _install_bridge() -> None:
    """Pone el puente primero en la fila de buscadores, una sola vez por proceso."""
    if not any(isinstance(finder, _TequioBridge) for finder in sys.meta_path):
        sys.meta_path.insert(0, _TequioBridge())


_install_bridge()
