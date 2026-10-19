"""Middleware ASGI que agrega headers HTTP defensivos a cada respuesta.

Headers como `X-Content-Type-Options: nosniff`, `X-Frame-Options`, `Referrer-Policy` y
`Strict-Transport-Security` (HSTS) endurecen la app en el navegador (anti-MIME-sniffing,
anti-clickjacking, control de referrer, forzar HTTPS). Aquí va la MAQUINARIA genérica
(inyectar un set de headers); QUÉ headers se mandan lo decide `register_middlewares`
desde Settings (defaults seguros, todo configurable/apagable).

Es ASGI puro (no `BaseHTTPMiddleware`) para no romper respuestas en streaming ni las
background tasks, y para ser liviano. Usa `setdefault`: si el endpoint YA fijó un header
(p. ej. un CSP específico de una ruta), no lo pisa.

Nonce de CSP (`csp_nonce=True`): cada request lleva un valor nuevo e imposible de adivinar en
`request.state.csp_nonce`, y el CSP lo agrega a `script-src` ('nonce-…'). El shell lo pone en sus
`<script>` pegados (`env_script()`, `{{ csp_nonce() }}`): esos corren y uno inyectado (sin el nonce
de esta respuesta) no. Si `script-src` ya permite 'unsafe-inline' no se agrega: en los navegadores
con CSP 2, un nonce apaga 'unsafe-inline' y romperían los scripts pegados sin nonce.
"""

from __future__ import annotations

import secrets

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Los dos nombres del header de CSP (enforcing y report-only), en minúsculas como los da Starlette.
CSP_HEADER_NAMES = frozenset({"content-security-policy", "content-security-policy-report-only"})
# Dónde queda el nonce de la request (request.state.csp_nonce).
CSP_NONCE_STATE_KEY = "csp_nonce"
# Bytes de azar del nonce (16 = 128 bits, lo que pide la recomendación de CSP 3).
CSP_NONCE_BYTES = 16


def policy_with_nonce(policy: str, nonce: str) -> str:
    """La política con 'nonce-<nonce>' en su `script-src`. Sin `script-src`, o si ya permite
    'unsafe-inline' (un nonce lo apagaría), regresa la política tal cual."""
    directives = [directive.strip() for directive in policy.split(";") if directive.strip()]
    with_nonce = []
    for directive in directives:
        name = directive.split(" ", 1)[0].lower()
        if name == "script-src" and "'unsafe-inline'" not in directive:
            directive = f"{directive} 'nonce-{nonce}'"
        with_nonce.append(directive)
    return "; ".join(with_nonce)


class SecurityHeadersMiddleware:
    """Inyecta `headers` en la respuesta de cada request HTTP (sin pisar los ya puestos)."""

    def __init__(self, app: ASGIApp, headers: dict[str, str], csp_nonce: bool = False) -> None:
        self.app = app
        self._headers = headers
        self._csp_nonce = csp_nonce

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Solo HTTP: websockets/lifespan pasan tal cual.
        if scope["type"] != "http" or not self._headers:
            await self.app(scope, receive, send)
            return

        # el nonce de ESTA request: lo lee el shell (request.state.csp_nonce) y va en el CSP de la respuesta
        nonce = secrets.token_urlsafe(CSP_NONCE_BYTES) if self._csp_nonce else ""
        if nonce:
            scope.setdefault("state", {})[CSP_NONCE_STATE_KEY] = nonce

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._headers.items():
                    # setdefault: respeta un header que el endpoint ya haya fijado.
                    if name not in headers:
                        headers[name] = (
                            policy_with_nonce(value, nonce) if nonce and name.lower() in CSP_HEADER_NAMES else value
                        )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
