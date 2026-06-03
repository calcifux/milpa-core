"""Configuración global de pytest.

Redirige los logs de la suite a `logs/tests/` para que los tests NO escriban en el
`logs/app.log` real. Los tests ejercen el Mailer (incluido el driver `log`, que vuelca
el MIME completo), el TestClient de HTTP y los crons —todo eso loguea—, así que sin esto
contaminarían el log de la app.

Debe correr ANTES de que se instancie `settings` o se llame a `setup_logging()`: por eso
solo toca `os.environ` aquí arriba (pytest importa este conftest antes que los módulos de
test, que son los que importan la app). `logs/` ya está en `.gitignore`, así que
`logs/tests/` también queda ignorado.
"""

from __future__ import annotations

import os

os.environ.setdefault("LOG_DIR", "logs/tests")
