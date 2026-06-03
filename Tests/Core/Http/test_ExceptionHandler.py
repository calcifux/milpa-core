"""Tests de los handlers globales: TODOS los errores en RFC 9457 (problem+json).

Sin BD ni red: se levanta la app factory y se le agregan rutas de prueba que lanzan
cada tipo de error. `raise_server_exceptions=False` deja que el handler 500 FORME la
respuesta en vez de re-lanzar la excepción dentro del test.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from milpa.Core.Errors import ConflictError, DomainError, ResourceNotFoundError
from milpa.Core.Http.Http import create_app


def _client() -> TestClient:
    app: FastAPI = create_app()

    @app.get("/_test/not-found")
    def _not_found() -> dict[str, str]:
        raise ResourceNotFoundError("La compañía 7 no existe", details={"id": 7})

    @app.get("/_test/conflict")
    def _conflict() -> dict[str, str]:
        raise ConflictError("Ya existe un registro con ese folio")

    @app.get("/_test/custom")
    def _custom() -> dict[str, str]:
        raise DomainError(
            "Saldo insuficiente", error_code="insufficient_funds", status_code=402, title="Payment Required"
        )

    @app.get("/_test/boom")
    def _boom() -> dict[str, str]:
        raise ValueError("detalle interno secreto que NO debe filtrarse")

    @app.get("/_test/validate")
    def _validate(n: int) -> dict[str, int]:  # n inválido => 422 de Pydantic
        return {"n": n}

    @app.get("/_test/http-error")
    def _http_error() -> dict[str, str]:  # HTTPException de Starlette => problem+json
        raise HTTPException(status_code=401, detail="API key inválida")

    return TestClient(app, raise_server_exceptions=False)


def test_domain_error_is_rfc9457_problem_json() -> None:
    response = _client().get("/_test/not-found")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Resource not found",
        "status": 404,
        "detail": "La compañía 7 no existe",
        "code": "resource_not_found",
        "errors": {"id": 7},
    }


def test_domain_error_subclass_uses_its_status_and_title() -> None:
    body = _client().get("/_test/conflict").json()
    assert body["status"] == 409
    assert body["title"] == "Conflict"
    assert body["code"] == "conflict"
    # Sin details => no se incluye la extensión `errors`.
    assert "errors" not in body


def test_domain_error_per_instance_overrides() -> None:
    response = _client().get("/_test/custom")
    assert response.status_code == 402
    body = response.json()
    assert body["code"] == "insufficient_funds"
    assert body["title"] == "Payment Required"
    assert body["detail"] == "Saldo insuficiente"


def test_validation_error_is_problem_json_grouped_by_field() -> None:
    response = _client().get("/_test/validate", params={"n": "no-soy-int"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["title"] == "Validation failed"
    # El error se agrupa bajo el nombre de campo 'n' (sin el prefijo 'query').
    assert "n" in body["errors"]
    assert isinstance(body["errors"]["n"], list)


def test_http_exception_is_normalized_to_problem_json() -> None:
    # Una HTTPException de Starlette (p. ej. un 401 de un guard) AHORA sale en problem+json.
    response = _client().get("/_test/http-error")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "API key inválida",
        "code": "unauthorized",
    }


def test_unexpected_error_returns_generic_500_without_internals() -> None:
    response = _client().get("/_test/boom")
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Error interno del servidor.",
        "code": "internal_error",
    }
    # El mensaje real de la excepción NUNCA debe filtrarse al cliente.
    assert "secreto" not in response.text
