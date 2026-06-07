"""Kernel de consola — arma la app de Typer (≈ app/Console/Kernel.php de Laravel).

NO es el entrypoint: ese es `jornal` (en la RAÍZ), que solo hace
`from milpa.Core.Console.Cli import run; run()`. Aquí vive la lógica: descubre los
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
from loguru import logger
from rich.console import Console

from milpa.Core.Config import settings
from milpa.Core.Console import build_command_table, import_submodules
from milpa.Core.Errors import DomainError
from milpa.Core.Logging import setup_logging
from milpa.Core.Registry import iter_cli_apps

# pretty_exceptions_enable=False: NOSOTROS controlamos el render de errores (ver `run`), para no
# escupir el traceback crudo de Typer/Rich (con locals) ante un error esperado de dominio.
app = typer.Typer(
    help=f"{settings.app_name} — comandos de consola (milpa 🌽).",
    pretty_exceptions_enable=False,
)


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
    En modo `--factory` uvicorn llama a `create_app()`; el string permite `--reload`.
    Si ASSET_URL es una RUTA (deploy bajo sub-ruta de reverse proxy), viaja
    también como root_path ASGI: el MISMO `jornal serve` funciona con y sin
    proxy, sin flags — una sola variable configurada (un CDN https:// no es
    prefijo del deploy: root raíz, como siempre)."""
    import uvicorn

    prefix = settings.asset_url if settings.asset_url.startswith("/") else ""
    uvicorn.run(
        "milpa.Core.Http.Http:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        root_path=prefix.rstrip("/"),
    )


@app.command(name="new", help="Crea un proyecto nuevo de milpa desde una plantilla. (≈ laravel new).")
def new(
    name: str = typer.Argument(..., help="Nombre del proyecto (carpeta a crear en el dir actual)."),
    demo: bool = typer.Option(
        False,
        "--demo",
        "--full-demo",
        help="Incluye los módulos de ejemplo (users/notes + RBAC/ABAC + HTMX + correos + factories/seeders): "
        "starter kit y referencia viva de cómo funciona todo.",
    ),
) -> None:
    """Genera un proyecto LISTO para correr: app/ (con un módulo Hello de ejemplo), jornal,
    .env y migrations/, con la config apuntando a TU código (MODULES_PACKAGE=app.Modules…).

    Con `--demo` copia además el módulo Demo (el sistema completo de referencia)."""
    from milpa.Core.Console.Scaffold import new_project

    console = Console()
    try:
        dest = new_project(name, demo=demo)
    except FileExistsError as error:
        console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]✓[/green] Proyecto creado en [bold]{dest}[/bold] 🌽\n")
    console.print("Siguientes pasos:")
    console.print(f"  [cyan]cd {name}[/cyan]")
    console.print("  [cyan]uv sync[/cyan]                 # instala milpa + dependencias")
    if demo:
        console.print("  [cyan]python jornal migrate make -m inicial && python jornal migrate run[/cyan]")
        console.print("  [cyan]python jornal db seed[/cyan]   # puebla users/notes (DemoSeeder)")
        console.print(
            "  [cyan]python jornal serve[/cyan]     # http://127.0.0.1:8000  (/, /hello, /dashboard, /api/...)"
        )
        console.print("\n[dim]El módulo Demo (auth/RBAC) usa JWT_SECRET/SESSION_SECRET: genéralos en .env.[/dim]")
    else:
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


def _render_cli_error(error: BaseException) -> int:
    """Renderiza un error del CLI y devuelve el exit code. Simétrico al handler HTTP RFC 9457:
    un `DomainError` (esperado) sale como mensaje LIMPIO + su código, SIN traceback; uno inesperado
    (bug) sale conciso en stdout, y su traceback COMPLETO al log vía loguru (observable a las 3am;
    con valores solo en dev, ver setup_logging). Nada se traga: todo error deja rastro."""
    console = Console()
    if isinstance(error, DomainError):
        console.print(f"[red]✗[/red] {error.message} [dim]({error.error_code})[/dim]")
        return 1
    logger.opt(exception=True).error("CLI | error inesperado ({t})", t=type(error).__name__)
    console.print(f"[red]✗[/red] Error interno ({type(error).__name__}). El detalle quedó en el log.")
    return 1


def run() -> None:
    """Entrypoint del CLI (lo llaman el launcher `jornal` y el script `milpa`). Envuelve `app()`
    con el borde de error: sin esto, cualquier error escupía el traceback crudo de Typer en consola."""
    setup_logging()  # sinks configurados (stderr concisa sin fuga de valores en prod + archivo)
    try:
        app()
    except DomainError as error:
        raise SystemExit(_render_cli_error(error)) from None
    except Exception as error:  # noqa: BLE001 — borde final del CLI: nada escapa sin loguearse
        raise SystemExit(_render_cli_error(error)) from None


if __name__ == "__main__":
    run()
