# Logging

milpa usa **Loguru**. El logging se configura al arrancar (HTTP y Celery), de forma que
worker, beat y API escriban igual. Celery **no** secuestra el root logger: Loguru lo
maneja.

## Usar el logger

```python
from loguru import logger

logger.info("Procesando pedido {id}", id=pedido_id)
logger.warning("Reintento {n}/{max}", n=intento, max=3)
logger.error("Falló el PAC: {body}", body=respuesta)
```

Usa el estilo de Loguru (`{campo}` + kwargs), no f-strings, para que los campos queden
estructurados.

## Configuración

| Setting | Default | Para qué |
|---------|---------|----------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_JSON` | `false` | `true` añade salida **JSON Lines** en `logs/app.jsonl`. |
| `LOG_DIR` | `logs` | Directorio de logs. |

```bash
LOG_LEVEL=DEBUG
LOG_JSON=true        # para ingestión en Loki/Grafana, Datadog, etc.
```

Con `LOG_JSON=true`, además de la consola/archivo legible, cada línea se escribe como un
objeto JSON por evento (apto para parseo automático).

## Logs por cron (`output=`)

Un `@cron_task(output="reminders")` rutea los logs de **esa** corrida a un archivo
propio con rotación diaria y retención: `logs/cron_reminders.log`. Así separas la salida
de cada cron sin mezclarla con el log general. Ver [Cron](12-programacion-cron.md).

## Dónde salen los logs

- **`jornal serve`** (API): consola + `logs/`.
- **`jornal queue work`** (worker): la salida de las tasks sale en la terminal del worker
  y en `logs/`.
- **Crons con `output`**: además, su archivo dedicado `logs/cron_<output>.log`.

El directorio `logs/` está en `.gitignore` (no se versiona).

## Siguiente paso

[Autenticación](15-autenticacion.md).
