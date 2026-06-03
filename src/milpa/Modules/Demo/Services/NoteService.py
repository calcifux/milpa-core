"""Servicio de notas: escrituras en UNA transacción, con el chequeo ABAC (Gate) ADENTRO
(carga el recurso → autoriza → muta), y devuelve un dict ya serializado (antes del commit,
para no chocar con el expire_on_commit / DetachedInstanceError)."""

from __future__ import annotations

from typing import Any

from milpa.Core.Auth import Authenticatable, Gate
from milpa.Core.Database import current_session, transactional
from milpa.Core.Errors import ResourceNotFoundError
from milpa.Core.Pipeline import Pipeline
from milpa.Models.Note import Note
from milpa.Modules.Demo.Pipes.CleanContent import CollapseWhitespace, NoteDraft, TrimContent
from milpa.Modules.Demo.Serializers import note_dict


class NoteService:
    @transactional
    def create(self, owner_id: int, title: str, body: str) -> dict[str, Any]:
        # estilo milpa: el contenido se NORMALIZA con un Pipeline (etapas componibles) antes de
        # persistir, en vez de strip()/split() sueltos. Ver Pipes/CleanContent.py.
        draft: NoteDraft = (
            Pipeline()
            .send(NoteDraft(title=title, body=body))
            .through([TrimContent(), CollapseWhitespace()])
            .then_return()
        )
        note = Note(owner_id=owner_id, title=draft.title, body=draft.body)
        current_session().add(note)
        current_session().flush()  # asigna PK
        return note_dict(note)

    @transactional
    def update(self, note_id: int, *, title: str, body: str, actor: Authenticatable) -> dict[str, Any]:
        note = self._find(note_id)
        Gate.authorize("note.update", note, user=actor)  # ABAC: solo el dueño
        note.title = title
        note.body = body
        return note_dict(note)

    @transactional
    def delete(self, note_id: int, *, actor: Authenticatable) -> None:
        note = self._find(note_id)
        Gate.authorize("note.delete", note, user=actor)
        current_session().delete(note)

    @staticmethod
    def _find(note_id: int) -> Note:
        note = current_session().get(Note, note_id)
        if note is None:
            raise ResourceNotFoundError(f"Nota {note_id} no existe", details={"id": note_id})
        return note
