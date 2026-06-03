"""Rate limiting sobre SlowAPI, en clave milpa: `@rate_limit("5/minute")` por ruta.

milpa NO reinventa el límite (SlowAPI/`limits` ya resuelven ventanas, estrategias y backends
Redis/memcached/memoria); solo lo envuelve para que (1) el dev escriba un decorador milpa-branded
en vez de acoplarse al singleton de SlowAPI, y (2) el 429 salga en RFC 9457 igual que TODO error
del framework, con `Retry-After` + `X-RateLimit-*` inyectados.

    @Post("/login")
    @rate_limit("5/minute")                 # el decorador de verbo va ARRIBA
    def login(self, request: Request, body: LoginInput) -> ...: ...

SlowAPI EXIGE `request: Request` en la firma del handler limitado (así engancha el contexto) y que
el decorador de verbo (`@Post`) quede por ENCIMA de `@rate_limit`. La clave por default es la IP del
cliente; pásale `key_func=` para limitar por otra cosa (p. ej. el usuario autenticado).

Config (Settings): `rate_limit_enabled` (off ⇒ no-op), `rate_limit_default` (límite global),
`rate_limit_storage_uri` ("memory://" por-proceso o "redis://…" en prod multi-worker),
`rate_limit_headers`. = el rate limiting de DRF, pero declarativo y con el mismo sobre de error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from milpa.Core.Config import settings
from milpa.Core.Http.ProblemDetails import PROBLEM_JSON_MEDIA_TYPE, build_problem
from milpa.Core.Http.Routing import add_route_wrapper

# Singleton del proceso: lee la config UNA vez al importar. La clave default = IP del cliente;
# `default_limits` aplica un tope global opcional (además de los @rate_limit por-ruta).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default] if settings.rate_limit_default else [],
    storage_uri=settings.rate_limit_storage_uri or None,
    headers_enabled=settings.rate_limit_headers,
    enabled=settings.rate_limit_enabled,
)


def rate_limit(
    limit_value: str, *, key_func: Callable[..., str] | None = None, **kwargs: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador `@rate_limit("5/minute")` para una ruta (≈ `@throttle` de DRF, declarativo).

    Acepta la sintaxis de SlowAPI/`limits`: "5/minute", "100/hour", "10/second;1000/day"… Pasa
    `key_func` para limitar por algo distinto a la IP (p. ej. por usuario). El resto de kwargs
    (`per_method`, `exempt_when`, `cost`…) se reenvían a `limiter.limit`. Recuerda: el handler DEBE
    tener `request: Request` y el `@Post/@Get` va por encima.

    NO envuelve aquí: MARCA la ruta (vía `add_route_wrapper`) para que el `@Controller` aplique el
    límite de SlowAPI al bound method — si lo aplicáramos a la función con `self`, SlowAPI cuenta
    `self` y le descuadra el índice de `request`. Así funciona idéntico en controllers class-based.
    """
    slowapi_decorator = limiter.limit(limit_value, key_func=key_func, **kwargs)

    def mark(func: Callable[..., Any]) -> Callable[..., Any]:
        add_route_wrapper(func, slowapi_decorator)
        return func

    return mark


async def _handle_rate_limit_exceeded(request: Request, exc: Exception) -> JSONResponse:
    """Traduce el 429 de SlowAPI al sobre RFC 9457 del framework (en vez del JSON propio de
    SlowAPI), e inyecta `Retry-After` + `X-RateLimit-*` que SlowAPI ya calculó para esta ruta."""
    assert isinstance(exc, RateLimitExceeded)
    response = JSONResponse(
        status_code=429,
        media_type=PROBLEM_JSON_MEDIA_TYPE,
        content=build_problem(
            status=429,
            title="Too Many Requests",
            detail=f"Límite de peticiones excedido ({exc.detail}).",
            code="rate_limit_exceeded",
        ),
    )
    # `view_rate_limit` lo deja SlowAPI en request.state al disparar el límite; con él calcula los
    # headers. Si faltara (forma defensiva, nunca-en-silencio), devolvemos el 429 igual, sin headers.
    view_limit = getattr(request.state, "view_rate_limit", None)
    if view_limit is not None:
        limiter._inject_headers(response, view_limit)
    return response


def register_rate_limit(app: FastAPI) -> None:
    """Cablea SlowAPI en la app: expone el limiter en `app.state` (lo exige) y registra el handler
    del 429 en formato RFC 9457. Lo llama `create_app`."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit_exceeded)
