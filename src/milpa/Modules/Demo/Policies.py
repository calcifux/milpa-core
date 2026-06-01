"""Policies (ABAC) del demo: quién puede editar/borrar una nota.

Combina ATRIBUTO del recurso (dueño) con ROLES del usuario (RBAC): el DUEÑO siempre puede,
y además los MODERADORES (rol admin/editor) pueden editar cualquier nota. Así se prueba el
cruce RBAC+ABAC: un usuario normal solo toca lo suyo; un editor/admin modera todo.

`register_policies()` registra las abilities en el Gate (lo llaman los controllers al importarse).
"""

from __future__ import annotations

from typing import Any

from milpa.Core.Auth import Authenticatable, Gate

_MODERATOR_ROLES = {"admin", "editor"}


def _can_manage_note(user: Authenticatable | None, note: Any) -> bool:
    if user is None:
        return False
    if _MODERATOR_ROLES & set(user.get_roles()):
        return True  # moderador: edita/borra cualquier nota
    return bool(getattr(note, "owner_id", None) == user.get_auth_identifier())  # resto: solo lo suyo


def register_policies() -> None:
    Gate.define("note.update", _can_manage_note)
    Gate.define("note.delete", _can_manage_note)
