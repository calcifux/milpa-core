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
from typing import Any, TypeVar

from fastapi import APIRouter

# Atributos donde se cuelga la metadata: en la FUNCIÓN (la ruta) y en la CLASE (el router armado).
ROUTE_ATTR = "__milpa_route__"
ROUTER_ATTR = "__milpa_router__"

F = TypeVar("F", bound=Callable[..., Any])
C = TypeVar("C", bound=type)


def _route_meta(func: Callable[..., Any]) -> dict[str, Any]:
    """Metadata de ruta de un método (la crea la primera vez). `methods` se acumula;
    `dependencies` lo rellenan también los decoradores de auth."""
    meta: dict[str, Any] | None = func.__dict__.get(ROUTE_ATTR)
    if meta is None:
        meta = {"methods": [], "path": "/", "kwargs": {}, "dependencies": []}
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


def add_route_dependency(func: Callable[..., Any], dependency: Any) -> None:
    """Anexa una dependency a la ruta de un método (lo usan `@Authenticated`/`@Roles`/`@Can`).
    Funciona sin importar el orden de decoradores: crea la metadata si aún no existe."""
    _route_meta(func)["dependencies"].append(dependency)


def Controller(
    prefix: str = "",
    *,
    tags: Sequence[str] | None = None,
    dependencies: Sequence[Any] | None = None,
) -> Callable[[C], C]:
    """Convierte una clase en un `APIRouter` auto-montable (≈ `@RestController` de Spring).

    `prefix`/`tags`/`dependencies` aplican a TODO el router (las `dependencies` corren antes de
    cada ruta, como un middleware del controller). El router queda en `cls.__milpa_router__` y el
    Registry lo descubre; la clase sigue siendo una clase usable.
    """

    def decorator(cls: C) -> C:
        instance = cls()  # singleton del proceso (stateless o auto-construye sus deps)
        router = APIRouter(
            prefix=prefix,
            tags=list(tags) if tags is not None else None,
            dependencies=list(dependencies) if dependencies is not None else None,
        )
        # Recorre los métodos en orden de definición; registra los marcados con un verbo.
        for name, attribute in list(vars(cls).items()):
            meta: dict[str, Any] | None = getattr(attribute, ROUTE_ATTR, None)
            if meta is None:
                continue
            endpoint = getattr(instance, name)  # bound method: self ya resuelto
            route_kwargs = dict(meta["kwargs"])
            extra_dependencies = meta["dependencies"]
            if extra_dependencies:
                route_kwargs["dependencies"] = [*route_kwargs.get("dependencies", []), *extra_dependencies]
            router.add_api_route(
                meta["path"],
                endpoint,
                methods=meta["methods"] or ["GET"],
                **route_kwargs,
            )
        setattr(cls, ROUTER_ATTR, router)
        return cls

    return decorator
