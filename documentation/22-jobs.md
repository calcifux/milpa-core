# Jobs en background (`@job`)

Un **job** es trabajo pesado que disparas **tú** desde tu código y corre fuera del ciclo
HTTP, en el worker. milpa lo modela al estilo `Job::dispatch` de Laravel: decoras una
función con `@job`, la encolas con `.dispatch(...)` y respondes al usuario sin esperar a
que termine.

```python
from app.Modules.Demo.Jobs.ExportNotesJob import export_user_notes

export_user_notes.dispatch(user_id=42)   # encola y regresa ya; lo corre `jornal queue work`
```

`@job` vive en `milpa/Core/Jobs` (no en `Core/Cron`) **a propósito**: un job y un cron son
dos modelos de ejecución distintos y mezclarlos lleva a errores sutiles. Más abajo está
la tabla que los contrasta.

## Declarar un job

Pon el job bajo `Modules/<X>/Jobs/` y decora la función con `@job`. El módulo de
referencia trae uno en `app/Modules/Demo/Jobs/ExportNotesJob.py`:

```python
# app/Modules/Demo/Jobs/ExportNotesJob.py
from loguru import logger
from milpa.Core.Jobs import job
from app.Modules.Demo.Repositories.NoteRepository import NoteRepository

@job(name="demo.export_notes", queue="exports")
def export_user_notes(user_id: int) -> dict[str, int]:
    """Corre en el WORKER: reúne las notas del usuario (el 'export' real iría aquí)."""
    notes = NoteRepository().for_owner(user_id)
    logger.info("demo.export_notes | usuario {u}: {n} notas", u=user_id, n=len(notes))
    return {"user_id": user_id, "exported": len(notes)}
```

`@job` es un wrapper fino sobre `@celery_app.task`: auto-nombra la task (`<módulo>.<func>`
si no pasas `name`), la registra y devuelve un **handle** `Job`. El descubrimiento es el
mismo que cualquier task: el Registry importa `Modules/<X>/Jobs/` al arrancar y el
decorador registra la task de Celery. No hay registro nuevo que mantener.

### Parámetros de `@job`

| Parámetro | Tipo | Para qué |
|-----------|------|----------|
| `name` | `str \| None` | Nombre de la task. `None` = `<módulo>.<función>` (auto). |
| `queue` | `str \| None` | Cola por defecto del job (ver [Colas y tareas](11-colas-y-tareas.md)). `None` = cola por defecto. |
| `retry_for` | `tuple[type[BaseException], ...]` | Excepciones **transitorias** que disparan reintento. Vacío = fire-and-forget. |
| `max_retries` | `int \| None` | Máx. de reintentos (solo aplica con `retry_for`). `None` = `settings.task_max_retries`. |
| `bind` | `bool` | `True` da `self` como primer argumento (para leer `self.request.retries`). |

> `schedule=` está **prohibido** en `@job`: si pasas uno, lanza `ValueError`. Para tareas
> programadas usa `@cron_task` (ver [Programación de tareas](12-programacion-cron.md)).

## Disparar un job: `.dispatch()` y `.delay()`

El handle `Job` expone dos formas de encolar y una de correr síncrono:

```python
export_user_notes.dispatch(42)                  # encola (broker-guarded) → recomendado
export_user_notes.dispatch(42, queue="urgent")  # encola, sobrescribiendo la cola del decorador
export_user_notes.delay(42)                      # API cruda de Celery (sin broker_guard)
export_user_notes(42)                            # SÍNCRONO, en el proceso actual (tests)
```

- **`.dispatch(*args, queue=None, **kwargs)`** — el camino idiomático. Encola con
  `apply_async`, envuelto en `broker_guard` (ver abajo). El kwarg `queue` sobrescribe,
  solo para esa llamada, la cola declarada en `@job(queue=...)`.
- **`.delay(...)`** — el handle delega cualquier atributo no definido al `Task` de Celery
  (`.delay`, `.apply_async`, `.s`, `.si`, `.name`…). Úsalo para firmas/chains avanzados;
  ojo: **no** pasa por `broker_guard`, así que un broker caído sale como el stacktrace
  crudo de kombu en vez de un 503 limpio.
- **Llamarlo directo `export_user_notes(42)`** — lo corre **síncrono** en el proceso
  actual, sin encolar. Útil en tests para verificar la lógica sin levantar un worker.

### Desde un endpoint

Así lo dispara el controller del demo (`app/Modules/Demo/Http/ApiController.py`). Encola y
responde `202 Accepted` de inmediato:

```python
@Post("/notes/export", status_code=202)
def export_notes(self, user: Authenticatable = _JwtUser) -> dict[str, str]:
    # @job de background: encola y regresa ya (broker caído → 503 RFC 9457, nunca drop mudo).
    export_user_notes.dispatch(user.get_auth_identifier())
    return {"status": "queued"}
```

