"""Rutas FIRMADAS y con vencimiento (= `URL::signedRoute` / `temporarySignedRoute` + middleware
`signed` de Laravel).

Un enlace firmado lleva en su propio query string la prueba de que lo armó el servidor y hasta
cuándo vale: nadie puede cambiarle un parámetro ni alargarle la vida sin invalidar la firma. Sirve
para lo que se abre FUERA de una sesión —un enlace en un correo, una descarga que caduca—:

    from datetime import timedelta
    from milpa import URL, Signed

    link = URL.temporary_signed("/v1/reportes/42/pdf", timedelta(hours=24),
                                purpose="report.download", base_url=settings.app_url)

    @Get("/reportes/{report_id}/pdf")
    @Signed(purpose="report.download")
    def download(self, report_id: int) -> Response: ...

Cómo se firma, y por qué así:

  - **HMAC-SHA256** sobre `purpose`, el PATH y el query CANÓNICO (pares ordenados, sin
    `signature`). El vencimiento (`expires`, epoch en segundos) va DENTRO del query firmado: no se
    puede estirar sin romper la firma.
  - **Relativa, no absoluta.** Se firma el path, no el host. Laravel firma la URL completa por
    default y detrás de un proxy (subcarpeta, túnel, otro Host) la firma deja de coincidir; el
    parche típico es forzar la raíz antes de firmar. Aquí el dominio lo pone quien arma el enlace
    (`base_url`) y no forma parte de lo que se verifica. El path se toma SIN el `root_path` de
    ASGI, así que montar la app bajo un prefijo no rompe firmas.
  - **`purpose` separa dominios.** Una firma de "descargar reporte" no sirve para "activar
    cuenta" aunque el path coincidiera: la llave de cada propósito se DERIVA de la maestra.
  - **Llave propia** (`URL_SIGNING_KEY`), no la de la sesión ni la del JWT: rotar una no debe
    invalidar las otras. Con `URL_SIGNING_PREVIOUS_KEYS` se rota sin tirar los enlaces vivos (se
    firma con la nueva; se acepta cualquiera).
  - **Comparación en tiempo constante** (`hmac.compare_digest`) y el vencimiento se revisa SOLO si
    la firma es válida: una firma inventada no averigua nada sobre si el enlace venció.

Lo que esto NO es: un token de un solo uso. Un enlace firmado vale todas las veces que se abra
hasta que vence. Para restablecer una contraseña o activar una cuenta, combínalo con un token
guardado en la base que se CONSUMA (ver la guía de autenticación).

Nunca falla en silencio: firmar sin `URL_SIGNING_KEY` truena con instrucción, en vez de producir
enlaces que nadie podría verificar.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends
from starlette.requests import Request

from milpa.Core.Config import settings
from milpa.Core.Errors import DomainError

SIGNATURE_PARAM = "signature"
EXPIRES_PARAM = "expires"

# Etiqueta de derivación: cambiarla invalida TODAS las firmas emitidas (es parte de la llave).
_KEY_LABEL = b"milpa.signed-url.v1"


class InvalidSignatureError(DomainError):
    """El enlace no lo firmó este servidor, o alguien le cambió algo (= 403)."""

    status_code = 403
    error_code = "invalid_signature"
    title = "Forbidden"


class ExpiredSignatureError(DomainError):
    """La firma es auténtica pero el enlace ya venció (= 403). Código aparte porque la interfaz
    tiene algo útil que decir ("pida otro enlace"), y solo se revela con una firma VÁLIDA."""

    status_code = 403
    error_code = "signature_expired"
    title = "Forbidden"


class SigningKeyMissingError(RuntimeError):
    """Se intentó firmar o verificar sin `URL_SIGNING_KEY` configurada."""


def _keys() -> list[bytes]:
    current = settings.url_signing_key.strip()
    if not current:
        raise SigningKeyMissingError(
            "URL_SIGNING_KEY está vacía: no se pueden firmar ni verificar enlaces. Genera una con "
            '`python -c "import secrets; print(secrets.token_urlsafe(48))"` y ponla en el .env.'
        )
    previous = [key.strip() for key in settings.url_signing_previous_keys.split(",") if key.strip()]
    return [key.encode() for key in (current, *previous)]


def _derived_key(master: bytes, purpose: str) -> bytes:
    """Una llave por propósito, derivada de la maestra (separación de dominios)."""
    return hmac.new(master, _KEY_LABEL + b"\x00" + purpose.encode(), hashlib.sha256).digest()


def _canonical_query(pairs: list[tuple[str, str]]) -> str:
    """Pares ordenados por llave y valor, sin la firma. Ordenar hace que reordenar el query en el
    camino (proxies, clientes de correo) no rompa la firma; conservar repetidos evita que
    `?a=1&a=2` y `?a=2` firmen igual."""
    return urlencode(sorted((key, value) for key, value in pairs if key != SIGNATURE_PARAM))


def _signature(key: bytes, purpose: str, path: str, pairs: list[tuple[str, str]]) -> str:
    message = f"{purpose}\n{path}\n{_canonical_query(pairs)}".encode()
    return hmac.new(_derived_key(key, purpose), message, hashlib.sha256).hexdigest()


def _expires_at(expires: datetime | timedelta | int) -> int:
    if isinstance(expires, timedelta):
        return int(time.time() + expires.total_seconds())
    if isinstance(expires, datetime):
        if expires.tzinfo is None:
            raise ValueError("`expires` necesita zona horaria: un datetime naive es ambiguo.")
        return int(expires.timestamp())
    return int(expires)


def _request_path(request: Request) -> str:
    """El path de la RUTA, sin el prefijo de montaje (`root_path`): el mismo que se firmó."""
    path: str = request.scope.get("path", request.url.path)
    root_path: str = request.scope.get("root_path", "")
    if root_path and path.startswith(root_path):
        path = path[len(root_path) :] or "/"
    return path


class URL:
    """Firma y verifica enlaces (= la parte "signed" de `Illuminate\\Routing\\UrlGenerator`)."""

    @staticmethod
    def signed(path: str, params: Mapping[str, Any] | None = None, *, purpose: str = "", base_url: str = "") -> str:
        """Enlace firmado SIN vencimiento (= `URL::signedRoute`). Úsalo poco: un enlace que nunca
        vence es una credencial eterna. Prefiere `temporary_signed`."""
        return URL._build(path, params, purpose=purpose, base_url=base_url, expires=None)

    @staticmethod
    def temporary_signed(
        path: str,
        expires: datetime | timedelta | int,
        params: Mapping[str, Any] | None = None,
        *,
        purpose: str = "",
        base_url: str = "",
    ) -> str:
        """Enlace firmado que vence (= `URL::temporarySignedRoute`). `expires`: un `timedelta`
        desde ahora, un `datetime` con zona, o epoch en segundos."""
        return URL._build(path, params, purpose=purpose, base_url=base_url, expires=_expires_at(expires))

    @staticmethod
    def _build(path: str, params: Mapping[str, Any] | None, *, purpose: str, base_url: str, expires: int | None) -> str:
        if not path.startswith("/"):
            raise ValueError(f"Se firma un PATH absoluto de la app ('/v1/...'), no {path!r}.")
        if params and (SIGNATURE_PARAM in params or EXPIRES_PARAM in params):
            raise ValueError(f"`{SIGNATURE_PARAM}` y `{EXPIRES_PARAM}` los pone la firma, no los parámetros.")
        pairs = [(str(key), str(value)) for key, value in (params or {}).items() if value is not None]
        if expires is not None:
            pairs.append((EXPIRES_PARAM, str(expires)))
        signature = _signature(_keys()[0], purpose, path, pairs)
        query = urlencode([*pairs, (SIGNATURE_PARAM, signature)])
        return f"{base_url.rstrip('/')}{path}?{query}"

    @staticmethod
    def has_valid_signature(request: Request, *, purpose: str = "") -> bool:
        """True si la firma es auténtica Y no ha vencido (= `$request->hasValidSignature()`)."""
        try:
            URL.verify(request, purpose=purpose)
        except InvalidSignatureError, ExpiredSignatureError:
            return False
        return True

    @staticmethod
    def verify(request: Request, *, purpose: str = "") -> None:
        """Lanza `InvalidSignatureError` o `ExpiredSignatureError` (403, RFC 9457)."""
        pairs = parse_qsl(request.url.query, keep_blank_values=True)
        provided = [value for key, value in pairs if key == SIGNATURE_PARAM]
        if len(provided) != 1:
            raise InvalidSignatureError("El enlace no es válido.")

        path = _request_path(request)
        if not any(hmac.compare_digest(_signature(key, purpose, path, pairs), provided[0]) for key in _keys()):
            raise InvalidSignatureError("El enlace no es válido.")

        # Solo con firma auténtica se mira el vencimiento: no es un oráculo para firmas inventadas.
        expires = [value for key, value in pairs if key == EXPIRES_PARAM]
        if expires:
            if len(expires) != 1 or not expires[0].isdigit():
                raise InvalidSignatureError("El enlace no es válido.")
            if int(expires[0]) < time.time():
                raise ExpiredSignatureError("El enlace ya venció.")


def require_signature(*, purpose: str = "") -> Callable[[Request], None]:
    """Dependency: exige firma válida y vigente (= middleware `signed` de Laravel)."""

    def dependency(request: Request) -> None:
        URL.verify(request, purpose=purpose)

    return dependency


def Signed(*, purpose: str = "") -> Callable[[Any], Any]:
    """Decorador de método de `@Controller`: la ruta solo responde a enlaces firmados por
    `URL.signed`/`URL.temporary_signed` con el MISMO `purpose` (azúcar sobre `require_signature`)."""

    def decorator(func: Any) -> Any:
        from milpa.Core.Http.Routing import add_route_dependency

        add_route_dependency(func, Depends(require_signature(purpose=purpose)))
        return func

    return decorator
