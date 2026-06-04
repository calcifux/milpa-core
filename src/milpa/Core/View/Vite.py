"""Integración Vite (estilo milpa): el `laravel-vite-plugin` + directiva `@vite` de milpa.

milpa es DUEÑO del shell HTML (Jinja) y Vite del pipeline de assets del frontend:
HMR en dev, chunks hasheados en prod. Cómo decide el modo (modelo Laravel, verificado
contra laravel.com/docs/12.x/vite y vite.dev/guide/backend-integration):

  • DEV  — existe el HOT-FILE de la app: lo escribe su dev server de Vite al arrancar
    (plugin `vite-plugin-milpa` del frontend) y lo borra al apagarse. El archivo
    CONTIENE la URL del dev server (p. ej. "http://localhost:5173"). `vite()` emite
    `<script type="module">` apuntando ahí: la página la sirve milpa y los módulos
    (con HMR) los sirve Vite — el navegador habla con ambos puertos.

  • PROD — no hay hot-file: `vite()` lee `dist/.vite/manifest.json` (build.manifest)
    y emite `<link rel="stylesheet">` + `<script type="module">` hasheados, servidos
    por milpa (mounts opt-in en Core/Http/Http.py).

MICROFRONTENDS por vertical (multi-app): cada equipo tiene SU app Vite en
`<VITE_APPS_DIR>/<app>/` — con la TECNOLOGÍA que quiera (React/Vue/Svelte/vanilla;
Vite las cubre todas) — y milpa la sirve en `<VITE_ASSETS_URL>/<app>`. La detección
es por convención: una carpeta es "app" si tiene `hot` (dev corriendo) o
`dist/.vite/manifest.json` (build hecho). Hot-file POR app: un equipo puede estar
en dev con HMR mientras los demás corren su build, sin estorbarse.

Forma tradicional vs estilo milpa: la forma tradicional corre cada SPA en su propio
servidor y abre CORS (config congelada en build-time); estilo milpa el backend sirve
los shells — mismo origen, cero CORS — e inyecta runtime-config (`window.__ENV`).

Todo es OPT-IN: sin apps detectadas (ni VITE_DIST_DIR explícito) la feature muere
en paz — no se monta nada — y `vite()` en un template truena con instrucción clara
(tenet: nunca fallar en silencio).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from markupsafe import Markup, escape

from milpa.Core.Config import settings

# Nombre interno del modo una-sola-app explícito (VITE_DIST_DIR): se monta en la
# raíz de VITE_ASSETS_URL, sin sub-ruta por app.
_EXPLICIT = ""

# Cache del manifest por ruta, invalidado por (mtime_ns, size): se relee solo si
# hubo rebuild. NO basta st_mtime (float en segundos): en filesystems con mtime de
# resolución gruesa, dos builds dentro del mismo segundo serían invisibles.
_manifest_cache: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


def resolve_apps() -> dict[str, Path]:
    """Apps frontend disponibles: {nombre: ruta_del_build}.

    Prioridad: `VITE_DIST_DIR` explícito (modo una-sola-app, estilo Laravel con el
    frontend en la raíz del proyecto) → {"": dist}. Si no, AUTO-DETECCIÓN doble
    (modelo Laravel: fuentes en `VITE_APPS_DIR`, builds en `VITE_PUBLIC_DIR`):
      • CONSTRUIDA — `public/<app>/.vite/manifest.json` existe (vite build ya corrió).
      • EN DEV     — `<apps_dir>/<app>/hot` existe (su dev server está corriendo),
        aunque nunca se haya buildeado (primer `npm run dev` recién clonado).
    Sin nada detectado → {} y la feature muere en paz (sin mounts; vite() instruye).
    """
    if settings.vite_dist_dir:
        return {_EXPLICIT: Path(settings.vite_dist_dir)}
    apps: dict[str, Path] = {}
    # Guard de vacío en AMBOS roots: Path("") es Path(".") y siempre is_dir() — sin
    # él, VITE_PUBLIC_DIR=/VITE_APPS_DIR= escanearían el cwd del proyecto (apps
    # fantasma). Vacío = apagado, el mismo idioma que el mount en Core/Http.
    public_root = Path(settings.vite_public_dir)
    if settings.vite_public_dir and public_root.is_dir():
        for candidate in sorted(public_root.iterdir()):
            if (candidate / ".vite" / "manifest.json").is_file():
                apps[candidate.name] = candidate
    apps_root = Path(settings.vite_apps_dir)
    if settings.vite_apps_dir and apps_root.is_dir():
        for candidate in sorted(apps_root.iterdir()):
            if candidate.name not in apps and (candidate / "hot").is_file():
                apps[candidate.name] = public_root / candidate.name
    return apps


def _app_dist(app: str | None) -> tuple[str, Path]:
    """Resuelve (nombre, dist) de la app pedida; con `app=None` aplica el default:
    la ÚNICA app disponible. Ambigüedad o ausencia truenan con instrucción."""
    apps = resolve_apps()
    if not apps:
        raise RuntimeError(
            f"No hay frontend Vite: ni apps detectadas en '{settings.vite_apps_dir}/' "
            "(VITE_APPS_DIR; una app = carpeta con `hot` o `dist/.vite/manifest.json`) "
            "ni VITE_DIST_DIR configurado. Corre `npm run dev`/`npm run build` en tu app "
            "— o quita vite() del template."
        )
    if app is None:
        if len(apps) > 1:
            disponibles = ", ".join(sorted(name or "(explícita)" for name in apps))
            raise RuntimeError(
                f"Hay varias apps Vite ({disponibles}): indica cuál — vite('src/main.jsx', app='<nombre>')."
            )
        return next(iter(apps.items()))
    if app not in apps:
        disponibles = ", ".join(sorted(name or "(explícita)" for name in apps)) or "ninguna"
        raise RuntimeError(f"No existe la app Vite '{app}' (disponibles: {disponibles}).")
    return app, apps[app]


def _assets_base(app_name: str) -> str:
    """URL pública de los assets de la app: la raíz de VITE_ASSETS_URL para el modo
    explícito; namespaced `/<assets_url>/<app>` para las apps de la carpeta (mismo
    esquema que los estáticos por módulo del backend). ASSET_URL (si está) se
    ANTEPONE — deploy bajo sub-ruta de reverse proxy o CDN (= ASSET_URL de Laravel;
    el mismo env var alimenta el `base` del build vía vite-plugin-milpa)."""
    root = settings.asset_url.rstrip("/") + settings.vite_assets_url.rstrip("/")
    return root if app_name == _EXPLICIT else f"{root}/{app_name}"


def _hot_file(app_name: str, dist_dir: Path) -> Path:
    """Hot-file de la app: vive con sus FUENTES (`<apps_dir>/<app>/hot` — lo escribe
    su dev server vía vite-plugin-milpa), no con el build. `VITE_HOT_FILE` lo
    overridea SOLO en modo una-sola-app (con varias apps sería ambiguo)."""
    if app_name == _EXPLICIT:
        if settings.vite_hot_file:
            return Path(settings.vite_hot_file)
        return dist_dir.parent / "hot"
    return Path(settings.vite_apps_dir) / app_name / "hot"


def _dev_server_url(app_name: str, dist_dir: Path) -> str | None:
    """URL del dev server si la app está en dev (existe su hot-file); si no, None."""
    hot = _hot_file(app_name, dist_dir)
    if not hot.is_file():
        return None
    url = hot.read_text(encoding="utf-8").strip().rstrip("/")
    return url or None


def _load_manifest(dist_dir: Path) -> dict[str, Any]:
    """Lee (con cache por mtime) el `.vite/manifest.json` del build."""
    manifest_path = dist_dir / ".vite" / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(
            f"No existe el manifest de Vite en {manifest_path}. Corre `npm run build` en el "
            "frontend (modo prod) o levanta `npm run dev` (modo dev vía hot-file)."
        )
    stat = manifest_path.stat()
    fingerprint = (stat.st_mtime_ns, stat.st_size)
    cached = _manifest_cache.get(str(manifest_path))
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    manifest = cast("dict[str, Any]", json.loads(manifest_path.read_text(encoding="utf-8")))
    _manifest_cache[str(manifest_path)] = (fingerprint, manifest)
    return manifest


def _entry_tags(manifest: dict[str, Any], entry: str, base: str, seen_css: set[str]) -> list[str]:
    """Tags de UN entry en prod, en el orden que documenta vite.dev/backend-integration:
    el CSS del chunk, luego el CSS de sus `imports` estáticos (recursivo), y al final
    el `<script type="module">` del entry. `seen_css` lo comparte el caller entre
    entries: el CSS de un chunk compartido se emite UNA sola vez (como `@vite`)."""
    chunk = manifest.get(entry)
    if chunk is None:
        available = ", ".join(sorted(name for name, data in manifest.items() if data.get("isEntry"))) or "ninguno"
        raise RuntimeError(
            f"El entry '{entry}' no está en el manifest de Vite (entries disponibles: {available}). "
            "Revisa build.rollupOptions.input en el vite.config del frontend."
        )
    tags: list[str] = []

    def collect_css(name: str, visited: set[str]) -> None:
        if name in visited:
            return
        visited.add(name)
        node: dict[str, Any] = manifest.get(name) or {}
        for css_file in node.get("css", []):
            if css_file not in seen_css:
                seen_css.add(css_file)
                tags.append(f'<link rel="stylesheet" href="{base}/{escape(css_file)}">')
        for imported in node.get("imports", []):
            collect_css(imported, visited)

    collect_css(entry, set())
    tags.append(f'<script type="module" src="{base}/{escape(chunk["file"])}"></script>')
    return tags


def vite(*entries: str, app: str | None = None) -> Markup:
    """La directiva `@vite` de milpa — uso: `{{ vite('src/main.jsx') }}` con una sola
    app, o `{{ vite('src/main.jsx', app='tienda') }}` en multi-app (microfrontends).

    DEV (hot-file de la app): inyecta el cliente HMR de Vite + cada entry desde SU
    dev server. PROD: inyecta los `<link>`/`<script>` hasheados de SU manifest.
    Devuelve `Markup` (HTML confiable generado aquí): el autoescape no lo toca.
    """
    app_name, dist_dir = _app_dist(app)
    dev_url = _dev_server_url(app_name, dist_dir)
    if dev_url:
        tags = [f'<script type="module" src="{escape(dev_url)}/@vite/client"></script>']
        tags.extend(
            f'<script type="module" src="{escape(dev_url)}/{escape(entry.lstrip("/"))}"></script>' for entry in entries
        )
        return Markup("\n".join(tags))
    manifest = _load_manifest(dist_dir)
    base = _assets_base(app_name)
    prod_tags: list[str] = []
    seen_css: set[str] = set()
    for entry in entries:
        prod_tags.extend(_entry_tags(manifest, entry, base, seen_css))
    return Markup("\n".join(prod_tags))


def vite_asset(path: str, app: str | None = None) -> str:
    """URL pública de un archivo de `public/` de la app (iconos, manifest.webmanifest…):
    esos NO pasan por el manifest de Vite (van sin hash) — solo se namespacean.
    `{{ vite_asset('icons/icon-192.png') }}` → "/vite/demo-spa/icons/icon-192.png".

    Ramifica dev/prod IGUAL que vite(): en DEV el public/ del surco lo sirve su dev
    server desde la raíz (el build — y el mount de milpa — pueden no existir aún);
    sin la rama, en dev saldría la URL del mount → 404 silencioso."""
    app_name, dist_dir = _app_dist(app)
    dev_url = _dev_server_url(app_name, dist_dir)
    if dev_url:
        return f"{dev_url}/{path.lstrip('/')}"
    return f"{_assets_base(app_name)}/{path.lstrip('/')}"


def vite_react_refresh(app: str | None = None) -> Markup:
    """Preámbulo de react-refresh (= `@viteReactRefresh` de Laravel): va ANTES de
    `vite()` en el `<head>`. Solo emite en DEV; en prod es no-op (cadena vacía).
    Solo aplica a apps React — una app Vue/Svelte simplemente no lo llama."""
    app_name, dist_dir = _app_dist(app)
    dev_url = _dev_server_url(app_name, dist_dir)
    if dev_url is None:
        return Markup("")
    return Markup(
        f"""<script type="module">
    import RefreshRuntime from '{escape(dev_url)}/@react-refresh'
    RefreshRuntime.injectIntoGlobalHook(window)
    window.$RefreshReg$ = () => {{}}
    window.$RefreshSig$ = () => (type) => type
    window.__vite_plugin_react_preamble_installed__ = true
</script>"""
    )