No hay `await`, no hay bloqueo: el export pesado corre en el worker mientras el cliente ya
tiene su respuesta. Para procesar la cola, levanta el worker con `jornal queue work`
(o `jornal queue work --queue=exports` para consumir esa cola en particular).

## Reintentos: opt-in, solo para fallos transitorios

Por defecto un job es **fire-and-forget**: si revienta, no se reintenta. Para activar
reintentos pasa `retry_for` con las excepciones **transitorias** que sí vale la pena
volver a intentar (timeouts, desconexiones, fallos de red):

```python
@job(retry_for=(ConnectionError, TimeoutError), max_retries=5)
def sync_invoices(account_id: int) -> None:
    ...
```

Bajo el cofre, `retry_for` aplica `retry_policy(...)` de
`milpa/Core/CeleryApp/Retry.py`: cablea `autoretry_for` + backoff exponencial con jitter.
Los defaults (`max_retries`, backoff y su tope) salen de `.env`
(`TASK_MAX_RETRIES`, `TASK_RETRY_BACKOFF`, `TASK_RETRY_BACKOFF_MAX`) o los pisas a mano por
job. Ver [Colas y tareas](11-colas-y-tareas.md).

> **No listes excepciones permanentes** en `retry_for` (validación, auth, archivo
> inexistente): reintentar no las arregla y solo agota intentos. Si necesitas reintentar a
> mano dentro de la función, usa `bind=True` para recibir `self` y llamar `self.retry(...)`.

## Job vs. cron: la distinción clave

Ambos corren en el worker de Celery, pero responden a preguntas distintas. Esta es la
regla mental:

| | **Job** (`@job`, `Core/Jobs`) | **Cron** (`@cron_task`, `Core/Cron`) |
|---|---|---|
| **Quién lo dispara** | **Tú**, desde tu código (`.dispatch()`). | El **scheduler** (`jornal schedule run`, vía crontab del SO). |
| **Cuándo corre** | On-demand, cuando lo encolas. | A una cadencia fija (`schedule="*/5 * * * *"`). |
| **Reintentos** | Opt-in (`retry_for=`). | **Nunca** (se re-agenda solo en la próxima corrida). |
| **Anti-overlap (lock)** | No. | Sí (`without_overlapping`, lock en Redis). |
| **Env-gating / output routing** | No. | Sí (`environments=`, `output=`). |
| **Analogía Laravel** | `Job::dispatch()` | `$schedule->command(...)->...` |

La regla rápida: **si lo disparas tú** (un endpoint, un comando, un evento) → `@job`. **Si
el reloj lo dispara** a intervalos → `@cron_task`. Por eso un cron **no** lleva reintentos
(reintentar encima de un re-agendado duplicaría trabajo) y un job **no** lleva lock (tú
controlas cuándo y cuántas veces lo disparas).

## Broker caído → `QueueUnavailableError` (503)

`.dispatch()` envuelve el encolado en `broker_guard()`. Si el broker (Redis por defecto) no
responde, Celery/kombu lanzarían un error de bajo nivel poco claro; `broker_guard` lo
traduce a un **`QueueUnavailableError`** con un mensaje accionable (qué falta: broker +
worker, y que existe el camino síncrono).

`QueueUnavailableError` hereda de `DomainError` con `status_code = 503`, así que el handler
global RFC 9457 (ver [Rutas y controladores](07-rutas-y-controladores.md)) lo rinde solo
como `application/problem+json` (503 Service Unavailable). **El controller que despacha
NO necesita `try/except`**: encola y ya. Faro, no silencio: el broker caído sale como un
error claro y observable, nunca un 500 técnico ni un drop mudo.

```json
{
  "type": "about:blank",
  "title": "Queue unavailable",
  "status": 503,
  "detail": "No se pudo encolar: el broker no responde en 'redis://localhost:6379/0'. ...",
  "code": "queue_unavailable"
}
```

> `.delay()` **no** pasa por `broker_guard`: con el broker caído verías el stacktrace de
> kombu en vez del 503 limpio. Por eso, en código de la app, prefiere `.dispatch()`.

## Forma tradicional vs. estilo milpa

| | Forma tradicional (Celery a pelo) | Estilo milpa (`@job`) |
|---|---|---|
| Declarar | `@celery_app.task(name="...", autoretry_for=(...), max_retries=..., retry_backoff=...)` | `@job(name="...", retry_for=(...))` — el backoff sale de `.env`. |
| Encolar | `task.apply_async(args=[...], queue="...")` | `task.dispatch(..., queue="...")` |
| Broker caído | Stacktrace crudo de kombu → 500 técnico. | `QueueUnavailableError` → 503 RFC 9457 automático. |
| En tests | Levantar worker o `task.apply()`. | `task(...)` lo corre síncrono. |

El estilo milpa no te quita nada de Celery (el handle delega al `Task`), solo enmascara el
ceremonial repetitivo y el manejo del broker caído.

## Siguiente paso

[Programación de tareas (cron)](12-programacion-cron.md).
