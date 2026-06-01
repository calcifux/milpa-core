"""Autorización: RBAC (roles) + ABAC (Gates/Policies estilo Laravel).

- **RBAC** — control por ROL: `require_roles("admin")` (dependency) y `@Roles("admin")`
  (decorador de método de `@Controller`). Autentica y exige que el user tenga alguno de los roles.
- **ABAC** — control por ATRIBUTOS/policy: `Gate.define(ability, fn)` registra una policy
  `(user, resource) -> bool`; `Gate.authorize(ability, resource)` lanza `ForbiddenError` si no
  aplica. Úsalo DENTRO del handler tras cargar el recurso (p. ej. "solo el dueño edita su nota").
  `@Can(ability)` protege rutas para abilities SIN recurso concreto (p. ej. `note.create`).

`guard=` permite fijar el carril (jwt/session/passport) por ruta; None usa `AUTH_GUARD`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends
from starlette.requests import Request

from milpa.Core.Auth.Auth import Auth, _resolve
from milpa.Core.Auth.Contracts import Authenticatable
from milpa.Core.Errors import ForbiddenError, UnauthorizedError

# ---------------------------------------------------------------- RBAC (roles)


def require_roles(*roles: str, guard: str | None = None) -> Callable[[Request], Awaitable[Authenticatable]]:
    """Dependency: autentica y exige que el user tenga ALGUNO de `roles` (si no, 403)."""

    async def dependency(request: Request) -> Authenticatable:
        user = await _resolve(request, guard)
        if user is None:
            raise UnauthorizedError("No autenticado.")
        if not set(user.get_roles()) & set(roles):
            raise ForbiddenError("Permisos insuficientes.", details={"required_roles": list(roles)})
        return user

    return dependency


def Roles(*roles: str, guard: str | None = None) -> Callable[[Any], Any]:
    """Decorador de método de `@Controller`: exige roles (azúcar sobre `require_roles`)."""

    def decorator(func: Any) -> Any:
        from milpa.Core.Http.Routing import add_route_dependency

        add_route_dependency(func, Depends(require_roles(*roles, guard=guard)))
        return func

    return decorator


# --------------------------------------------------------- ABAC (Gate/Policy)

# Una policy decide `(user, resource) -> bool`. `user` puede ser None (anónimo).
PolicyFn = Callable[[Authenticatable | None, Any], bool]
_policies: dict[str, PolicyFn] = {}


def reset_policies() -> None:
    """Limpia el registro de policies (SOLO para tests)."""
    _policies.clear()


class Gate:
    """Registro y evaluación de policies (≈ `Gate` de Laravel)."""

    @staticmethod
    def define(ability: str, policy: PolicyFn) -> None:
        """Registra la policy de una ability (p. ej. `Gate.define("note.update", fn)`)."""
        _policies[ability] = policy

    @staticmethod
    def allows(ability: str, resource: Any = None, *, user: Authenticatable | None = None) -> bool:
        actor = user if user is not None else Auth.user()
        policy = _policies.get(ability)
        if policy is None:
            return False  # sin policy registrada => denegado por seguridad
        return bool(policy(actor, resource))

    @staticmethod
    def denies(ability: str, resource: Any = None, *, user: Authenticatable | None = None) -> bool:
        return not Gate.allows(ability, resource, user=user)

    @staticmethod
    def authorize(ability: str, resource: Any = None, *, user: Authenticatable | None = None) -> None:
        """Lanza `ForbiddenError` (403 problem+json) si la policy no autoriza."""
        if not Gate.allows(ability, resource, user=user):
            raise ForbiddenError("No autorizado para esta acción.", details={"ability": ability})


def _can_dependency(ability: str, guard: str | None) -> Callable[[Request], Awaitable[Authenticatable]]:
    async def dependency(request: Request) -> Authenticatable:
        user = await _resolve(request, guard)
        if user is None:
            raise UnauthorizedError("No autenticado.")
        Gate.authorize(ability, None, user=user)
        return user

    return dependency


def Can(ability: str, *, guard: str | None = None) -> Callable[[Any], Any]:
    """Decorador de método: exige la ability SIN recurso (p. ej. `note.create`). Para abilities
    con recurso concreto, usa `Gate.authorize(ability, recurso)` dentro del handler."""

    def decorator(func: Any) -> Any:
        from milpa.Core.Http.Routing import add_route_dependency

        add_route_dependency(func, Depends(_can_dependency(ability, guard)))
        return func

    return decorator
