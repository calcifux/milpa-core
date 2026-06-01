"""Tests del SecurityHeadersMiddleware: headers defensivos según Settings, apagables,
y sin pisar los que el endpoint ya fijó. Sin red real (TestClient en proceso)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from milpa.Core.Config import settings
from milpa.Core.Http.Middleware import register_middlewares
from milpa.Core.Http.SecurityHeaders import SecurityHeadersMiddleware


def _app_with_route() -> FastAPI:
    app = FastAPI()
    register_middlewares(app)

    @app.get("/x")
    def _x() -> dict[str, str]:
        return {"ok": "1"}

    return app


def test_default_security_headers_present(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "security_headers_enabled", True)
    monkeypatch.setattr(settings, "security_frame_options", "DENY")
    monkeypatch.setattr(settings, "security_referrer_policy", "no-referrer")
    monkeypatch.setattr(settings, "hsts_enabled", False)
    monkeypatch.setattr(settings, "content_security_policy", "")

    response = TestClient(_app_with_route()).get("/x")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    # HSTS y CSP NO se mandan por default.
    assert "strict-transport-security" not in response.headers
    assert "content-security-policy" not in response.headers


def test_hsts_header_when_enabled(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hsts_enabled", True)
    monkeypatch.setattr(settings, "hsts_max_age", 1000)
    monkeypatch.setattr(settings, "hsts_include_subdomains", True)

    response = TestClient(_app_with_route()).get("/x")

    assert response.headers["strict-transport-security"] == "max-age=1000; includeSubDomains"


def test_csp_header_when_configured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "content_security_policy", "default-src 'self'")

    response = TestClient(_app_with_route()).get("/x")

    assert response.headers["content-security-policy"] == "default-src 'self'"


def test_security_headers_can_be_disabled(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "security_headers_enabled", False)

    app = _app_with_route()
    classes: set[object] = {mw.cls for mw in app.user_middleware}
    assert SecurityHeadersMiddleware not in classes

    response = TestClient(app).get("/x")
    assert "x-content-type-options" not in response.headers


def test_does_not_override_header_set_by_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "security_headers_enabled", True)
    monkeypatch.setattr(settings, "security_frame_options", "DENY")

    app = FastAPI()
    register_middlewares(app)

    @app.get("/same-origin")
    def _same_origin() -> JSONResponse:
        return JSONResponse({"ok": "1"}, headers={"X-Frame-Options": "SAMEORIGIN"})

    response = TestClient(app).get("/same-origin")
    # El endpoint pidió SAMEORIGIN explícito: el middleware NO lo pisa (setdefault).
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
