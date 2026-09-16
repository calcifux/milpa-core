"""`Auth.validate_credentials` paga el mismo hash exista o no el identificador.

Sin BD: provider falso. Antes de 1.1.0, un correo inexistente respondía sin verificar ningún
hash y el tiempo delataba qué correos tienen cuenta (enumeración por tiempo, OWASP).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from milpa.Core.Auth import Auth, Authenticatable, Hash, set_user_provider


class _FakeUser:
    def __init__(self, password: str) -> None:
        self._hash = Hash.make(password)

    def get_auth_identifier(self) -> int:
        return 1

    def get_auth_password(self) -> str:
        return self._hash

    def get_roles(self) -> list[str]:
        return []


class _FakeProvider:
    def __init__(self) -> None:
        self.user = _FakeUser("la buena")

    def by_id(self, identifier: object) -> _FakeUser | None:
        return None

    def by_identifier(self, value: str) -> _FakeUser | None:
        return self.user if value == "a@example.com" else None

    def validate(self, user: Authenticatable, password: str) -> bool:
        return Hash.verify(password, user.get_auth_password())


@pytest.fixture
def provider() -> Iterator[_FakeProvider]:
    fake = _FakeProvider()
    set_user_provider(fake)
    yield fake
    set_user_provider(None)


def test_a_missing_identifier_still_verifies_a_hash(provider: _FakeProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    verified: list[str] = []
    real_verify = Hash.verify

    def counting_verify(password: str, hashed: str) -> bool:
        verified.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(Hash, "verify", staticmethod(counting_verify))
    assert Auth.validate_credentials("nadie@example.com", "cualquiera") is None
    assert len(verified) == 1


def test_valid_and_invalid_credentials_behave_as_before(provider: _FakeProvider) -> None:
    found = Auth.validate_credentials("a@example.com", "la buena")
    assert found is not None
    assert found.get_auth_identifier() == provider.user.get_auth_identifier()
    assert Auth.validate_credentials("a@example.com", "la mala") is None
