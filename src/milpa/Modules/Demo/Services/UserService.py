"""Servicio de usuarios del demo: alta (register) compartida por el carril API y el web."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from milpa.Core.Auth import Hash
from milpa.Core.Database import current_session, transactional
from milpa.Core.Errors import ConflictError
from milpa.Models.User import User
from milpa.Modules.Demo.Serializers import user_dict


class UserService:
    @transactional
    def register(self, name: str, email: str, password: str, *, roles: str = "") -> dict[str, Any]:
        """Crea un usuario (password hasheado). `ConflictError` si el email ya existe."""
        if current_session().execute(select(User).where(User.email == email)).scalars().first() is not None:
            raise ConflictError("El email ya está registrado.", details={"email": email})
        user = User(name=name, email=email, password=Hash.make(password), roles=roles)
        current_session().add(user)
        current_session().flush()
        return user_dict(user)
