# Colas y tareas

milpa usa **Celery** para trabajo en background. El transporte es **agnóstico del
broker** (Redis, RabbitMQ, SQS…), se elige por `.env`, y los flujos síncronos no lo
tocan.

## La app de Celery

`milpa/Core/CeleryApp/CeleryApp.py` configura la instancia `celery_app` de forma
agnóstica:

| Setting (`.env`) | Default | Para qué |
|------------------|---------|----------|
| `BROKER_URL` | `""` → `redis://localhost:6379/0` | Transporte. `redis://…`, `amqp://…` (RabbitMQ), `sqs://…`. |
| `RESULT_BACKEND_URL` | `""` → sin backend | Backend de resultados. Opcional (fire-and-forget). |
| `LOCK_URL` | `""` → redis local | Store de locks para `without_overlapping` (crons). |
| `REDIS_VISIBILITY_TIMEOUT` | `3600` | Segundos antes de re-entregar una task no reconocida (redis/SQS). |

Otros defaults: serialización **JSON** (no pickle), `task_track_started=True`,
`result_expires=3600`, timezone de `settings.timezone`, y Loguru maneja el logging
(Celery no secuestra el root logger).

> Redis local es solo un fallback de conveniencia para dev. En `docker compose` ya viene
> Redis (y RabbitMQ opcional). ActiveMQ **no** es compatible con Celery (AMQP 1.0); usa
> RabbitMQ.

## Definir una task

Una task es una función decorada con `@celery_app.task`. Ponla bajo `Modules/<X>/Jobs/`:

```python
# app/Modules/Example/Jobs/HelloJob.py
from loguru import logger
from milpa.Core.CeleryApp import celery_app

@celery_app.task(name="example.hello")
def hello_world(name: str = "mundo") -> str:
    logger.info("example.hello | ¡Hola, {name}! (en el worker)", name=name)
    return f"Hola, {name}!"
```

Se registra sola al importarse (el Registry importa `Jobs/` de cada módulo en
`import_all_tasks()`). No hay que listarla en ningún lado.

## Despachar trabajo

```python
hello_world.delay(name="Calcifux")                     # cola por defecto
hello_world.apply_async(args=["Calcifux"], queue="emails")   # cola con nombre
```

Lo procesa un worker (`jornal queue work`).

## Arrancar el worker

```bash
uv run python jornal queue work                     # cola por defecto
uv run python jornal queue work --queue emails,reports
uv run python jornal queue work --concurrency 8
```

Opciones: `--queue` (colas a consumir, coma-separadas; `= queue:work --queue=`),
`--concurrency` (procesos en paralelo; default = nº de CPUs), `--loglevel`.

> El worker **no** arranca el scheduler. Los crons se disparan aparte
> (`schedule work` / `schedule run`), así dev no auto-dispara crons. Ver
> [Cron](12-programacion-cron.md).

## Encolar con guarda de broker

Si el broker está caído, despachar lanza errores de bajo nivel (kombu/redis). El helper
`broker_guard()` los traduce a un `QueueUnavailableError` accionable:

```python
from milpa.Core.CeleryApp import broker_guard, QueueUnavailableError

try:
    with broker_guard():
        hello_world.delay(name="Calcifux")
except QueueUnavailableError as e:
    logger.error(e)
    # fallback: corre síncrono si tiene sentido
```

`Mail.queue` ya usa esto por dentro (ver [Correo](10-correo.md)).

## Colas con nombre

Para separar cargas (ej. un worker dedicado a `emails`):

```python
task.apply_async(queue="emails")          # productor
```
```bash
uv run python jornal queue work --queue emails    # consumidor dedicado
```

Si nadie consume esa cola, el mensaje se queda ahí hasta que un worker la atienda.

## Compartir un broker entre apps

Pasa en serio: dos servicios distintos apuntan **al mismo redis** (la misma `BROKER_URL`,
el mismo db) porque "ya estaba ahí". A partir de ese momento las colas son un bus
**compartido** y empiezan los robos silenciosos.

| Síntoma | Por qué pasa | Qué se ve |
|---------|--------------|-----------|
| Una corrida **se pierde** | El worker de la app B saca de la cola un mensaje de la app A cuya task **no conoce**. Celery no puede deserializarla → la **descarta** (`KeyError` / `NotRegistered`). | La task "se ejecutó" (salió de la cola) pero **nunca corrió**. Nadie se entera. |
| **Ejecución cruzada SILENCIOSA** | `mail.send`, `events.handle` y demás tasks del framework están registradas en **TODAS** las apps milpa/tequio con el **mismo nombre**. El worker de la app B sí la conoce, así que la corre… con **su** config (su SMTP, su BD). | El correo de la app A sale por el servidor de la app B. Sin error. El peor caso: parece que funciona. |

> Esto no es hipotético: le pasó al dueño en la mega-red **aqua**, con varias apps milpa/tequio
> en el mismo redis. La task desconocida = corrida perdida; `mail.send` registrada en todas =
> envíos saliendo por la app equivocada.

### El paño tibio: un db por app

Lo primero que uno intenta es darle a cada app **su propio db de redis** (`…/0`, `…/1`, `…/2`
en la `BROKER_URL`). Funciona… hasta que llegas a **Redis Cluster**, que solo expone el **db
0**. Ahí todas las apps vuelven a caer en el mismo espacio y el problema regresa. El db-por-app
es una mitigación de juguete, no una solución durable.

