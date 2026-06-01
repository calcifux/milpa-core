"""Tests del middleware CSRF (double-submit cookie).

Regla: CSRF solo se verifica cuando la request trae la COOKIE DE SESIÓN (carril cookie).
Sin sesión (login/registro, clientes API por JSON) y con bearer/JWT → exento.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from milpa.Core.Config import settings
from milpa.Core.Http.Csrf import CsrfMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CsrfMiddleware)

    @app.get("/safe")
    def safe() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/unsafe")
    def unsafe() -> dict[str, bool]:
        return {"ok": True}

    return app


def _client_with_session() -> TestClient:
    client = TestClient(_app())
    client.cookies.set(settings.session_cookie, "una-sesion-cualquiera")
    return client


def test_safe_request_seeds_csrf_cookie() -> None:
    response = TestClient(_app()).get("/safe")
    assert response.status_code == 200
    assert response.cookies.get(settings.csrf_cookie) is not None


def test_unsafe_without_session_is_exempt() -> None:
    # Sin cookie de sesión (caso login/registro o cliente API): no se exige CSRF.
    response = TestClient(_app()).post("/unsafe")
    assert response.status_code == 200


def test_unsafe_with_session_but_no_token_is_forbidden() -> None:
    response = _client_with_session().post("/unsafe")
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "csrf_failed"


def test_unsafe_with_session_and_matching_token_passes() -> None:
    client = _client_with_session()
    client.get("/safe")  # siembra la cookie CSRF
    token = client.cookies.get(settings.csrf_cookie)
    assert token is not None
    response = client.post("/unsafe", headers={settings.csrf_header: token})
    assert response.status_code == 200


def test_unsafe_with_session_and_mismatched_token_is_forbidden() -> None:
    client = _client_with_session()
    client.get("/safe")
    response = client.post("/unsafe", headers={settings.csrf_header: "token-que-no-coincide"})
    assert response.status_code == 403


def test_bearer_requests_are_exempt() -> None:
    response = _client_with_session().post("/unsafe", headers={"Authorization": "Bearer abc"})
    assert response.status_code == 200
