# Changelog

Todos los cambios notables de **milpa** se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). En `0.x` la API puede cambiar entre minors.

## [Unreleased]

## [0.3.1] - 2026-06-02

Primer release **publicado a PyPI**. Consolida el paquete instalable (extraído en `0.3.0a0`) con el
set completo de patrones estilo milpa, la API REST estilo DRF, el demo integral y el manual.

### Added

- **Patrones estilo milpa** (OPT-IN, auto-descubribles): `Events`/`Observers` (1:N, transporte
  adaptativo worker/síncrono), `Mediator` (command bus 1:1, transport-neutral HTTP+CLI) y `Pipeline`
  (modelo cebolla). No impuestos: patrones que un arquitecto puede sugerir.
- **Background**: `@job` (on-demand, `.dispatch()`) separado a propósito de `@cron_task` (agendado).
- **API REST (estilo DRF)**: versionado (`@Controller(version="v1")`), rate limiting (`@rate_limit`),
  filtering DSL (`FilterQueryModel`) + paginación por cursor, negociación de contenido (una ruta
  sirve JSON o HTML según `Accept`) y serializers Pydantic v2 (`computed_field`).
- **Módulo `Demo`** integral (reemplaza a `Example`): users/notes ejercitando auth dual, RBAC+ABAC,
  los tres patrones, correos por evento + mailables firmados, y UI HTMX + Alpine + Pico.css.
- **Manual** ampliado (mkdocs): eventos/observers, mediator, pipeline, jobs, versionado, rate
  limiting, filtrado/paginación, negociación de contenido, serializadores y errores RFC 9457.
- **Skeleton del scaffolder**: `.env.example` con sección de correo (`MAIL_DRIVER=log` por default,
  que imprime en la terminal de `jornal serve`; Mailpit para inbox web) y `docker-compose.yml`
  (redis + mailpit) para la infra de dev.

### Fixed

- **`milpa new --demo` funciona out-of-the-box**: `faker` se incluye en el grupo dev del proyecto
  generado y `Core/Database/Faker.py` da un error accionable si falta (las factories/seeders lo
  necesitan; es dependencia de dev, no de producción).

### Changed

- Heredado de `0.3.0a0`: `DATABASE_URL` con default `sqlite`, `pymysql` movido al extra
  `milpa[mysql]` (core agnóstico de dialecto), y el paquete importable `app` → `milpa`.

## [0.3.0a0] - 2026-06-01

Primera versión **INSTALABLE**: milpa se extrae como paquete (`pip install milpa`) con un
scaffolder de proyectos. Alpha — la API puede cambiar entre versiones.

### Added

- **Paquete instalable** (`pip install milpa` / `uv add milpa`): src-layout (`src/milpa`),
  `[build-system]` hatchling, comando de consola `milpa`, versión single-source en `__init__`.
- **`milpa new <app>`** — scaffolder que genera un proyecto listo para correr (estilo
  `laravel new` / `django-admin startproject`) desde un skeleton embebido en el paquete.
- **Config-seam**: el Core resuelve módulos/modelos/recursos/migraciones del proyecto desde
  `Settings`/`.env` (`MODULES_PACKAGE`, `MODELS_PACKAGE`, `USER_VIEWS_DIR`, …) en vez de rutas
  hardcodeadas — un proyecto externo apunta milpa a su propio código. Nuevo `milpa.Core.Discovery`.
- Pipeline de release a PyPI (Trusted Publishing OIDC) + gates de empaquetado en CI
  (`uv build` + smoke de instalación).

### Changed

- **`DATABASE_URL`** ahora tiene default `sqlite:///./milpa.db` (zero-config: milpa arranca sin
  configurar nada, como Django en dev). En QA/prod se pone el motor real en `.env`.
- **`pymysql`** sale del core → extra opcional `milpa[mysql]` (el core queda agnóstico de dialecto).
- El paquete importable se renombró `app` → `milpa`.

## [0.2.0] - 2026-05-30

DX de la consola: más comandos `jornal` (estilo `artisan`) y una lista coherente y legible.

### Added

- **`jornal route list`** — lista las rutas HTTP montadas (método/path/nombre) en tabla rich,
  construyendo la app real (≈ `php artisan route:list`).
