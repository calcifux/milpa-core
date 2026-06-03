"""Policies (ABAC) del demo: quién puede editar/borrar una nota.

Combina ATRIBUTO del recurso (dueño) con ROLES del usuario (RBAC): el DUEÑO siempre puede,
y además los MODERADORES (rol admin/editor) pueden editar cualquier nota. Así se prueba el
cruce RBAC+ABAC: un usuario normal solo toca lo suyo; un editor/admin modera todo.

estilo milpa: las abilities se AUTO-REGISTRAN con `@policy` al importarse este módulo
(`import_all_policies()` lo hace en el arranque). No hay `register_policies()` manual que
los controllers tengan que recordar llamar (esa fuga dejaba el Gate fallando en silencio).
"""

from __future__ import annotations

from typing import Any

from milpa.Core.Auth import Authenticatable, policy

_MODERATOR_ROLES = {"admin", "editor"}


@policy("note.update")
@policy("note.delete")
def can_manage_note(user: Authenticatable | None, note: Any) -> bool:
    """El dueño siempre puede; un moderador (admin/editor) puede sobre cualquier nota."""
    if user is None:
        return False
    if _MODERATOR_ROLES & set(user.get_roles()):
        return True  # moderador: edita/borra cualquier nota
    return bool(getattr(note, "owner_id", None) == user.get_auth_identifier())  # resto: solo lo suyo
