"""Carril API (JWT) del demo — para frontends SEPARADOS (SPA/móvil).

`POST /api/login` → JWT; el resto exige `Authorization: Bearer <jwt>` (guard 'jwt'). RBAC en
`/api/admin/users` (@require_roles admin) y ABAC en update/delete de notas (Gate, dentro del
service). Mismas reglas que el carril web; lo único que cambia es el mecanismo de auth.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import and_, or_

from milpa.Core.Auth import Auth, Authenticatable, guarded, require_roles
from milpa.Core.Errors import UnauthorizedError
from milpa.Core.Http import Controller, Delete, Get, Post, Put
from milpa.Models.Note import Note
from milpa.Models.User import User
from milpa.Modules.Demo.Policies import register_policies
from milpa.Modules.Demo.Repositories.NoteRepository import NoteRepository
from milpa.Modules.Demo.Repositories.UserRepository import UserRepository
from milpa.Modules.Demo.Serializers import note_dict, user_dict
from milpa.Modules.Demo.Services.NoteService import NoteService
from milpa.Modules.Demo.Services.UserService import UserService

register_policies()  # registra las abilities ABAC (note.update / note.delete)

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


@Controller("/api", tags=["demo-api"])
class ApiController:
    @Post("/register", status_code=201)
    def register(self, body: RegisterInput) -> dict[str, Any]:
        return UserService().register(body.name, body.email, body.password)

    @Post("/login")
    def login(self, body: LoginInput) -> dict[str, str]:
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
        return NoteService().create(user.get_auth_identifier(), body.title, body.body)

    @Put("/notes/{note_id}")
    def update_note(self, note_id: int, body: NoteInput, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        return NoteService().update(note_id, title=body.title, body=body.body, actor=user)

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
