# Changelog

Todos los cambios notables de **milpa** se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). En `0.x` la API puede cambiar entre minors.

## [Unreleased]

## [0.5.0] - 2026-06-07

Los backports de lo aprendido en los proyectos hermanos — tequio-core (la extracción worker-side,
PyPI `tequio-core`) y aklara-dispersa (la primera app real) — más la **fachada pública** del
framework. Plan y evidencia: `docs/prerelease/34-backports-tequio-aklara.md`.

### Added

- **Fachada pública perezosa** (`from milpa import job, Controller, view, Mail, Repository, …`):
  la API estable en un import plano (PEP 562), incluida la superficie web. `import milpa` a secas
  queda SIN efectos colaterales (no instancia Celery, ni Settings, ni el engine) y las rutas
  profundas (`from milpa.Core.Http import Controller`) siguen siendo válidas. *(Patrón estrenado
  en tequio 0.1.2.)*
- **`py.typed`** (PEP 561): milpa es mypy-strict pero no publicaba sus tipos; los consumidores de
  `milpa-core` ahora reciben los type hints completos.

- **`jornal serve` detrás de reverse proxy sin flags**: si `ASSET_URL` es una RUTA (`/prefijo`),
  viaja también como `root_path` ASGI — una sola variable y la app entera sabe que vive bajo el
  prefijo (`BASE_PATH` del `window.__ENV`, redirects vía `base_path()`). Un CDN (`https://`) no es
  prefijo: root raíz, como siempre. **Validado con reverse proxy en docker** (aklara-dispersa, donde
  vivió como command del proyecto hasta hoy).
- **Scopes any-of de Passport**: `require_any_scope(...)` + el decorador `@Scope(...)` — el
  `scope:a,b` (CheckForAnyScope, ALGUNO) de Laravel Passport; milpa solo cubría `scopes:a,b`
  (CheckScopes, TODOS) con `require_scopes`. Destilado del Auth de la primera app real.
- **`set_revocation_check(fn)`**: API pública para el hook de revocación de tokens que antes era
  solo un seam privado (`Passport._is_revoked`) — el proyecto conecta su consulta (p. ej. contra
  `oauth_access_tokens` del legacy) sin monkeypatchear; el monkeypatch viejo sigue funcionando.
- **`@Fallback` (catch-all post-mounts)**: registro OPT-IN de un controller que `create_app()` monta
  AL FINAL — después de `/static`, `/vite` y `/status`. Una SPA puede ser dueña de la raíz sin
  tragarse los estáticos (en Starlette gana el primer match; antes el workaround era prefijo propio
  + redirect de `/`).
- **`assets_dev()`**: el template/shell ya puede saber si los assets vienen del dev server o del
  build (la convención del hot-file, expuesta) — para gatear speculation rules y similares sin que
  cada app replique la convención. Disponible como global de Jinja y opcional en `window.__ENV`.
- **El beat agenda los `@cron_task`** *(adoptado de tequio)*: `collect_beat_schedule()` fusiona los
  `@cron_task(schedule=…)` auto-descubiertos (su expresión cron convertida con el nuevo
  `to_crontab()`, conversor estricto de 5 campos que truena claro ante una expresión rara) con los
  `beat_schedule` de `Console/Kernel.py` (la vía declarativa, con precedencia). El
  `demo.daily_digest` que declaraba `daily_at("08:00")` desde 0.x por fin entra al calendario de
  `schedule work`. Los gates de ejecución (anti-overlap, `environments`) siguen en `@cron_task`.
  OJO operativo: beat **o** crontab del SO con `schedule run` — las dos vías a la vez = doble
  despacho.
- Skeleton: `pythonpath = ["."]` en el `pyproject.toml` generado — los tests del proyecto importan
  `app.*` sin tocar `sys.path` (feedback de la primera app real).
- 24 tests nuevos, incluidos los guardrails `test_WorkerTaskDiscovery` (las tasks del framework
  quedan registradas en el worker), `test_FallbackOrder` (los mounts ganan al fallback) y
  `test_FakerLazy` (importar factories no exige la dep de dev).

### Changed

