"""Tests de @policy (auto-registro) + el híbrido de abilities no registradas.

Tenet 'nunca falla en silencio': una ability sin policy NO se traga — deniega + loguea (default)
o truena (AUTH_STRICT_ABILITIES). Sin BD.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest import MonkeyPatch

from milpa.Core.Auth import Gate, policy
from milpa.Core.Auth.Authorization import reset_policies
from milpa.Core.Config import settings
from milpa.Core.Errors import UndefinedAbilityError


@pytest.fixture(autouse=True)
def _clean_policies() -> Iterator[None]:
    reset_policies()
    yield
    reset_policies()


def test_policy_decorator_registers_ability() -> None:
    @policy("note.update")
    def can_update(user: object, note: object) -> bool:
        return note == "owned"

    assert Gate.allows("note.update", "owned", user=None) is True
    assert Gate.allows("note.update", "other", user=None) is False


def test_unregistered_ability_denies_by_default() -> None:
    # Sin @policy: deniega (secure-by-default). NO lanza (modo no-estricto). Loguea WARNING.
    assert Gate.allows("inexistente.ability", user=None) is False


def test_unregistered_ability_raises_when_strict(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_strict_abilities", True)
    with pytest.raises(UndefinedAbilityError):
        Gate.allows("inexistente.ability", user=None)


def test_reset_clears_registry() -> None:
    @policy("temp.ability")
    def can(user: object, resource: object) -> bool:
        return True

    assert Gate.allows("temp.ability", user=None) is True
    reset_policies()
    assert Gate.allows("temp.ability", user=None) is False  # ya no registrada -> deniega
