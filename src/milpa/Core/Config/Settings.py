"""Configuración de milpa = la de tequio (BD, broker, correo, zona, logging, layout del proyecto) más lo
que solo usa la web: puerto, middlewares, encabezados de seguridad, CSP, sesión, CSRF, JWT, Passport,
enlaces firmados, límites de peticiones y Vite.

Hay UN solo objeto de configuración por proceso, y es de ESTA clase: tequio la toma de milpa al
arrancar (ver `milpa.Core.TequioExtension`). Lo que lee el worker y lo que lee la web es lo mismo,
y una prueba que cambia un campo lo cambia para los dos.

El .env es la ÚNICA fuente de verdad de secretos/config por-entorno.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import SettingsConfigDict

# OJO: se importa el ARCHIVO de la clase y no `tequio.Core.Config`: este módulo se carga mientras tequio
# todavía arma su objeto de configuración, y en ese momento la clase ya existe pero el objeto no.
from tequio.Core.Config.Settings import Settings as WorkerSettings

if TYPE_CHECKING:
    settings: Settings


class Settings(WorkerSettings):
    # env_file NO está clavado al CWD: se lee de MILPA_ENV_FILE (default ".env"). Así un
    # mismo despliegue puede apuntar a otro archivo (p. ej. MILPA_ENV_FILE=/run/secrets/app.env
    # en docker) SIN symlinkear .env al CWD del proceso — el hack que antes necesitaban los
    # beats en contenedores. Es la ruta tal cual la entrega el SO (relativa al CWD o absoluta).
    model_config = SettingsConfigDict(
        env_file=os.environ.get("MILPA_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Infraestructura ---
    # Default sqlite local: milpa arranca y se usa SIN configurar nada (zero-config, como
    # Django en dev) → `milpa new`/`milpa serve` funcionan de inmediato. En QA/prod pon tu
    # motor real en .env: DATABASE_URL=postgresql+psycopg://... (o mysql+pymysql://...).
    database_url: str = "sqlite:///./milpa.db"

    # --- Operativo ---
    app_port: int = 8000  # puerto del servidor web (`jornal serve`)

    # --- HTTP / middlewares (todos coma-separados; defaults SEGUROS) ---
    # CORS: vacío => NO se monta CORS (same-origin, seguro). En dev pon el origin de
    # tu front (p. ej. "http://localhost:3000"). NUNCA "*" con credentials en prod.
    cors_allow_origins: str = ""
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"
    cors_allow_credentials: bool = False
    # TrustedHost: "*" => off. Fija dominios en prod (anti Host-header attack).
    trusted_hosts: str = "*"
    # GZip: off por default (en prod suele hacerse mejor en nginx/proxy).
    gzip_enabled: bool = False
    gzip_min_size: int = 500

    # --- HTTP / security headers (defensivos; defaults SEGUROS, todo apagable) ---
    # Trío seguro (nosniff + X-Frame-Options + Referrer-Policy): ON por default (downside ~0).
    security_headers_enabled: bool = True
    security_frame_options: str = "DENY"  # DENY | SAMEORIGIN | "" (no mandar)
    security_referrer_policy: str = "no-referrer"
    # HSTS: fuerza HTTPS en el navegador. OFF por default (solo tiene sentido sirviendo
    # HTTPS; encenderlo mal "encierra" al cliente en https). Actívalo en prod tras TLS.
    hsts_enabled: bool = False
    hsts_max_age: int = 31536000  # 1 año (segundos)
    hsts_include_subdomains: bool = True
    # CSP: defensa contra XSS (incluido el robo de tokens en cookies legibles por JS). Va en
    # REPORT-ONLY por default (csp_report_only=True): el navegador REPORTA las violaciones pero
    # NO bloquea — seguro para CUALQUIER app existente (un CSP estricto en enforcing sí rompe la
    # página; en report-only nunca). Afinas con los reportes y, cuando esté limpio, pones
    # csp_report_only=false (enforcing). El default es estricto a propósito: el `<script>` inline
    # de __ENV se REPORTA (no se bloquea) para que sepas nóncearlo antes de enforce. Vacío => off.
    content_security_policy: str = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    csp_report_only: bool = True  # True => header Content-Security-Policy-Report-Only (observa, no bloquea)
    csp_report_uri: str = ""  # opcional: URL a donde el navegador POSTea las violaciones (report-uri)
    # Nonce de CSP: un valor nuevo en cada request que se agrega a `script-src` ('nonce-…') y que el shell pone en sus
    # <script> pegados (env_script() y `{{ csp_nonce() }}`): con él la política ya no los reporta y en enforcing corren.
    # Si la política ya permite 'unsafe-inline' no se agrega (un nonce lo apagaría y romperían los scripts sin nonce).
    csp_nonce_enabled: bool = True

    # --- Errores (RFC 9457 Problem Details) ---
    # Base del campo `type` de los errores. Vacío => "about:blank" (default RFC-correcto).
    # Si publicas docs de errores, apúntalo ahí: "https://tudominio.com/problems".
    problem_base_url: str = ""

    # --- Correo (fallback de destinatarios cuando system_config no tiene el name) ---
    admin_system_mails: str = ""  # coma-separado; = config('constants.admin_system_mails')
    mail_cco_recipient: str = ""  # = config('constants.mail_cco_recipient')
    # Compartimos BD con esquema legacy: NUNCA crear/alterar tablas solos.
    auto_create_tables: bool = False

    # --- Auth propia (login de milpa: JWT + sesión; ver milpa/Core/Auth) ---
    auth_guard: str = "jwt"  # guard por default: jwt | session | passport
    # Modelo Authenticatable que usa el SqlAlchemyUserProvider (ruta dotted). Lo genera el demo.
    auth_user_model: str = "milpa.Models.User.User"
    jwt_secret: str = ""  # HS256: OBLIGATORIO para emitir/validar los JWT propios
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 3600  # vigencia del JWT (1 h)
    # Tenet "nunca falla en silencio": una ability sin @policy registrada se DENIEGA (seguro)
    # y se LOGUEA (WARNING). Con esto en True (dev/test), TRUENA en su lugar — para cazar el
    # olvido del @policy o del discovery de inmediato. Default False (secure en prod).
    auth_strict_abilities: bool = False

    # --- Enlaces firmados (URL.signed / URL.temporary_signed / @Signed) ---
    # Llave maestra HMAC de los enlaces firmados. PROPIA a propósito (no la de sesión ni la del
    # JWT): rotar una no debe invalidar las otras. Vacía => firmar/verificar truena con instrucción.
    url_signing_key: str = Field(default="", validation_alias=AliasChoices("URL_SIGNING_KEY"))
    # Llaves anteriores, separadas por coma: se ACEPTAN al verificar (no se firma con ellas). Es
    # como se rota sin tirar los enlaces que ya salieron en correos.
    url_signing_previous_keys: str = Field(default="", validation_alias=AliasChoices("URL_SIGNING_PREVIOUS_KEYS"))

    # --- Rate limiting (SlowAPI) ---
    # Activa los @rate_limit declarados. En False, TODOS son no-op (útil para tests/local).
    rate_limit_enabled: bool = True
    # Límite GLOBAL opcional aplicado a toda la app (p. ej. "200/minute"). Vacío = sin global;
    # solo cuentan los @rate_limit por-ruta.
    rate_limit_default: str = ""
    # Backend de conteo: "memory://" (por-proceso, default) o "redis://host:6379" en prod
    # multi-worker (memoria NO se comparte entre workers; ahí el límite se multiplica por worker).
    rate_limit_storage_uri: str = "memory://"
    # X-RateLimit-* + Retry-After en las respuestas. Default OFF (la estilo milpa: endpoints limpios):
    # SlowAPI EXIGE un `response: Response` en cada handler limitado para inyectarlos, y nosotros
    # devolvemos dicts. Actívalo solo si añades `response: Response` a tus rutas limitadas; entonces
    # el 429 también sale con headers completos.
    rate_limit_headers: bool = False

    # --- Cookies ---
    # Prefijo de TODAS las cookies de la app (sesión, CSRF). Si los nombres de abajo se
    # dejan vacíos, se derivan como "<cookie_prefix>_session" / "<cookie_prefix>_csrf".
    # Default: "milpa".
    cookie_prefix: str = "milpa"

    # --- Auth: sesión cookie (carril browser/HTMX, estilo Sanctum) ---
    # Firma la cookie de sesión (Starlette SessionMiddleware). Vacío => no se monta la sesión.
    session_secret: str = ""
    session_cookie: str = ""  # vacío => "<cookie_prefix>_session"
    session_ttl_seconds: int = 1209600  # 14 días
    session_secure: bool = False  # True en PROD (HTTPS): cookie con flag Secure. HttpOnly siempre on.
    session_same_site: str = "lax"  # lax | strict | none

    # --- CSRF (double-submit cookie; protege el carril cookie/sesión, exime bearer/JWT) ---
    csrf_enabled: bool = True
    csrf_cookie: str = ""  # vacío => "<cookie_prefix>_csrf". NO HttpOnly (el front lo lee y reenvía)
    csrf_header: str = "X-CSRF-Token"

    @model_validator(mode="after")
    def _derive_cookie_names(self) -> Self:
        """Deriva los nombres de cookies del prefijo cuando no se fijaron explícitos."""
        if not self.session_cookie:
            self.session_cookie = f"{self.cookie_prefix}_session"
        if not self.csrf_cookie:
            self.csrf_cookie = f"{self.cookie_prefix}_csrf"
        return self

    # --- Auth: llave pública de Passport (RS256, tokens EXTERNOS de Laravel) ---
    passport_public_key: str | None = None
    passport_public_key_path: str | None = None
    passport_expected_audience: str | None = None

    # --- Layout del PROYECTO (lo web; lo demás viene de tequio) ---
    user_static_dir: str = ""  # p. ej. "app/Resources/Static" (se sirve en "/static")

    # Prefijo PÚBLICO de los assets (= ASSET_URL de Laravel): se antepone a las URLs
    # que EMITEN asset() y vite()/vite_asset() — para deploy detrás de un reverse
    # proxy bajo sub-ruta (ASSET_URL=/nombre-reverse) o un CDN (https://cdn.x.com).
    # NO cambia los mounts (el proxy stripea el prefijo antes de llegar a la app) y
    # en DEV vite() lo ignora (los módulos salen del dev server, vía hot-file).
    # DEBE coincidir con el ASSET_URL con el que se buildea el frontend
    # (vite-plugin-milpa lee la MISMA env var en build).
    # Si es RUTA (/prefijo, no URL de CDN), TAMBIÉN viaja como root_path ASGI en
    # `jornal serve`: una sola variable y la app entera sabe que vive bajo el
    # prefijo (BASE_PATH del window.__ENV, redirects vía base_path()) — agnóstica
    # del reverse proxy, cero flags.
    asset_url: str = ""

    # --- Vite (asset-pipeline del frontend, estilo laravel-vite; OPT-IN) ---
    # Carpeta convencional de APPS frontend (microfrontends por vertical: cada equipo
    # su app, con su tecnología — React/Vue/Svelte; Vite las cubre). AUTO-DETECCIÓN:
    # es app toda carpeta con `hot` (dev corriendo) o `dist/.vite/manifest.json`
    # (build hecho). Sin apps detectadas la feature muere en paz (no se monta nada).
    vite_apps_dir: str = "surcos"
    # Carpeta public/ del PROYECTO (estilo Laravel): el build de cada surco cae en
    # "<public>/<app>" (lo hace vite-plugin-milpa) y milpa la monta COMPLETA en
    # VITE_ASSETS_URL. Las fuentes viven en VITE_APPS_DIR; aquí solo artefactos.
    vite_public_dir: str = "public"
    # Override EXPLÍCITO para una sola app (estilo Laravel con el frontend en la raíz
    # del proyecto): apunta directo al dist/ y se ignora la auto-detección.
    vite_dist_dir: str = ""  # p. ej. "public/vite"
    # Hot-file del modo una-sola-app (con VITE_DIST_DIR). Vacío => "<dist>/../hot".
    # En multi-app el hot-file SIEMPRE es "<app>/hot" (uno por equipo).
    vite_hot_file: str = ""
    # Raíz pública de los assets: cada app se sirve en "<assets_url>/<app>" (multi-app)
    # o directo en "<assets_url>" (modo explícito). DEBE coincidir con el `base` del
    # vite.config del frontend (los chunks se referencian entre sí con esa base).
    vite_assets_url: str = "/vite"

    def load_passport_public_key(self) -> str | None:
        if self.passport_public_key:
            return self.passport_public_key
        if self.passport_public_key_path:
            with open(self.passport_public_key_path, encoding="utf-8") as file:
                return file.read()
        return None


def __getattr__(name: str) -> Any:
    """`from milpa.Core.Config.Settings import settings` = el objeto único del proceso (lo arma tequio)."""
    if name == "settings":
        from tequio.Core.Config import settings

        return settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
