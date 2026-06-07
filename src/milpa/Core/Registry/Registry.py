"""Registro del monolito modular: descubre y ensambla los módulos presentes.

Layout estilo Laravel (PascalCase). Convención por módulo en app/Modules/<Name>/:
  - Http/Controllers/  -> paquete que expone `routers` (lista de APIRouter)
  - Jobs/ y Console/Commands/ -> tareas Celery (se descubren con pkgutil)
  - Console/Kernel.py  -> diccionario `beat_schedule` (los crons; como Kernel.php)

Los módulos se descubren SOLOS escaneando app/Modules/. Tener un módulo presente
NO dispara nada por sí mismo:
  - Registrar tasks (`import_all_tasks`) solo las vuelve ejecutables bajo demanda.
  - Montar rutas (`iter_routers`) solo responde a requests entrantes.
  - El único disparo AUTOMÁTICO es `celery beat` leyendo el beat_schedule; y aun
    así, cada cron solo se ejecuta donde su guard `@cron_task(environments=[...])`
    lo permite. La autoridad del auto-disparo vive en `@cron_task`, no aquí.

Los MODELOS NO viven por módulo: son COMPARTIDOS en app/Models (una sola fuente
por tabla, porque todos los módulos comparten la BD legacy).
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator
from types import ModuleType
from typing import TYPE_CHECKING

import typer
from fastapi import APIRouter

from milpa.Core.Config import settings
from milpa.Core.Console import build_cli_apps, import_submodules
from milpa.Core.Discovery import _module_absent, package_dir

if TYPE_CHECKING:
    # Solo para tipos: importar Core/Http/Routing a nivel de módulo cerraría el ciclo
    # Registry → Http/__init__ → Http → Registry. El runtime usa un import DIFERIDO dentro
    # de iter_fallback_routes (mismo patrón que collect_beat_schedule con Cron).
    from milpa.Core.Http.Routing import FallbackRoute


def module_packages() -> list[str]:
    """TODOS los módulos presentes en app/Modules/ (escaneo del filesystem con
    pkgutil). No hay concepto de "activo/inactivo": un módulo existe si su
    carpeta existe, igual que Laravel descubre los packages instalados. El
    control de qué corre solo NO está aquí, sino en `@cron_task` (environments)
    + en si arrancas `celery beat`."""
    package = settings.modules_package
    try:
        modules_root = importlib.import_module(package)
    except ModuleNotFoundError:
        return []  # paquete de módulos no presente (p. ej. proyecto recién creado): cero módulos
    if not hasattr(modules_root, "__path__"):
        return []
    return [
        f"{package}.{info.name}"
        for info in pkgutil.iter_modules(modules_root.__path__)
        if info.ispkg and not info.name.startswith("_")
    ]


def _try_import(dotted_path: str) -> ModuleType | None:
    try:
        return importlib.import_module(dotted_path)
    except ModuleNotFoundError as error:
        # Faro: None solo si el módulo objetivo no existe (ausencia esperada); si el import
        # falla por un bug DENTRO del módulo del usuario, se re-lanza (nunca se traga en silencio).
        if _module_absent(error, dotted_path):
            return None
        raise


def import_all_models() -> None:
    """Registra TODAS las tablas en Base.metadata. Basta importar el paquete: su
    __init__ auto-importa todos los modelos (self-discovery con pkgutil), así agregar
    un modelo = crear su archivo; no hay lista manual en ningún __init__."""
    importlib.import_module(settings.models_package)


def import_all_tasks() -> None:
    """Importa Jobs/, Crons/ y Console/Commands/ de cada módulo para que sus decoradores
    (@job / @cron_task / @celery_app.task) queden registrados (los vuelve ejecutables; NO
    los dispara). `Crons/` va aparte de `Jobs/` a propósito: refuerza la separación mental
    job (on-demand) ≠ cron (agendado), igual que `Core/Jobs` vive separado de `Core/Cron`.

    El discovery usa `import_submodules` (pkgutil): escanea uno a uno los
    archivos de cada carpeta en vez de importar solo su `__init__`. Así un solo
    mecanismo cubre todo el discovery del monolito (mismo que `iter_cli_apps`),
    y los módulos ya no dependen de que sus `__init__.py` re-importen los
    archivos para que las tasks se registren.
    """
    for package in module_packages():
        import_submodules(f"{package}.Jobs")
        import_submodules(f"{package}.Crons")
        import_submodules(f"{package}.Console.Commands")


def import_all_seeders() -> None:
    """Importa Seeders/ de cada módulo para que sus subclases de `Seeder` se registren
    (las descubre `db:seed`). Mismo discovery por convención que tasks/commands."""
    for package in module_packages():
        import_submodules(f"{package}.Seeders")


def import_all_observers() -> None:
    """Importa Observers/ de cada módulo para que sus subclases de `Observer` se registren
    (las dispara `Events.dispatch`). Mismo discovery por convención que seeders."""
    for package in module_packages():
        import_submodules(f"{package}.Observers")


def import_all_handlers() -> None:
    """Importa Handlers/ de cada módulo para que sus `@handles(Cmd)` se registren
    (los resuelve `Mediator.send`). Mismo discovery por convención que seeders."""
    for package in module_packages():
        import_submodules(f"{package}.Handlers")


def import_all_policies() -> None:
    """Importa Policies/ de cada módulo para que sus `@policy(ability)` se registren en el Gate
    (adiós a `register_policies()` manual). Mismo discovery por convención que seeders."""
    for package in module_packages():
        import_submodules(f"{package}.Policies")


def collect_beat_schedule() -> dict[str, object]:
    """Arma el beat_schedule que `celery beat` programa, fusionando DOS fuentes:

    1. Los `@cron_task(schedule=...)` descubiertos (`registered_crons()`): cada uno
       se vuelve una entrada del beat, con su expresión cron de 5 campos convertida
       a `crontab` (vía `to_crontab`). La clave del dict es el nombre del cron (=
       nombre de la task de Celery); si declara `queue`, se enruta con
       `options={"queue": ...}` (el equivalente beat del `apply_async(queue=...)`
       que hace `schedule run`).
    2. Los `beat_schedule` declarados en cada `Console/Kernel.py` (la vía
       DECLARATIVA). Se aplican AL FINAL, así un nombre declarado en Kernel.py
       PRECEDE (sobrescribe) al cron auto-derivado con el mismo nombre.

    Que un cron entre al schedule NO equivale a EJECUTARLO: el beat solo AGENDA.
    Los gates (`environments`, anti-overlap por lock de redis) siguen viviendo en
    `@cron_task` y corren AL EJECUTAR dentro de su wrapper, no aquí. Y nada de esto
    corre si no arrancas el proceso `beat`. El discovery (`import_all_tasks()`) debe
    haber corrido antes para que `registered_crons()` esté poblado (lo garantiza
    CeleryApp en `on_after_configure`).
    """
    # Import DIFERIDO (no a nivel de módulo): Cron importa CeleryApp y CeleryApp
    # importa este Registry, así que importar Cron arriba cerraría el ciclo. Igual
    # que el discovery, esto se resuelve cuando la función corre (Celery ya
    # configurado), con todo el árbol cargado.
    from milpa.Core.Cron import registered_crons, to_crontab

    schedule: dict[str, object] = {}
    # (1) Auto-derivados de @cron_task. registered_crons() solo trae los que tienen
    # schedule (los sin cadencia ya quedan fuera, ver Cron.py).
    for rc in registered_crons():
        entry: dict[str, object] = {"task": rc.name, "schedule": to_crontab(rc.schedule)}
        if rc.queue is not None:
            entry["options"] = {"queue": rc.queue}
        schedule[rc.name] = entry
    # (2) Kernel.py por módulo, AL FINAL: precedencia en colisión de nombre.
    for package in module_packages():
        kernel = _try_import(f"{package}.Console.Kernel")
        if kernel and hasattr(kernel, "beat_schedule"):
            schedule.update(kernel.beat_schedule)
    return schedule


def _iter_http_modules(http_package: str) -> Iterator[ModuleType]:
    """Importa y rinde cada submódulo (recursivo) bajo Modules/<X>/Http/, más el
    propio paquete Http (por si el router vive en su __init__)."""
    package = _try_import(http_package)
    if package is None:
        return
    yield package
    if not hasattr(package, "__path__"):
        return
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{http_package}.", onerror=lambda _name: None):
        if info.name.rsplit(".", 1)[-1].startswith("_"):
            continue
        module = _try_import(info.name)
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
    for package in module_packages():
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
    for package in module_packages():
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
    for package in module_packages():
        module_name = package.rsplit(".", 1)[-1]
        static_dir = modules_dir / module_name / "Resources" / "Static"
        if static_dir.is_dir():
            yield f"/static/{module_name.lower()}", str(static_dir)


def iter_cli_apps() -> Iterator[tuple[str, typer.Typer]]:
    """Itera los sub-apps de Typer (grupo, sub_app) de todos los módulos presentes.

    Primero dispara el discovery por convención: para cada módulo importa los
    archivos de `Console/Commands` con `import_submodules` (pkgutil), lo que
    ejecuta los decoradores @console_command y llena el registro de Console.
    Después delega en `build_cli_apps()`, que arma un Typer por grupo desde ese
    registro ya poblado.

    El acoplamiento hacia los módulos es por imports DINÁMICOS (rutas en string):
    Core no importa Modules de forma estática, así que import-linter no marca una
    violación Core↛Modules.
    """
    for package in module_packages():
        import_submodules(f"{package}.Console.Commands")
    yield from build_cli_apps()
