"""`DomainError(extensions=...)`: miembros extra de primer nivel en el problem+json (RFC 9457 §3.2).

Sin BD ni red. Lo que se protege: que la extensión salga a primer nivel, que NUNCA pise un
miembro estándar y que un error sin extensiones responda idéntico a antes (compatibilidad 1.0).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from milpa.Core.Errors import DomainError
from milpa.Core.Http.Http import create_app
from milpa.Core.Http.ProblemDetails import build_problem


def _client() -> TestClient:
    app: FastAPI = create_app()

    @app.get("/_test/locked")
    def _locked() -> dict[str, str]:
        raise DomainError(
            "Correo o contraseña incorrectos.",
            status_code=401,
            error_code="invalid_credentials",
            extensions={"remaining_attempts": 3, "status": 999, "code": "pisado"},
        )

    @app.get("/_test/plain")
    def _plain() -> dict[str, str]:
        raise DomainError("Sin extras", error_code="plain", status_code=409)

    return TestClient(app, raise_server_exceptions=False)


def test_extensions_go_to_the_top_level_without_overriding_standard_members() -> None:
    body = _client().get("/_test/locked").json()
    assert body["remaining_attempts"] == 3
    assert body["status"] == 401
    assert body["code"] == "invalid_credentials"


def test_an_error_without_extensions_keeps_the_1_0_shape() -> None:
    body = _client().get("/_test/plain").json()
    assert set(body) == {"type", "title", "status", "detail", "code"}


def test_build_problem_ignores_missing_extensions() -> None:
    problem = build_problem(status=400, title="t", detail="d", code="c")
    assert "remaining_attempts" not in problem
    assert build_problem(status=400, title="t", detail="d", code="c", extensions={"x": 1})["x"] == 1
