"""Tests del SecurityHeadersMiddleware: headers defensivos según Settings, apagables,
y sin pisar los que el endpoint ya fijó. Sin red real (TestClient en proceso)."""

from __future__ import annotations

from fastapi import FastAPI, Request
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


def test_csp_header_report_only_by_default(monkeypatch: MonkeyPatch) -> None:
    # Default csp_report_only=True: el navegador OBSERVA pero NO bloquea -> header Report-Only.
    monkeypatch.setattr(settings, "content_security_policy", "default-src 'self'")
    monkeypatch.setattr(settings, "csp_report_only", True)
    monkeypatch.setattr(settings, "csp_report_uri", "")

    response = TestClient(_app_with_route()).get("/x")

    assert response.headers["content-security-policy-report-only"] == "default-src 'self'"
    assert "content-security-policy" not in response.headers  # NO el enforcing


def test_csp_header_enforcing_when_report_only_false(monkeypatch: MonkeyPatch) -> None:
    # csp_report_only=False: enforcing real (Content-Security-Policy), con report-uri opcional.
    monkeypatch.setattr(settings, "content_security_policy", "default-src 'self'")
    monkeypatch.setattr(settings, "csp_report_only", False)
    monkeypatch.setattr(settings, "csp_report_uri", "/csp-report")

    response = TestClient(_app_with_route()).get("/x")

    assert response.headers["content-security-policy"] == "default-src 'self'; report-uri /csp-report"
    assert "content-security-policy-report-only" not in response.headers


def _app_reading_the_nonce() -> FastAPI:
    """Una ruta que regresa el nonce que vio en request.state (el que el shell pone en sus <script>)."""
    app = FastAPI()
    register_middlewares(app)

    @app.get("/nonce")
    def _nonce(request: Request) -> dict[str, str]:
        return {"nonce": getattr(request.state, "csp_nonce", "")}

    return app


def test_csp_nonce_en_script_src_y_en_request_state(monkeypatch: MonkeyPatch) -> None:
    # El nonce de la request va en script-src del header Y en request.state: es el mismo valor.
    monkeypatch.setattr(settings, "content_security_policy", "default-src 'self'; script-src 'self'")
    monkeypatch.setattr(settings, "csp_report_only", True)
    monkeypatch.setattr(settings, "csp_report_uri", "")
    monkeypatch.setattr(settings, "csp_nonce_enabled", True)

    response = TestClient(_app_reading_the_nonce()).get("/nonce")
    nonce = response.json()["nonce"]

    assert len(nonce) >= 20
    assert (
        response.headers["content-security-policy-report-only"]
        == f"default-src 'self'; script-src 'self' 'nonce-{nonce}'"
    )


def test_csp_nonce_cambia_en_cada_request(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "content_security_policy", "script-src 'self'")
    monkeypatch.setattr(settings, "csp_nonce_enabled", True)

    client = TestClient(_app_reading_the_nonce())
    first, second = client.get("/nonce").json()["nonce"], client.get("/nonce").json()["nonce"]

    assert first and second and first != second


def test_csp_nonce_no_toca_una_politica_con_unsafe_inline(monkeypatch: MonkeyPatch) -> None:
    # Con 'unsafe-inline' un nonce lo apagaría (CSP 2) y romperían los scripts pegados sin nonce: se deja tal cual.
    monkeypatch.setattr(settings, "content_security_policy", "script-src 'self' 'unsafe-inline'")
    monkeypatch.setattr(settings, "csp_report_only", True)
    monkeypatch.setattr(settings, "csp_report_uri", "")
    monkeypatch.setattr(settings, "csp_nonce_enabled", True)

    response = TestClient(_app_with_route()).get("/x")

    assert response.headers["content-security-policy-report-only"] == "script-src 'self' 'unsafe-inline'"


def test_csp_nonce_se_puede_apagar(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "content_security_policy", "script-src 'self'")
    monkeypatch.setattr(settings, "csp_report_only", True)
    monkeypatch.setattr(settings, "csp_report_uri", "")
    monkeypatch.setattr(settings, "csp_nonce_enabled", False)

    response = TestClient(_app_reading_the_nonce()).get("/nonce")

    assert response.headers["content-security-policy-report-only"] == "script-src 'self'"
    assert response.json()["nonce"] == ""


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
