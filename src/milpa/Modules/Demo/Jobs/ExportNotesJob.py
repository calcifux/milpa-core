"""Job de background ON-DEMAND: "exportar las notas de un usuario".

Demuestra `@job` (≠ cron): lo DISPARAS tú desde un endpoint con `export_user_notes.dispatch(uid)`
y lo corre `queue work` (no bloquea el request). Aquí solo cuenta + loguea; en un caso real
generaría un CSV/ZIP y lo mandaría por correo (trabajo pesado fuera del ciclo HTTP).
"""

from __future__ import annotations

from loguru import logger

from milpa.Core.Jobs import job
from milpa.Modules.Demo.Repositories.NoteRepository import NoteRepository


@job(name="demo.export_notes", queue="exports")
def export_user_notes(user_id: int) -> dict[str, int]:
    """Corre en el WORKER: reúne las notas del usuario (el 'export' real iría aquí)."""
    notes = NoteRepository().for_owner(user_id)
    logger.info("demo.export_notes | usuario {u}: {n} notas exportadas (en el worker)", u=user_id, n=len(notes))
    return {"user_id": user_id, "exported": len(notes)}
