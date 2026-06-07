# Consola (`jornal`)

`jornal` es el "artisan" de milpa: el entrypoint de consola, en la raíz del proyecto.
Es un launcher fino; el kernel real vive en `milpa/Core/Console`.

```bash
uv run python jornal list             # lista TODOS los comandos (= php artisan list)
uv run python jornal --help           # ayuda de Typer (grupos)
./jornal list                         # si el venv está activo
```

## Comandos incluidos

| Comando | Qué hace | Equivalente Laravel |
|---------|----------|---------------------|
| `jornal list` | Lista todos los comandos agrupados, con su ayuda. | `php artisan list` |
| `jornal serve` | Levanta la API (uvicorn factory). Opciones `--host`, `--port`, `--reload/--no-reload`, `--workers`. | `php artisan serve` |
| `jornal queue work` | Arranca el worker de Celery. Opciones `--queue`, `--concurrency`, `--loglevel`. | `php artisan queue:work` |
| `jornal schedule work` | Arranca el beat (scheduler). Una sola instancia. Opción `--schedule-file`. | (Laravel scheduler) |
| `jornal schedule run` | Despacha los crons que tocan este minuto. Lo llama el crontab del SO. | `php artisan schedule:run` |

```bash
uv run python jornal serve --port 9000 --no-reload
uv run python jornal serve --workers 4               # prod: varios procesos (fuerza --no-reload)
uv run python jornal queue work --queue emails,reports --concurrency 8
```

### `serve --workers N` (varios procesos)

`--workers N` (entero, default `1`) corre la app en **N procesos** uvicorn —el modo de
prod—. Es **incompatible con `--reload`**: al pasar `workers>1`, milpa **fuerza
`--no-reload`** (con un aviso en consola). En `N=1` (el default) no se le pasa nada a
uvicorn por ese lado, así que el `--reload` de dev se respeta tal cual.

```bash
uv run python jornal serve --workers 4               # 4 procesos, sin recarga
uv run python jornal serve --workers 4 --reload      # el --reload se ignora (aviso)
```

### `schedule work --schedule-file <ruta>`

`schedule work` (el beat) persiste su calendario en un archivo de estado (`-s` de Celery);
el default es `./celerybeat-schedule` del **CWD**. En contenedores con el repo montado de
solo-lectura ese default **no se puede escribir**: apúntalo a un volumen escribible con
`--schedule-file`.

```bash
uv run python jornal schedule work --schedule-file /tmp/celerybeat-schedule
```

Ver [Colas y tareas](11-colas-y-tareas.md) y [Cron](12-programacion-cron.md) para
`queue work` / `schedule run/work`.

## Cómo funciona el descubrimiento

`jornal` solo hace `from milpa.Core.Console.Cli import app; app()`. Al importar `Cli.py`:

1. Se importan los comandos del framework (`milpa.Core.Console.Commands`) y los del
   proyecto a nivel app (`app.Console.Commands`) con `import_submodules(...)`.
2. Los decoradores `@console_command` se registran en un registro interno.
3. `iter_cli_apps()` (del Registry) importa los comandos de cada módulo y arma un
   `typer.Typer` por **grupo**, que se monta como sub-app.

No hay lista central de comandos: se auto-descubren por convención.

## Crear un comando

### En un módulo

Pon el archivo bajo `Modules/<X>/Console/Commands/`. El **grupo se deduce del módulo**
(`app.Modules.Billing...` → grupo `billing`):

```python
# app/Modules/Billing/Console/Commands/CloseCommand.py
import typer
from milpa.Core.Console import console_command

@console_command(name="close", help="Cierra el periodo contable.")
def close_period(period: str = typer.Option(..., "--period", help="YYYY-MM")) -> None:
    typer.echo(f"Cerrando {period}...")
```

Se invoca:

```bash
uv run python jornal billing close --period 2026-05
```

### A nivel de proyecto (sin módulo)

Pon el archivo bajo `app/Console/Commands/`. Aquí el grupo **no se puede deducir**, así
que es obligatorio pasarlo:

```python
# app/Console/Commands/DbSeedCommand.py
from milpa.Core.Console import console_command

@console_command(name="seed", group="db", help="Carga datos de ejemplo.")
def db_seed() -> None:
    ...
```

```bash
uv run python jornal db seed
```

## El decorador `console_command`

```python
def console_command(
    name: str,
    *,
    group: str | None = None,
    help: str | None = None,
    **typer_kwargs: Any,
) -> Callable[[Callable], Callable]
```

| Parámetro | Para qué |
|-----------|----------|
| `name` | Nombre del comando (ej. `"work"`, `"close"`). |
| `group` | Grupo. Si es `None`, se deduce del path del módulo; obligatorio fuera de un módulo. |
| `help` | Texto de ayuda (se ve en `--help` y en `jornal list`). |
| `**typer_kwargs` | Cualquier opción extra de Typer. |

> El decorador **no envuelve** la función: queda intacta y reutilizable (puedes
> llamarla directo en tests). El adaptador de Typer es fino. (Contrasta con
> `@cron_task`, que sí envuelve — ver [Cron](12-programacion-cron.md).)

Las opciones de cada comando son `typer.Option(...)` / `typer.Argument(...)` estándar.

## Siguiente paso

[Vistas](09-vistas.md).
