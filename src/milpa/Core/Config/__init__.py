"""Configuración de milpa: la clase (`Settings`) y el objeto único del proceso (`settings`).

`settings` se entrega al pedirlo y no al importar este paquete: tequio importa la clase de aquí
MIENTRAS arma ese objeto (ver `milpa.Core.TequioExtension`), así que todavía no existe en ese momento.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from milpa.Core.Config.Settings import Settings

if TYPE_CHECKING:
    settings: Settings

__all__ = ["Settings", "settings"]


def __getattr__(name: str) -> Any:
    """`from milpa.Core.Config import settings` = el MISMO objeto que lee tequio (uno por proceso)."""
    if name == "settings":
        from tequio.Core.Config import settings

        return settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
