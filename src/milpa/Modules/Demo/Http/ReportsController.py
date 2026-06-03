"""Carril API VERSIONADO del demo — muestra el API versioning (Fase 3) EN ACCIÓN.

Mismo recurso (`/reports/notes`), dos versiones que CONVIVEN: el cliente viejo sigue pegándole a
`/v1/...` y el nuevo a `/v2/...`, sin romper nada. La URL la antepone `@Controller(version=...)`
y el handler lee su versión con `api_version(request)`:

    GET /v1/reports/notes  → {"version":"v1", "total": N}                       (básico)
    GET /v2/reports/notes  → {"version":"v2", "total": N, "archived": M, "active": N-M}   (evolucionado)

Así se EVOLUCIONA la API agregando v2 sin tocar v1. Ambos exigen JWT (mismo guard que el resto).
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from sqlalchemy import and_

from milpa.Core.Auth import Authenticatable, guarded
from milpa.Core.Http import Controller, Get, api_version
from milpa.Models.Note import Note
from milpa.Modules.Demo.Repositories.NoteRepository import NoteRepository

_JwtUser = Depends(guarded("jwt"))


@Controller("/reports", version="v1", tags=["demo-versioned"])
class ReportsV1Controller:
    @Get("/notes")
    def notes_report(self, request: Request, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        """v1: reporte BÁSICO — solo el total de notas del usuario."""
        owner_id = user.get_auth_identifier()
        return {"version": api_version(request), "total": NoteRepository().count(where=Note.owner_id == owner_id)}


@Controller("/reports", version="v2", tags=["demo-versioned"])
class ReportsV2Controller:
    @Get("/notes")
    def notes_report(self, request: Request, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        """v2: reporte EVOLUCIONADO — desglosa archivadas/activas. NO rompe a los clientes de v1."""
        owner_id = user.get_auth_identifier()
        repo = NoteRepository()
        total = repo.count(where=Note.owner_id == owner_id)
        archived = repo.count(where=and_(Note.owner_id == owner_id, Note.archived.is_(True)))
        return {"version": api_version(request), "total": total, "archived": archived, "active": total - archived}
