"""Test del carril SESIÓN cookie: Auth.login + guard 'session' (round-trip de cookie).

CSRF se prueba aparte (test_Csrf); aquí se desactiva para enfocar el flujo de sesión.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from milpa.Core.Auth import Auth, Authenticatable, guarded, set_user_provider
from milpa.Core.Config import settings
from milpa.Core.Http.Http import create_app


class _FakeUser:
    def __init__(self, identifier: int) -> None:
        self._id = identifier

    def get_auth_identifier(self) -> int:
        return self._id

    def get_auth_password(self) -> str:
        return ""

    def get_roles(self) -> list[str]:
        return []


class _FakeProvider:
    def __init__(self, user: _FakeUser) -> None:
        self._user = user

    def by_id(self, identifier: object) -> _FakeUser | None:
        return self._user if str(identifier) == str(self._user.get_auth_identifier()) else None

    def by_identifier(self, value: str) -> _FakeUser | None:
        return None

    def validate(self, user: Authenticatable, password: str) -> bool:
        return True


@pytest.fixture
def session_client(monkeypatch: MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "session_secret", "session-secret-please-change-0123456789")
    monkeypatch.setattr(settings, "csrf_enabled", False)
    user = _FakeUser(5)
    set_user_provider(_FakeProvider(user))

    app = create_app()

    @app.post("/_t/login")
    def login(request: Request) -> dict[str, bool]:
        Auth.login(request, user)
        return {"ok": True}

    @app.get("/_t/me")
    def me(current: Authenticatable = Depends(guarded("session"))) -> dict[str, object]:
        return {"id": current.get_auth_identifier()}

    try:
        yield TestClient(app)
    finally:
        set_user_provider(None)


def test_protected_route_requires_session(session_client: TestClient) -> None:
    assert session_client.get("/_t/me").status_code == 401


def test_login_sets_session_and_grants_access(session_client: TestClient) -> None:
    assert session_client.post("/_t/login").status_code == 200
    response = session_client.get("/_t/me")
    assert response.status_code == 200
    assert response.json() == {"id": 5}