### La solución durable: `QUEUE_NAMESPACE`

Le das a cada app un **prefijo de colas** y deja de existir el cruce: cada worker consume
**solo lo suyo** dentro del MISMO db (por eso **sobrevive en Redis Cluster**).

```bash
# app A
QUEUE_NAMESPACE=ventas
# app B
QUEUE_NAMESPACE=reportes
```

Con un namespace activo (ej. `ventas`):

- La **cola por defecto** pasa de `celery` a `ventas.celery` (vía `task_default_queue`). Esto
  cubre TODO lo que se despacha **sin** `queue=` explícito: `events.handle`, un `Mail.queue`
  sin cola, los jobs y crons a la default. Ahí estaba el cruce silencioso de `mail.send`/
  `events.handle` — y ahí se corta.
- Las **colas con nombre** se prefijan: `emails` → `ventas.emails`, `reports` → `ventas.reports`.
  Tú sigues tecleando `emails`; el prefijo lo pone el framework en un solo lugar.
- El **lock anti-overlapping** de los crons también se namespacea: `cron-lock:<name>` →
  `cron-lock:ventas:<name>`, para que dos apps con un cron homónimo no compartan lock (ver
  [Cron](12-programacion-cron.md)).

Vacío (el **default**) = comportamiento de siempre, **100% retrocompatible**: sin prefijo, las
keys actuales intactas. No tienes que hacer nada hasta que de verdad compartas un broker.

Arrancar el worker no cambia: tú pides la cola lógica y el framework la califica.

```bash
# app A (QUEUE_NAMESPACE=ventas) — consume ventas.celery + ventas.emails
uv run python jornal queue work --queue celery,emails
```

> Bajo el capó vive un resolvedor único — `qualified_queue(name)` en
> `milpa/Core/CeleryApp/Dispatch.py` (junto a `broker_guard`) — por el que pasa **cada**
> call-site que despacha con `queue=` explícito. Un solo lugar aplica el prefijo, así no hay
> dos reglas distintas regándose por el código.

## Síncrono vs. encolado

| | Síncrono | Encolado |
|--|----------|----------|
| Cómo | llamar la función / `Mail.send` | `.delay()` / `.apply_async()` / `Mail.queue` |
| Broker | **no** lo necesita | sí (redis/RabbitMQ/…) |
| Bloquea | sí | no |
| Cuándo | local, tests, confirmación inmediata | producción, trabajo pesado |

## Reintentos ante fallos transitorios

Una task que toca la red (SMTP, HTTP, otra BD) puede fallar por algo **momentáneo**: el
servicio se cayó un segundo, un timeout, la conexión se reinició. Para eso está el helper
`retry_policy(...)` (`milpa/Core/CeleryApp`): cablea `autoretry_for` + **backoff exponencial**
de forma reutilizable y **configurable de dos maneras** — por `.env` o **a mano en código**.

```python
from smtplib import SMTPException

from milpa.Core.CeleryApp import celery_app, retry_policy

# (1) Defaults framework-wide desde .env (TASK_MAX_RETRIES / TASK_RETRY_BACKOFF / ...):
@celery_app.task(bind=True, name="mail.send", **retry_policy(retry_for=(SMTPException,)))
def send_mail_task(self, ...): ...

# (2) Configurado A MANO para ESTA task (pisa el .env, sin tocar el entorno):
@celery_app.task(
    bind=True,
    name="sync.invoices",
    **retry_policy(retry_for=(ConnectionError, TimeoutError), max_retries=5, backoff=10),
)
def sync_invoices(self, ...): ...
```

Claves de diseño:

- **Configurable a mano, no solo `.env`.** Cada parámetro de `retry_policy(...)` toma su
  default de Settings (`TASK_MAX_RETRIES`, `TASK_RETRY_BACKOFF`, `TASK_RETRY_BACKOFF_MAX`),
  pero se puede **fijar explícito por-task** (`max_retries=5`, `backoff=10`, `jitter=False`).
- **Solo se reintenta lo TRANSITORIO.** `retry_for` lista las excepciones que tiene sentido
  reintentar. Un fallo **permanente** (credenciales inválidas, un adjunto inexistente →
  `FileNotFoundError`) **no** debe ir ahí: reintentar no lo arregla y agota intentos. Por
  eso `mail.send` usa `(SMTPException, ConnectionError, TimeoutError)` y NO `OSError` a secas.
- **Backoff exponencial con jitter.** El reintento N espera ~`backoff · 2^(N-1)` segundos,
  con tope `backoff_max`. El `jitter` desincroniza los reintentos para no martillar al
  servicio caído justo cuando vuelve.
- **Observabilidad.** `mail.send` loguea `intento N/total` (vía `self.request.retries`), así
  un fallo transitorio queda visible y auditable en los logs.

**Ojo con los crons** (`@cron_task`): NO les pongas `retry_policy` — un cron se reagenda solo
y ya trae lock anti-overlapping; un reintento encima duplicaría trabajo.

## Siguiente paso

[Programación de tareas (cron)](12-programacion-cron.md).
