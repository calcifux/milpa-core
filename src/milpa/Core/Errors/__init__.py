"""Errores de dominio del framework (neutrales al transporte). Impórtalos desde aquí:

from milpa.Core.Errors import DomainError, ResourceNotFoundError

Los generales son de tequio (`milpa.Core.Errors.Errors` es el mismo módulo, ver `milpa.Core`); los de
entrar y permisos son de milpa (`WebErrors.py`).
"""

from __future__ import annotations

from milpa.Core.Errors.Errors import (
    ConflictError,
    DomainError,
    HandlerNotFoundError,
    InvalidFilterError,
    ResourceNotFoundError,
)
from milpa.Core.Errors.WebErrors import ForbiddenError, UnauthorizedError, UndefinedAbilityError

__all__ = [
    "ConflictError",
    "DomainError",
    "ForbiddenError",
    "HandlerNotFoundError",
    "InvalidFilterError",
    "ResourceNotFoundError",
    "UnauthorizedError",
    "UndefinedAbilityError",
]
