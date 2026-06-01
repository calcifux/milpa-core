"""Protección CSRF por **double-submit cookie** (middleware ASGI).

El servidor pone un token en una cookie NO-HttpOnly (`csrf_cookie`); el front/HTMX la lee y lo
reenvía en un header (`csrf_header`). En cada método NO-seguro (POST/PUT/PATCH/DELETE) el
middleware exige que header == cookie. Como el SOP impide que otro origen LEA la cookie o ponga
ese header custom cross-origin, el match prueba mismo-origen. Va de la mano con `SameSite=Lax`.

CSRF SOLO aplica al carril **cookie/sesión** (modelo Sanctum): la verificación corre únicamente
cuando la request trae la **cookie de sesión** (la credencial ambiente que un atacante podría
explotar). Quedan EXENTAS: las requests con `Authorization: Bearer` (API/JWT) y las que NO traen
sesión (clientes API por JSON, y el propio login/registro, que aún no tienen sesión). El rechazo
es un 403 `application/problem+json` emitido directo desde el ASGI.
"""

from __future__ import annotations

import json
import secrets
from hmac import compare_digest

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from milpa.Core.Config import settings
from milpa.Core.Http.ProblemDetails import PROBLEM_JSON_MEDIA_TYPE, build_problem

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _cookie_value(headers: Headers, name: str) -> str | None:
    cookie_header = headers.get("cookie")
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return None


def _has_bearer(headers: Headers) -> bool:
    return headers.get("authorization", "").lower().startswith("bearer ")


def _csrf_set_cookie(token: str) -> str:
    # NO HttpOnly a propósito: el front/HTMX debe LEER la cookie para reenviar el header.
    attributes = [
        f"{settings.csrf_cookie}={token}",
        "Path=/",
        f"SameSite={settings.session_same_site.capitalize()}",
    ]
    if settings.session_secure:
        attributes.append("Secure")
    return "; ".join(attributes)


async def _send_csrf_forbidden(send: Send) -> None:
    body = json.dumps(
        build_problem(
            status=403,
            title="Forbidden",
            detail="Token CSRF inválido o ausente.",
            code="csrf_failed",
        )
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", PROBLEM_JSON_MEDIA_TYPE.encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


class CsrfMiddleware:
    """Double-submit CSRF: verifica los métodos no-seguros con cookie y siembra el token."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        method: str = scope["method"]
        cookie_token = _cookie_value(headers, settings.csrf_cookie)
        has_session = _cookie_value(headers, settings.session_cookie) is not None

        # Verifica SOLO si hay sesión-cookie (credencial ambiente). Bearer y sin-sesión exentos.
        if method not in _SAFE_METHODS and has_session and not _has_bearer(headers):
            header_token = headers.get(settings.csrf_header)
            if not cookie_token or not header_token or not compare_digest(cookie_token, header_token):
                await _send_csrf_forbidden(send)
                return

        # Siembra el token-cookie si aún no existe (para que el front lo pueda reenviar).
        token_to_set = None if cookie_token else secrets.token_urlsafe(32)

        async def send_with_csrf_cookie(message: Message) -> None:
            if message["type"] == "http.response.start" and token_to_set is not None:
                MutableHeaders(scope=message).append("set-cookie", _csrf_set_cookie(token_to_set))
            await send(message)

        await self.app(scope, receive, send_with_csrf_cookie)
