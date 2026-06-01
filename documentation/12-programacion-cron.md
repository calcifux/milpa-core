# Programación de tareas (cron)

milpa reproduce el **scheduler de Laravel** sobre Celery: declaras la cadencia pegada al
job con `@cron_task`, y un disparador (`schedule run`, llamado por el crontab del SO)
despacha lo que toca.

## Declarar un cron

Pon el job bajo `Modules/<X>/Jobs/` y decóralo:

```python
# app/Modules/Example/Jobs/SendReminders.py
from loguru import logger
from app.Core.Cron import cron_task, every_five_minutes

@cron_task(
    name="send_reminders",
    schedule=every_five_minutes(),
    environments=["qa", "production"],
    without_overlapping=True,
    output="reminders",
    queue="emails",
)
def send_reminders() -> None:
    logger.info("Enviando recordatorios...")
    # ...
```

Se registra al importarse. (El Registry importa `Jobs/` de cada módulo.)

## El decorador `@cron_task`

```python
def cron_task(
    *,
    name: str,
    schedule: str | None = None,
    queue: str | None = None,
    environments: Sequence[str] | None = None,
    without_overlapping: bool = False,
    output: str | None = None,
    lock_timeout: int | None = None,
    **celery_options: Any,
) -> Callable[[DecoratedTask], Any]
```

| Parámetro | Default | Semántica | Laravel |
|-----------|---------|-----------|---------|
| `name` | (obligatorio) | Identificador único de la task. | — |
| `schedule` | `None` | Expresión cron (5 campos). Si es `None`, la task existe pero no se agenda. | `->cron()` |
| `queue` | `None` | Cola de Celery; `None` = cola por defecto. | `->onQueue()` |
| `environments` | `None` → todos | Lista de `APP_ENV` donde corre; si `app_env` no está, se omite. | `->environments()` |
| `without_overlapping` | `False` | Lock en Redis; si la corrida previa sigue, se omite esta. | `->withoutOverlapping()` |
| `output` | `None` | Rutea los logs de la corrida a `logs/cron_<output>.log` (rotación diaria, 14 días). | `->appendOutputTo()` |
| `lock_timeout` | derivado | Timeout del lock. Por defecto `visibility_timeout + 300s`. | — |
| `**celery_options` | — | Cualquier opción extra de Celery (`rate_limit`, etc.). | — |

> A diferencia de `@console_command`, `@cron_task` **sí envuelve** la función: la wrapper
> ejecuta los guards (entorno, lock, logs) antes de tu código, y devuelve una task de
> Celery. Puedes llamarla con `.delay()` o directo `task()`.

## Cadencia: helpers de `Schedule`

En vez de escribir cron raw, usa los helpers (`app/Core/Cron`):

| Helper | Cron | Laravel |
|--------|------|---------|
| `every_minute()` | `* * * * *` | `everyMinute()` |
| `every_minutes(n)` | `*/n * * * *` | `everyNMinutes()` |
| `every_five_minutes()` | `*/5 * * * *` | `everyFiveMinutes()` |
| `every_ten_minutes()` | `*/10 * * * *` | `everyTenMinutes()` |
| `every_fifteen_minutes()` | `*/15 * * * *` | `everyFifteenMinutes()` |
| `every_thirty_minutes()` | `*/30 * * * *` | `everyThirtyMinutes()` |
| `hourly()` | `0 * * * *` | `hourly()` |
| `hourly_at(min)` | `<min> * * * *` | `hourlyAt()` |
| `daily()` | `0 0 * * *` | `daily()` |
| `daily_at("HH:MM")` | `<m> <h> * * *` | `dailyAt()` |
| `weekly()` | `0 0 * * 0` | `weekly()` |
| `monthly()` | `0 0 1 * *` | `monthly()` |
| `cron("expr")` | escape hatch (raw) | `cron()` |

```python
from app.Core.Cron import cron_task, daily_at, hourly_at, cron

@cron_task(name="backup", schedule=daily_at("02:30"), environments=["production"])
def backup() -> None: ...

@cron_task(name="reporte", schedule=cron("15 9 * * 1-5"))   # 9:15 lun-vie
def reporte() -> None: ...
```

## Cómo se disparan: `schedule run` vs `schedule work`

Hay dos modos. **Elige uno**:

### A) `schedule run` desde el crontab del SO (recomendado)

`jornal schedule run` evalúa qué crons tocan **este minuto** y los despacha; arranca,
despacha en milisegundos y sale (stateless). Lo llamas cada minuto desde el crontab:

```cron
* * * * * cd /ruta/al/proyecto && /usr/bin/uv run python jornal schedule run
```

### B) `schedule work` (beat de Celery)

`jornal schedule work` arranca el beat (un proceso de larga duración que dispara los
crons). **Corre una sola instancia** (varios beats = crons duplicados):

```bash
uv run python jornal schedule work
```

> Arrancar el beat **sí dispara crons** según el `environments` de cada uno. En dev
> normalmente no lo corres: pruebas un job a mano (`mi_job.delay()`).

En ambos casos, el worker (`jornal queue work`) es quien **ejecuta** el job despachado.

## Los guards (en orden)

Cuando un cron se ejecuta, la wrapper aplica:

1. **Entorno** — si `environments` no está vacío y `APP_ENV` no está en la lista, se
   omite (loguea y retorna sin ejecutar).
2. **Logs** — si hay `output`, los logs de la corrida van a `logs/cron_<output>.log`.
3. **Lock** — si `without_overlapping`, toma un lock Redis `cron-lock:<name>`; si ya está
   tomado (la corrida anterior sigue), se omite.

### El invariante del lock

`lock_timeout` debe ser **mayor** que `redis_visibility_timeout`. Si fueran iguales,
expirarían juntos: Redis re-entregaría la task y un segundo worker tomaría el lock recién
liberado → **doble ejecución**. Por eso el default es `visibility_timeout + 300s`, y si
pasas un `lock_timeout` menor o igual, **falla al decorar** (no en runtime).

## Flujo completo

```
1. @cron_task registra el cron (cadencia + guards).
2. crontab del SO: cada minuto → jornal schedule run
3. schedule run: ¿toca este minuto (croniter)?  ¿aplica el entorno?  → despacha a la cola
4. worker (queue work): ejecuta la wrapper (guards) → tu función
```

## Siguiente paso

[Localización (i18n)](13-localizacion-i18n.md).
