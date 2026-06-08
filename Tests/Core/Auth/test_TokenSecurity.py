"""Batería de SEGURIDAD de los JWT PROPIOS de milpa (HS256, `Tokens.py`): que `decode_token`
rechace alg:none, firma alterada, expirado, secreto equivocado, y —clave— que el algoritmo esté
PINEADO (un token con otro alg no pasa, aunque venga firmado con el secreto bueno). Sin BD.

`decode_token` lanza `jwt.PyJWTError` crudo (no HTTPException, a diferencia de Passport): es la
primitiva de validación, el carril web la envuelve aparte.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import jwt
import pytest
from jwt.utils import base64url_encode
from pytest import MonkeyPatch

from milpa.Core.Auth.Tokens import decode_token, issue_token
from milpa.Core.Config import settings

# ≥64 bytes a propósito: HS512 (test del pin) exige llave larga; evita InsecureKeyLengthWarning.
_SECRET = "secreto-de-prueba-no-para-prod-0123456789-abcdefghijklmnopqrstuvwxyz-0123456789"


@pytest.fixture(autouse=True)
def _hs256(monkeypatch: MonkeyPatch) -> None:
    """Fija un secreto + HS256 conocidos para toda la batería."""
    monkeypatch.setattr(settings, "jwt_secret", _SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")


def _claims(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"sub": "7", "exp": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)}
    base.update(overrides)
    return base


def _unsigned(**overrides: Any) -> str:
    """Crafta un token alg:none (sin firma) a mano."""
    header = base64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode()
    data = _claims(**overrides)
    data["exp"] = int(data["exp"].timestamp())
    payload = base64url_encode(json.dumps(data).encode()).decode()
    return f"{header}.{payload}."


# ── happy path ─────────────────────────────────────────────────────────────────────
def test_valid_token_roundtrips() -> None:
    assert decode_token(issue_token("7"))["sub"] == "7"


# ── alg:none ───────────────────────────────────────────────────────────────────────
def test_alg_none_is_rejected() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_token(_unsigned(sub="999"))


# ── firma alterada ─────────────────────────────────────────────────────────────────
def test_tampered_signature_is_rejected() -> None:
    header, payload, signature = issue_token("7").split(".")
    flipped = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    with pytest.raises(jwt.PyJWTError):
        decode_token(f"{header}.{payload}.{flipped}")


# ── expirado ───────────────────────────────────────────────────────────────────────
def test_expired_token_is_rejected() -> None:
    expired = jwt.encode(_claims(exp=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)), _SECRET, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired)


# ── secreto equivocado (atacante con OTRO secreto) ─────────────────────────────────
def test_wrong_secret_is_rejected() -> None:
    forged = jwt.encode(_claims(sub="999"), "secreto-del-atacante-largo-pero-equivocado-xyz", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(forged)


# ── algoritmo PINEADO: HS512 (aunque firmado con el secreto bueno) se rechaza ───────
def test_algorithm_is_pinned() -> None:
    """`settings.jwt_algorithm = HS256` → `decode` pinea `[HS256]`. Un token HS512 firmado con el
    MISMO secreto debe rechazarse: el algoritmo lo manda el servidor, NO el header del token."""
    other_alg = jwt.encode(_claims(), _SECRET, algorithm="HS512")
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_token(other_alg)