- **`Mail.queue`/`enqueue_mail` truenan AL ENCOLAR** si el `__init__` del Mailable exige argumentos
  y no se pasó `init_kwargs` *(bug real cazado en tequio)*: antes el `TypeError` ocurría en el
  worker al reinstanciar — fallo asíncrono invisible para quien encoló. Ahora el `ValueError` sale
  en el proceso que encola, con instrucción accionable.
- **Faker perezoso** (`_LazyFaker` proxy): importar `Core/Database/Faker` (y por tanto cualquier
  factory) ya no exige tener `faker` instalado — el error accionable sale solo al USARLO. Defensa
  en profundidad: hoy el discovery de milpa no importa factories en runtime, pero cualquier import
  futuro lo haría tronar en una instalación sin dev-deps *(le pasó a tequio en su smoke de CI)*.
- `make:mailable` genera un stub rico: asume la cola **`emails`** (`Mail.queue(..., queue="emails",
  init_kwargs=…)`, se consume con `queue work --queue emails`), apunta la plantilla a la convención
  namespaced del módulo y recuerda el contrato de `init_kwargs`.
- `resolve_apps()` (Vite) ahora se cachea — la estructura de surcos no se re-escanea del filesystem
  en cada uso; el estado VIVO del hot-file (dev vs build) NO se congela. Escape: `clear_apps_cache()`.

### Fixed

- Docstrings que mentían: `CeleryApp`/`ScheduleWorkCommand` decían que el beat juntaba los crons de
  todos los módulos (solo leía `Console/Kernel.py` — ahora con el cambio de arriba la frase es
  verdad y quedó precisa); `Clock.py` afirmaba el patrón `self._database.clock.now()` que nunca
  estuvo cableado (el reloj se inyecta a mano; `FixedClock` = `Carbon::setTestNow`).

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

Arreglo para que `milpa new --demo` corra **de fábrica** (OOTB) + ajustes de docs.

### Fixed

- **`milpa new --demo` funciona OOTB** — el proyecto generado traía Faker (factories/seeders del
  demo) fuera del *dev-group*; ahora va en el grupo `dev` del skeleton, así un `milpa new --demo`
  recién clonado siembra sin instalar nada a mano.

### Docs

- README actualizado a **v0.3.0** (características, estructura `src/milpa`, módulo Demo) y aclaración
  de la **instalación local** (todavía no en PyPI).

## [0.3.0] - 2026-06-02

milpa pasa de *repo que se clona* a **paquete instalable** + un scaffolder `milpa new` que genera
tu proyecto. Fases A–C del *packaging*: extraer el framework a `src/milpa`, que el Core resuelva el
código del USUARIO desde Settings, y embeber un skeleton que `milpa new` materializa.

### Added

#### Packaging + scaffolder

- **Framework extraído a paquete instalable** — el código del Core/Modules vive en `src/milpa` y se
  instala como paquete; ya no se asume el layout de un repo clonado.
- **El Core resuelve el código del USUARIO desde `Settings`** (Fase B) — módulos, modelos, recursos
  y migraciones del proyecto se leen de config (`MODULES_PACKAGE`, `MODELS_PACKAGE`,
  `USER_VIEWS_DIR`, `MIGRATIONS_DIR`, …), no contando carpetas desde el propio paquete (eso, en
  *site-packages*, apuntaba a otro lado).
- **Scaffolder `milpa new` + skeleton embebido** (Fase C) — genera un proyecto nuevo a partir de un
  skeleton que viaja DENTRO del paquete (archivos `.tmpl` que se renderizan sustituyendo el nombre
  del proyecto).

#### Consola

- **`make:*` escribe en el `app/` del USUARIO** (`settings.app_dir`), no en el paquete instalado —
  tus controllers/modelos/módulos generados aterrizan en tu proyecto, donde el Registry los
  auto-monta.
- **El módulo `Hello` generado usa `@Controller` class-based** — el stub de bienvenida estrena el
  routing estilo Spring (`@Controller` + `@Get`) en vez del `APIRouter`.

### Tests

- Guardrail que **ejecuta el launcher `jornal`** (regresión del rename del entrypoint) tras
  corregir que importaba el símbolo equivocado (`milpa` en vez de `app`).

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
[0.3.1]: https://github.com/calcifux/milpa/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/calcifux/milpa/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/calcifux/milpa/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/calcifux/milpa/releases/tag/v0.1.0
