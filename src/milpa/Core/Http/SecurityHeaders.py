"""Middleware ASGI que agrega headers HTTP defensivos a cada respuesta.

Headers como `X-Content-Type-Options: nosniff`, `X-Frame-Options`, `Referrer-Policy` y
`Strict-Transport-Security` (HSTS) endurecen la app en el navegador (anti-MIME-sniffing,
anti-clickjacking, control de referrer, forzar HTTPS). Aquí va la MAQUINARIA genérica
(inyectar un set de headers); QUÉ headers se mandan lo decide `register_middlewares`
desde Settings (defaults seguros, todo configurable/apagable).

Es ASGI puro (no `BaseHTTPMiddleware`) para no romper respuestas en streaming ni las
background tasks, y para ser liviano. Usa `setdefault`: si el endpoint YA fijó un header
(p. ej. un CSP específico de una ruta), no lo pisa.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Inyecta `headers` en la respuesta de cada request HTTP (sin pisar los ya puestos)."""

    def __init__(self, app: ASGIApp, headers: dict[str, str]) -> None:
        self.app = app
        self._headers = headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Solo HTTP: websockets/lifespan pasan tal cual.
        if scope["type"] != "http" or not self._headers:
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._headers.items():
                    # setdefault: respeta un header que el endpoint ya haya fijado.
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
