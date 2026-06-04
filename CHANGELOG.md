# Changelog

Todos los cambios notables de **milpa** se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). En `0.x` la API puede cambiar entre minors.

## [Unreleased]

## [0.4.0] - 2026-06-04

Frontend a la milpa: asset-pipeline **Vite** estilo `laravel-vite`, **microfrontends por vertical**
(los *surcos*) que el backend sirve **same-origin** (cero CORS), **PWA** sin boilerplate y
**runtime-config** del shell (`window.__ENV`). Todo OPT-IN: sin surcos detectados nada se monta.

Forma tradicional vs estilo milpa: la forma tradicional corre cada SPA en su propio servidor y
abre CORS con la config congelada en *build-time*; estilo milpa el backend es dueño del shell HTML
(Jinja) y Vite del pipeline de assets — mismo origen, e inyecta lo que cambia por deploy en runtime.

### Added

#### Asset-pipeline Vite (estilo milpa)

- **Helpers Jinja `vite()` / `vite_asset()` / `vite_react_refresh()`** (`Core/View/Vite.py`) — la
  directiva `@vite` de milpa. En **DEV** inyecta el cliente HMR desde el dev server vía el *hot-file*
  por app; en **PROD** lee `dist/.vite/manifest.json` y emite los `<link>`/`<script>` hasheados.
  Sin apps detectadas no se monta nada y `vite()` truena con instrucción clara (nunca falla en
  silencio).
- **Microfrontends por vertical (los *surcos*)** — cada app Vite vive en `surcos/<app>` con la
  tecnología que quiera (React/Vue/Svelte/vanilla; Vite las cubre todas). **Auto-detección por
  convención**: una carpeta es app si tiene `hot` (dev corriendo) o `dist/.vite/manifest.json`
  (build hecho). En multi-app, `vite('src/main.jsx', app='tienda')` desambigua — y los equipos
  pueden mezclar dev (HMR) y build simultáneamente sin estorbarse.
- **PWA sin boilerplate** (`Core/View/Pwa.py`) — `Pwa.webmanifest(request, ...)` y
  `Pwa.service_worker(request, ...)` como *one-liners* de controller. El manifest se arma **EN
  RUNTIME** (`start_url`/`scope` con el prefijo real del deploy, así salen bien tras un reverse
  proxy bajo sub-ruta **sin rebuild**); los iconos se **auto-descubren** del build por convención
  (`icons/icon-<size>.png` y `icons/icon-<size>-maskable.png`); el SW se sirve con
  `Cache-Control: no-cache` (un SW cacheado = updates que nunca llegan).
- **Runtime-config del shell** (`Core/Http/Shell.py`) — `shell_context(request)` inyecta
  `window.__ENV` (`APP_NAME`/`APP_ENV`/`BASE_PATH` + extras del surco): lo que `NEXT_PUBLIC_*`/
  `VITE_*` **no pueden** dar sin rebuild. Exporta `base_path`, `runtime_env_json` y `shell_context`
  desde `Core/Http`. `BASE_PATH` (el `root_path` ASGI) es la mitad **runtime** del soporte
  reverse-proxy bajo sub-ruta; `ASSET_URL` es la mitad **build-time**.
- **Global Jinja `env_script()`** (`Core/View/TemplateEngine.py`) — emite el
  `<script>window.__ENV = {...}</script>` completo y seguro (el JSON viene con `<` escapado desde
  el Core, así un valor raro no puede cerrar el tag) sin copiar el `| safe` en cada template.

#### Frontend (paquete npm + scaffolder)

- **Plugin npm `vite-plugin-milpa` `^0.1.2`** (publicado) — deriva el `base` de la carpeta del
  surco, escribe el manifest y el *hot-file* que leen los helpers Jinja, y trae un **file-router**
  de runtime (`vite-plugin-milpa/router`) que es el espejo del auto-montado de `Modules/<X>/Http`
  del backend. `0.1.1` agregó chunks con nombre legible; `0.1.2` corrige el modo dev con
  PWA (el middleware de serwist tronaba en cada request del dev server).
- **`milpa new --demo` materializa también el frontend** (`_skeleton_demo`): los surcos +
  `package.json` raíz pnpm + `pnpm-workspace.yaml` (con el override a `link:` comentado) + `.nvmrc`.
  Regla por sufijo: `.tmpl` = texto renderizado, el resto = bytes intactos (los PNG de la PWA
  viajan sin corromperse).
