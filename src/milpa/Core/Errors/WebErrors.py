"""Los errores de dominio que solo existen con la capa web de milpa: entrar (401), permisos (403) y una
ability del Gate sin su policy. Los demás (no existe, choque, filtro inválido, comando sin handler) son
de tequio y se usan igual desde milpa (`milpa.Core.Errors`).

Heredan del MISMO `DomainError` de tequio: el handler RFC 9457 de milpa los convierte en
`application/problem+json` sin distinguir de dónde vienen.
"""

from __future__ import annotations

from tequio.Core.Errors.Errors import DomainError


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
