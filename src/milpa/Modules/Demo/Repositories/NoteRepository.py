"""Repositorio de notas (lecturas)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from milpa.Core.Database import Repository
from milpa.Models.Note import Note


class NoteRepository(Repository[Note, int]):
    model = Note

    def for_owner(self, owner_id: int) -> Sequence[Note]:
        """Las notas de un dueño, más recientes primero."""
        return (
            self.session.execute(select(Note).where(Note.owner_id == owner_id).order_by(Note.id.desc())).scalars().all()
        )
