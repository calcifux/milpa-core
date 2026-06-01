"""Guards: resuelven el usuario autenticado DESDE el request, por mecanismo.

- `JwtGuard`: bearer JWT propio de milpa (HS256). Para APIs / frontends separados.
- `PassportGuard`: bearer RS256 externo de Laravel Passport (reusa `Passport.py`). Para migrar.
- (Fase C) `SessionGuard`: cookie de sesión firmada. Para HTMX/browser.

`get_guard(name)` devuelve el guard por `AUTH_GUARD` o uno explícito (la facade `Auth` y las
dependencies lo usan). Cada guard SOLO lee el request y resuelve el user vía el `UserProvider`.
"""

from __future__ import annotations

from typing import Protocol

import jwt
from starlette.requests import Request

from milpa.Core.Auth.Contracts import Authenticatable
from milpa.Core.Auth.Passport import _decode_token as decode_passport_token
from milpa.Core.Auth.Providers import get_user_provider
from milpa.Core.Auth.Tokens import decode_token, issue_token
from milpa.Core.Config import settings


class Guard(Protocol):
    """Resuelve el usuario autenticado (o None) a partir del request."""

    def authenticate(self, request: Request) -> Authenticatable | None: ...


def bearer_token(request: Request) -> str | None:
    """Extrae el token de `Authorization: Bearer <token>` (o None)."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    return None


class JwtGuard:
    """Bearer JWT propio de milpa."""

    def authenticate(self, request: Request) -> Authenticatable | None:
        token = bearer_token(request)
        if not token:
            return None
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            return None  # token inválido/expirado → no autenticado (la dep decide si es 401)
        subject = payload.get("sub")
        if subject is None:
            return None
        return get_user_provider().by_id(subject)

    def issue(self, user: Authenticatable) -> str:
        """Emite un JWT para `user` (lo usa `Auth.attempt`)."""
        return issue_token(str(user.get_auth_identifier()))


class SessionGuard:
    """Sesión en cookie firmada (Starlette SessionMiddleware). Carril browser/HTMX."""

    def authenticate(self, request: Request) -> Authenticatable | None:
        # scope["session"] solo existe si SessionMiddleware está montado (SESSION_SECRET set).
        session = request.scope.get("session")
        if not session:
            return None
        subject = session.get("user_id")
        if subject is None:
            return None
        return get_user_provider().by_id(subject)


class PassportGuard:
    """Bearer RS256 externo de Laravel Passport (reusa la validación de `Passport.py`)."""

    def authenticate(self, request: Request) -> Authenticatable | None:
        token = bearer_token(request)
        if not token:
            return None
        claims = decode_passport_token(token)  # 401 (HTTPException) si el token es inválido
        subject = claims.get("sub")
        if subject is None:
            return None
        return get_user_provider().by_id(subject)


def get_guard(name: str | None = None) -> Guard:
    """El guard por `AUTH_GUARD` (o el `name` explícito). SessionGuard se añade en la Fase C."""
    guard_name = name or settings.auth_guard
    if guard_name == "jwt":
        return JwtGuard()
    if guard_name == "session":
        return SessionGuard()
    if guard_name == "passport":
        return PassportGuard()
    raise ValueError(f"AUTH_GUARD desconocido: {guard_name!r} (usa jwt|session|passport).")
