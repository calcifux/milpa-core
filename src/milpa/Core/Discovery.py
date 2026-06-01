"""Localiza en disco la carpeta de un paquete (importable o pip-instalado) SIN
ejecutarlo, para descubrir recursos por-módulo (vistas, lang, static) sin recurrir
a aritmética de `__file__`/`parents[N]`.

Por qué existe: cuando milpa se instala como paquete, `Path(__file__).parents[N]`
apunta a site-packages, no al proyecto del usuario. `find_spec` resuelve la ruta REAL
del paquete configurado (p. ej. `settings.modules_package`), funcione en el repo o
instalado. Es la pieza que vuelve a milpa "consciente" de dónde vive el código del
usuario en vez de adivinarlo contando carpetas.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def package_dir(dotted: str) -> Path | None:
    """Carpeta en disco del paquete `dotted` (p. ej. "app.Modules"), o None si no
    existe o no es un paquete. No ejecuta el `__init__` del paquete (usa find_spec).
    """
    try:
        spec = importlib.util.find_spec(dotted)
    except ModuleNotFoundError, ValueError, ImportError:
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))
