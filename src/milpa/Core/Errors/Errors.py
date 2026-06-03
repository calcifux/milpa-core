"""Errores de DOMINIO, neutrales a la capa de transporte (sin FastAPI).

Los lanza el dominio (services, repositories) para expresar lo que SABE explicar:
"no existe", "ya existe / choca con el estado", "no autorizado para esto". Cada uno
lleva los datos que el handler HTTP mapea a un cuerpo RFC 9457 (Problem Details):
  - `error_code` → `code` (código ESTABLE, máquina; los clientes ramifican en él),
  - `title`      → `title` (resumen humano ESTABLE del tipo; no cambia por ocurrencia),
  - `message`    → `detail` (explicación de ESTA ocurrencia),
  - `details`    → `errors` (datos opcionales: qué id, qué campo, etc.),
  - `status_code`→ `status`.

El controller NO las atrapa: el handler global (`app/Core/Http/ExceptionHandler.py`) las
convierte en `application/problem+json`. Viven FUERA de `Http` a propósito, para que la
capa de persistencia (p. ej. `Repository.find_or_fail`) pueda lanzarlas sin importar el
framework web (mantiene el layering: la persistencia no depende de FastAPI ni del RFC).
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base de los errores de negocio. Subclasea para fijar `status_code`/`error_code`/
    `title` por defecto, o instánciala directo para un caso puntual:

        raise DomainError("Saldo insuficiente", error_code="insufficient_funds",
                          status_code=409, title="Conflict")
    """

    status_code: int = 400
    error_code: str = "domain_error"
    title: str = "Domain error"

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        error_code: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        # Permiten override por-instancia sin tener que subclasear para cada caso.
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code
        if title is not None:
            self.title = title


class ResourceNotFoundError(DomainError):
    """El recurso pedido no existe (= 404). Lo usa, p. ej., `Repository.find_or_fail()`."""

    status_code = 404
    error_code = "resource_not_found"
    title = "Resource not found"


class ConflictError(DomainError):
    """Choque con el estado actual: duplicado, transición inválida, etc. (= 409)."""

    status_code = 409
    error_code = "conflict"
    title = "Conflict"


class UnauthorizedError(DomainError):
    """Falta autenticación / credencial inválida (= 401)."""

    status_code = 401
    error_code = "unauthorized"
    title = "Unauthorized"


class ForbiddenError(DomainError):
    """Autenticado pero sin permiso para esta acción (= 403)."""

    status_code = 403
    error_code = "forbidden"
    title = "Forbidden"


class InvalidFilterError(DomainError):
    """El cliente pidió un filtro/orden NO permitido (campo fuera de la whitelist, etc.) (= 422).

    Es error de CLIENTE, no bug: el `FilterQueryModel` lo lanza en vez de ignorar el parámetro en
    silencio (esa fuga deja al cliente creyendo que ordenó/filtró cuando no pasó nada). El `errors`
    lleva la lista de campos permitidos para que el cliente se corrija.
    """

    status_code = 422
    error_code = "invalid_filter"
    title = "Invalid filter"


class HandlerNotFoundError(DomainError):
    """No hay handler registrado para el comando despachado por el [[Mediator]].

    Es un BUG de programación (olvidaste `@handles(MiComando)` o el módulo no se
    descubrió), no un error de cliente: por eso 500 y no 4xx. Los handlers globales
    lo rinden como problem+json sin código de transporte nuevo.
    """

    status_code = 500
    error_code = "handler_not_found"
    title = "Handler not found"

    def __init__(self, *, command_type: str) -> None:
        super().__init__(
            f"No hay handler registrado para el comando {command_type!r}.",
            details={"command_type": command_type},
        )


class UndefinedAbilityError(DomainError):
    """Se evaluó una ability del `Gate` que NO está registrada (con `AUTH_STRICT_ABILITIES`).

    Es un BUG de configuración (olvidaste `@policy("...")` o el discovery no la importó), no un
    error de cliente: por eso 500. En modo no-estricto el Gate deniega + loguea en vez de lanzar
    (secure-by-default), pero NUNCA en silencio.
    """

    status_code = 500
    error_code = "undefined_ability"
    title = "Undefined ability"

    def __init__(self, *, ability: str) -> None:
        super().__init__(
            f"La ability {ability!r} sin policy. Defínela: @policy({ability!r}) en Modules/<X>/Policies/ "
            f"(se auto-descubre al arranque).",
            details={"ability": ability},
        )
