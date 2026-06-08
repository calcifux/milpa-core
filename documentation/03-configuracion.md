# Configuración

Toda la configuración vive en un archivo `.env` en la raíz y se lee a través de una
única clase `Settings` (pydantic-settings).

```bash
cp .env.example .env
```

## La clase `Settings`

`milpa/Core/Config/Settings.py` define la clase `Settings` (pydantic `BaseSettings`) y
exporta una **instancia única**:

```python
from milpa.Core.Config import settings

print(settings.app_name)
print(settings.database_url)
```

Se carga del `.env` **una sola vez** al arrancar el proceso (es un singleton). Cambiar
el `.env` requiere reiniciar. El atributo `extra="ignore"` permite que varios módulos
compartan el mismo `.env` sin chocar.

> `DATABASE_URL` es la **única variable obligatoria** (sin default). Un clone limpio no
> arranca hasta configurarla.

## Referencia de variables

### Base de datos

| Variable | Default | Para qué |
|----------|---------|----------|
| `DATABASE_URL` | (obligatorio) | Conexión SQLAlchemy; el prefijo elige el motor. |
| `AUTO_CREATE_TABLES` | `false` | Si la app puede crear tablas. Contra BD legacy: **`false`**. |

### Aplicación

| Variable | Default | Para qué |
|----------|---------|----------|
| `APP_NAME` | `App` | Nombre del proyecto (se usa en i18n como `%{app_name}` y en el título). |
| `APP_ENV` | `qa` | Entorno: `local`, `qa`, `production`. Gatea crons y CCO de correo. |
| `APP_PORT` | `8000` | Puerto de FastAPI (uvicorn). |
| `APP_FALLBACK_LOCALE` | `es` | Locale por defecto de i18n cuando no se pasa uno explícito. |
| `TIMEZONE` | zona del host | Zona IANA (ej. `America/Mexico_City`). Gobierna timestamps y fechas. |

> **`TIMEZONE`**: si se omite, milpa detecta la zona del **host**. En un servidor
> (suele estar en UTC) **fíjala explícita**: quien monta el server puede no ser quien
> programa.

### Colas / broker (Celery)

| Variable | Default | Para qué |
|----------|---------|----------|
| `BROKER_URL` | `""` → redis local | Transporte de Celery (`redis://…`, `amqp://…`, `sqs://…`). |
| `RESULT_BACKEND_URL` | `""` → sin backend | Backend de resultados (opcional; crons son fire-and-forget). |
| `LOCK_URL` | `""` → redis local | Store de locks para `without_overlapping`. |
| `REDIS_VISIBILITY_TIMEOUT` | `3600` | Segundos antes de re-entregar una task (redis/SQS). |
| `QUEUE_NAMESPACE` | `""` → sin prefijo | Prefijo de colas para convivir en un **broker compartido** (varias apps en el mismo redis db). Vacío = comportamiento actual. Con valor, la cola por defecto pasa a `<ns>.celery` y las nombradas a `<ns>.<cola>`. |
| `EVENTS_QUEUE` | `""` → cola por defecto | Cola dedicada para eventos/observers (`events.handle`). Vacío = caen en `<ns>.celery` con todo lo demás. Con valor (ej. `events`) van a `<ns>.events`: métricas de eventos separadas en Prometheus **sin** proceso extra (mismo worker, si la agregas a `queue work --queue …,events`). |

Ver [Colas y tareas](11-colas-y-tareas.md) → *Compartir un broker entre apps*.

### HTTP / middlewares

| Variable | Default | Para qué |
|----------|---------|----------|
| `CORS_ALLOW_ORIGINS` | `""` → sin CORS | Orígenes permitidos, coma-separado. Vacío = same-origin. |
| `CORS_ALLOW_METHODS` | `*` | Métodos CORS. |
| `CORS_ALLOW_HEADERS` | `*` | Headers CORS. |
| `CORS_ALLOW_CREDENTIALS` | `false` | `true` requiere orígenes explícitos (no `*`). |
| `TRUSTED_HOSTS` | `*` | Hosts permitidos. `*` = desactivado (anti Host-header attack). |
| `GZIP_ENABLED` | `false` | Compresión GZip de respuestas (mejor en el proxy/nginx en prod). |
| `GZIP_MIN_SIZE` | `500` | Tamaño mínimo (bytes) para comprimir. |

Los middlewares solo se montan si su setting lo activa. Ver [Ciclo de vida](05-ciclo-de-vida.md).

### Correo

| Variable | Default | Para qué |
|----------|---------|----------|
| `MAIL_DRIVER` | `smtp` | `smtp` (real), `log` (lo escribe en el log), `null`/`array` (no-op). |
| `MAIL_HOST` | `localhost` | Host SMTP (en local: Mailpit). |
| `MAIL_PORT` | `1025` | Puerto SMTP. |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | `""` | Credenciales SMTP (vacío si no aplica). |
| `MAIL_ENCRYPTION` | `""` | `""` (sin), `tls` (STARTTLS), `ssl` (SMTPS). |
| `MAIL_FROM_ADDRESS` | `no-reply@example.com` | Remitente (alias `MAIL_FROM_EMAIL`). |
| `MAIL_FROM_NAME` | `App` | Nombre del remitente. |
| `ADMIN_SYSTEM_MAILS` | `""` | Destinatarios de sistema (fallback), coma-separado. |
| `MAIL_CCO_RECIPIENT` | `""` | CCO para auditoría. |

