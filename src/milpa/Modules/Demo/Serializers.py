"""Serializadores del demo: modelo → dict JSON-able, con **Pydantic v2** (= un Serializer de
DRF / un API Resource de Laravel). El plus de estilo milpa: `computed_field` agrega campos
DERIVADOS (excerpt, is_admin) que NO viven en la tabla, sin escribirlos a mano en cada endpoint.

Se llaman MIENTRAS la sesión sigue abierta (en reads @auto_session los escalares ya cargados son
accesibles aun detached; en writes @transactional, antes del commit). `note_dict`/`user_dict` se
mantienen como API estable: delegan en los modelos Pydantic, así los call sites no cambian.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from milpa.Models.Note import Note
from milpa.Models.User import User


class NoteOut(BaseModel):
    """Serializador de una nota. `from_attributes` permite `model_validate(note)` (lee el ORM)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    owner_id: int
    archived: bool = False

    @computed_field  # type: ignore[prop-decorator]  # Pydantic v2: computed sobre @property
    @property
    def excerpt(self) -> str:
        """Vista previa del cuerpo (primeros 80 chars) — DERIVADO, no vive en la tabla."""
        text = self.body.strip()
        return text if len(text) <= 80 else f"{text[:80].rstrip()}…"


class UserOut(BaseModel):
    """Serializador de usuario: `roles` como lista + `is_admin` derivado (computed_field)."""

    id: int
    name: str
    email: str
    roles: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


def note_dict(note: Note) -> dict[str, Any]:
    """Dict JSON-able de una nota (vía NoteOut/Pydantic v2; incluye `excerpt` computado)."""
    return NoteOut.model_validate(note).model_dump()


def user_dict(user: User) -> dict[str, Any]:
    """Dict JSON-able de un usuario (vía UserOut; `roles` lista + `is_admin` computado)."""
    return UserOut(id=user.id, name=user.name, email=user.email, roles=user.get_roles()).model_dump()
