"""Parseo de Accept-Language → locale (mayor q, subtag primario; fallback al config)."""

from __future__ import annotations

from milpa.Core.Config import settings
from milpa.Core.Translate import resolve_accept_language


def test_picks_highest_q_primary_subtag() -> None:
    assert resolve_accept_language("es-MX,es;q=0.9,en;q=0.8") == "es"
    assert resolve_accept_language("en-US,en;q=0.9,es;q=0.5") == "en"


def test_q_values_are_respected() -> None:
    assert resolve_accept_language("en;q=0.3,es;q=0.9") == "es"


def test_empty_or_wildcard_falls_back_to_config() -> None:
    assert resolve_accept_language("") == settings.app_fallback_locale
    assert resolve_accept_language("*") == settings.app_fallback_locale
