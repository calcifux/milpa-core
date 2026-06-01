# milpa

[![CI](https://github.com/calcifux/milpa/actions/workflows/ci.yml/badge.svg)](https://github.com/calcifux/milpa/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)
![uv](https://img.shields.io/badge/deps-uv-DE5FE9)
![Ruff](https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white)
![Mypy](https://img.shields.io/badge/types-mypy_strict-2A6DB2)
![License](https://img.shields.io/badge/license-MIT-blue)

**milpa** es un microframework de **Python 3.14** para construir **monolitos
modulares**, inspirado en la ergonomía de **Laravel** y la disciplina de capas de
**Spring**. Junta cuatro piezas maduras detrás de una estructura opinada y un kernel
compartido reutilizable:

- **FastAPI** para HTTP, **Celery** para tareas/crons, **SQLAlchemy 2.0** para datos,
  **Typer** para la consola.

Pensado para dos cosas: **arrancar servicios nuevos** sin re-decidir la arquitectura
cada vez, y **migrar apps legacy de Laravel** a Python conservando conceptos familiares
(artisan, scheduler, mailables, soft-deletes, timestamps, Passport).

- **API**: FastAPI (`app/Core/Http/Http.py:create_app`); descubre los módulos activos.
- **Crons / tareas**: Celery worker + beat (`app/Core/CeleryApp/CeleryApp.py:celery_app`).
- **CLI** (estilo `artisan`): `jornal` en la raíz (launcher fino del kernel de consola).
- **Infra**: Docker **solo** levanta Redis + Mailpit (+ RabbitMQ opcional); la app
  corre en el host.

> **El kernel (`app/Core`) es el framework.** Es genérico y reutilizable entre
> proyectos. Lo específico de cada app vive fuera de `Core`: en `app/Modules/*`,
> `app/Models`, `app/Dictionaries`, `app/Resources` y el launcher `jornal`.

## 📖 Documentación

La guía completa estilo Laravel está en **[`documentation/`](documentation/README.md)**:
instalación, configuración, ciclo de vida HTTP, módulos, consola, correo, colas, cron,
i18n, autenticación y base de datos (modelos, repositorios y transacciones).

---

## 1. Requisitos

- **Python 3.14+**
- **Docker** + Docker Compose (para Redis y Mailpit en local)
- Una **base de datos** alcanzable (el engine es agnóstico del motor: MySQL/MariaDB,
  PostgreSQL, Oracle, SQL Server, SQLite). Se elige con `DATABASE_URL`.
- (Recomendado) **[uv](https://docs.astral.sh/uv/)** como gestor de entorno y deps.

---

## 2. Instalación

### Opción A — con `uv` (recomendada)

```bash
uv sync
```

Eso crea el entorno y resuelve dependencias (incluidas las de dev) desde
`pyproject.toml` / `uv.lock`. Antepón `uv run` a cualquier comando (no necesitas
activar el venv): `uv run pytest`, `uv run python jornal list`, etc.

> Solo producción (sin herramientas de dev): `uv sync --no-dev`.
> Driver de BD según tu motor (extras opcionales): `uv sync --extra postgres`
> (también `oracle`, `mssql`; MySQL/MariaDB ya va en el core).

### Opción B — Python + venv (pip)

```bash
python3.14 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e .                   # dependencias de ejecución
pip install --group dev            # herramientas de dev (pip >= 25.1)
# pip más viejo:  pip install pytest ruff mypy import-linter
```

Con el venv **activado**, corre los comandos **sin** el prefijo `uv run`.

---

## 3. Configuración (`.env`)

```bash
cp .env.example .env
```

Variables clave (el `.env.example` trae todas, comentadas):

| Variable | Para qué |
|----------|----------|
| `DATABASE_URL` | Conexión SQLAlchemy. Define el motor: `mysql+pymysql://…`, `postgresql+psycopg://…`, `sqlite:///app.db`, … |
| `BROKER_URL` | Transporte de Celery para lo **encolado**. Vacío => Redis local. (`redis://…`, `amqp://…`). |
| `TIMEZONE` | Zona de la app (nombre IANA, ej. `America/Mexico_City`). Gobierna timestamps y cálculos de fecha. |
| `APP_NAME` / `APP_ENV` | Nombre del proyecto y entorno (`local`/`prod`); el env gatea crons y CCO de correo. |
| `APP_PORT` | Puerto del servidor FastAPI. |
| `AUTO_CREATE_TABLES` | Si la app puede crear tablas. Contra una BD legacy: **`false`**. |
| `APP_FALLBACK_LOCALE` | Locale de fallback de i18n (correos, API) cuando no se pasa uno explícito. |
| `MAIL_DRIVER` | `smtp` (real) · `log` (lo escribe en el log, dev sin SMTP) · `null` (no-op). |
| `MAIL_*` | Host/puerto/credenciales/remitente del correo (en local apunta a Mailpit). |
| `CORS_*` / `TRUSTED_HOSTS` / `GZIP_ENABLED` | Middlewares HTTP (defaults seguros si se omiten). |
| `SECURITY_HEADERS_ENABLED` / `HSTS_*` / `CONTENT_SECURITY_POLICY` | Security headers defensivos (nosniff/X-Frame-Options/Referrer-Policy ON; HSTS/CSP opt-in). |
| `AUTH_GUARD` / `JWT_SECRET` / `SESSION_SECRET` | Auth propia: guard por default + secretos del JWT (API) y de la sesión (browser). |
| `PASSPORT_PUBLIC_KEY_PATH` | (Opcional) Llave pública para validar tokens OAuth2 de Laravel Passport (ver §4). |
| `LOG_LEVEL` / `LOG_JSON` | Logging (Loguru). `LOG_JSON=true` agrega `logs/app.jsonl`. |

> **Host vs Docker:** si corres la app en el host (lo normal en dev), usa
> `localhost`/`127.0.0.1` en las URLs. El `.env.example` asume Docker y lo aclara.

---

## 4. Secrets (opcional)

La carpeta `secrets/` se versiona vacía (`.gitkeep`); **su contenido lo ignora git**.
Úsala para llaves locales. Caso típico al **migrar desde Laravel**: validar tokens
**OAuth2 de Passport** colocando ahí la llave **pública** RS256 del legacy
(`storage/oauth-public.key`) y apuntando `PASSPORT_PUBLIC_KEY_PATH` a ella.

Nunca subas llaves ni el `.env` al repo.

---

## 5. Levantar la infraestructura (Docker)

Docker **solo** corre infraestructura. La app NO va en Docker.

```bash
docker compose up -d        # Redis + Mailpit (RabbitMQ opcional, ver compose)
```

- **Redis**: `localhost:6379` (broker/lock por default de Celery).
- **Mailpit**: SMTP en `localhost:1025`; **UI web en http://localhost:8025**
  (ahí ves los correos que manda la app en local).

```bash
docker compose down         # apagar la infra
```

---

## 6. Correr la aplicación

Todo se opera desde **`jornal`** (el "artisan" de milpa). Con `uv` antepón
`uv run python`; con el venv activo basta `./jornal`.

```bash
uv run python jornal serve            # API FastAPI (= artisan serve; --host --port --no-reload)
uv run python jornal queue work       # worker de Celery (tareas en background)
uv run python jornal schedule work    # beat: scheduler de crons (corre UNA sola instancia)
uv run python jornal schedule run     # despacha los crons del minuto (lo dispara el crontab del SO)
uv run python jornal list             # ve todos los comandos disponibles
```

`serve` arranca uvicorn con la app factory del kernel (`app.Core.Http.Http:create_app`);
por default escucha en `127.0.0.1:$APP_PORT` con `--reload`.

> **Beat: una sola instancia** (≈ `onOneServer()` de Laravel). Varios beats = crons
> duplicados. Los crons se declaran con `@cron_task(...)` (`app/Core/Cron`): gate por
> `APP_ENV` (`environments=[...]`), lock en Redis (`without_overlapping=True`) y logs
> por cron con rotación (`output="<nombre>"`).

---

## 🎮 Demo corrible

Un demo completo (usuarios + notas) que ejercita TODO el stack: **auth dual** (JWT API + sesión
cookie/CSRF), **RBAC + ABAC**, **routing class-based** (`@Controller`/`@Get`) y UI **HTMX + Alpine +
Pico.css**. Sobre **SQLite**, sin levantar infraestructura:

```bash
# 1) Config mínima en .env (sqlite + secretos)
echo 'DATABASE_URL=sqlite:///milpa.db'                  >> .env
echo 'JWT_SECRET=pon-un-secreto-largo-y-aleatorio'      >> .env
echo 'SESSION_SECRET=pon-otro-secreto-largo-aleatorio'  >> .env

# 2) migrar + sembrar + servir
uv run python jornal migrate run     # crea las tablas (Alembic, motor-agnóstico)
uv run python jornal db seed         # admin@demo.test + ana/beto + notas (todos: "password")
uv run python jornal serve           # http://127.0.0.1:8000
```

- **Web (HTMX):** abre `http://127.0.0.1:8000` y entra como `admin@demo.test` / `password`. Crea y
  borra notas (HTMX), y entra a **Usuarios** (solo rol `admin` → RBAC). Solo editas/borras tus
  propias notas (ABAC).
- **API (JWT):** `POST /api/login` → `{access_token}`; luego `Authorization: Bearer <token>` en
  `/api/me`, `/api/notes` (CRUD), `/api/admin/users`. OpenAPI en **`/docs`**.

El demo vive en `app/Modules/Demo/`; los modelos `User`/`Note` en `app/Models/`. Más en
[Autenticación](documentation/15-autenticacion.md).

---

## 7. Calidad (tests + guardrails)

Todo corre en local, **sin base de datos** (tests unitarios; sin TestContainers).

```bash
uv run pytest                       # tests (rápidos, sin BD)

uv run ruff check .                 # lint            | --fix  arregla
uv run ruff format .                # formato         | --check  solo verifica (CI)
uv run mypy                         # tipos (estricto)
uv run lint-imports                 # fronteras entre módulos
```

Todo de una (lo que validaría el CI):

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
```

> Un test solo: `uv run pytest Tests/Core/Mail/test_Mailer.py::test_x` · por palabra:
> `uv run pytest -k "mail"` · `-x` corta al primer fallo, `-v` verbose.

---

## 8. Estructura

```
app/
  Core/            # EL FRAMEWORK (genérico, reutilizable):
    Config/        #   settings (pydantic-settings, lee .env)
    Console/       #   kernel de consola (Typer) + comandos base
    CeleryApp/     #   app de Celery + dispatch (broker-agnostic)
    Cron/          #   @cron_task + scheduler estilo Laravel
    Database/      #   Base, Session (engine agnóstico), Repository, @transactional, mixins
    Http/          #   create_app() FastAPI + middlewares + locale boundary
    Mail/          #   Mailable + Mailer (smtp/log/null) + TemplateEngine
    Translate/     #   i18n (i18nice, YAML)
    View/          #   motor de templates (Jinja2)
  Models/          # modelos SQLAlchemy compartidos (auto-discovery; vacío en el base)
  Dictionaries/    # constantes de dominio (auto-discovery por submódulo)
  Modules/
    Example/       # módulo de ejemplo: Http, Jobs, Mail, Resources
  Resources/       # assets/lang/views compartidos del proyecto
Tests/             # tests unitarios (espeja app/ 1:1, sin BD)
docs/              # ADRs y notas de diseño
secrets/           # llaves locales (contenido ignorado por git)
jornal             # entrypoint de consola (artisan) en la raíz
docker-compose.yml # SOLO infra: redis + mailpit (+ rabbitmq opcional)
```

---

## 9. Arquitectura (de un vistazo)

Monolito **modular**: un **kernel compartido** (`Core`/`Models`/`Dictionaries`) y
**módulos independientes** (`app/Modules/*`) que **no se importan entre sí** (lo fuerza
`import-linter`). Cada módulo es un microservicio en potencia: se puede extraer sin
desenredar imports cruzados.

- **Persistencia estilo Spring Data.** `Repository[Model, Id]` tipado (CRUD heredado),
  escrituras en services `@transactional` (commit/rollback automático), lecturas con
  `@auto_session`. El engine es **agnóstico del motor** (se elige por `DATABASE_URL`);
  lo específico de cada dialecto está aislado en `Core/Database/Session.py`.
- **Tareas y crons.** Celery con transporte **agnóstico** (`BROKER_URL`): Redis o
  RabbitMQ en local, nubes como referencia. Los crons se declaran con `@cron_task`.
- **Correo.** `Mailable` + `Mailer` con drivers intercambiables (`smtp`/`log`/`null`),
  plantillas Jinja2 e i18n por YAML.
- **HTTP.** `create_app()` arma FastAPI, monta los módulos activos y fija el locale en
  el **boundary** (ambiente); middlewares (CORS/TrustedHost/GZip) con defaults seguros.
- **Calidad forzada.** Ruff + MyPy estricto + import-linter + pytest como guardrails.

---

## 10. Agregar un módulo

1. Crea `app/Modules/<Nombre>/` (mira `Modules/Example` como plantilla).
2. Pon dentro lo que necesite: `Http/` (rutas), `Jobs/` (tareas), `Mail/`, `Services/`,
   `Repositories/`, `Resources/` (lang/views namespaced), `Console/Commands/`.
3. Actívalo por configuración. La API y el beat lo **descubren solos**; el
   `import-linter` garantiza que no se enrede con otros módulos.

No tocas el kernel: el framework descubre modelos, diccionarios, recursos, comandos y
crons por convención.

---

## Notas

- **Borrado lógico** (`deleted_at`) y **timestamps** (`created_at`/`updated_at`) son
  automáticos y declarativos (estilo Laravel/JPA); las fechas usan la zona de `TIMEZONE`.
- **Auto-discovery**: soltar un modelo en `app/Models`, un diccionario en
  `app/Dictionaries` o un módulo en `app/Modules` "simplemente funciona", sin editar
  índices a mano.
- **Migrar desde Laravel**: el kernel reproduce conceptos familiares (artisan→`jornal`,
  scheduler→`@cron_task`, mailables, soft-deletes, timestamps, validación de tokens
  Passport) para acortar la curva.
