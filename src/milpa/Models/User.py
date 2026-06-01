"""Modelo User del demo (Authenticatable). Es `AUTH_USER_MODEL` por default.

Greenfield: milpa lo trae para arrancar. Si MIGRAS de Laravel, usa tu tabla `users` y registra
tu propio provider en vez de este modelo. `roles` es CSV ("admin" / "" / "admin,editor").
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from milpa.Core.Auth.Contracts import AuthenticatableMixin
from milpa.Core.Database import Base, TimestampMixin


class User(TimestampMixin, AuthenticatableMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(default="")
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password: Mapped[str] = mapped_column()  # hash (argon2id), NUNCA el password en claro
    roles: Mapped[str] = mapped_column(default="")  # CSV: roles del usuario para RBAC
