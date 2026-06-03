"""Carril WEB del demo: un mini-DASHBOARD server-rendered (HTMX + Alpine + Pico.css), auth por
SESIÓN cookie (+ CSRF). Sin Inertia: HTMX cubre la interactividad (búsqueda en vivo + scroll
infinito) y Alpine las micro-interacciones.

No autenticado → redirect a /login (browser-friendly, no el 401 JSON del carril API). Las
mutaciones post-login van por HTMX (el layout reenvía el token CSRF). Login/registro son forms
normales (aún sin sesión → CSRF exento).

Búsqueda + scroll comparten un endpoint de partial por lista: `append_only = offset > 0`
(offset 0 = búsqueda → reemplaza la lista; offset>0 = load-more → reemplaza el marcador).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi import Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import and_, or_

from milpa.Core.Auth import Auth, set_current_user
from milpa.Core.Auth.Guards import SessionGuard
from milpa.Core.Config import settings
from milpa.Core.Errors import ConflictError
from milpa.Core.Events import dispatch
from milpa.Core.Http import Controller, Get, Post
from milpa.Core.Translate import current_locale
from milpa.Core.View import view
from milpa.Models.Note import Note
from milpa.Models.User import User
from milpa.Modules.Demo.Events import NoteCreated, UserRegistered
from milpa.Modules.Demo.Repositories.NoteRepository import NoteRepository
from milpa.Modules.Demo.Repositories.UserRepository import UserRepository
from milpa.Modules.Demo.Services.NoteService import NoteService
from milpa.Modules.Demo.Services.UserService import UserService

# Las policies ABAC se auto-registran con @policy (import_all_policies al arranque); sin
# register_policies() manual aquí.

NOTES_PER_PAGE = 6
USERS_PER_PAGE = 12

# Favicon para servirlo también en la RAÍZ (/favicon.ico), que es lo que el navegador pide por
# default para el ícono de la pestaña (además del <link rel="icon"> del layout).
_FAVICON = Path(__file__).resolve().parents[1] / "Resources" / "Static" / "favicon.ico"


def _web_user(request: Request) -> User | None:
    """Resuelve el usuario de la sesión-cookie (o None) y lo fija en el contextvar."""
    user = SessionGuard().authenticate(request)
    set_current_user(user)
    return cast("User | None", user)


def _page(name: str, *, user: User | None = None, **context: object) -> HTMLResponse:
    return view(
        name, {"user": user, "csrf_cookie": settings.csrf_cookie, "csrf_header": settings.csrf_header, **context}
    )


def _notes_results(user: User, *, offset: int = 0, q: str = "", append_only: bool = False) -> HTMLResponse:
    where = Note.owner_id == user.get_auth_identifier()
    if q:
        where = and_(where, Note.title.ilike(f"%{q}%"))
    page = NoteRepository().paginate(offset=offset, limit=NOTES_PER_PAGE, order_by=Note.id.desc(), where=where)
    return view(
        "demo/_notes_results",
        {
            "notes": page.items,
            "has_more": page.has_more,
            "next_offset": page.next_offset,
            "q": q,
            "append_only": append_only,
        },
    )


def _users_results(*, offset: int = 0, q: str = "", append_only: bool = False) -> HTMLResponse:
    where = None
    if q:
        pattern = f"%{q}%"
        where = or_(User.name.ilike(pattern), User.email.ilike(pattern))
    page = UserRepository().paginate(offset=offset, limit=USERS_PER_PAGE, order_by=User.id.asc(), where=where)
    return view(
        "demo/_users_results",
        {
            "users": page.items,
            "has_more": page.has_more,
            "next_offset": page.next_offset,
            "q": q,
            "append_only": append_only,
        },
    )


@Controller("", tags=["demo-web"])
class WebController:
    # ---------------------------------------------------------------- auth
    @Get("/")
    def home(self, request: Request) -> Response:
        return RedirectResponse("/dashboard" if _web_user(request) else "/login", status_code=303)

    @Get("/favicon.ico", include_in_schema=False)
    def favicon(self) -> FileResponse:
        return FileResponse(_FAVICON)

    @Get("/login")
    def login_form(self, request: Request) -> HTMLResponse:
        return _page("demo/login", error=None)

    @Post("/login")
    def login_submit(self, request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
        user = Auth.validate_credentials(email, password)
        if user is None:
            return _page("demo/login", error="Credenciales inválidas.")
        Auth.login(request, user)
        return RedirectResponse("/dashboard", status_code=303)

    @Get("/register")
    def register_form(self, request: Request) -> HTMLResponse:
        return _page("demo/register", error=None)

    @Post("/register")
    def register_submit(
        self, request: Request, name: str = Form(""), email: str = Form(...), password: str = Form(...)
    ) -> Response:
        try:
            created = UserService().register(name, email, password)
        except ConflictError:
            return _page("demo/register", error="Ese email ya está registrado.")
        # Evento de dominio → el Observer avisa al admin (igual que el carril API).
        dispatch(UserRegistered(user_id=int(created["id"]), name=name, email=email))
        request.session["user_id"] = str(created["id"])  # login inmediato
        return RedirectResponse("/dashboard", status_code=303)

    @Post("/logout")
    def logout(self, request: Request) -> Response:
        Auth.logout(request)
        return Response(status_code=204, headers={"HX-Redirect": "/login"})

    # ---------------------------------------------------------------- dashboard
    @Get("/dashboard")
    def dashboard(self, request: Request) -> Response:
        user = _web_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        is_admin = "admin" in user.get_roles()
        notes_count = NoteRepository().count(where=Note.owner_id == user.get_auth_identifier())
        users_count = UserRepository().count() if is_admin else None
        return _page("demo/dashboard", user=user, notes_count=notes_count, users_count=users_count)

    # ---------------------------------------------------------------- notas (search + scroll)
    @Get("/notes")
    def notes_page(self, request: Request) -> Response:
        user = _web_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        page = NoteRepository().paginate(
            offset=0, limit=NOTES_PER_PAGE, order_by=Note.id.desc(), where=Note.owner_id == user.get_auth_identifier()
        )
        return _page(
            "demo/notes",
            user=user,
            notes=page.items,
            has_more=page.has_more,
            next_offset=page.next_offset,
            q="",
            append_only=False,
        )

    @Get("/partials/notes")
    def notes_partial(self, request: Request, offset: int = 0, q: str = "") -> Response:
        user = _web_user(request)
        if user is None:
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        return _notes_results(user, offset=offset, q=q, append_only=offset > 0)

    @Post("/notes")
    def create_note(self, request: Request, title: str = Form(...), body: str = Form("")) -> Response:
        user = _web_user(request)
        if user is None:
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        created = NoteService().create(user.get_auth_identifier(), title, body)
        # Evento de dominio → el Observer confirma al dueño por correo (auto, i18n).
        dispatch(
            NoteCreated(
                note_id=int(created["id"]),
                title=str(created["title"]),
                owner_id=user.get_auth_identifier(),
                owner_email=user.email,
                locale=current_locale(),
            )
        )
        return _notes_results(user)  # primera página, lista completa

    @Post("/notes/{note_id}/delete")
    def delete_note(self, request: Request, note_id: int) -> Response:
        user = _web_user(request)
        if user is None:
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        NoteService().delete(note_id, actor=user)  # ABAC: dueño o moderador (Gate)
        return _notes_results(user)

    # ---------------------------------------------------------------- usuarios (admin, search + scroll)
    @Get("/admin/users")
    def admin_users_page(self, request: Request) -> Response:
        user = _web_user(request)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        if "admin" not in user.get_roles():  # RBAC
            forbidden = _page("demo/forbidden", user=user)
            forbidden.status_code = 403
            return forbidden
        page = UserRepository().paginate(offset=0, limit=USERS_PER_PAGE, order_by=User.id.asc())
        return _page(
            "demo/admin_users",
            user=user,
            users=page.items,
            has_more=page.has_more,
            next_offset=page.next_offset,
            q="",
            append_only=False,
        )

    @Get("/partials/users")
    def users_partial(self, request: Request, offset: int = 0, q: str = "") -> Response:
        user = _web_user(request)
        if user is None:
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        if "admin" not in user.get_roles():
            return Response(status_code=403)
        return _users_results(offset=offset, q=q, append_only=offset > 0)
