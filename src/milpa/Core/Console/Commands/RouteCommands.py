"""Command `route list`: lista las rutas HTTP montadas (= `php artisan route:list`).

Construye la app (auto-montaje de todos los módulos) y muestra método/path/nombre en una tabla
rich. Útil para ver de un vistazo qué endpoints expone el proyecto.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from starlette.routing import Route

from milpa.Core.Console import console_command


@console_command(name="list", group="route", help="Lista las rutas HTTP montadas. (≈ php artisan route:list)")
def route_list() -> None:
    from milpa.Core.Http.Http import create_app  # lazy: construir la app solo al ejecutar

    app = create_app()
    rows: list[tuple[str, str, str]] = []
    for route in app.routes:
        if isinstance(route, Route):  # APIRoute hereda de Route; los Mount (estáticos) se omiten
            methods = ",".join(sorted(route.methods)) if route.methods else ""
            rows.append((methods, route.path, route.name or ""))

    table = Table(title="Rutas HTTP", title_justify="left", header_style="bold")
    table.add_column("Método", style="cyan", no_wrap=True)
    table.add_column("Path")
    table.add_column("Nombre", style="dim")
    for methods, path, name in sorted(rows, key=lambda row: row[1]):
        table.add_row(methods, path, name)
    Console().print(table)
