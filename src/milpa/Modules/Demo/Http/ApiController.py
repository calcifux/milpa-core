"""Carril API (JWT) del demo — para frontends SEPARADOS (SPA/móvil).

`POST /api/login` → JWT; el resto exige `Authorization: Bearer <jwt>` (guard 'jwt'). RBAC en
`/api/admin/users` (@require_roles admin) y ABAC en update/delete/archive de notas (Gate, dentro
del service/handler). Mismas reglas que el carril web; lo único que cambia es el mecanismo de auth.

estilo milpa demostrado aquí: al crear nota/usuario se DISPARA un evento (`dispatch`) que un Observer
convierte en correo (auto); `share` manda un correo MANUAL (`Mail.send`); `archive` reusa el
[[Mediator]] (`send`, mismo comando que la CLI); `export` encola un `@job` de background.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import Depends, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import and_, or_

from milpa.Core.Auth import Auth, Authenticatable, Gate, guarded, require_roles
from milpa.Core.Errors import UnauthorizedError
from milpa.Core.Events import dispatch
from milpa.Core.Http import Controller, Delete, Get, Post, Put, rate_limit
from milpa.Core.Mail import Mail
from milpa.Core.Mediator import send
from milpa.Core.Translate import current_locale
from milpa.Models.Note import Note
from milpa.Models.User import User
from milpa.Modules.Demo.Commands import ArchiveNote
from milpa.Modules.Demo.Events import NoteCreated, UserRegistered
from milpa.Modules.Demo.Jobs.ExportNotesJob import export_user_notes
from milpa.Modules.Demo.Mail.ShareNoteMailable import ShareNoteMailable
from milpa.Modules.Demo.Repositories.NoteRepository import NoteRepository
from milpa.Modules.Demo.Repositories.UserRepository import UserRepository
from milpa.Modules.Demo.Serializers import note_dict, user_dict
from milpa.Modules.Demo.Services.NoteService import NoteService
from milpa.Modules.Demo.Services.UserService import UserService

# Las abilities ABAC (note.update / note.delete) se auto-registran con @policy en Policies.py
# (las descubre import_all_policies al arranque) — el controller ya NO las registra a mano.

# Guards explícitos: este carril es SIEMPRE JWT (la app sirve los dos carriles a la vez).
_JwtUser = Depends(guarded("jwt"))
_AdminJwt = Depends(require_roles("admin", guard="jwt"))

_API_PER_PAGE = 20


class RegisterInput(BaseModel):
    name: str = ""
    email: str
    password: str


class LoginInput(BaseModel):
    email: str
    password: str


class NoteInput(BaseModel):
    title: str
    body: str = ""


class ShareInput(BaseModel):
    to_email: str


@Controller("/api", tags=["demo-api"])
class ApiController:
    @Post("/register", status_code=201)
    def register(self, body: RegisterInput) -> dict[str, Any]:
        created = UserService().register(body.name, body.email, body.password)
        # Evento de dominio → el Observer NotifyAdminOnUserRegistered avisa al admin (auto).
        dispatch(UserRegistered(user_id=int(created["id"]), name=body.name, email=body.email))
        return created

    @Post("/login")
    @rate_limit("5/minute")  # anti fuerza-bruta: máx 5 intentos/min por IP (429 RFC 9457 al exceder)
    def login(self, request: Request, body: LoginInput) -> dict[str, str]:
        token = Auth.attempt(body.email, body.password)
        if token is None:
            raise UnauthorizedError("Credenciales inválidas.")
        return {"access_token": token, "token_type": "bearer"}

    @Get("/me")
    def me(self, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        return user_dict(cast("User", user))

    @Get("/notes")
    def list_notes(self, user: Authenticatable = _JwtUser, offset: int = 0, q: str = "") -> dict[str, Any]:
        where = Note.owner_id == user.get_auth_identifier()
        if q:
            where = and_(where, Note.title.ilike(f"%{q}%"))
        page = NoteRepository().paginate(offset=offset, limit=_API_PER_PAGE, order_by=Note.id.desc(), where=where)
        return {"items": [note_dict(n) for n in page.items], "has_more": page.has_more, "next_offset": page.next_offset}

    @Post("/notes", status_code=201)
    def create_note(self, body: NoteInput, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        created = NoteService().create(user.get_auth_identifier(), body.title, body.body)
        # Evento de dominio → el Observer NotifyOwnerOnNoteCreated confirma al dueño (auto, i18n).
        owner = cast("User", user)
        dispatch(
            NoteCreated(
                note_id=int(created["id"]),
                title=str(created["title"]),
                owner_id=owner.get_auth_identifier(),
                owner_email=owner.email,
                locale=current_locale(),
            )
        )
        return created

    @Post("/notes/export", status_code=202)
    def export_notes(self, user: Authenticatable = _JwtUser) -> dict[str, str]:
        # @job de background: encola y regresa ya (broker caído → 503 RFC 9457, nunca drop mudo).
        export_user_notes.dispatch(user.get_auth_identifier())
        return {"status": "queued"}

    @Put("/notes/{note_id}")
    def update_note(self, note_id: int, body: NoteInput, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        return NoteService().update(note_id, title=body.title, body=body.body, actor=user)

    @Post("/notes/{note_id}/archive")
    def archive_note(self, note_id: int, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        # Mediator: MISMO comando que `jornal demo archive` (caso de uso transport-neutral).
        result: dict[str, Any] = send(ArchiveNote(note_id=note_id, actor_id=user.get_auth_identifier()))
        return result

    @Post("/notes/{note_id}/share", status_code=202)
    def share_note(self, note_id: int, body: ShareInput, user: Authenticatable = _JwtUser) -> dict[str, str]:
        note = NoteRepository().find_or_fail(note_id)
        Gate.authorize("note.update", note, user=user)  # solo dueño/moderador comparte
        sharer = cast("User", user)
        # Correo MANUAL (on-demand) — contrasta con los automáticos por Observer. El endpoint
        # promete 202 (Accepted): el envío es best-effort-pero-OBSERVABLE. Si SMTP falla, el Mailer
        # ya logueó el traceback; aquí lo registramos y NO convertimos el 202 en un 500 (ni dejamos
        # al cliente bloqueado en un error de transporte que no controla).
        try:
            Mail.send(ShareNoteMailable(title=note.title, body=note.body, from_name=sharer.name), to=[body.to_email])
        except Exception:
            logger.exception("share_note | envío de correo falló | note_id:{n} to:{to}", n=note_id, to=body.to_email)
        return {"status": "accepted", "to": body.to_email}

    @Delete("/notes/{note_id}", status_code=204)
    def delete_note(self, note_id: int, user: Authenticatable = _JwtUser) -> None:
        NoteService().delete(note_id, actor=user)

    @Get("/admin/users")
    def admin_users(self, user: Authenticatable = _AdminJwt, offset: int = 0, q: str = "") -> dict[str, Any]:
        where = None
        if q:
            pattern = f"%{q}%"
            where = or_(User.name.ilike(pattern), User.email.ilike(pattern))
        page = UserRepository().paginate(offset=offset, limit=_API_PER_PAGE, order_by=User.id.asc(), where=where)
        return {"items": [user_dict(u) for u in page.items], "has_more": page.has_more, "next_offset": page.next_offset}
