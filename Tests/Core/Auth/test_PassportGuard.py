"""Tests de PassportGuard: sin bearer → None, token válido → user, token inválido propaga 401. Sin BD."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import HTTPException
from pytest import MonkeyPatch
from starlette.requests import Request

import milpa.Core.Auth.Guards as guards_mod
from milpa.Core.Auth.Guards import PassportGuard
from milpa.Core.Auth.Providers import set_user_provider


class _FakeUser:
    def get_auth_identifier(self) -> Any:
        return 7

    def get_auth_password(self) -> str:
        return ""

    def get_roles(self) -> list[str]:
        return []


class _FakeProvider:
    """UserProvider de mentira: solo conoce al usuario 7."""

    def by_id(self, identifier: Any) -> _FakeUser | None:
        return _FakeUser() if str(identifier) == "7" else None

    def by_identifier(self, value: str) -> _FakeUser | None:
        return None

    def validate(self, user: Any, password: str) -> bool:
        return True


@pytest.fixture
def fake_provider() -> Iterator[None]:
    set_user_provider(_FakeProvider())
    yield
    set_user_provider(None)


def _request(authorization: str | None = None) -> Request:
    headers = [(b"authorization", authorization.encode())] if authorization else []
    return Request({"type": "http", "headers": headers})


def test_no_bearer_returns_none() -> None:
    assert PassportGuard().authenticate(_request()) is None


def test_valid_token_resolves_user(fake_provider: None, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(guards_mod, "decode_passport_token", lambda token: {"sub": "7"})
    user = PassportGuard().authenticate(_request("Bearer good"))
    assert user is not None
    assert user.get_auth_identifier() == 7


def test_token_without_sub_returns_none(fake_provider: None, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(guards_mod, "decode_passport_token", lambda token: {})
    assert PassportGuard().authenticate(_request("Bearer no-sub")) is None


def test_invalid_token_propagates_401(monkeypatch: MonkeyPatch) -> None:
    def _boom(token: str) -> dict[str, Any]:
        raise HTTPException(status_code=401, detail="Token inválido")

    monkeypatch.setattr(guards_mod, "decode_passport_token", _boom)
    with pytest.raises(HTTPException) as exc_info:
        PassportGuard().authenticate(_request("Bearer bad"))
    assert exc_info.value.status_code == 401
