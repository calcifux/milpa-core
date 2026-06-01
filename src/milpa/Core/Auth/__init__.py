"""API pública de auth de milpa: hashing, guards (JWT/Passport), facade `Auth`,
contratos y dependencies. Impórtalos desde aquí:

    from milpa.Core.Auth import Auth, CurrentUser, Hash, authenticated, guarded
"""

from milpa.Core.Auth.Auth import (
    Auth,
    CurrentUser,
    OptionalUser,
    authenticated,
    guarded,
    optional_user,
    set_current_user,
)
from milpa.Core.Auth.Authorization import Can, Gate, Roles, require_roles
from milpa.Core.Auth.Contracts import Authenticatable, AuthenticatableMixin, UserProvider
from milpa.Core.Auth.Guards import JwtGuard, PassportGuard, SessionGuard, get_guard
from milpa.Core.Auth.Hash import Hash
from milpa.Core.Auth.Passport import TokenPrincipal, get_current_token, require_scopes
from milpa.Core.Auth.Providers import SqlAlchemyUserProvider, get_user_provider, set_user_provider

__all__ = [
    "Auth",
    "Authenticatable",
    "AuthenticatableMixin",
    "Can",
    "CurrentUser",
    "Gate",
    "Hash",
    "JwtGuard",
    "OptionalUser",
    "PassportGuard",
    "Roles",
    "SessionGuard",
    "SqlAlchemyUserProvider",
    "TokenPrincipal",
    "UserProvider",
    "authenticated",
    "get_current_token",
    "get_guard",
    "get_user_provider",
    "guarded",
    "optional_user",
    "require_roles",
    "require_scopes",
    "set_current_user",
    "set_user_provider",
]
