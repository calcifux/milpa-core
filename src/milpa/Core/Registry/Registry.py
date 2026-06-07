"""Registro del monolito modular: descubre y ensambla los módulos presentes.

Layout estilo Laravel (PascalCase). Los módulos viven en `settings.modules_package`
(default del skeleton: `app.Modules`; aquí en el repo: `milpa.Modules`) y se
descubren SOLOS escaneando esa carpeta con pkgutil.

ENCARPETADO LIBRE (estilo milpa, sin estructura rígida). El discovery YA NO exige
una jerarquía fija dentro de cada módulo: importa TODO el árbol del módulo de forma
recursiva (`import_submodules(package, recursive=True)`), así los decoradores
(@job / @cron_task / @console_command / @handles / @policy / la subclase de Seeder u
Observer) corren vivan donde vivan sus archivos. Organiza tu app como quieras; para
una prueba de concepto puedes escribir TODO de corrido en un solo archivo y funciona
igual.

milpa PROPONE (como sugerencia de LECTURA, NO como obligación) un layout: las carpetas
`Http/`, `Jobs/`, `Crons/`, `Observers/`, `Handlers/`, `Policies/`, `Seeders/` y
`Console/Commands/` son la convención que generan los `make:*`. Pero como el barrido
baja por TODO el árbol, cualquier otro encarpetado (subcarpetas, archivos sueltos)
funciona idéntico. Lo especial sigue siendo `Console/Kernel.py`: la VÍA DECLARATIVA del
beat_schedule, con PRECEDENCIA. Porque ahora los `@cron_task` descubiertos TAMBIÉN
alimentan el beat (se convierten a crontab y se agendan solos), Kernel.py deja de ser la
única fuente y pasa a ser la declaración explícita que GANA si su nombre colisiona con un
cron auto-derivado.

OJO (decisión consciente del discovery libre): como el barrido recursivo importa el
árbol COMPLETO, en CLI/worker también se importan los archivos de `Http/` de cada
módulo. No pasa nada por diseño: los decoradores de ruta (@Get/@Post/@Controller) SOLO
REGISTRAN en estructuras del proceso; quien SIRVE las rutas es `create_app` por la vía
web (`iter_routers`/`iter_fallback_routes`). Importar un controller fuera del proceso
web no levanta nada.

Tener un módulo presente NO dispara nada por sí mismo:
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


def _import_all_modules() -> None:
    """Corazón del discovery libre: importa TODO el árbol de cada módulo presente
    (`import_submodules(package, recursive=True)`). Idempotente — `sys.modules`
    cachea, así llamarlo varias veces no reimporta. Es lo que vuelve la estructura
    interna del módulo IRRELEVANTE para el registro: corra el decorador donde corra,
    su archivo se importa.

    Las cinco `import_all_*` de abajo (tasks/seeders/observers/handlers/policies)
    delegan TODAS aquí (hacen exactamente lo mismo). Es deliberado: con el
    encarpetado libre ya no hay una carpeta concreta que escanear, así que el único
    barrido honesto es el árbol completo.
    """
    for package in module_packages():
        import_submodules(package, recursive=True)


def import_all_tasks() -> None:
    """Importa el árbol completo de cada módulo para que las tasks (@job / @cron_task /
    @celery_app.task) queden registradas (las vuelve ejecutables; NO las dispara).

    Por qué sigue existiendo (y no se fusionó con las otras cuatro): el nombre es
    DOCUMENTACIÓN en el call-site — `import_all_tasks()` en CeleryApp dice "estoy
    cargando tasks". Con el encarpetado libre ya no importa una carpeta concreta
    (`Jobs/`, `Crons/`), por eso las cinco delegan en `_import_all_modules` (un
    solo barrido recursivo del árbol); las mantenemos separadas para conservar la
    claridad de cada call-site y dejar la puerta abierta a re-especializarlas en el
    futuro (p. ej. filtrar por convención) sin tocar a quien las llama.
    """
    _import_all_modules()


def import_all_seeders() -> None:
    """Importa el árbol completo de cada módulo para que las subclases de `Seeder`
    se registren (las descubre `db:seed`).

    Alias de claridad (ver `import_all_tasks`): las cinco `import_all_*` hacen lo
    mismo —un barrido recursivo del árbol del módulo— pero cada nombre documenta su
    call-site (aquí: `db:seed` cargando seeders) y deja la opción futura de
    re-especializar el discovery sin cambiar al llamador.
    """
    _import_all_modules()


def import_all_observers() -> None:
    """Importa el árbol completo de cada módulo para que las subclases de `Observer`
    se registren (las dispara `Events.dispatch`).

    Alias de claridad (ver `import_all_tasks`): las cinco `import_all_*` hacen lo
    mismo —un barrido recursivo del árbol del módulo— pero cada nombre documenta su
    call-site (aquí: el bootstrap de eventos cargando observers) y deja abierta la
    re-especialización futura sin cambiar al llamador.
    """
    _import_all_modules()


def import_all_handlers() -> None:
    """Importa el árbol completo de cada módulo para que los `@handles(Cmd)` se
    registren (los resuelve `Mediator.send`).

    Alias de claridad (ver `import_all_tasks`): las cinco `import_all_*` hacen lo
    mismo —un barrido recursivo del árbol del módulo— pero cada nombre documenta su
    call-site (aquí: el Mediator cargando handlers) y deja abierta la
    re-especialización futura sin cambiar al llamador.
    """
    _import_all_modules()


def import_all_policies() -> None:
    """Importa el árbol completo de cada módulo para que sus `@policy(ability)` se
    registren en el Gate (adiós a `register_policies()` manual).

    Alias de claridad (ver `import_all_tasks`): las cinco `import_all_*` hacen lo
    mismo —un barrido recursivo del árbol del módulo— pero cada nombre documenta su
    call-site (aquí: el Gate cargando policies) y deja abierta la re-especialización
    futura sin cambiar al llamador.
    """
    _import_all_modules()


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
    # configurado), con todo el árbol cargado. qualified_queue (Core/CeleryApp) va
    # diferido por la misma razón: CeleryApp importa este Registry.
    from milpa.Core.CeleryApp import qualified_queue
    from milpa.Core.Cron import registered_crons, to_crontab

    schedule: dict[str, object] = {}
    # (1) Auto-derivados de @cron_task. registered_crons() solo trae los que tienen
    # schedule (los sin cadencia ya quedan fuera, ver Cron.py).
    for rc in registered_crons():
        entry: dict[str, object] = {"task": rc.name, "schedule": to_crontab(rc.schedule)}
        if rc.queue is not None:
            # qualified_queue aplica el QUEUE_NAMESPACE (bus compartido) si hay; igual que el
            # apply_async(queue=...) de `schedule run`, pero para la vía beat.
            entry["options"] = {"queue": qualified_queue(rc.queue)}
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

    Primero dispara el discovery: para cada módulo importa TODO su árbol con
    `import_submodules(package, recursive=True)`, lo que ejecuta los decoradores
    @console_command vivan donde vivan (milpa PROPONE `Console/Commands/` para el
    automontaje, pero el barrido recursivo encuentra el command en cualquier
    carpeta — incluso todo de corrido en un solo archivo). Después delega en
    `build_cli_apps()`, que arma un Typer por grupo desde el registro ya poblado.

    El acoplamiento hacia los módulos es por imports DINÁMICOS (rutas en string):
    Core no importa Modules de forma estática, así que import-linter no marca una
    violación Core↛Modules.
    """
    for package in module_packages():
        import_submodules(package, recursive=True)
    yield from build_cli_apps()
