"""PWA sobre el build Vite (estilo milpa): manifest y Service Worker sin boilerplate.

Forma tradicional: cada app copia ~40 líneas (manifest hardcodeado que truena tras un
reverse proxy + la ruta del sw.js a mano). Estilo milpa: DOS one-liners en el
controller —

    @Get("/manifest.webmanifest")
    def manifest(self, request: Request) -> Response:
        return Pwa.webmanifest(request, prefix="/spa", app="mi-app", theme_color="#...", background_color="#...")

    @Get("/sw.js")
    def sw(self) -> FileResponse:
        return Pwa.service_worker(app="mi-app")

— y el framework arma el resto EN RUNTIME: `start_url`/`scope` con el prefijo real
del deploy (root_path; bajo sub-ruta de proxy salen correctos sin rebuild) e iconos
AUTO-DESCUBIERTOS del build por convención: `icons/icon-<size>.png` y
`icons/icon-<size>-maskable.png` (archivo APARTE con safe-zone — Android recorta los
maskable; reusar el normal pierde las orillas). Las URLs usan la misma base que
`vite_asset()` (dev server en DEV; con `ASSET_URL` heredado en PROD).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from fastapi.responses import FileResponse, Response
from starlette.requests import Request

from milpa.Core.Config import settings
from milpa.Core.Errors import ResourceNotFoundError

# Helpers internos del hermano Vite (misma capa Core/View): resolución de la app,
# namespacing de assets y detección de dev. _app_dist truena con instrucción si no
# hay apps o hay ambigüedad.
from milpa.Core.View.Vite import _app_dist, _assets_base, _dev_server_url

# icons/icon-192.png · icons/icon-512-maskable.png → (192, maskable?)
_ICON_RE = re.compile(r"^icon-(\d+)(-maskable)?\.png$")


def _discover_icons(app_name: str, dist_dir: Path) -> list[dict[str, str]]:
    """Iconos del manifest por CONVENCIÓN: en PROD se leen del build (`<dist>/icons/`);
    en DEV sin build todavía, de la FUENTE del surco (`<apps_dir>/<app>/public/icons/`,
    que su dev server sirve desde la raíz — sin esto el manifest saldría con
    `icons: []` durante todo el flujo dev). Los normales primero, luego los maskable
    (con su `purpose`). Sin carpeta o sin matches → lista vacía (un manifest sin
    iconos es legal; el navegador lo avisa). La base de las URLs se resuelve UNA vez
    — no un re-escaneo de apps por icono."""
    dev_url = _dev_server_url(app_name, dist_dir)
    icons_dir = dist_dir / "icons"
    if not icons_dir.is_dir() and app_name and dev_url:
        icons_dir = Path(settings.vite_apps_dir) / app_name / "public" / "icons"
    if not icons_dir.is_dir():
        return []
    base = dev_url or _assets_base(app_name)
    icons: list[dict[str, str]] = []
    for icon_file in sorted(icons_dir.iterdir(), key=lambda f: (("-maskable" in f.name), f.name)):
        match = _ICON_RE.match(icon_file.name)
        if match is None:
            continue
        size, maskable = match.group(1), match.group(2)
        entry = {
            "src": f"{base}/icons/{icon_file.name}",
            "sizes": f"{size}x{size}",
            "type": "image/png",
        }
        if maskable:
            entry["purpose"] = "maskable"
        icons.append(entry)
    return icons


def webmanifest(
    request: Request,
    *,
    prefix: str,
    theme_color: str,
    background_color: str,
    app: str | None = None,
    name: str | None = None,
    short_name: str | None = None,
    description: str = "",
    display: str = "standalone",
    extra: Mapping[str, object] | None = None,
) -> Response:
    """El manifest de la PWA, armado EN RUNTIME (por eso lo sirve el backend y no es
    un estático del frontend): `start_url`/`scope` llevan el prefijo real del deploy
    (start_url DEBE caer dentro de scope — MDN) y los iconos salen del build por
    convención. `extra` agrega/sobrescribe claves (p. ej. orientation, shortcuts)."""
    app_name, dist_dir = _app_dist(app)
    # Prefijo del deploy (root_path ASGI) — misma línea que Core/Http/Shell.base_path;
    # se calcula aquí para no acoplar Core/View con Core/Http.
    base = str(request.scope.get("root_path", "")).rstrip("/")
    prefix = "/" + prefix.strip("/")
    label = app_name or settings.app_name
    manifest: dict[str, object] = {
        "name": name or (f"{app_name} · {settings.app_name}" if app_name else settings.app_name),
        "short_name": short_name or label,
        "description": description,
        # Barra final TAMBIÉN en start_url: el algoritmo in-scope del W3C compara
        # prefijos de RUTA, y '/spa' NO empieza con '/spa/' — sin la barra, start_url
        # queda fuera de scope y el navegador DESCARTA el scope (cayendo a uno más
        # ancho que ya no acota la PWA a su prefijo).
        "start_url": f"{base}{prefix}/",
        "scope": f"{base}{prefix}/",
        "display": display,
        "background_color": background_color,
        "theme_color": theme_color,
        "icons": _discover_icons(app_name, dist_dir),
        **(extra or {}),
    }
    return Response(json.dumps(manifest, ensure_ascii=False), media_type="application/manifest+json")


def service_worker(app: str | None = None, *, filename: str = "sw.js") -> FileResponse:
    """El Service Worker compilado (`<dist>/sw.js`), con el `no-cache` OBLIGATORIO:
    un SW cacheado = updates que nunca llegan (el navegador revalida byte a byte
    contra esta respuesta). Sírvelo desde el prefijo del surco (p. ej. `/spa/sw.js`)
    para que su scope cubra a la app — y declara la ruta ANTES del catch-all."""
    _app_name, dist_dir = _app_dist(app)
    sw_file = dist_dir / filename
    if not sw_file.is_file():
        raise ResourceNotFoundError(f"No hay {filename} en el build de Vite (corre `npm run build` en el frontend).")
    return FileResponse(
        sw_file,
        media_type="text/javascript",
        headers={"Cache-Control": "no-cache"},
    )
