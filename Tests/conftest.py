"""Configuración global de pytest.

Redirige los logs de la suite a `logs/tests/` para que los tests NO escriban en el
`logs/app.log` real. Los tests ejercen el Mailer (incluido el driver `log`, que vuelca
el MIME completo), el TestClient de HTTP y los crons —todo eso loguea—, así que sin esto
contaminarían el log de la app.

También re-apunta los paquetes del USUARIO (modules/models/commands) al paquete del propio
framework: los defaults de Settings apuntan a `app.*` (el layout de `milpa new`) para que una
instalación sin .env NO auto-descubra el Demo empaquetado, pero el dev del framework trabaja
DENTRO de este repo (su código vive en src/milpa). Sin esto la suite dejaría de descubrir el
Demo (test_WorkerTaskDiscovery, Tests/Modules/Demo/*, etc.) y los tests cambiarían de
comportamiento — mismo patrón que el LOG_DIR.

Debe correr ANTES de que se instancie `settings` o se llame a `setup_logging()`: por eso
solo toca `os.environ` aquí arriba (pytest importa este conftest antes que los módulos de
test, que son los que importan la app). `logs/` ya está en `.gitignore`, así que
`logs/tests/` también queda ignorado.
"""

from __future__ import annotations

import os

os.environ.setdefault("LOG_DIR", "logs/tests")
# setdefault: si el dev ya exportó otro paquete, se respeta.
os.environ.setdefault("MODULES_PACKAGE", "milpa.Modules")
os.environ.setdefault("MODELS_PACKAGE", "milpa.Models")
os.environ.setdefault("APP_COMMANDS_PACKAGE", "milpa.Console.Commands")
