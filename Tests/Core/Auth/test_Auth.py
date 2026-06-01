"""Tests del carril JWT: tokens, facade Auth y la dependency `authenticated`.

Sin BD: se inyecta un UserProvider FAKE (set_user_provider) y se ejercita el flujo real de
emisión/validación de JWT propios. El JWT_SECRET se fija por monkeypatch.
"""

from __future__ import annotations

from collections.abc import Iterator

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from milpa.Core.Auth import Auth, Authenticatable, Hash, authenticated, set_user_provider
from milpa.Core.Auth.Tokens import decode_token, issue_token
from milpa.Core.Config import settings
from milpa.Core.Http.Http import create_app

# Secreto de prueba ≥32 bytes (evita el InsecureKeyLengthWarning de pyjwt para HS256).
_TEST_SECRET = "test-secret-please-change-0123456789-abcdef"


class _FakeUser:
    def __init__(self, identifier: int, password_hash: str) -> None:
        self._id = identifier
        self._password = password_hash

    def get_auth_identifier(self) -> int:
        return self._id

    def get_auth_password(self) -> str:
        return self._password

    def get_roles(self) -> list[str]:
        return []


class _FakeProvider:
    def __init__(self) -> None:
        self._by_id: dict[str, _FakeUser] = {}
        self._by_identifier: dict[str, _FakeUser] = {}

    def add(self, *, identifier: int, email: str, password: str) -> _FakeUser:
        user = _FakeUser(identifier, Hash.make(password))
        self._by_id[str(identifier)] = user
        self._by_identifier[email] = user
        return user

    def by_id(self, identifier: object) -> _FakeUser | None:
        return self._by_id.get(str(identifier))

    def by_identifier(self, value: str) -> _FakeUser | None:
        return self._by_identifier.get(value)

    def validate(self, user: Authenticatable, password: str) -> bool:
        return Hash.verify(password, user.get_auth_password())


@pytest.fixture
def provider(monkeypatch: MonkeyPatch) -> Iterator[_FakeProvider]:
    monkeypatch.setattr(settings, "jwt_secret", _TEST_SECRET)
    monkeypatch.setattr(settings, "auth_guard", "jwt")
    fake = _FakeProvider()
    set_user_provider(fake)
    yield fake
    set_user_provider(None)


def test_issue_requires_secret(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "")
    with pytest.raises(RuntimeError):
        issue_token("1")


def test_token_round_trip(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", _TEST_SECRET)
    token = issue_token("42")
    assert decode_token(token)["sub"] == "42"


def test_decode_rejects_expired(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", _TEST_SECRET)
    monkeypatch.setattr(settings, "jwt_ttl_seconds", -10)  # exp en el pasado
    token = issue_token("1")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_attempt_returns_jwt_for_valid_credentials(provider: _FakeProvider) -> None:
    provider.add(identifier=7, email="a@example.com", password="pw")
    token = Auth.attempt("a@example.com", "pw")
    assert token is not None
    assert decode_token(token)["sub"] == "7"


def test_attempt_returns_none_for_bad_credentials(provider: _FakeProvider) -> None:
    provider.add(identifier=7, email="a@example.com", password="pw")
    assert Auth.attempt("a@example.com", "WRONG") is None
    assert Auth.attempt("nadie@example.com", "pw") is None


def test_authenticated_dependency_and_contextvar(provider: _FakeProvider) -> None:
    provider.add(identifier=7, email="a@example.com", password="pw")
    token = Auth.attempt("a@example.com", "pw")
    assert token is not None

    app = create_app()

    @app.get("/_t/me")
    def me(user: Authenticatable = Depends(authenticated)) -> dict[str, object]:
        # `user` viene de la dep; `Auth.id()` viene del contextvar (debe llegar a un endpoint sync).
        return {"param_id": user.get_auth_identifier(), "ctx_id": Auth.id()}

    client = TestClient(app, raise_server_exceptions=False)

    ok = client.get("/_t/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json() == {"param_id": 7, "ctx_id": 7}


def test_authenticated_dependency_rejects_missing_token(provider: _FakeProvider) -> None:
    app = create_app()

    @app.get("/_t/me2")
    def me2(user: Authenticatable = Depends(authenticated)) -> dict[str, object]:
        return {"id": user.get_auth_identifier()}

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/_t/me2")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "unauthorized"
