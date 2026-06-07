"""Tests de `require_any_scope` (el `scope:` any-of de Passport) — sin BD, en memoria.

milpa-core PURO: sin tabla `oauth_access_tokens` ni servicio de revocación (eso es de
la app que migra). Solo se valida firma + el any-of de scopes. Llaves RSA efímeras y
tokens firmados ad-hoc, mismo arsenal que `test_PassportGuard`.
"""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pytest import MonkeyPatch

from milpa.Core.Auth import TokenPrincipal, get_current_token, require_any_scope
from milpa.Core.Config import settings


@pytest.fixture
def llaves_rsa(monkeypatch: MonkeyPatch) -> bytes:
    """Par RS256 efímero: parcha la pública en settings y devuelve la privada (PEM)."""
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_privada = privada.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    pem_publica = privada.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    monkeypatch.setattr(settings, "passport_public_key", pem_publica.decode())
    return pem_privada


def _validar(pem_privada: bytes, *, scopes: list[str]) -> TokenPrincipal:
    """Token sintético → la MISMA cadena de dependencias que usa el endpoint."""
    token = jwt.encode(
        {"sub": "7", "jti": "jti-1", "scopes": scopes, "exp": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)},
        pem_privada,
        algorithm="RS256",
    )
    credenciales = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    principal = get_current_token(credenciales)
    return require_any_scope("auctioneer_invoice_read", "op_site")(principal)


def test_con_uno_de_los_scopes_basta(llaves_rsa: bytes) -> None:
    assert _validar(llaves_rsa, scopes=["op_site", "profile"]).token_id == "jti-1"


def test_sin_ninguno_da_403(llaves_rsa: bytes) -> None:
    with pytest.raises(HTTPException) as exc:
        _validar(llaves_rsa, scopes=["profile"])
    assert exc.value.status_code == 403
    # El 403 es GENÉRICO a propósito: no filtra qué scopes darían acceso.
    assert "auctioneer_invoice_read" not in str(exc.value.detail)


def test_token_sin_scopes_da_403(llaves_rsa: bytes) -> None:
    with pytest.raises(HTTPException) as exc:
        _validar(llaves_rsa, scopes=[])
    assert exc.value.status_code == 403
