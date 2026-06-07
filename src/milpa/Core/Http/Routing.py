"""Routing class-based estilo Spring/Litestar SOBRE FastAPI.

`@Controller("/cats", tags=["cats"])` sobre una clase + `@Get/@Post/@Put/@Patch/@Delete`
sobre sus métodos arma un `APIRouter` automáticamente. El Registry lo auto-monta igual que
cualquier router (no hay que listarlo). CONVIVE con el estilo función `router = APIRouter()`;
no lo reemplaza.

    @Controller("/cats", tags=["cats"])
    class CatsController:
        @Get("/")
        def index(self) -> list[str]: ...

        @Get("/{cat_id}")
        def show(self, cat_id: int) -> dict[str, int]: ...

        @Post("/", status_code=201)
        def store(self, body: CatInput) -> dict[str, str]: ...

Por qué **bound methods**: `@Controller` instancia la clase UNA vez (singleton) y registra los
métodos YA LIGADOS (`getattr(instance, name)`), así FastAPI ve solo los params reales
(path/query/body/`Depends`) y nunca intenta inyectar `self`. El controller puede tener estado o
construir sus dependencias en `__init__` (sin args por ahora; aún no hay contenedor DI).

Los decoradores de verbo aceptan los MISMOS kwargs que `APIRouter.add_api_route` (`status_code`,
`response_model`, `summary`, `dependencies`, `responses`, …): se pasan tal cual. Los decoradores de
auth (Fase D: `@Authenticated`/`@Roles`/`@Can`) anexan dependencies a la misma metadata.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any, TypeVar

from fastapi import APIRouter, Depends
from starlette.requests import Request

# Atributos donde se cuelga la metadata: en la FUNCIÓN (la ruta) y en la CLASE (el router armado
# + las rutas @Fallback acumuladas, que NO van al router del controller sino al final de create_app).
ROUTE_ATTR = "__milpa_route__"
ROUTER_ATTR = "__milpa_router__"
FALLBACKS_ATTR = "__milpa_fallbacks__"

# Una ruta @Fallback ya resuelta (endpoint ligado + lo que necesita `app.add_api_route`): el
# Registry la recolecta (`iter_fallback_routes`) y create_app la monta DESPUÉS de los mounts.
FallbackRoute = tuple[Callable[..., Any], str, list[str], dict[str, Any]]

F = TypeVar("F", bound=Callable[..., Any])
C = TypeVar("C", bound=type)


def _route_meta(func: Callable[..., Any]) -> dict[str, Any]:
    """Metadata de ruta de un método (la crea la primera vez). `methods` se acumula;
    `dependencies` lo rellenan también los decoradores de auth."""
    meta: dict[str, Any] | None = func.__dict__.get(ROUTE_ATTR)
    if meta is None:
        meta = {"methods": [], "path": "/", "kwargs": {}, "dependencies": [], "wrappers": [], "fallback": False}
        func.__dict__[ROUTE_ATTR] = meta
    return meta


def _verb(http_method: str) -> Callable[..., Callable[[F], F]]:
    """Fabrica un decorador de verbo (`Get`, `Post`, …) que marca el método con su ruta."""

    def factory(path: str = "/", **fastapi_kwargs: Any) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            meta = _route_meta(func)
            meta["methods"].append(http_method)
            meta["path"] = path
            meta["kwargs"].update(fastapi_kwargs)
            return func

        return decorator

    return factory


Get = _verb("GET")
Post = _verb("POST")
Put = _verb("PUT")
Patch = _verb("PATCH")
Delete = _verb("DELETE")


def Fallback[FuncT: Callable[..., Any]](func: FuncT) -> FuncT:
    """Marca una ruta para registrarla DESPUÉS de los mounts del kernel (/static, /vite,
    /status), NO dentro del router del controller. Es el mecanismo opt-in para un CATCH-ALL
    en la RAÍZ (un `@Get("/{path:path}")` con prefijo "") que sirve el shell de una SPA sin
    comerse los estáticos.

    EL PROBLEMA DEL ORDEN: `create_app` (Core/Http/Http.py) incluye los routers de los
    controllers ANTES de montar /static, /vite y /status; y en Starlette gana el PRIMER match
    de `app.routes`. Así que un catch-all raíz registrado como ruta normal se tragaría esos
    mounts (404 planos en lugar de los assets y el health check). Por eso, hasta ahora, una SPA
    debía usar un prefijo propio (`/app`) + un redirect de `/` para no chocar con los mounts.

    `@Fallback` invierte el orden SOLO para esa ruta: el `@Controller` NO la agrega a su router
    (la acumula en `cls.__milpa_fallbacks__`) y `create_app` la monta AL FINAL, tras los mounts
    — así /api, /static, /vite y /status ya ganaron su match y el catch-all solo recoge lo que
    nadie reclamó. Se combina con un verbo (el verbo da el path/methods; `@Fallback` solo marca
    el momento de registro). Estilo milpa: el opt-in vive en un decorador descubrible, no en
    plomería que cada app reescribe.

        @Controller("", tags=["spa"])
        class SpaController:
            @Fallback
            @Get("/{path:path}")
            def shell(self, request: Request, path: str) -> HTMLResponse: ...
    """
    _route_meta(func)["fallback"] = True
    return func


def add_route_dependency(func: Callable[..., Any], dependency: Any) -> None:
    """Anexa una dependency a la ruta de un método (lo usan `@Authenticated`/`@Roles`/`@Can`).
    Funciona sin importar el orden de decoradores: crea la metadata si aún no existe."""
    _route_meta(func)["dependencies"].append(dependency)


def add_route_wrapper(func: Callable[..., Any], wrapper: Callable[[Callable[..., Any]], Callable[..., Any]]) -> None:
    """Marca un decorador que el `@Controller` aplicará al endpoint YA LIGADO (bound method),
    no a la función con `self`. Lo necesitan los decoradores que DEBEN envolver el endpoint (no
    bastan dependencies) y asumen firma función-style — p. ej. SlowAPI en `@rate_limit`: contar
    `self` le descuadra el índice de `request`; envolver el bound method (firma ya sin `self`) lo
    arregla. Igual que `add_route_dependency`, no depende del orden de decoradores."""
    _route_meta(func)["wrappers"].append(wrapper)


def _set_api_version(version: str) -> Callable[[Request], None]:
    """Dependency de router que fija la versión de API de la ruta en `request.state`."""

    def dependency(request: Request) -> None:
        request.state.api_version = version

    return dependency


def api_version(request: Request) -> str | None:
    """La versión de API de la ruta actual (la del `@Controller(version=...)`), o `None` si la
    ruta no está versionada. Útil para ramificar o marcar deprecación dentro del handler.
    Úsalo con `Annotated[str | None, Depends(api_version)]` o `api_version(request)`."""
    return getattr(request.state, "api_version", None)


def Controller(
    prefix: str = "",
    *,
    tags: Sequence[str] | None = None,
    dependencies: Sequence[Any] | None = None,
    version: str | None = None,
) -> Callable[[C], C]:
    """Convierte una clase en un `APIRouter` auto-montable (≈ `@RestController` de Spring).

    `prefix`/`tags`/`dependencies` aplican a TODO el router (las `dependencies` corren antes de
    cada ruta, como un middleware del controller). El router queda en `cls.__milpa_router__` y el
    Registry lo descubre; la clase sigue siendo una clase usable.

    `version` (p. ej. `"v1"`) versiona la API por URL-path: el prefijo pasa a `/{version}{prefix}`
    (ej. `/v1/notes`), se agrega a los tags (Swagger agrupa por versión) y queda accesible en el
    handler vía `api_version(request)`. Evolucionas la API sin romper clientes (= DRF versioning).
    """

    def decorator(cls: C) -> C:
        instance = cls()  # singleton del proceso (stateless o auto-construye sus deps)
        effective_prefix = f"/{version}{prefix}" if version else prefix
        router_tags: list[str | Enum] = [*tags] if tags is not None else []
        router_dependencies: list[Any] = [*dependencies] if dependencies is not None else []
        if version:
            if version not in router_tags:
                router_tags.append(version)  # Swagger agrupa por versión
            router_dependencies.append(Depends(_set_api_version(version)))
        router = APIRouter(
            prefix=effective_prefix,
            tags=router_tags or None,
            dependencies=router_dependencies or None,
        )
        # Las rutas @Fallback NO entran al router del controller: se acumulan aquí y el Registry
        # las recolecta para que create_app las monte AL FINAL (ver Fallback). Path versionado por
        # el prefijo igual que las normales (un fallback bajo un controller versionado lo respeta).
        fallbacks: list[FallbackRoute] = []
        # Recorre los métodos en orden de definición; registra los marcados con un verbo.
        for name, attribute in list(vars(cls).items()):
            meta: dict[str, Any] | None = getattr(attribute, ROUTE_ATTR, None)
            if meta is None:
                continue
            endpoint = getattr(instance, name)  # bound method: self ya resuelto
            # Decoradores que DEBEN envolver (p. ej. SlowAPI): se aplican AQUÍ, sobre el bound
            # method (firma ya sin `self`), no en el cuerpo de la clase. Ver add_route_wrapper.
            for wrapper in meta["wrappers"]:
                endpoint = wrapper(endpoint)
            route_kwargs = dict(meta["kwargs"])
            extra_dependencies = meta["dependencies"]
            if extra_dependencies:
                route_kwargs["dependencies"] = [*route_kwargs.get("dependencies", []), *extra_dependencies]
            methods = meta["methods"] or ["GET"]
            if meta["fallback"]:
                # Misma resolución de path que una ruta normal, pero diferida al final de create_app.
                fallbacks.append((endpoint, f"{effective_prefix}{meta['path']}", methods, route_kwargs))
                continue
            router.add_api_route(meta["path"], endpoint, methods=methods, **route_kwargs)
        setattr(cls, ROUTER_ATTR, router)
        setattr(cls, FALLBACKS_ATTR, fallbacks)
        return cls

    return decorator
