# Changelog

Todos los cambios notables de **milpa** se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). En `0.x` la API puede cambiar entre minors.

## [Unreleased]

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

[Unreleased]: https://github.com/calcifux/milpa/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/calcifux/milpa/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/calcifux/milpa/releases/tag/v0.1.0