- **Surcos de ejemplo** — `demo-spa` (React 19 + react-router 7 con file-router por
  `import.meta.glob` + PWA Serwist offline-first: precache del shell, `NetworkOnly` para `/api`,
  fallback offline al shell) y `tablero` (vanilla, sin PWA). La marca pública del demo es
  **StackCraft**.
- **Demo del backend** — `SpaController` sirve el shell React+PWA en `/spa` con catch-all
  SPA-fallback acotado al prefijo (no se come `/api`), y el manifest y el `sw.js` como *one-liners*;
  `TableroController` es el surco vanilla. Vistas `spa.html.j2` / `tablero.html.j2`. La convención
  es del framework, no de la tecnología del frontend.

### Changed

- **`asset()` ahora antepone `ASSET_URL`** (`Core/View/TemplateEngine.py`) — para deploy bajo
  sub-ruta de reverse proxy (`ASSET_URL=/nombre-reverse`) o CDN (`https://cdn.x.com`). Igual lo
  honran `vite()` / `vite_asset()`. **DEBE coincidir** con el `ASSET_URL` con el que se buildea el
  frontend (`vite-plugin-milpa` lee la **misma** env var en build).
- **Mount del `public/` del proyecto en `VITE_ASSETS_URL`** (`Core/Http/Http.py`) — cada surco
  buildea a `public/<app>` y milpa lo sirve completo en **un solo** mount (como el `public/` de
  Laravel), todo same-origin. Modo una-sola-app con `VITE_DIST_DIR` explícito.
- **Nuevos settings de Vite** (`Core/Config/Settings.py`) — `ASSET_URL` (prefijo público de
  `asset()`/`vite()`), `VITE_APPS_DIR` (default `surcos`), `VITE_PUBLIC_DIR` (`public`),
  `VITE_DIST_DIR` (`""`), `VITE_HOT_FILE` (`""`), `VITE_ASSETS_URL` (`/vite`).
- **Workspace npm → pnpm** (`pnpm-workspace.yaml`) — `node_modules` **por paquete** (sin *phantom
  deps*: la dep no declarada truena en dev, no al extraer el surco a su repo), `allowBuilds`
  explícito (esbuild), y el plugin sale por default del **registro**; el override
  `link:../vite-plugin-milpa` queda **comentado** como camino contributor.
- **Piso del skeleton: `milpa-core>=0.4.0`** — el proyecto generado depende de `milpa-core` en PyPI
  (el import y el comando siguen siendo `milpa`); el scaffolder ya escribe el correo en el `.env`
  generado y MySQL queda como extra de `milpa-core`.

### Docs

- `.env.example` (repo y skeleton) documenta la sección **Vite / ASSET_URL** completa: la
  auto-detección en `VITE_APPS_DIR`, dónde caen los builds (`public/<surco>`), y la regla de oro de
  que `ASSET_URL` debe ser el **mismo** en backend y build del frontend.

### Notas

- Frontend **OPT-IN**: requiere Node `>=22.13` (`.nvmrc` = 22; pnpm 11 usa `node:sqlite`) y **pnpm 11**
  (`packageManager`/volta). Comandos: `pnpm install` en la raíz · `pnpm --filter <surco> dev` ·
  `pnpm -r build`. Sin tocar nada de esto, milpa sigue sirviendo lo de siempre.

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
  `milpa-core[mysql]` (core agnóstico de dialecto), y el paquete importable `app` → `milpa`.

## [0.3.0a0] - 2026-06-01

Primera versión **INSTALABLE**: milpa se extrae como paquete (`pip install milpa-core`) con un
scaffolder de proyectos. Alpha — la API puede cambiar entre versiones.

### Added

- **Paquete instalable** (`pip install milpa-core` / `uv add milpa-core`): src-layout (`src/milpa`),
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
- **`pymysql`** sale del core → extra opcional `milpa-core[mysql]` (el core queda agnóstico de dialecto).
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

[Unreleased]: https://github.com/calcifux/milpa/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/calcifux/milpa/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/calcifux/milpa/compare/v0.2.0...v0.3.1
[0.2.0]: https://github.com/calcifux/milpa/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/calcifux/milpa/releases/tag/v0.1.0
