"""RFC 9457 — *Problem Details for HTTP APIs* (reemplaza al RFC 7807, mismo concepto).

El sobre JSON ESTÁNDAR de la industria para errores HTTP. Media type
`application/problem+json` con los campos del RFC:

  - `type`    URI que identifica el TIPO de problema (default `about:blank`).
  - `title`   resumen humano y ESTABLE del tipo (no cambia entre ocurrencias).
  - `status`  el código HTTP (duplicado en el cuerpo, por conveniencia del cliente).
  - `detail`  explicación humana de ESTA ocurrencia concreta.
  - extensiones: `code` (código estable, máquina) y `errors` (detalles/campos).

Una sola forma para TODOS los errores (dominio, validación, HTTP, 500), así el cliente
parsea un único shape. Aquí va solo la construcción del cuerpo; los handlers que lo
emiten viven en `ExceptionHandler.py`.
"""

from __future__ import annotations

from typing import Any

from milpa.Core.Config import settings

# Media type del RFC. Distinguirlo de application/json deja que un cliente sepa, por el
# Content-Type, que el cuerpo es un Problem Details y no un payload de negocio.
PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"


def problem_type_uri(code: str) -> str:
    """`type` del problema. Si hay `PROBLEM_BASE_URL`, apunta a la doc del código
    (`<base>/<code-kebab>`); si no, `about:blank` (el default RFC-correcto cuando no
    publicas páginas de error — evita inventar URLs que no resuelven)."""
    base = settings.problem_base_url.rstrip("/")
    if not base:
        return "about:blank"
    return f"{base}/{code.replace('_', '-')}"


def build_problem(*, status: int, title: str, detail: str, code: str, errors: Any = None) -> dict[str, Any]:
    """Arma el cuerpo `application/problem+json`. `errors` (extensión) solo si viene."""
    problem: dict[str, Any] = {
        "type": problem_type_uri(code),
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if errors is not None:
        problem["errors"] = errors
    return problem
