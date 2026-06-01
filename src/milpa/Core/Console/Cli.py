"""Kernel de consola — arma la app de Typer (≈ app/Console/Kernel.php de Laravel).

NO es el entrypoint: ese es `jornal` (en la RAÍZ), que solo hace
`from milpa.Core.Console.Cli import milpa; app()`. Aquí vive la lógica: descubre los
commands (Core + generales + módulos) y los monta como sub-apps de Typer. No
declara commands hardcodeados; se auto-descubren (`@console_command` + discovery),
así que agregar uno nuevo es solo crear su archivo — este módulo no se vuelve a editar.

Uso (vía el launcher `jornal` de la raíz):
    uv run python jornal list                  # ve todos los comandos
    uv run python jornal serve                 # levanta la API (= artisan serve)
    uv run python jornal queue work            # arranca el worker de Celery

Vive en CORE (framework): NO importa Modules de forma estática — el discovery es
DINÁMICO (`import_submodules` + `iter_cli_apps`), igual que el kernel web. Por eso
puede vivir en Core sin romper "Core ↛ Modules" (que es sobre imports estáticos).
"""

from __future__ import annotations

import typer
from rich.console import Console

from milpa.Core.Config import settings
from milpa.Core.Console import build_command_table, import_submodules
from milpa.Core.Registry import iter_cli_apps

app = typer.Typer(help=f"{settings.app_name} — comandos de consola (milpa 🌽).")


@app.callback()
def main() -> None:
    """Sin esto, Typer colapsa la app de un solo comando y no exige el nombre
    del subcomando. El callback la fuerza a modo "grupo" (estilo artisan), para
    que se invoque siempre como `<grupo> <command>` y soporte más comandos después.
    """


@app.command(name="list", help="Lista todos los comandos disponibles. (≈ php artisan list)")
def list_commands() -> None:
    """El `--help` de la raíz solo muestra los grupos; esto lista TODO (comandos raíz como
    `serve`/`list` + cada `<grupo> <command>`) con su ayuda, en tabla rich coloreada."""
    general = sorted((command.name or "", command.help or "") for command in app.registered_commands if command.name)
    Console().print(build_command_table(general))


@app.command(name="serve", help="Levanta el servidor web (uvicorn). (≈ php artisan serve)")
def serve(
    host: str = typer.Option("127.0.0.1", help="Host de escucha."),
    port: int = typer.Option(settings.app_port, help="Puerto (default: APP_PORT)."),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Auto-recarga en cambios (dev)."),
) -> None:
    """Arranca FastAPI con uvicorn usando la app factory del kernel web (Core).
    En modo `--factory` uvicorn llama a `create_app()`; el string permite `--reload`."""
    import uvicorn

    uvicorn.run("milpa.Core.Http.Http:create_app", factory=True, host=host, port=port, reload=reload)


@app.command(name="new", help="Crea un proyecto nuevo de milpa desde una plantilla. (≈ laravel new).")
def new(
    name: str = typer.Argument(..., help="Nombre del proyecto (carpeta a crear en el dir actual)."),
) -> None:
    """Genera un proyecto LISTO para correr: app/ (con un módulo Hello de ejemplo), jornal,
    .env y migrations/, con la config apuntando a TU código (MODULES_PACKAGE=app.Modules…)."""
    from milpa.Core.Console.Scaffold import new_project

    console = Console()
    try:
        dest = new_project(name)
    except FileExistsError as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]✓[/green] Proyecto creado en [bold]{dest}[/bold] 🌽\n")
    console.print("Siguientes pasos:")
    console.print(f"  [cyan]cd {name}[/cyan]")
    console.print("  [cyan]uv sync[/cyan]                 # instala milpa + dependencias")
    console.print("  [cyan]python jornal serve[/cyan]     # http://127.0.0.1:8000  (prueba / y /hello)")


# Dispara los decoradores de los commands del FRAMEWORK (Core) —p. ej. `queue
# work` y `schedule work`— y de los commands GENERALES del proyecto (app-level).
# El discovery importa cada archivo y, al importarse, sus `@console_command` se
# registran. Debe ir ANTES del loop para que ya estén en el registro cuando
# `iter_cli_apps` arme los grupos.
import_submodules("milpa.Core.Console.Commands")
import_submodules(settings.app_commands_package)

# Monta cada grupo descubierto (módulos activos + generales) como sub-app de
# Typer. Así el CLI no necesita saber qué commands existen: solo los enchufa.
for group, sub_app in iter_cli_apps():
    app.add_typer(sub_app, name=group)


if __name__ == "__main__":
    app()
