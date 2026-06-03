# milpa 🌽

[![CI](https://github.com/calcifux/milpa-core/actions/workflows/ci.yml/badge.svg)](https://github.com/calcifux/milpa-core/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)
![uv](https://img.shields.io/badge/deps-uv-DE5FE9)
![Ruff](https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white)
![Mypy](https://img.shields.io/badge/types-mypy_strict-2A6DB2)
![License](https://img.shields.io/badge/license-MIT-blue)

**milpa** es un microframework de **Python 3.14** para construir **monolitos modulares**,
inspirado en la ergonomía de **Laravel** y la disciplina de capas de **Spring**. Junta cuatro
piezas maduras detrás de una estructura opinada y un kernel reutilizable:

> **FastAPI** para HTTP · **Celery** para tareas/crons · **SQLAlchemy 2.0** para datos ·
> **Typer** para la consola.

Pensado para dos cosas: **arrancar servicios nuevos** sin re-decidir la arquitectura cada vez,
y **migrar apps legacy de Laravel** a Python conservando conceptos familiares (artisan,
scheduler, mailables, soft-deletes, timestamps, Passport).

---

## 🚀 Quickstart

`milpa` se instala como cualquier paquete y trae el comando `milpa new`, que genera un proyecto
listo para correr (estilo `laravel new` / `django-admin startproject`):

```bash
# 1) instala el paquete (de forma aislada con uv, o como dependencia con pip)
uv tool install milpa-core     # o:  pipx install milpa-core  ·  pip install milpa-core
# El paquete se llama `milpa-core` en PyPI (porque `milpa` choca con otro proyecto), pero el
# comando de consola y el import SIGUEN siendo `milpa`: `milpa new …` / `import milpa`.

# 2) crea un proyecto CON el demo de notas (auth, RBAC/ABAC, correos, patrones estilo milpa)
milpa new miapp --demo
cd miapp

# 3) instálalo y arráncalo
uv sync                        # instala milpa + deps + faker (dev)
uv run python jornal migrate run    # crea las tablas (sqlite por default, zero-config)
uv run python jornal db seed        # admin@demo.test + ana/beto + notas (todos: "password")
uv run python jornal serve          # 👉 http://127.0.0.1:8000
```

Entra como `admin@demo.test` / `password`. La API con OpenAPI está en `/docs`. Sin `--demo`
obtienes un esqueleto limpio (un módulo `Hello` mínimo) para empezar de cero.

> **`jornal`** es el "artisan" de milpa (lo genera el scaffolder en la raíz del proyecto):
> `serve`, `queue work`, `schedule work`, `make controller|model|module`, `migrate`, `db seed`, …
> Ve todo con `uv run python jornal list`.

---

## ✨ Características

Todo es **OPT-IN** y auto-descubrible (no estorba si no lo usas):

- **Patrones estilo milpa** — `Events`/`Observers` (1:N, transporte adaptativo: worker si hay
  broker, si no síncrono), `Mediator` (command bus 1:1, transport-neutral HTTP+CLI) y `Pipeline`
  (modelo cebolla). Patrones ya probados que un arquitecto puede sugerir, no impuestos.
- **Background** — `@job` (on-demand, `.dispatch()`) y `@cron_task` (agendado, anti-overlap),
  separados a propósito (job ≠ cron).
- **API REST (estilo DRF)** — versionado (`@Controller(version="v1")`), rate limiting
  (`@rate_limit`), filtering DSL (`FilterQueryModel`) + paginación por cursor, y negociación de
  contenido (una ruta sirve JSON o HTML según `Accept`).
- **Auth** — RBAC (roles) + ABAC (`Gate`/`@policy`), JWT (API) + sesión cookie/CSRF (browser,
  estilo Sanctum); valida también tokens OAuth2 de Laravel Passport.
- **Errores que NUNCA fallan en silencio** — todo error HTTP sale en **RFC 9457**
  (`application/problem+json`); el CLI rinde errores limpios (sin traceback crudo ni fuga de
  valores); mensajes accionables que apuntan al fix.
- **Datos estilo Spring Data** — `Repository[Model, Id]` tipado, `@transactional`, serializers
  Pydantic v2 (`computed_field`), soft-delete y timestamps automáticos; engine agnóstico del motor.
- **HTTP** — controllers class-based (`@Controller`/`@Get`/`@Post`), Jinja2 + HTMX/Alpine (sin
  Inertia) · **i18n** (YAML) · **mail** (`Mailable` + drivers smtp/log/null + plantillas firmadas).

---

## 🎮 El demo (`milpa new --demo`)

`--demo` materializa un módulo de referencia **corrible** (usuarios + notas) que ejercita TODO el
stack y sirve de plantilla viva: **auth dual** (JWT API + sesión cookie/CSRF), **RBAC + ABAC**,
**routing class-based**, los **patrones estilo milpa** (eventos→correos automáticos, mediator,
pipeline, `@job`, `@cron_task`) y UI **HTMX + Alpine + Pico.css**. Corre sobre **SQLite** sin
levantar infraestructura.

- **Web (HTMX):** `http://127.0.0.1:8000` como `admin@demo.test` / `password`. Crea/borra notas
  (HTMX), entra a **Usuarios** (solo rol `admin` → RBAC); editas/borras solo tus notas (ABAC).
- **API (JWT):** `POST /api/login` → `{access_token}`; luego `Authorization: Bearer <token>` en
  `/api/me`, `/api/notes` (CRUD), `/v1/reports/notes` vs `/v2/...` (versionado). OpenAPI en `/docs`.
- **Correos:** el `.env` trae `MAIL_DRIVER=log` (los correos se imprimen en la terminal de
  `jornal serve`). Para verlos en un **inbox web**, `docker compose up -d` levanta **Mailpit**
  (http://localhost:8025) y pones `MAIL_DRIVER=smtp`.

> Cada feature tiene su página en el [manual](https://calcifux.github.io/milpa/) y se demuestra
> ejecutable en el módulo Demo (contrastando la *forma tradicional* vs *estilo milpa*).

---

## 📖 Documentación

La guía completa estilo Laravel se publica en **<https://calcifux.github.io/milpa/>**:
instalación, configuración, ciclo de vida HTTP, módulos, consola, correo, colas, cron, jobs,
i18n, autenticación, base de datos (modelos, repositorios, filtrado/paginación), los **patrones
estilo milpa** (eventos/observers, mediator, pipeline), la **API REST** (versionado, rate limiting,
negociación de contenido, serializadores) y los **errores RFC 9457**.

---

## 🗂️ Estructura de un proyecto milpa

`milpa new` genera un proyecto donde TÚ trabajas en `app/`, y `milpa` (el framework, instalado
como paquete) aporta el kernel `milpa.Core`:

```
miapp/
  app/
    Modules/
      Demo/          # con --demo: módulo de referencia (users/notes + TODOS los patrones)
    Models/          # modelos SQLAlchemy (auto-discovery)
    Dictionaries/    # constantes de dominio
    Resources/       # assets/lang/views del proyecto
  migrations/        # revisiones Alembic (motor-agnóstico)
  jornal             # consola (artisan) del proyecto
  docker-compose.yml # SOLO infra de dev: redis + mailpit
  .env               # configuración (DATABASE_URL, MAIL_*, secretos, …)
  pyproject.toml     # depende de `milpa`
```

El **kernel** que aporta el paquete (`milpa.Core`) es genérico y reutilizable: `Http` (create_app +
`@Controller` + RateLimit), `Database` (Repository, `@transactional`, Filtering), `Auth` (RBAC+ABAC,
JWT/sesión, Passport), `Events`/`Mediator`/`Pipeline`, `Jobs`/`Cron`, `Mail`, `Errors` (RFC 9457),
`Translate` (i18n), `Console` (kernel Typer). No tocas el kernel: el framework descubre tus
modelos, diccionarios, recursos, comandos y crons por convención.

### Agregar un módulo

```bash
uv run python jornal make module Facturacion
```

Crea `app/Modules/Facturacion/` con `Http/`, `Services/`, `Repositories/`, `Jobs/`, `Crons/`,
`Observers/`, `Handlers/`, `Pipes/`, `Policies/`, `Mail/`, `Resources/`, `Console/Commands/`. La API
y el beat lo **descubren solos**; el `import-linter` garantiza que no se enrede con otros módulos
(cada módulo es un microservicio en potencia: se puede extraer sin desenredar imports cruzados).

---

## ✅ Calidad

milpa trae los guardrails de fábrica; en el proyecto generado corres:

```bash
uv run pytest          # tests rápidos, SIN base de datos
uv run ruff check .    # lint           (ruff format . para formato)
uv run mypy            # tipos (estricto)
uv run lint-imports    # fronteras entre módulos
```

> `faker` es dependencia de **dev** (la usan factories/seeders para `jornal db seed`): viene en el
> grupo dev del proyecto, así que `uv sync` la trae; un `pip install milpa-core` "pelón" no la incluye.

---

## 🐘 Base de datos

El engine es **agnóstico del motor**; se elige con `DATABASE_URL`. Por default `sqlite` (zero-config,
viene en Python). Para otro motor instala su extra:

```bash
uv add "milpa-core[postgres]"   # PostgreSQL (psycopg v3)
uv add "milpa-core[mysql]"      # MySQL / MariaDB (pymysql)
uv add "milpa-core[oracle]"     # Oracle (oracledb)
uv add "milpa-core[mssql]"      # SQL Server (pyodbc)
```

---

## Migrar desde Laravel

El kernel reproduce conceptos familiares para acortar la curva: `artisan`→`jornal`,
`scheduler`→`@cron_task`, mailables, soft-deletes (`deleted_at`), timestamps automáticos
(`created_at`/`updated_at`), y validación de tokens **OAuth2 de Passport** (coloca la llave pública
RS256 del legacy y apunta `PASSPORT_PUBLIC_KEY_PATH` a ella).

---

## Licencia

[MIT](LICENSE) © @Calcifux (Carlos Guillermo Reyes Ramiro)
