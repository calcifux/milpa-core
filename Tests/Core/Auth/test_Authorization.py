"""Tests de autorización: RBAC (require_roles / @Roles) y ABAC (Gate/policies). Sin BD."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from milpa.Core.Auth import (
    Authenticatable,
    Gate,
    Roles,
    require_roles,
    set_current_user,
    set_user_provider,
)
from milpa.Core.Auth.Authorization import reset_policies
from milpa.Core.Auth.Tokens import issue_token
from milpa.Core.Config import settings
from milpa.Core.Errors import ForbiddenError
from milpa.Core.Http import Controller, Get
from milpa.Core.Http.Http import create_app
from milpa.Core.Http.Routing import ROUTER_ATTR

_SECRET = "test-secret-please-change-0123456789-abcdef"


class _User:
    def __init__(self, identifier: int, roles: list[str]) -> None:
        self._id = identifier
        self._roles = roles

    def get_auth_identifier(self) -> int:
        return self._id

    def get_auth_password(self) -> str:
        return ""

    def get_roles(self) -> list[str]:
        return list(self._roles)


class _Provider:
    def __init__(self) -> None:
        self._by_id: dict[str, _User] = {}

    def add(self, identifier: int, roles: list[str]) -> _User:
        user = _User(identifier, roles)
        self._by_id[str(identifier)] = user
        return user

    def by_id(self, identifier: object) -> _User | None:
        return self._by_id.get(str(identifier))

    def by_identifier(self, value: str) -> _User | None:
        return None

    def validate(self, user: Authenticatable, password: str) -> bool:
        return True


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    reset_policies()
    yield
    reset_policies()
    set_current_user(None)
    set_user_provider(None)


@pytest.fixture
def provider(monkeypatch: MonkeyPatch) -> _Provider:
    monkeypatch.setattr(settings, "jwt_secret", _SECRET)
    monkeypatch.setattr(settings, "auth_guard", "jwt")
    instance = _Provider()
    set_user_provider(instance)
    return instance


def _bearer(identifier: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(str(identifier))}"}


# ----------------------------------------------------------------- RBAC


def test_require_roles_grants_matching_role(provider: _Provider) -> None:
    provider.add(1, ["admin"])
    app = create_app()

    @app.get("/_t/admin")
    def admin(user: Authenticatable = Depends(require_roles("admin"))) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app, raise_server_exceptions=False).get("/_t/admin", headers=_bearer(1))
    assert response.status_code == 200


def test_require_roles_forbids_without_role(provider: _Provider) -> None:
    provider.add(2, ["user"])
    app = create_app()

    @app.get("/_t/admin2")
    def admin2(user: Authenticatable = Depends(require_roles("admin"))) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app, raise_server_exceptions=False).get("/_t/admin2", headers=_bearer(2))
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_require_roles_unauthenticated_is_401(provider: _Provider) -> None:
    app = create_app()

    @app.get("/_t/admin3")
    def admin3(user: Authenticatable = Depends(require_roles("admin"))) -> dict[str, bool]:
        return {"ok": True}

    assert TestClient(app, raise_server_exceptions=False).get("/_t/admin3").status_code == 401


def test_roles_decorator_on_controller(provider: _Provider) -> None:
    provider.add(3, ["admin"])
    provider.add(4, ["user"])

    @Controller("/_t/panel")
    class _PanelController:
        @Get("/")
        @Roles("admin")
        def index(self) -> dict[str, bool]:
            return {"ok": True}

    app = create_app()
    app.include_router(getattr(_PanelController, ROUTER_ATTR))
    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/_t/panel/", headers=_bearer(3)).status_code == 200
    assert client.get("/_t/panel/", headers=_bearer(4)).status_code == 403


# ----------------------------------------------------------------- ABAC (Gate)


def _owns_note(user: Authenticatable | None, note: object) -> bool:
    return user is not None and isinstance(note, dict) and note.get("owner_id") == user.get_auth_identifier()


def test_gate_allows_owner_and_denies_others() -> None:
    Gate.define("note.update", _owns_note)
    owner = _User(10, [])
    set_current_user(owner)

    assert Gate.allows("note.update", {"owner_id": 10}) is True
    assert Gate.denies("note.update", {"owner_id": 99}) is True
    Gate.authorize("note.update", {"owner_id": 10})  # no lanza

    with pytest.raises(ForbiddenError):
        Gate.authorize("note.update", {"owner_id": 99})


def test_gate_denies_unknown_ability() -> None:
    assert Gate.allows("ability.sin.policy", None) is False
