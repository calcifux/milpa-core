"""Proveedores de usuarios: recuperan/validan usuarios. Default sobre SQLAlchemy.

El provider activo es un singleton de proceso; cámbialo con `set_user_provider(...)` (BD
legacy, LDAP, tests). El `SqlAlchemyUserProvider` resuelve el modelo desde `AUTH_USER_MODEL`.
"""

from __future__ import annotations

import importlib
from typing import Any, cast

from sqlalchemy import select

from milpa.Core.Auth.Contracts import Authenticatable, UserProvider
from milpa.Core.Auth.Hash import Hash
from milpa.Core.Config import settings
from milpa.Core.Database.Transactional import auto_session, current_session


def _resolve_user_model() -> type[Any]:
    """Importa el modelo User desde la ruta dotted de `AUTH_USER_MODEL`."""
    module_path, _, class_name = settings.auth_user_model.rpartition(".")
    if not module_path or not class_name:
        raise ValueError(f"AUTH_USER_MODEL inválido: {settings.auth_user_model!r}")
    module = importlib.import_module(module_path)
    return cast("type[Any]", getattr(module, class_name))


class SqlAlchemyUserProvider:
    """Provider por defecto: busca el User en la BD (motor agnóstico) y verifica con `Hash`."""

    def __init__(self, model: type[Any] | None = None, *, identifier_field: str = "email") -> None:
        self._model = model
        self._identifier_field = identifier_field

    @property
    def model(self) -> type[Any]:
        if self._model is None:
            self._model = _resolve_user_model()  # perezoso: el modelo puede no existir al importar
        return self._model

    @auto_session
    def by_id(self, identifier: Any) -> Authenticatable | None:
        return current_session().get(self.model, identifier)

    @auto_session
    def by_identifier(self, value: str) -> Authenticatable | None:
        column = getattr(self.model, self._identifier_field)
        return current_session().execute(select(self.model).where(column == value)).scalars().first()

    def validate(self, user: Authenticatable, password: str) -> bool:
        return Hash.verify(password, user.get_auth_password())


_provider: UserProvider | None = None


def get_user_provider() -> UserProvider:
    """El provider activo (default `SqlAlchemyUserProvider`)."""
    global _provider
    if _provider is None:
        _provider = SqlAlchemyUserProvider()
    return _provider


def set_user_provider(provider: UserProvider | None) -> None:
    """Reemplaza el provider activo (BD legacy / tests). `None` resetea al default."""
    global _provider
    _provider = provider
