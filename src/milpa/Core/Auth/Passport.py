"""Validación de access tokens de Laravel Passport (OAuth2, RS256).

Verifica firma + claims con la llave PÚBLICA del legacy. La revocación contra
oauth_access_tokens queda como hook (_is_revoked) para cuando migremos eso: la
API pública para conectarlo es `set_revocation_check(fn)`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from milpa.Core.Config import settings

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass
class TokenPrincipal:
    """Lo que sabemos del llamante una vez validado el token."""

    user_id: str | None
    client_id: str | None
    token_id: str | None
    scopes: list[str] = field(default_factory=list)


def _default_revocation_check(token_id: str | None) -> bool:
    # TODO: consultar oauth_access_tokens.revoked al migrar ese módulo.
    return False


# Hook de revocación: por default no revoca (solo firma/exp/aud). Se rebinda con
# `set_revocation_check(fn)` (o el viejo `Passport._is_revoked = fn`). El call-site lo
# lee como GLOBAL en runtime, así que ambos caminos siguen siendo válidos. Anotado como
# Callable para que la reasignación sea type-compatible bajo mypy --strict.
_is_revoked: Callable[[str | None], bool] = _default_revocation_check


def set_revocation_check(check: Callable[[str | None], bool]) -> None:
    """Registra la verificación de revocación que `get_current_token` consultará.

    Punto de extensión PÚBLICO del hook que milpa deja designado: por default
    `_is_revoked` devuelve False (solo se valida firma/exp/aud). Una app que migra
    desde Laravel conecta aquí su consulta contra `oauth_access_tokens` (estilo
    strangler). `check(token_id) -> True` significa REVOCADO (la dependency lanza 401).

        from milpa.Core.Auth import set_revocation_check
        set_revocation_check(lambda jti: jti is None or not mi_servicio.is_active(jti))

    Equivale al rebind directo `Passport._is_revoked = fn`, que sigue siendo válido:
    el call-site lee el global en runtime.
    """
    global _is_revoked
    _is_revoked = check


def _decode_token(token: str) -> dict[str, Any]:
    public_key = settings.load_passport_public_key()
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth no configurada: falta PASSPORT_PUBLIC_KEY(_PATH) en .env",
        )

    verification_options = {"verify_aud": settings.passport_expected_audience is not None}
    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.passport_expected_audience,
            options=verification_options,  # type: ignore[arg-type]
        )
    except jwt.PyJWTError as exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exception}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exception


def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenPrincipal:
    """Dependencia FastAPI: valida el Bearer token y devuelve el principal."""
    claims = _decode_token(credentials.credentials)

    token_id = claims.get("jti")
    if _is_revoked(token_id):
        raise HTTPException(status_code=401, detail="Token revocado")

    audience = claims.get("aud")
    return TokenPrincipal(
        user_id=claims.get("sub"),
        client_id=audience if isinstance(audience, str) else None,
        token_id=token_id,
        scopes=claims.get("scopes", []) or [],
    )


def require_scopes(*required_scopes: str) -> Callable[..., TokenPrincipal]:
    """Fábrica de dependencia que exige scopes concretos."""

    def check_scopes(
        principal: TokenPrincipal = Depends(get_current_token),
    ) -> TokenPrincipal:
        missing_scopes = [s for s in required_scopes if s not in principal.scopes]
        if missing_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Faltan scopes: {', '.join(missing_scopes)}",
            )
        return principal

    return check_scopes


def require_any_scope(*accepted_scopes: str) -> Callable[..., TokenPrincipal]:
    """Fábrica de dependencia que exige ALGUNO de `accepted_scopes` (any-of).

    Complemento de `require_scopes` (all-of): es el `scope:a,b` (CheckForAnyScope) de
    Laravel Passport, frente al `scopes:a,b` (CheckScopes) que cubre `require_scopes`.
    El 403 es genérico a propósito: no revela qué scopes darían acceso.
    """

    def check_any_scope(
        principal: TokenPrincipal = Depends(get_current_token),
    ) -> TokenPrincipal:
        if not set(accepted_scopes) & set(principal.scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar la acción",
            )
        return principal

    return check_any_scope
