"""Commands `make ...`: scaffolding de archivos (= los `make:*` de artisan).

Generan un stub idiomático y se auto-montan por convención (no hay que registrarlos a mano).
Idempotente: NUNCA sobrescriben un archivo existente.
"""

from __future__ import annotations

from pathlib import Path

import typer

from milpa.Core.Config import settings
from milpa.Core.Console import console_command


def _app_dir() -> Path:
    """Raíz del código del USUARIO donde escribe `make:*` (cwd/app por default,
    configurable con APP_DIR). Se resuelve en CADA llamada → relativa al cwd donde el dev
    corre `jornal`, NO a la ubicación del paquete instalado (que es el bug que evita)."""
    return Path(settings.app_dir).resolve()


def _write(path: Path, content: str) -> None:
    """Escribe `content` en `path` si NO existe; si existe, aborta (no sobrescribe)."""
    if path.exists():
        typer.echo(f"✗ ya existe (no se sobrescribe): {path}")
        raise typer.Exit(code=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    typer.echo(f"✓ creado: {path}")


def controller_stub(name: str) -> str:
    """Stub de un controller class-based (estilo Spring)."""
    slug = name.lower()
    return (
        f'"""Controller {name} (se auto-monta por el Registry)."""\n\n'
        "from __future__ import annotations\n\n"
        "from milpa.Core.Http import Controller, Get\n\n\n"
        f'@Controller("/{slug}", tags=["{slug}"])\n'
        f"class {name}Controller:\n"
        '    @Get("/")\n'
        "    def index(self) -> dict[str, str]:\n"
        f'        return {{"controller": "{name}", "status": "ok"}}\n'
    )


def model_stub(name: str) -> str:
    """Stub de un modelo SQLAlchemy (con timestamps)."""
    table = f"{name.lower()}s"
    return (
        f'"""Modelo {name}."""\n\n'
        "from __future__ import annotations\n\n"
        "from sqlalchemy.orm import Mapped, mapped_column\n\n"
        "from milpa.Core.Database import Base, TimestampMixin\n\n\n"
        f"class {name}(TimestampMixin, Base):\n"
        f'    __tablename__ = "{table}"\n\n'
        "    id: Mapped[int] = mapped_column(primary_key=True)\n"
        "    # TODO: agrega tus columnas, p. ej.:\n"
        '    # name: Mapped[str] = mapped_column(default="")\n'
    )


@console_command(
    name="controller", group="make", help="Crea un controller class-based en un módulo. (≈ php artisan make:controller)"
)
def make_controller(module: str, name: str) -> None:
    _write(_app_dir() / "Modules" / module / "Http" / f"{name}Controller.py", controller_stub(name))


@console_command(name="model", group="make", help="Crea un modelo SQLAlchemy en app/Models. (≈ php artisan make:model)")
def make_model(name: str) -> None:
    _write(_app_dir() / "Models" / f"{name}.py", model_stub(name))


@console_command(name="module", group="make", help="Crea el esqueleto de un módulo (paquete + Http + controller).")
def make_module(name: str) -> None:
    base = _app_dir() / "Modules" / name
    _write(base / "__init__.py", f'"""Módulo {name}."""\n')
    _write(base / "Http" / "__init__.py", '"""Controllers del módulo (se auto-montan)."""\n')
    _write(base / "Http" / f"{name}Controller.py", controller_stub(name))
