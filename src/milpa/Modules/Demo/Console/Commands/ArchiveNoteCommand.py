"""Command CLI `demo archive <note_id> <actor_id>`: archiva una nota desde la terminal.

Demuestra el caso de uso transport-NEUTRAL del [[Mediator]]: el MISMO `send(ArchiveNote(...))` que
usa el endpoint `POST /api/notes/{id}/archive` corre aquí, sin duplicar la lógica. La CLI es un
proceso aparte (no pasa por el lifespan web), así que asegura a mano el discovery de lo que el caso
de uso usa: los HANDLERS (para el Mediator) y las POLICIES (el handler hace `Gate.authorize` ABAC).
"""

from __future__ import annotations

import typer

from milpa.Core.Console import console_command
from milpa.Core.Mediator import send
from milpa.Core.Registry import import_all_handlers, import_all_policies
from milpa.Modules.Demo.Commands import ArchiveNote


@console_command(name="archive", help="Archiva una nota (vía Mediator; mismo comando que el API).")
def archive_note(note_id: int, actor_id: int) -> None:
    """Envía el comando ArchiveNote y reporta el resultado."""
    # La CLI no corre el lifespan web: registra a mano lo que el caso de uso necesita.
    import_all_handlers()  # handlers del Mediator (resuelve ArchiveNote -> ArchiveNoteHandler)
    import_all_policies()  # policies del Gate (el handler autoriza 'note.update' ABAC) — sin esto deniega
    result = send(ArchiveNote(note_id=note_id, actor_id=actor_id))
    typer.echo(f"Nota {result['id']} archivada (archived={result['archived']}).")
