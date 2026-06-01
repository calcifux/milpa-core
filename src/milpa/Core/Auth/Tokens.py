"""Emisión/validación de los JWT PROPIOS de milpa (HS256 por default, vía pyjwt).

Distinto de `Passport.py` (que valida tokens RS256 EXTERNOS de Laravel Passport): aquí milpa
emite sus propios tokens para apps nuevas. El secreto es `JWT_SECRET` (.env), obligatorio.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from milpa.Core.Config import settings


def issue_token(subject: str, *, extra_claims: dict[str, Any] | None = None) -> str:
    """Emite un JWT firmado con `sub`, `iat` y `exp` (+ claims extra opcionales)."""
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET vacío: define JWT_SECRET en .env para emitir/validar tokens propios.")
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_ttl_seconds),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Valida firma + expiración y devuelve los claims. Lanza `jwt.PyJWTError` si es inválido."""
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET vacío: define JWT_SECRET en .env para emitir/validar tokens propios.")
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
