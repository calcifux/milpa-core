"""Configuración central tipada (pydantic-settings). El .env es la ÚNICA fuente
de verdad de secretos/config por-entorno; infraestructura va SIN default
(obligatoria) para fallar claro si falta.
"""

from __future__ import annotations

from typing import Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default local para lo ENCOLADO (broker y lock) cuando no se configura nada. Es solo
# un FALLBACK de conveniencia para dev; no asumimos que siempre haya redis (los flujos
# síncronos no lo tocan). El config expone BROKER_URL/LOCK_URL (agnósticos), no un
# "REDIS_URL" redis-específico.
_DEFAULT_LOCAL_REDIS = "redis://localhost:6379/0"


def _host_timezone() -> str:
    """IANA timezone del HOST — el default cuando no se define TIMEZONE en .env.

    El framework NO impone zona horaria: es responsabilidad del dev/devops fijar
    TIMEZONE explícito (importante sobre todo si quien monta la app no es quien la
    programa — un server suele estar en UTC). Cae a 'UTC' si no se puede detectar.
    """
    try:
        import tzlocal

        return str(tzlocal.get_localzone_name() or "UTC")
    except Exception:
        return "UTC"


class Settings(BaseSettings):
    # extra="ignore": varios módulos comparten el mismo .env; cada Settings
    # ignora las variables que no declara.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Infraestructura ---
    # Default sqlite local: milpa arranca y se usa SIN configurar nada (zero-config, como
    # Django en dev) → `milpa new`/`milpa serve` funcionan de inmediato. Siempre hay BD
    # (milpa la requiere); el default solo evita el crash de primer arranque. En QA/prod
    # pon tu motor real en .env: DATABASE_URL=postgresql+psycopg://... (o mysql+pymysql://...).
    database_url: str = "sqlite:///./milpa.db"

    # --- Colas / broker-agnostic ---
    # BROKER de Celery: CUALQUIER transporte (redis://, amqp:// RabbitMQ, sqs://, ...).
    # Vacío => redis local por default. Solo se usa para lo ENCOLADO (los flujos
    # síncronos no lo tocan). ActiveMQ NO es compatible (AMQP 1.0).
    broker_url: str = ""
    # Result backend: OPCIONAL. Nuestros crons son fire-and-forget, así que por default
    # NO hay backend (vacío). Ponlo solo si necesitas leer resultados (AsyncResult).
    result_backend_url: str = ""
    # Store de LOCKS para without_overlapping: redis da `.lock()`, los MQ no. Va aparte
    # del broker (un redis chico basta). Vacío => redis local por default.
    lock_url: str = ""

    # Visibility-timeout (segundos) — SOLO aplica a redis/SQS: si una task no se
    # reconoce en este tiempo, el broker la REENTREGA. El default lock de @cron_task se
    # deriva de aquí para garantizar `lock_timeout > visibility_timeout` por construcción.
    redis_visibility_timeout: int = 3600

    # --- Reintentos de tasks (defaults framework-wide; backoff exponencial con jitter) ---
    # Son los DEFAULTS de `retry_policy(...)` (app/Core/CeleryApp). Se pueden fijar por .env
    # O sobreescribir A MANO en código al declarar cada task. Solo afectan a tasks que OPTAN
    # por reintentar (pasan `autoretry_for`); NUNCA a los crons. 0 => sin reintentos.
    task_max_retries: int = 3
    task_retry_backoff: int = 2  # segundos base del 1er reintento (luego se duplica)
    task_retry_backoff_max: int = 600  # tope del backoff entre reintentos (10 min)

    # --- Operativo ---
    # Default GENÉRICO (Core es reutilizable): cada proyecto pone su APP_NAME en .env.
    app_name: str = "App"
    app_env: str = "qa"  # local | qa | production (como config('app.env') del legacy)
    app_port: int = 8000  # puerto del servidor web (`jornal serve`)
    # Locale de fallback de toda la app (i18n transversal: correos, API, etc.) cuando
    # no se pasa locale explícito. Override en .env con APP_FALLBACK_LOCALE.
    app_fallback_locale: str = "es"
    # Locale de Faker para factories/seeders (datos falsos). Configurable: "es_MX", "es_ES",
    # "en_US", … (cualquier locale de Faker). Lo usa milpa.Core.Database.Faker.
    faker_locale: str = "es_MX"
    # Default = zona del HOST (no la imponemos). El dev/devops DEBE fijar TIMEZONE en .env.
    timezone: str = Field(default_factory=_host_timezone)

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
    # CSP: vacío => no se manda (es ESPECÍFICO de cada app; un CSP malo rompe la página).
    content_security_policy: str = ""

    # --- Errores (RFC 9457 Problem Details) ---
    # Base del campo `type` de los errores. Vacío => "about:blank" (default RFC-correcto).
    # Si publicas docs de errores, apúntalo ahí: "https://tudominio.com/problems".
    problem_base_url: str = ""

    # --- Correo (fallback de destinatarios cuando system_config no tiene el name) ---
    admin_system_mails: str = ""  # coma-separado; = config('constants.admin_system_mails')
    mail_cco_recipient: str = ""  # = config('constants.mail_cco_recipient')

    # --- Correo (equivalente a config('mail.*') del legacy) ---
    # En local apuntan a Mailpit (localhost:1025); en QA/prod al SMTP corporativo.
    # MAIL_DRIVER (= mail.default de Laravel): cómo se MANDA.
    #   "smtp" (default) -> envía por SMTP real.
    #   "log"            -> NO envía: escribe el correo en el log (dev/sin SMTP; cross-platform).
    #   "null"/"array"   -> no-op: descarta el correo (tests / silenciar).
    mail_driver: str = "smtp"
    mail_host: str = "localhost"
    mail_port: int = 1025
    mail_username: str = ""
    mail_password: str = ""
    mail_encryption: str = ""  # "" (sin cifrado, ej. Mailpit) | "tls" (STARTTLS) | "ssl" (SMTPS)
    # Remitente. Aceptamos el nombre de Laravel (MAIL_FROM_ADDRESS) y el natural.
    mail_from_email: str = Field(
        default="no-reply@example.com",
        validation_alias=AliasChoices("MAIL_FROM_ADDRESS", "MAIL_FROM_EMAIL"),
    )
    mail_from_name: str = "App"
    # Compartimos BD con esquema legacy: NUNCA crear/alterar tablas solos.
    auto_create_tables: bool = False

    # --- Auth propia (login de milpa: JWT + sesión; ver app/Core/Auth) ---
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
    # Igual para los Observers: un observer que falla se loguea ruidoso (best-effort). Con esto
    # en True (dev/test), RE-LANZA — para que el bug del observer truene fuerte. Default False.
    events_strict: bool = False

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

    # --- Logging (Loguru) ---
    log_level: str = "INFO"
    log_json: bool = False
    log_dir: str = "logs"

    # --- Layout del PROYECTO: DÓNDE vive el código del USUARIO ---
    # milpa instalado como paquete NO puede adivinar dónde está tu proyecto contando
    # carpetas desde sí mismo (en site-packages eso apunta a otro lado). Lo lee de aquí.
    # Los DEFAULTS = el layout de ESTE repo, así no se rompe nada si no configuras.
    # Un proyecto EXTERNO los apunta a su propio paquete/carpetas vía .env:
    #   MODULES_PACKAGE=app.Modules   MODELS_PACKAGE=app.Models
    #   USER_VIEWS_DIR=app/Resources/Views   MIGRATIONS_DIR=migrations  ...
    # Paquetes (notación punteada, importables):
    modules_package: str = "milpa.Modules"  # dónde escanear los módulos (rutas/jobs/crons/seeders/i18n/vistas)
    models_package: str = "milpa.Models"  # dónde viven los modelos (se cargan en Base.metadata)
    app_commands_package: str = "milpa.Console.Commands"  # commands GENERALES del proyecto (opcional; tolera ausencia)
    # Carpetas de recursos del USUARIO (relativas al cwd del proyecto). "" => no se usan
    # (en ESTE repo van vacías: las vistas/lang/static del framework salen del paquete).
    user_views_dir: str = ""  # p. ej. "app/Resources/Views" en un proyecto externo
    user_lang_dir: str = ""  # p. ej. "app/Resources/Lang"
    user_static_dir: str = ""  # p. ej. "app/Resources/Static" (se sirve en "/static")
    # Carpeta de migraciones Alembic, relativa al cwd del proyecto. Default "migrations".
    migrations_dir: str = "migrations"

    # Prefijo PÚBLICO de los assets (= ASSET_URL de Laravel): se antepone a las URLs
    # que EMITEN asset() y vite()/vite_asset() — para deploy detrás de un reverse
    # proxy bajo sub-ruta (ASSET_URL=/nombre-reverse) o un CDN (https://cdn.x.com).
    # NO cambia los mounts (el proxy stripea el prefijo antes de llegar a la app) y
    # en DEV vite() lo ignora (los módulos salen del dev server, vía hot-file).
    # DEBE coincidir con el ASSET_URL con el que se buildea el frontend
    # (vite-plugin-milpa lee la MISMA env var en build).
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
    # Raíz del código del USUARIO donde escribe `make:*` (modelos/controllers/módulos),
    # relativa al cwd. Default "app" (el layout que genera `milpa new`). En el repo del
    # PROPIO framework, donde el código vive en src/milpa, pon APP_DIR=src/milpa en .env.
    app_dir: str = "app"

    @property
    def effective_broker_url(self) -> str:
        """Broker de Celery; cae al redis local por default si BROKER_URL está vacío."""
        return self.broker_url or _DEFAULT_LOCAL_REDIS

    @property
    def effective_lock_url(self) -> str:
        """Store de locks (redis); cae al redis local por default si LOCK_URL está vacío."""
        return self.lock_url or _DEFAULT_LOCAL_REDIS

    @property
    def effective_result_backend(self) -> str | None:
        """Result backend; None (sin backend) por default — crons fire-and-forget."""
        return self.result_backend_url or None

    @property
    def broker_uses_visibility_timeout(self) -> bool:
        """visibility_timeout solo aplica a redis/SQS (no a RabbitMQ/AMQP, etc.)."""
        return self.effective_broker_url.startswith(("redis://", "rediss://", "sqs://"))

    def load_passport_public_key(self) -> str | None:
        if self.passport_public_key:
            return self.passport_public_key
        if self.passport_public_key_path:
            with open(self.passport_public_key_path, encoding="utf-8") as file:
                return file.read()
        return None


settings = Settings()
