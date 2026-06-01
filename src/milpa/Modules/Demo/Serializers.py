"""Serializadores del demo: modelo → dict JSON-able. Se llaman MIENTRAS la sesión sigue
abierta (en reads @auto_session los escalares ya cargados son accesibles aun detached; en
writes @transactional, antes del commit)."""

from __future__ import annotations

from typing import Any

from milpa.Models.Note import Note
from milpa.Models.User import User


def note_dict(note: Note) -> dict[str, Any]:
    return {"id": note.id, "title": note.title, "body": note.body, "owner_id": note.owner_id}


def user_dict(user: User) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "roles": user.get_roles()}