Ver [Correo](10-correo.md).

### Autenticación (Passport)

| Variable | Default | Para qué |
|----------|---------|----------|
| `PASSPORT_PUBLIC_KEY_PATH` | `None` | Ruta al archivo con la llave pública RS256 de Passport. |
| `PASSPORT_PUBLIC_KEY` | `None` | La llave pública en texto (alternativa a la ruta). |
| `PASSPORT_EXPECTED_AUDIENCE` | `None` | Audience (`aud`) esperado en el JWT (opcional). |

Ver [Autenticación](15-autenticacion.md).

### Logging

| Variable | Default | Para qué |
|----------|---------|----------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_JSON` | `false` | `true` agrega `logs/app.jsonl` (JSON Lines para Loki/Grafana). |
| `LOG_DIR` | `logs` | Directorio de logs. |

Ver [Logging](14-logging.md).

### Vite / frontend (opt-in)

Solo aplica si usas el asset-pipeline o los microfrontends (surcos). Los defaults son los
del layout que genera `milpa new`; en un proyecto recién creado no tocas nada.

| Variable | Default | Para qué |
|----------|---------|----------|
| `VITE_APPS_DIR` | `surcos` | Carpeta de las **fuentes** de los surcos (uno por vertical). |
| `VITE_PUBLIC_DIR` | `public` | Carpeta `public/`: el build de cada surco cae en `public/<app>`. |
| `VITE_ASSETS_URL` | `/vite` | Raíz pública donde milpa monta el `public/` (cada app en `<assets_url>/<app>`). |
| `VITE_DIST_DIR` | `""` | Override **explícito** para una-sola-app (ignora la auto-detección). |
| `VITE_HOT_FILE` | `""` | Hot-file del modo una-sola-app. Vacío ⇒ `<dist>/../hot`. |
| `ASSET_URL` | `""` | Prefijo público de `asset()`/`vite()`/`vite_asset()` (CDN o sub-ruta de proxy). DEBE coincidir con el del build. |

Ver [Vite y assets](29-vite-y-assets.md).

### Layout del proyecto

milpa instalado como paquete no puede adivinar dónde vive tu código contando carpetas
desde sí mismo (en `site-packages` eso apunta a otro lado): lo lee de estas variables. Los
defaults apuntan a `app.*` —el layout que genera `milpa new`—, así una instalación limpia
encuentra TU código sin configurar nada (y, a propósito, **no** auto-descubre el Demo
EMPAQUETADO del framework).

| Variable | Default | Para qué |
|----------|---------|----------|
| `MODULES_PACKAGE` | `app.Modules` | Paquete (punteado) donde se escanean los módulos (rutas/jobs/crons/seeders/observers…). |
| `MODELS_PACKAGE` | `app.Models` | Paquete donde viven los modelos (se cargan en `Base.metadata`). |
| `APP_COMMANDS_PACKAGE` | `app.Console.Commands` | Commands generales del proyecto (opcional; tolera ausencia). |
| `MIGRATIONS_DIR` | `migrations` | Carpeta de migraciones Alembic, relativa al cwd. |
| `APP_DIR` | `app` | Raíz donde `make:*` escribe (controllers/modelos/…), relativa al cwd. |
| `USER_VIEWS_DIR` | `""` | Vistas/plantillas propias de un proyecto externo (ej. `app/Resources/Views`). Vacío = usa las del paquete. |
| `USER_LANG_DIR` | `""` | Catálogos i18n propios de un proyecto externo (ej. `app/Resources/Lang`). Vacío = usa los del paquete. |

!!! warning "Si trabajas DENTRO de este repo"
    El código de milpa vive en `src/milpa`, no en `app/`. Para que el discovery encuentre los
    módulos del framework (el Demo y sus crons/jobs) re-apunta los tres paquetes a `milpa.*`
    en tu `.env` (lo documenta `.env.example`). En la suite, `Tests/conftest.py` ya hace ese
    `setdefault` por ti.

## Propiedades calculadas útiles

`Settings` expone helpers para no repetir lógica de fallback:

| Método | Qué devuelve |
|--------|--------------|
| `settings.effective_broker_url()` | `broker_url` o redis local si vacío. |
| `settings.effective_lock_url()` | `lock_url` o redis local si vacío. |
| `settings.effective_result_backend()` | `result_backend_url` o `None`. |
| `settings.broker_uses_visibility_timeout()` | `True` si el broker es redis/SQS (no RabbitMQ). |
| `settings.load_passport_public_key()` | Lee la llave desde literal o archivo. |

## Siguiente paso

[Estructura de directorios](04-estructura-directorios.md).
