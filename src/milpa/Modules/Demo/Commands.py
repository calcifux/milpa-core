"""Comandos del demo para el [[Mediator]] (command bus 1:1). Un comando es una INTENCIÓN
que envías con `send(ArchiveNote(...))` y de la que esperas un resultado; lo resuelve UN handler
(`Modules/Demo/Handlers/`). A diferencia de un evento (1:N, sin retorno), aquí hay 1 handler y
retorno. Lo mismo se envía desde HTTP y desde la CLI → caso de uso transport-neutral, sin duplicar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArchiveNote:
    """Archivar una nota. `actor_id` = quién la archiva (para el chequeo ABAC en el handler)."""

    note_id: int
    actor_id: int
