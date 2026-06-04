"""Runtime-config del shell (estilo milpa): lo que TODO surco inyecta en su template.

`window.__ENV` es lo que `NEXT_PUBLIC_*`/`VITE_*` no pueden dar sin rebuild: el
backend lo inyecta al SERVIR el shell, así que cambia por entorno/deploy en runtime.
Trae siempre `BASE_PATH` (el `root_path` ASGI) — la mitad RUNTIME del soporte
reverse-proxy bajo sub-ruta: el frontend deriva de ahí su basename, el registro del
SW y sus llamadas a la API (la mitad build-time es `ASSET_URL`).

Forma tradicional: cada controller copia su `_runtime_env_json` + contexto a mano.
Estilo milpa: `view("mi/shell", shell_context(request))` y listo — `extra` agrega
las claves propias del surco.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from starlette.requests import Request

from milpa.Core.Config import settings


def base_path(request: Request) -> str:
    """Prefijo del deploy (`root_path` ASGI): "" sirviendo en raíz; "/nombre-reverse"
    detrás de un reverse proxy con sub-ruta (uvicorn --root-path; el proxy stripea).
    Starlette lo trae en el scope de CADA request — runtime puro, sin setting propio."""
    return str(request.scope.get("root_path", "")).rstrip("/")


def runtime_env_json(request: Request, extra: Mapping[str, object] | None = None) -> str:
    """`window.__ENV` como JSON seguro para un `<script>` inline: se escapa `<` para
    que un valor malicioso/raro no pueda cerrar el tag (`</script>`). Base del
    framework: APP_NAME / APP_ENV / BASE_PATH; `extra` agrega (o sobrescribe) las
    claves propias del surco."""
    runtime_env: dict[str, object] = {
        "APP_NAME": settings.app_name,
        "APP_ENV": settings.app_env,
        "BASE_PATH": base_path(request),
        **(extra or {}),
    }
    return json.dumps(runtime_env, ensure_ascii=False).replace("<", "\\u003c")


def shell_context(request: Request, extra: Mapping[str, object] | None = None) -> dict[str, object]:
    """Contexto Jinja del shell de un surco: `env_json` (el `window.__ENV`) +
    `base_path` (para los href del propio template — manifest de la PWA, etc.).
    `extra` va al `__ENV`; claves extra del template se agregan con `{**...}`."""
    return {"env_json": runtime_env_json(request, extra), "base_path": base_path(request)}
