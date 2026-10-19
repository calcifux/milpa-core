"""Lo que milpa descubre de cada módulo y tequio no: sus rutas (`Http/`), sus permisos (`@policy`) y
sus estáticos (`Resources/Static`).

El barrido de módulos es el de tequio (`milpa.Core.Registry.Registry` es el mismo módulo, ver
`milpa.Core`). Aquí se llama por el MÓDULO (`_registry.module_packages()`) y no por un nombre importado
suelto: así, si una prueba cambia `module_packages` en el registro, estas funciones ven el cambio.
"""

from __future__ import annotations

import pkgutil
from collections.abc import Iterator
from types import ModuleType
from typing import TYPE_CHECKING

import tequio.Core.Registry.Registry as _registry
from fastapi import APIRouter

from milpa.Core.Config import settings
from milpa.Core.Discovery import package_dir

if TYPE_CHECKING:
    # Solo para tipos: importar Core/Http/Routing a nivel de módulo cerraría el ciclo
    # Registry → Http/__init__ → Http → Registry. El runtime usa un import DIFERIDO dentro
    # de iter_fallback_routes (mismo patrón que collect_beat_schedule con Cron).
    from milpa.Core.Http.Routing import FallbackRoute


def import_all_policies() -> None:
    """Importa el árbol completo de cada módulo para que sus `@policy(ability)` se
    registren en el Gate (adiós a `register_policies()` manual).

    Alias de claridad (ver `import_all_tasks`): las `import_all_*` hacen lo mismo —un barrido
    recursivo del árbol del módulo— pero cada nombre documenta su call-site (aquí: el Gate
    cargando policies) y deja abierta la re-especialización futura sin cambiar al llamador.
    """
    _registry.import_all_tasks()


def _iter_http_modules(http_package: str) -> Iterator[ModuleType]:
    """Importa y rinde cada submódulo (recursivo) bajo Modules/<X>/Http/, más el
    propio paquete Http (por si el router vive en su __init__)."""
    package = _registry._try_import(http_package)
    if package is None:
        return
    yield package
    if not hasattr(package, "__path__"):
        return
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{http_package}.", onerror=lambda _name: None):
        if info.name.rsplit(".", 1)[-1].startswith("_"):
            continue
        module = _registry._try_import(info.name)
        if module is not None:
            yield module


def iter_routers() -> Iterator[APIRouter]:
    """Auto-monta los endpoints de los módulos. Escanea `Modules/<X>/Http/` (recursivo),
    importa cada controller y recolecta CUALQUIER `APIRouter` a nivel de módulo. Así
    agregar endpoints = crear un controller con `router = APIRouter(...)`; no hay que
    listarlo en ningún lado (mismo discovery que commands/models). Dedup por identidad.

    El acoplamiento a Modules es por import DINÁMICO (Core no importa Modules estático),
    igual que `iter_cli_apps`, así import-linter no marca Core↛Modules.
    """
    seen: set[int] = set()
    for package in _registry.module_packages():
        for module in _iter_http_modules(f"{package}.Http"):
            for value in vars(module).values():
                if isinstance(value, APIRouter) and id(value) not in seen:
                    seen.add(id(value))
                    yield value
                # Controllers class-based (@Controller): el router armado vive en el __dict__
                # de la CLASE (no heredado), igual de descubrible que un APIRouter de módulo.
                elif isinstance(value, type):
                    controller_router = value.__dict__.get("__milpa_router__")
                    if isinstance(controller_router, APIRouter) and id(controller_router) not in seen:
                        seen.add(id(controller_router))
                        yield controller_router


def iter_fallback_routes() -> Iterator[FallbackRoute]:
    """Recolecta las rutas marcadas con `@Fallback` en los `@Controller` de los módulos, para
    que `create_app` las monte AL FINAL (después de los mounts /static, /vite, /status). Mismo
    escaneo que `iter_routers` (los `Modules/<X>/Http/` recursivo), pero en vez de leer el router
    armado lee `cls.__milpa_fallbacks__` — la lista de rutas que `@Controller` apartó a propósito.

    Una ruta @Fallback es un catch-all RAÍZ (`@Get("/{path:path}")` con prefijo ""): montarla al
    final es lo que evita que se coma los estáticos. En Starlette gana el primer match, así que
    /api, /static, /vite y /status ya ganaron el suyo cuando esta ruta entra. Ver `Fallback`.

    El acoplamiento a Modules es por import DINÁMICO (Core no importa Modules estático), igual que
    `iter_routers`, así import-linter no marca Core↛Modules. Dedup por identidad del controller.
    """
    # Import DIFERIDO del nombre del atributo: a nivel de módulo, importar Core/Http/Routing
    # dispara Http/__init__ y cierra el ciclo con Registry (ver el bloque TYPE_CHECKING arriba).
    from milpa.Core.Http.Routing import FALLBACKS_ATTR

    seen: set[int] = set()
    for package in _registry.module_packages():
        for module in _iter_http_modules(f"{package}.Http"):
            for value in vars(module).values():
                if not isinstance(value, type) or id(value) in seen:
                    continue
                fallbacks = value.__dict__.get(FALLBACKS_ATTR)
                if not isinstance(fallbacks, list):
                    continue
                seen.add(id(value))
                yield from fallbacks


def iter_static_mounts() -> Iterator[tuple[str, str]]:
    """Auto-monta los ASSETS estáticos de los módulos. Para cada
    `Modules/<X>/Resources/Static` que exista, rinde `(url_path, directory)`:
    "/static/<x>" -> esa carpeta. Namespaced por módulo (como las vistas), así los
    assets viajan con el módulo al extraerlo y dos módulos nunca chocan de ruta.

    Como el resto del Registry, el acoplamiento a Modules es por RUTA del filesystem
    (string), no por import estático, así import-linter no marca Core↛Modules.
    La carpeta de módulos se resuelve con `package_dir(settings.modules_package)`
    (funciona en el repo y pip-instalado), no con aritmética de __file__.
    """
    modules_dir = package_dir(settings.modules_package)
    if modules_dir is None:
        return
    for package in _registry.module_packages():
        module_name = package.rsplit(".", 1)[-1]
        static_dir = modules_dir / module_name / "Resources" / "Static"
        if static_dir.is_dir():
            yield f"/static/{module_name.lower()}", str(static_dir)
