"""Stack base de middlewares: se montan SEGÚN Settings, con defaults seguros
(CORS/TrustedHost off si no se configuran). Sin red — solo inspeccionamos el stack.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pytest import MonkeyPatch

from milpa.Core.Config import settings
from milpa.Core.Http.Middleware import register_middlewares


def _classes(app: FastAPI) -> set[Any]:
    return {mw.cls for mw in app.user_middleware}


def test_cors_not_added_when_no_origins(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cors_allow_origins", "")
    app = FastAPI()
    register_middlewares(app)
    assert CORSMiddleware not in _classes(app)


def test_cors_added_when_origins_configured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cors_allow_origins", "http://localhost:3000")
    app = FastAPI()
    register_middlewares(app)
    assert CORSMiddleware in _classes(app)


def test_trustedhost_off_when_wildcard(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_hosts", "*")
    app = FastAPI()
    register_middlewares(app)
    assert TrustedHostMiddleware not in _classes(app)


def test_trustedhost_on_when_configured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_hosts", "api.example.com")
    app = FastAPI()
    register_middlewares(app)
    assert TrustedHostMiddleware in _classes(app)
