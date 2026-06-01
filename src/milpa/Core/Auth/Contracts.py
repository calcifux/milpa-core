"""Contratos de autenticación (neutrales al transporte y, en lo posible, al ORM).

- `Authenticatable`: lo que milpa necesita de un "usuario" (identificador, hash, roles). Tu
  modelo lo cumple (p. ej. heredando `AuthenticatableMixin`). milpa NO impone el esquema.
- `UserProvider`: cómo se RECUPERA un usuario (por id / por identificador) y se VALIDA su
  password. El default es `SqlAlchemyUserProvider`; registra el tuyo para BD legacy/LDAP/etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


@runtime_checkable
class Authenticatable(Protocol):
    """Un usuario, desde el punto de vista del auth (no del ORM)."""

    def get_auth_identifier(self) -> Any:
        """La PK / identificador único (va en el `sub` del token)."""
        ...

    def get_auth_password(self) -> str:
        """El hash de password almacenado."""
        ...

    def get_roles(self) -> list[str]:
        """Roles del usuario (para RBAC)."""
        ...


class AuthenticatableMixin:
    """Implementación por defecto de `Authenticatable` para modelos SQLAlchemy.

    Asume columnas `id`, `password` (hash) y `roles` (CSV, p. ej. "admin,editor"). El modelo
    concreto las declara como `Mapped[...]`; aquí solo van los métodos del contrato.
    """

    # Solo para el type-checker: el modelo concreto declara estas columnas como Mapped[...].
    # En runtime NO existen aquí, para que el mapper de SQLAlchemy no las vea en el mixin.
    if TYPE_CHECKING:
        id: Any
        password: Any
        roles: Any

    def get_auth_identifier(self) -> Any:
        return self.id

    def get_auth_password(self) -> str:
        return str(self.password)

    def get_roles(self) -> list[str]:
        return [role.strip() for role in str(self.roles or "").split(",") if role.strip()]


class UserProvider(Protocol):
    """Cómo recuperar/validar usuarios. Inyectable (registra el tuyo con `set_user_provider`)."""

    def by_id(self, identifier: Any) -> Authenticatable | None: ...

    def by_identifier(self, value: str) -> Authenticatable | None: ...

    def validate(self, user: Authenticatable, password: str) -> bool: ...
