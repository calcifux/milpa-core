"""Handlers de excepción GLOBALES: normalizan TODOS los errores a RFC 9457 (Problem
Details), una sola forma `application/problem+json` para el cliente.

Se instalan cuatro handlers, para que NINGÚN error escape del formato estándar:

  - `DomainError` (y subclases): error de NEGOCIO → su `status`/`title`/`code` + `detail`
    (el `message`) y `errors` (los `details`). Es esperado: se loguea a INFO.
  - `RequestValidationError` (422): los errores de validación de Pydantic/FastAPI se
    reagrupan por campo en `errors: {campo: [mensajes]}` (en vez del `{"detail":[...]}`
    propio de FastAPI), así el 422 sale en la MISMA forma que todo lo demás.
  - `HTTPException` (de FastAPI/Starlette): auth/infra/404/405… → problem+json con el
    `title`/`code` derivados del status (vía `http.HTTPStatus`).
  - catch-all `Exception`: cualquier cosa NO prevista (bug, infra caída) → 500 genérico +
    log con traceback COMPLETO, SIN filtrar el mensaje real de la excepción al cliente.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from milpa.Core.Errors import DomainError
from milpa.Core.Http.ProblemDetails import PROBLEM_JSON_MEDIA_TYPE, build_problem

# Categorías de ubicación que Pydantic antepone en `loc` y que NO son el nombre del campo.
_LOC_PREFIXES = {"body", "query", "path", "header", "cookie"}


def _problem_response(*, status_code: int, title: str, detail: str, code: str, errors: Any = None) -> JSONResponse:
    """JSONResponse con el cuerpo problem+json y su media type (RFC 9457)."""
    return JSONResponse(
        status_code=status_code,
        media_type=PROBLEM_JSON_MEDIA_TYPE,
        content=build_problem(status=status_code, title=title, detail=detail, code=code, errors=errors),
    )


def _status_title(status_code: int) -> str:
    """Título humano y estable del status (p. ej. 401 → 'Unauthorized'). Genérico si raro."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _status_code_slug(status_code: int) -> str:
    """Código máquina estable del status (p. ej. 404 → 'not_found')."""
    try:
        return HTTPStatus(status_code).name.lower()
    except ValueError:
        return "http_error"


def _field_name(location: Any) -> str:
    """Nombre de campo a partir del `loc` de Pydantic, sin el prefijo de ubicación
    (body/query/...). p. ej. ('body','email') → 'email'; ('body','user','rfc') → 'user.rfc'."""
    parts = [str(part) for part in location]
    if parts and parts[0] in _LOC_PREFIXES:
        parts = parts[1:]
    return ".".join(parts) or "_"


def register_exception_handlers(app: FastAPI) -> None:
    """Instala los handlers globales en la app (lo llama `create_app`)."""

    async def _handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
        # exc: Exception (firma que pide Starlette); narrow para el type-checker + seguridad.
        assert isinstance(exc, DomainError)
        logger.info("DomainError | {code} | {msg}", code=exc.error_code, msg=exc.message)
        return _problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.message,
            code=exc.error_code,
            errors=exc.details,
        )

    async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        # Reagrupa por campo: {"email": ["...", "..."], "rfc": ["..."]} (estilo Laravel).
        errors: dict[str, list[str]] = {}
        for error in exc.errors():
            field = _field_name(error.get("loc", ()))
            errors.setdefault(field, []).append(str(error.get("msg", "")))
        return _problem_response(
            status_code=422,  # literal: el alias status.HTTP_422_* cambió de nombre y deprecó
            title="Validation failed",
            detail="La solicitud no superó la validación.",
            code="validation_error",
            errors=errors,
        )

    async def _handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, StarletteHTTPException)
        detail = exc.detail if isinstance(exc.detail, str) else _status_title(exc.status_code)
        return _problem_response(
            status_code=exc.status_code,
            title=_status_title(exc.status_code),
            detail=detail,
            code=_status_code_slug(exc.status_code),
        )

    async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        # No previsto: ES un bug o infra caída. Traceback COMPLETO al log; al cliente, un
        # 500 genérico SIN internals (nunca exponemos el mensaje real de la excepción).
        logger.exception("Unhandled exception | {t}", t=type(exc).__name__)
        return _problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Error interno del servidor.",
            code="internal_error",
        )

    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
