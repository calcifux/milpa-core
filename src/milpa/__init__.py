"""Fachada pública de milpa: la API estable en UN import plano.

    from milpa import job, cron_task, celery_app, Mailable, Repository, Controller, view, Auth, ...

Re-exporta la superficie que las docs, el Demo y el skeleton enseñan; las rutas
profundas (`from milpa.Core.Jobs import job`, `from milpa.Core.Http.Routing import Get`)
SIGUEN siendo válidas y estables. La fachada solo re-exporta.

PEREZOSA a propósito (PEP 562, `__getattr__` de módulo): `import milpa` a secas NO
tiene efectos colaterales. Una fachada eager arrastraría dos costos caros:

  - `Core.CeleryApp.CeleryApp`, que instancia Celery + lee Settings + configura logging
    EN IMPORT TIME (acceder a `celery_app`/`broker_guard`/`retry_policy` es lo que lo paga;
    OJO: `CeleryApp/__init__` eager-importa `celery_app`, así que CUALQUIER símbolo de ese
    paquete instancia Celery al primer acceso, no en `import milpa`).
  - el kernel WEB: importar cualquier submódulo de `Core.Http` (Routing, RateLimit, Shell)
    ejecuta primero el `__init__` del paquete `Http`, que eager-importa `create_app` y
    arrastra engine de BD, Logging, RateLimit/Limiter, Registry y Middleware. Igual con
    `view`/`negotiate`/`prefers_html`/`Pwa`, que instancian el singleton `TemplateEngine()`
    (Jinja2 + Vite + Translate). Todo eso debe ocurrir cuando pides la capa web, no cuando
    una herramienta (mkdocs, pickle, el smoke del CI) hace `import milpa`.

Mismo espíritu que el Faker perezoso de `Core/Database/Faker.py`. El bloque TYPE_CHECKING
da los tipos reales a mypy/IDEs (el paquete publica `py.typed`, PEP 561).

Nota de paridad: esta fachada porta el patrón de la fachada de tequio (el subconjunto sin
capa web) y le suma la superficie WEB de milpa (Http/Auth/View/i18n). `auto_session` es
una adición deliberada de milpa (cierra el par con `transactional`/`session_scope`), no
parte del subconjunto portado; quien compare ambas fachadas no debe leerlo como
inconsistencia.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from milpa.Core.Auth.Auth import Auth, CurrentUser, authenticated, guarded
    from milpa.Core.Auth.Authorization import (
        Can,
        Gate,
        Roles,
        Scope,
        policy,
        require_roles,
    )
    from milpa.Core.Auth.Contracts import Authenticatable, AuthenticatableMixin
    from milpa.Core.Auth.Hash import Hash
    from milpa.Core.Auth.Passport import (
        TokenPrincipal,
        get_current_token,
        require_any_scope,
        require_scopes,
        set_revocation_check,
    )
    from milpa.Core.CeleryApp import QueueUnavailableError, broker_guard, celery_app, retry_policy
    from milpa.Core.Clock import Clock, FixedClock, SystemClock
    from milpa.Core.Config import Settings, settings
    from milpa.Core.Console import console_command
    from milpa.Core.Cron import (
        cron,
        cron_task,
        daily,
        daily_at,
        every_fifteen_minutes,
        every_five_minutes,
        every_minute,
        every_minutes,
        every_ten_minutes,
        every_thirty_minutes,
        hourly,
        hourly_at,
        monthly,
        weekly,
    )
    from milpa.Core.Database import (
        Base,
        CursorPage,
        Factory,
        Page,
        Repository,
        SoftDeleteMixin,
        TimestampMixin,
        auto_session,
        current_session,
        session_scope,
        transactional,
    )
    from milpa.Core.Database.Faker import faker
    from milpa.Core.Database.Seeder import Seeder
    from milpa.Core.Errors import ConflictError, DomainError, ResourceNotFoundError
    from milpa.Core.Events import Observer, dispatch
    from milpa.Core.Http.RateLimit import rate_limit
    from milpa.Core.Http.Routing import (
        Controller,
        Delete,
        Fallback,
        Get,
        Patch,
        Post,
        Put,
        api_version,
    )
    from milpa.Core.Http.Shell import shell_context
    from milpa.Core.Jobs import Job, job
    from milpa.Core.Mail import Mail, Mailable, MailContent
    from milpa.Core.Mediator import handles, send
    from milpa.Core.Pipeline import Pipe, Pipeline
    from milpa.Core.Translate.I18n import (
        current_locale,
        resolve_accept_language,
        set_request_locale,
        t,
    )
    from milpa.Core.View import Pwa  # módulo re-exportado por View/__init__, no un símbolo-función
    from milpa.Core.View.View import negotiate, prefers_html, view

# Dónde vive CADA símbolo (su módulo canónico). Apuntamos a los módulos DEFINIDORES
# (Dispatch/Retry/Routing/Auth/…), NO a los paquetes, por paridad exacta con el patrón de
# tequio. OJO: el `__init__` del paquete padre (CeleryApp, Http) igual eager-importa y
# arrastra su costo, pero solo al PRIMER ACCESO a un símbolo de ese paquete, jamás en
# `import milpa`. `Pwa` es un MÓDULO re-exportado por `View/__init__`: `getattr(View, "Pwa")`
# lo resuelve igual que cualquier otro símbolo.
_EXPORTS: Final[dict[str, str]] = {
    # Celery: la app, la guarda de broker y la política de reintentos
    "celery_app": "milpa.Core.CeleryApp",
    "broker_guard": "milpa.Core.CeleryApp.Dispatch",
    "QueueUnavailableError": "milpa.Core.CeleryApp.Dispatch",
    "retry_policy": "milpa.Core.CeleryApp.Retry",
    # Jobs on-demand (`@job` + `.dispatch()`)
    "Job": "milpa.Core.Jobs",
    "job": "milpa.Core.Jobs",
    # Crons (`@cron_task`) + azúcar de schedule (daily/hourly/…)
    "cron": "milpa.Core.Cron",
    "cron_task": "milpa.Core.Cron",
    "daily": "milpa.Core.Cron",
    "daily_at": "milpa.Core.Cron",
    "every_fifteen_minutes": "milpa.Core.Cron",
    "every_five_minutes": "milpa.Core.Cron",
    "every_minute": "milpa.Core.Cron",
    "every_minutes": "milpa.Core.Cron",
    "every_ten_minutes": "milpa.Core.Cron",
    "every_thirty_minutes": "milpa.Core.Cron",
    "hourly": "milpa.Core.Cron",
    "hourly_at": "milpa.Core.Cron",
    "monthly": "milpa.Core.Cron",
    "weekly": "milpa.Core.Cron",
    # Correo (Mailables + envío síncrono/encolado)
    "Mail": "milpa.Core.Mail",
    "Mailable": "milpa.Core.Mail",
    "MailContent": "milpa.Core.Mail",
    # Eventos + observers
    "Observer": "milpa.Core.Events",
    "dispatch": "milpa.Core.Events",
    # Mediator (commands/queries con handler único)
    "handles": "milpa.Core.Mediator",
    "send": "milpa.Core.Mediator",
    # Pipeline (cadena de pipes)
    "Pipe": "milpa.Core.Pipeline",
    "Pipeline": "milpa.Core.Pipeline",
    # Base de datos: declarativa, repositorios, sesiones y transacciones
    "Base": "milpa.Core.Database",
    "CursorPage": "milpa.Core.Database",
    "Factory": "milpa.Core.Database",
    "Page": "milpa.Core.Database",
    "Repository": "milpa.Core.Database",
    "SoftDeleteMixin": "milpa.Core.Database",
    "TimestampMixin": "milpa.Core.Database",
    "current_session": "milpa.Core.Database",
    "session_scope": "milpa.Core.Database",
    "transactional": "milpa.Core.Database",
    "auto_session": "milpa.Core.Database",  # adición milpa: par de `transactional` para lecturas
    "Seeder": "milpa.Core.Database.Seeder",
    "faker": "milpa.Core.Database.Faker",
    # Consola (commands estilo artisan)
    "console_command": "milpa.Core.Console",
    # Configuración (pydantic-settings)
    "Settings": "milpa.Core.Config",
    "settings": "milpa.Core.Config",
    # Reloj inyectable (= java.time.Clock / Carbon::setTestNow)
    "Clock": "milpa.Core.Clock",
    "FixedClock": "milpa.Core.Clock",
    "SystemClock": "milpa.Core.Clock",
    # Errores de dominio (RFC 9457-ready)
    "ConflictError": "milpa.Core.Errors",
    "DomainError": "milpa.Core.Errors",
    "ResourceNotFoundError": "milpa.Core.Errors",
    # HTTP: controllers, verbos-decoradores, catch-all SPA y versionado de API
    "Controller": "milpa.Core.Http.Routing",
    "Get": "milpa.Core.Http.Routing",
    "Post": "milpa.Core.Http.Routing",
    "Put": "milpa.Core.Http.Routing",
    "Patch": "milpa.Core.Http.Routing",
    "Delete": "milpa.Core.Http.Routing",
    "Fallback": "milpa.Core.Http.Routing",
    "api_version": "milpa.Core.Http.Routing",
    # Rate limiting (decorador; el `limiter` crudo es interno)
    "rate_limit": "milpa.Core.Http.RateLimit",
    # Shell del frontend (SPA/PWA/surcos): contexto del cascarón HTML
    "shell_context": "milpa.Core.Http.Shell",
    # Vistas: render de templates y negociación HTML/JSON
    "view": "milpa.Core.View.View",
    "negotiate": "milpa.Core.View.View",
    "prefers_html": "milpa.Core.View.View",
    "Pwa": "milpa.Core.View",  # módulo (Pwa.webmanifest / Pwa.service_worker), no función
    # Autenticación: facade, dependency del usuario actual y guards de ruta
    "Auth": "milpa.Core.Auth.Auth",
    "CurrentUser": "milpa.Core.Auth.Auth",
    "authenticated": "milpa.Core.Auth.Auth",
    "guarded": "milpa.Core.Auth.Auth",
    # Autorización: gate, dependencies de habilidad/rol/scope y decorador de policy
    "Gate": "milpa.Core.Auth.Authorization",
    "Can": "milpa.Core.Auth.Authorization",
    "Roles": "milpa.Core.Auth.Authorization",
    "Scope": "milpa.Core.Auth.Authorization",
    "policy": "milpa.Core.Auth.Authorization",
    "require_roles": "milpa.Core.Auth.Authorization",
    # Passport (OAuth/tokens): scopes, principal del token y hook de revocación
    "require_scopes": "milpa.Core.Auth.Passport",
    "require_any_scope": "milpa.Core.Auth.Passport",
    "get_current_token": "milpa.Core.Auth.Passport",
    "set_revocation_check": "milpa.Core.Auth.Passport",
    "TokenPrincipal": "milpa.Core.Auth.Passport",
    # Hashing de passwords (registro/login)
    "Hash": "milpa.Core.Auth.Hash",
    # Contratos del modelo autenticable (User)
    "Authenticatable": "milpa.Core.Auth.Contracts",
    "AuthenticatableMixin": "milpa.Core.Auth.Contracts",
    # i18n de la UI (transversal): traducción, locale ambiente y Accept-Language
    "t": "milpa.Core.Translate.I18n",
    "current_locale": "milpa.Core.Translate.I18n",
    "set_request_locale": "milpa.Core.Translate.I18n",
    "resolve_accept_language": "milpa.Core.Translate.I18n",
}

# Lista ESTÁTICA a propósito (no `sorted(_EXPORTS)`): mypy y ruff solo entienden
# re-exports con un `__all__` literal. El test de la fachada la mantiene en sync.
__all__ = [
    "Auth",
    "Authenticatable",
    "AuthenticatableMixin",
    "Base",
    "Can",
    "Clock",
    "ConflictError",
    "Controller",
    "CurrentUser",
    "CursorPage",
    "Delete",
    "DomainError",
    "Factory",
    "Fallback",
    "FixedClock",
    "Gate",
    "Get",
    "Hash",
    "Job",
    "Mail",
    "MailContent",
    "Mailable",
    "Observer",
    "Page",
    "Patch",
    "Pipe",
    "Pipeline",
    "Post",
    "Put",
    "Pwa",
    "QueueUnavailableError",
    "Repository",
    "ResourceNotFoundError",
    "Roles",
    "Scope",
    "Seeder",
    "Settings",
    "SoftDeleteMixin",
    "SystemClock",
    "TimestampMixin",
    "TokenPrincipal",
    "api_version",
    "authenticated",
    "auto_session",
    "broker_guard",
    "celery_app",
    "console_command",
    "cron",
    "cron_task",
    "current_locale",
    "current_session",
    "daily",
    "daily_at",
    "dispatch",
    "every_fifteen_minutes",
    "every_five_minutes",
    "every_minute",
    "every_minutes",
    "every_ten_minutes",
    "every_thirty_minutes",
    "faker",
    "get_current_token",
    "guarded",
    "handles",
    "hourly",
    "hourly_at",
    "job",
    "monthly",
    "negotiate",
    "policy",
    "prefers_html",
    "rate_limit",
    "require_any_scope",
    "require_roles",
    "require_scopes",
    "resolve_accept_language",
    "retry_policy",
    "send",
    "session_scope",
    "set_request_locale",
    "set_revocation_check",
    "settings",
    "shell_context",
    "t",
    "transactional",
    "view",
    "weekly",
]


def __getattr__(name: str) -> Any:
    """Resuelve los símbolos de `_EXPORTS` al primer acceso (PEP 562) y los cachea."""
    try:
        module_path = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_path), name)
    globals()[name] = value  # cachea: los accesos siguientes ya no pasan por aquí
    return value


def __dir__() -> list[str]:
    """`dir(milpa)` lista la fachada completa aunque aún no se haya resuelto nada."""
    return sorted(set(globals()) | set(_EXPORTS))


# La versión vive AQUÍ como única fuente de verdad: hatch la lee para el pyproject
# ([tool.hatch.version]). Esta línea es la divergencia deliberada con el repo de
# desarrollo (milpa-framework, que no publica paquete y versiona en su pyproject).
__version__ = "1.0.0"
