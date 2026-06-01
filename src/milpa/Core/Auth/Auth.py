"""Facade `Auth` (≈ Laravel) + dependencies de FastAPI + `current_user` (contextvar).

- `Auth.attempt(email, pw)` → JWT (login de API) · `Auth.validate_credentials(...)` → user|None.
- `Auth.user()/id()/check()` → leen el usuario del request actual (contextvar, lo fija la dep).
- `authenticated` / `optional_user` / `guarded(name)` → dependencies que resuelven el user,
  fijan el contextvar y devuelven el usuario (401 vía `UnauthorizedError` cuando es requerido).

Las dependencies son **async**: una dep sync corre en threadpool y su `contextvar.set()` no
llegaría al endpoint (mismo motivo que el locale). El trabajo BLOQUEANTE del guard (cargar el
user de la BD) va a un threadpool; el `set` del contextvar ocurre en el contexto async.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from starlette.requests import Request

from milpa.Core.Auth.Contracts import Authenticatable
from milpa.Core.Auth.Guards import JwtGuard, get_guard
from milpa.Core.Auth.Providers import get_user_provider
from milpa.Core.Errors import UnauthorizedError

_current_user: ContextVar[Authenticatable | None] = ContextVar("current_user", default=None)


def set_current_user(user: Authenticatable | None) -> None:
    """Fija el usuario del request actual (lo llaman las dependencies)."""
    _current_user.set(user)


class Auth:
    """Punto de entrada para login y usuario actual (= la facade `Auth` de Laravel)."""

    @staticmethod
    def validate_credentials(identifier: str, password: str) -> Authenticatable | None:
        provider = get_user_provider()
        user = provider.by_identifier(identifier)
        if user is not None and provider.validate(user, password):
            return user
        return None

    @staticmethod
    def attempt(identifier: str, password: str) -> str | None:
        """Login de API: valida credenciales y devuelve un JWT (o None si fallan)."""
        user = Auth.validate_credentials(identifier, password)
        return JwtGuard().issue(user) if user is not None else None

    @staticmethod
    def login(request: Request, user: Authenticatable) -> None:
        """Inicia sesión por COOKIE (carril browser): guarda el id en la sesión firmada.
        Requiere SessionMiddleware montado (SESSION_SECRET en .env)."""
        request.session["user_id"] = str(user.get_auth_identifier())

    @staticmethod
    def logout(request: Request) -> None:
        """Cierra la sesión por cookie (vacía la sesión)."""
        request.session.clear()

    @staticmethod
    def user() -> Authenticatable | None:
        return _current_user.get()

    @staticmethod
    def id() -> Any:
        user = _current_user.get()
        return user.get_auth_identifier() if user is not None else None

    @staticmethod
    def check() -> bool:
        return _current_user.get() is not None


async def _resolve(request: Request, guard_name: str | None) -> Authenticatable | None:
    # El guard puede tocar la BD (cargar el user) → threadpool; el set va en el contexto async.
    user = await run_in_threadpool(get_guard(guard_name).authenticate, request)
    set_current_user(user)
    return user


async def authenticated(request: Request) -> Authenticatable:
    """Dependency: exige usuario autenticado (guard por default). 401 si no hay."""
    user = await _resolve(request, None)
    if user is None:
        raise UnauthorizedError("No autenticado.")
    return user


async def optional_user(request: Request) -> Authenticatable | None:
    """Dependency: resuelve el user si lo hay (sin 401). Útil para vistas públicas con estado."""
    return await _resolve(request, None)


def guarded(name: str) -> Callable[[Request], Awaitable[Authenticatable]]:
    """Dependency factory para un guard EXPLÍCITO (p. ej. `guarded('jwt')` en la API y
    `guarded('session')` en el browser dentro de la MISMA app)."""

    async def dependency(request: Request) -> Authenticatable:
        user = await _resolve(request, name)
        if user is None:
            raise UnauthorizedError("No autenticado.")
        return user

    return dependency


# Azúcar para inyectar el usuario en un endpoint: `def me(user=CurrentUser): ...`
CurrentUser = Depends(authenticated)
OptionalUser = Depends(optional_user)
