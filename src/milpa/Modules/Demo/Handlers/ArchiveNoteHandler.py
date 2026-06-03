"""Handler del comando `ArchiveNote` (Mediator 1:1).

Saca el caso de uso "archivar nota" del controller para reusarlo desde HTTP y desde la CLI con
el MISMO `send(ArchiveNote(...))`. Aplica el ABAC (Gate) adentro (carga recurso + actor → autoriza
→ muta), igual que NoteService. Devuelve el dict serializado ANTES del commit (evita el detached
del expire_on_commit).
"""

from __future__ import annotations

from typing import Any

from milpa.Core.Auth import Gate
from milpa.Core.Database import current_session, transactional
from milpa.Core.Errors import ResourceNotFoundError
from milpa.Core.Mediator import handles
from milpa.Models.Note import Note
from milpa.Models.User import User
from milpa.Modules.Demo.Commands import ArchiveNote
from milpa.Modules.Demo.Serializers import note_dict


@handles(ArchiveNote)
class ArchiveNoteHandler:
    """Marca `archived=True` si el actor puede gestionar la nota (dueño o moderador)."""

    @transactional
    def handle(self, command: ArchiveNote) -> dict[str, Any]:
        note = current_session().get(Note, command.note_id)
        if note is None:
            raise ResourceNotFoundError(f"Nota {command.note_id} no existe", details={"id": command.note_id})
        actor = current_session().get(User, command.actor_id)  # None => la policy deniega (403)
        Gate.authorize("note.update", note, user=actor)  # ABAC: dueño o moderador
        note.archived = True
        return note_dict(note)