- **`jornal db fresh`** — recrea la BD: baja todo, re-migra y siembra. Destructivo; pide
  confirmación salvo `--force` (≈ `php artisan migrate:fresh --seed`).
- **`jornal make controller|model|module`** — scaffolding idempotente de stubs idiomáticos
  (los controllers se auto-montan por el Registry; nunca sobrescribe un archivo existente)
  (≈ `php artisan make:*`).

### Changed

- **`jornal list`** ahora incluye también los comandos raíz (p. ej. `serve`, `list`), no solo los
  agrupados; y estrena título: **🌽 Labores de la milpa**.
- Descripciones (`help`) de **todos** los comandos normalizadas a un estilo coherente
  `<imperativo>. (≈ php artisan X)`.

### Docs

- Guía de BD: cuándo sembrar un **catálogo fijo** en la propia migración con `op.bulk_insert`
  (vs. seeder + factory para datos de ejemplo).

### Tests

- Cobertura (sin BD) de los comandos nuevos (registro de `route`/`db`/`make`, delegación de
  `db fresh`, pureza de los stubs) y del `PassportGuard` (sin bearer → `None`, token válido →
  user, token inválido → 401).

## [0.1.0] - 2026-05-30

Primera versión: el esqueleto del microframework + auth, demo y herramientas de datos.

### Added

#### Kernel / HTTP
- App factory FastAPI (`create_app`) con auto-discovery de routers por módulo.
- Routing **class-based** estilo Spring: `@Controller` + `@Get/@Post/@Put/@Patch/@Delete`
  (convive con el estilo `APIRouter`).
- Errores en **RFC 9457** (`application/problem+json`): `DomainError` y subclases + handler global
  (dominio, validación 422, `HTTPException`, catch-all 500).
- Middlewares: CORS / TrustedHost / GZip + **SecurityHeaders** (nosniff/X-Frame-Options/HSTS/CSP).

#### Auth (modelo Sanctum) + autorización
- **JWT** propio (HS256), guard `jwt`, `Auth.attempt`; **sesión cookie** firmada + **CSRF**
  double-submit, guard `session`; **PassportGuard** (RS256 externo) para migrar Laravel.
- `Hash` (argon2id + verifica bcrypt `$2y$` de Laravel), `UserProvider` (SQLAlchemy, overridable),
  `current_user`/`CurrentUser`, `guarded(name)`.
- **RBAC** (`@Roles`/`require_roles`) + **ABAC** (`Gate.define/authorize`, `@Can`).
- Nombres de cookie configurables con prefijo (`COOKIE_PREFIX`, default `milpa`).

#### Datos (estilo Spring/Laravel)
- `Repository[Model, Id]` tipado: `get/all/add/delete/find_or_fail/first_or_create` + `paginate()`
  (offset/limit sin COUNT, `Page`). Sesión ambiente (`@transactional`/`session_scope`), soft-delete,
  timestamps. Engine **agnóstico del motor**.
- **Migraciones** con Alembic (`jornal migrate make/run/status/rollback`).
- **Seeders** (`jornal db seed`) y **Factories** `Factory[Model]` con **Faker** (locale configurable
  vía `FAKER_LOCALE`).

#### Tareas / consola / correo / i18n
- Celery (broker-agnóstico) + crons `@cron_task` con **retry/backoff** (`retry_policy`).
- Consola `jornal` (Typer) con auto-discovery y salida en tabla **rich**.
- Mail (`Mailable`/`Mailer`, drivers smtp/log/null, Jinja2, i18n) y Logging (loguru, JSON).

#### Demo + tooling
- Módulo **Demo** corrible (SQLite): dashboard con auth dual, RBAC+ABAC, **búsqueda en vivo** +
  **scroll infinito** (HTMX), branding StackCraft (Pico.css + Alpine). 100 usuarios vía factories.
- **CI** (GitHub Actions): ruff + mypy strict + import-linter + pytest. Sitio de docs (MkDocs
  Material) publicable a GitHub Pages.

### Notas
- Todo es **síncrono** (SQLAlchemy + Celery). Tests **sin base de datos** (fakes + monkeypatch).

[Unreleased]: https://github.com/calcifux/milpa/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/calcifux/milpa/compare/v0.2.0...v0.3.1
[0.2.0]: https://github.com/calcifux/milpa/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/calcifux/milpa/releases/tag/v0.1.0
