"""i18n automático por Accept-Language: el endpoint de Example renderiza `t(...)`
SIN pasar locale, y la dependency global resuelve el idioma del header (o fallback).
Demuestra que milpa endurece FastAPI por default (el dev no hace nada).
"""

from __future__ import annotations

from starlette.testclient import TestClient

from milpa.Core.Http import create_app


def test_welcome_honors_accept_language() -> None:
    client = TestClient(create_app())
    en = client.get("/example/welcome", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert "Hello from the Example module" in en.text


def test_welcome_falls_back_to_config_locale() -> None:
    client = TestClient(create_app())
    es = client.get("/example/welcome")  # sin Accept-Language → app_fallback_locale (es)
    assert "Hola desde el módulo Example" in es.text
