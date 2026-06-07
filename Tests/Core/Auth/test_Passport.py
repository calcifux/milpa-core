"""Tests del hook de revocación de Passport (`set_revocation_check`) — sin BD.

milpa-core PURO: el revocado se SIMULA con la fn del setter (no hay tabla
`oauth_access_tokens` aquí; eso lo aporta la app que migra). Llaves RSA efímeras,
mismo patrón que `test_Scopes`/`test_PassportGuard`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pytest import MonkeyPatch

import milpa.Core.Auth.Passport as Passport
from milpa.Core.Auth import get_current_token, set_revocation_check
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


@pytest.fixture(autouse=True)
def _restaura_hook() -> Iterator[None]:
    """El hook es un GLOBAL del módulo: hay que restaurarlo para no filtrar estado."""
    original: Callable[[str | None], bool] = Passport._is_revoked
    yield
    Passport._is_revoked = original


def _cred(pem_privada: bytes, jti: str = "jti-1") -> HTTPAuthorizationCredentials:
    token = jwt.encode(
        {"sub": "7", "jti": jti, "scopes": [], "exp": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)},
        pem_privada,
        algorithm="RS256",
    )
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_default_no_revoca(llaves_rsa: bytes) -> None:
    assert get_current_token(_cred(llaves_rsa)).user_id == "7"


def test_set_revocation_check_da_401(llaves_rsa: bytes) -> None:
    set_revocation_check(lambda jti: jti == "jti-1")
    with pytest.raises(HTTPException) as exc:
        get_current_token(_cred(llaves_rsa))
    assert exc.value.status_code == 401


def test_monkeypatch_directo_sigue_funcionando(llaves_rsa: bytes) -> None:
    """Compat del hook viejo: rebind directo del global sigue siendo válido."""
    Passport._is_revoked = lambda jti: True
    with pytest.raises(HTTPException) as exc:
        get_current_token(_cred(llaves_rsa))
    assert exc.value.status_code == 401
