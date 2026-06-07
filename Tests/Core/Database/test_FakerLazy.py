"""Tests del shim perezoso de Faker (defensa en profundidad, 2026-06-06).

`faker` es dependencia de DEV: en una instalación LIMPIA del wheel (sin dev-deps) un
import-en-duro de `faker` al cargar el módulo tronaría cualquier código que importe una
factory en runtime. El shim perezoso lo evita: importar el módulo es gratis; el error
accionable sale solo al USAR el faker. Cada test corre en SUBPROCESO bloqueando `faker`
antes de importar (simula el wheel sin dev-deps).
"""

from __future__ import annotations

import subprocess
import sys

# Bloquea `import faker` (None en sys.modules => ImportError), como si no estuviera instalado.
_BLOQUEA_FAKER = "import sys; sys.modules['faker'] = None; "


def test_importing_factories_without_faker_is_free() -> None:
    """Importar las factories del Demo NO requiere faker (el shim es perezoso)."""
    code = _BLOQUEA_FAKER + "import milpa.Modules.Demo.Factories.factories; print('libre')"

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "libre" in result.stdout


def test_using_faker_without_dependency_raises_the_actionable_error() -> None:
    """USARLO sin la dependencia sí truena — con la pista accionable, no el error pelón."""
    code = _BLOQUEA_FAKER + "from milpa.Core.Database.Faker import faker; faker.name()"

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode != 0
    assert "uv add faker" in result.stderr  # la instrucción, no solo "No module named"
