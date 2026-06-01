# Ciclo de vida de la petición

El corazón HTTP de milpa es la fábrica `create_app()` en `app/Core/Http/Http.py`. Es el
equivalente al bootstrap de Laravel: arma la app de FastAPI, monta middlewares,
descubre los módulos y fija el ciclo de vida.

## `create_app()`

```python
def create_app() -> FastAPI:
    ...
```

Qué hace, en orden:

1. Configura el logging (Loguru) — ver [Logging](14-logging.md).
2. Crea la app:
   `FastAPI(title=settings.app_name, lifespan=_lifespan, dependencies=[Depends(_use_request_locale)])`.
3. Registra los middlewares (`register_middlewares(app)`).
4. Auto-monta los routers de los módulos (`iter_routers()`).
5. Auto-monta los estáticos por módulo (`/static/<x>`) y los compartidos (`/static`).
6. Expone un endpoint `/status` que devuelve `{servicio, modulos, status}`.

Es una **app factory**: uvicorn la llama con `--factory`, así cada arranque construye una
instancia fresca (necesario para `--reload`).

```bash
uv run python jornal serve            # = uvicorn app.Core.Http.Http:create_app --factory ...
```

## Lifespan (arranque y apagado)

```python
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    ...
```

- **Antes del `yield`** (startup): importa todos los modelos y, **solo si**
  `AUTO_CREATE_TABLES=true`, crea las tablas. Loguea los módulos activos.
- **Después del `yield`** (shutdown): limpieza (vacío hoy).

## Frontera de locale

```python
async def _use_request_locale(accept_language: str = Header(default="")) -> None:
    set_request_locale(resolve_accept_language(accept_language))
```

Esta dependency es **global** (`dependencies=[Depends(_use_request_locale)]` en
`create_app`), así que corre en **todos** los endpoints. Lee el header `Accept-Language`,
resuelve el idioma (`es-MX` → `es`, toma el de mayor `q`) y lo fija en un contextvar.
A partir de ahí, `t()` y `current_locale()` lo usan sin que tengas que pasarlo.

Es **async a propósito**: una dependency sync correría en un threadpool distinto y el
`contextvar.set()` no sería visible para el handler. Ver [Localización](13-localizacion-i18n.md).

## Middlewares

`app/Core/Http/Middleware.py` → `register_middlewares(app)`. Cada middleware se monta
**solo si su setting lo activa** (defaults seguros: nada de más):

| Middleware | Se monta si… | Settings |
|------------|--------------|----------|
| **GZip** | `GZIP_ENABLED=true` | `gzip_min_size` |
| **TrustedHost** | `TRUSTED_HOSTS` ≠ `*` | `trusted_hosts` (coma-separado) |
| **CORS** | `CORS_ALLOW_ORIGINS` no vacío | `cors_allow_*` |

> **Orden**: el último que se agrega es el más **externo**. CORS se agrega al final para
> que procese el preflight `OPTIONS` antes que los demás. No cambies el orden sin saber
> esto.

Configúralos en el `.env` (ver [Configuración](03-configuracion.md)). En producción:
restringe `TRUSTED_HOSTS` a tus dominios y `CORS_ALLOW_ORIGINS` a tus orígenes.

## El endpoint `/status`

`create_app()` registra un único endpoint propio:

```
GET /status  →  {"servicio": "<APP_NAME>", "modulos": ["Example", ...], "status": "ok"}
```

Útil para health checks y para confirmar qué módulos están montados. Todo lo demás
viene de los módulos (ver [Rutas y controladores](07-rutas-y-controladores.md)).

## Flujo completo de una petición

```
Request
  → middlewares (CORS / TrustedHost / GZip, los que estén activos)
  → dependency global _use_request_locale (fija el locale desde Accept-Language)
  → router del módulo (auto-montado por iter_routers)
  → tu handler
  → response
```

## Siguiente paso

[Monolito modular](06-monolito-modular.md).
