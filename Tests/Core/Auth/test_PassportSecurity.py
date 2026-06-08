"""Batería de SEGURIDAD del puente Passport (RS256): que la validación rechace los ataques
clásicos de JWT — alg:none, confusión RS256→HS256, firma/payload alterados, expirado, llave
equivocada, audiencia equivocada. Sin BD; llaves RSA efímeras (mismo patrón que test_Passport).

Estos tests BLINDAN la costura que escribimos a mano (CÓMO llamamos a pyjwt): pyjwt hace la
matemática de la firma, pero el pineo del algoritmo (`algorithms=["RS256"]`) y la verificación de
claims son nuestros. Si alguien afloja el pin o desactiva una verificación, el CI se pone rojo —
ese es el punto de este archivo: que la decisión de seguridad la sostenga el gate, no la memoria.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.utils import base64url_decode, base64url_encode
from pytest import MonkeyPatch

from milpa.Core.Auth import get_current_token
from milpa.Core.Config import settings


def _generate_rsa() -> tuple[bytes, str]:
    """Par RS256 efímero → (privada PEM bytes, pública PEM str)."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    pub_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return priv_pem, pub_pem.decode()


@pytest.fixture
def rsa_keys(monkeypatch: MonkeyPatch) -> tuple[bytes, str]:
    """Parcha la PÚBLICA en settings (y limpia path/audiencia); devuelve (privada, pública)."""
    priv_pem, pub_pem = _generate_rsa()
    monkeypatch.setattr(settings, "passport_public_key", pub_pem)
    monkeypatch.setattr(settings, "passport_public_key_path", None)
    monkeypatch.setattr(settings, "passport_expected_audience", None)
    return priv_pem, pub_pem


def _claims(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sub": "7",
        "jti": "jti-1",
        "scopes": [],
        "exp": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5),
    }
    base.update(overrides)
    return base


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _rs256(priv_pem: bytes, **overrides: Any) -> str:
    return jwt.encode(_claims(**overrides), priv_pem, algorithm="RS256")


def _json_claims(**overrides: Any) -> bytes:
    """Serializa claims a JSON crudo (para crafteo manual): convierte exp datetime → timestamp."""
    data = _claims(**overrides)
    data["exp"] = int(data["exp"].timestamp())
    return json.dumps(data).encode()


# ── happy path (baseline: que los rechazos de abajo signifiquen algo) ──────────────
def test_valid_rs256_token_is_accepted(rsa_keys: tuple[bytes, str]) -> None:
    priv_pem, _ = rsa_keys
    assert get_current_token(_creds(_rs256(priv_pem))).user_id == "7"


# ── alg:none → sin firma, debe rechazarse ──────────────────────────────────────────
def test_alg_none_is_rejected(rsa_keys: tuple[bytes, str]) -> None:
    header = base64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode()
    payload = base64url_encode(_json_claims(sub="999")).decode()
    forged = f"{header}.{payload}."  # tercer segmento vacío = sin firma
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(forged))
    assert exc.value.status_code == 401


# ── confusión RS256 → HS256: EL ataque crítico ─────────────────────────────────────
def test_rs256_to_hs256_confusion_is_rejected(rsa_keys: tuple[bytes, str]) -> None:
    """Forjar un HS256 usando la LLAVE PÚBLICA como secreto HMAC (la pública es... pública).
    Como `_decode_token` pinea `["RS256"]`, el servidor ni intenta HS256 → rechazado. Si alguien
    metiera HS256 a la lista de algoritmos, ESTE test truena: es el guardián del bug catastrófico.

    Doble capa: `jwt.encode` se NIEGA a usar un PEM como secreto HMAC (pyjwt ya cazó el ataque),
    así que forjamos el token A MANO (como haría un atacante) para probar NUESTRO pin, no el de pyjwt.
    """
    _, pub_pem = rsa_keys
    header = base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = base64url_encode(_json_claims(sub="999"))
    signing_input = header + b"." + payload
    signature = base64url_encode(hmac.new(pub_pem.encode(), signing_input, hashlib.sha256).digest())
    forged = (signing_input + b"." + signature).decode()
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(forged))
    assert exc.value.status_code == 401


# ── firma alterada ─────────────────────────────────────────────────────────────────
def test_tampered_signature_is_rejected(rsa_keys: tuple[bytes, str]) -> None:
    priv_pem, _ = rsa_keys
    header, payload, signature = _rs256(priv_pem).split(".")
    flipped = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(f"{header}.{payload}.{flipped}"))
    assert exc.value.status_code == 401


# ── payload alterado: re-pegar la firma vieja a claims nuevos (escalar usuario) ─────
def test_tampered_payload_is_rejected(rsa_keys: tuple[bytes, str]) -> None:
    priv_pem, _ = rsa_keys
    header, payload, signature = _rs256(priv_pem, sub="7").split(".")
    original: dict[str, Any] = json.loads(base64url_decode(payload))
    original["sub"] = "999"  # me hago pasar por otro sin re-firmar
    forged_payload = base64url_encode(json.dumps(original).encode()).decode()
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(f"{header}.{forged_payload}.{signature}"))
    assert exc.value.status_code == 401


# ── expirado ───────────────────────────────────────────────────────────────────────
def test_expired_token_is_rejected(rsa_keys: tuple[bytes, str]) -> None:
    priv_pem, _ = rsa_keys
    token = _rs256(priv_pem, exp=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1))
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(token))
    assert exc.value.status_code == 401


# ── firmado por OTRO emisor (no la pública configurada) ────────────────────────────
def test_token_from_wrong_key_is_rejected(rsa_keys: tuple[bytes, str]) -> None:
    other_priv, _ = _generate_rsa()
    token = jwt.encode(_claims(), other_priv, algorithm="RS256")
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(token))
    assert exc.value.status_code == 401


# ── audiencia ──────────────────────────────────────────────────────────────────────
def test_wrong_audience_is_rejected(rsa_keys: tuple[bytes, str], monkeypatch: MonkeyPatch) -> None:
    priv_pem, _ = rsa_keys
    monkeypatch.setattr(settings, "passport_expected_audience", "api-prod")
    token = _rs256(priv_pem, aud="api-OTRA")
    with pytest.raises(HTTPException) as exc:
        get_current_token(_creds(token))
    assert exc.value.status_code == 401


def test_correct_audience_is_accepted(rsa_keys: tuple[bytes, str], monkeypatch: MonkeyPatch) -> None:
    priv_pem, _ = rsa_keys
    monkeypatch.setattr(settings, "passport_expected_audience", "api-prod")
    token = _rs256(priv_pem, aud="api-prod")
    assert get_current_token(_creds(token)).user_id == "7"
