"""Las funciones que milpa pone en TODAS las plantillas (las de la web; las de correo son de tequio).

El motor de plantillas es el de tequio (`tequio.Core.View.TemplateEngine`): uno solo para vistas y
correos. tequio pide estas funciones al armar cada motor (ver `milpa.Core.TequioExtension`), así que
están igual en el motor del proceso y en los que arman las pruebas con su propia carpeta.

OJO: este archivo se importa mientras tequio arma su motor. No importes aquí `milpa.Core.View` ni el
motor: cerrarías un ciclo con tequio a medio cargar.
"""

from __future__ import annotations

from typing import Any

from jinja2 import pass_context
from jinja2.runtime import Context
from markupsafe import Markup

from milpa.Core.Config import settings
from milpa.Core.View.Vite import assets_dev, vite, vite_asset, vite_react_refresh


def _asset(path: str) -> str:
    """URL de un estatico bajo /static (= asset() de Laravel). No hardcodear /static
    en los templates: `{{ asset('welcome.css') }}` -> "/static/welcome.css". ASSET_URL
    (si esta configurado) se antepone — deploy bajo sub-ruta de proxy o CDN."""
    return f"{settings.asset_url.rstrip('/')}/static/{path.lstrip('/')}"


@pass_context
def _env_script(context: Context) -> Markup:
    """`{{ env_script() }}` — el `<script>window.__ENV = {...}</script>` del shell,
    SIN boilerplate ni `| safe` a mano: toma `env_json` del contexto (lo pone
    `shell_context(request)` de Core/Http/Shell) y emite el tag completo. Es seguro
    como Markup porque el JSON ya viene con `<` escapado desde el Core (un valor
    malicioso no puede cerrar el tag). Ponlo en el <body> ANTES de `vite()`: corre
    primero que los modulos (los <script type="module"> son deferred por spec), asi
    window.__ENV ya existe cuando el frontend monta."""
    env_json = context.get("env_json")
    # `not` (no `is None`): un env_json="" pasaría el guard y emitiría
    # `window.__ENV = ;` — SyntaxError en el navegador en vez de instrucción clara.
    if not env_json:
        raise RuntimeError(
            "env_script() necesita `env_json` en el contexto del template: renderiza el shell con "
            "view('tu/shell', shell_context(request)) — Core/Http/Shell."
        )
    # con el nonce de CSP de esta request (shell_context lo trae), la política no lo reporta y en enforcing corre
    nonce = _csp_nonce(context)
    nonce_attribute = Markup(' nonce="{}"').format(nonce) if nonce else ""
    return Markup(f"<script{nonce_attribute}>window.__ENV = {env_json};</script>")


@pass_context
def _csp_nonce(context: Context) -> str:
    """`{{ csp_nonce() }}` — el nonce de CSP de esta request, para un `<script>` propio pegado en el template:
    `<script nonce="{{ csp_nonce() }}">…</script>`. Lo trae `shell_context(request)` (csp_nonce_value); sin él, ""."""
    return str(context.get("csp_nonce_value") or "")


def web_template_globals() -> dict[str, Any]:
    """Nombre en la plantilla → función."""
    return {
        # `asset()` (= asset() de Laravel): la URL de un estatico servido bajo /static, para CSS/JS en
        # vistas web sin hardcodear la ruta. asset("welcome.css") -> /static/welcome.css; por módulo,
        # asset("example/x.css") -> /static/example/x.css (lo sirve el mount namespaced del módulo).
        "asset": _asset,
        # `vite()` / `vite_asset()` / `vite_react_refresh()` (= @vite / Vite::asset / @viteReactRefresh de
        # Laravel): los assets del frontend Vite — dev server con HMR (hot-file por app) o manifest hasheado
        # de dist/ según el modo (ver Core/View/Vite.py). Multi-app: `vite('src/main.jsx', app='tienda')`.
        # OPT-IN: solo truenan (con instrucción clara) si se usan sin apps detectadas.
        "vite": vite,
        "vite_asset": vite_asset,
        "vite_react_refresh": vite_react_refresh,
        # `assets_dev()`: True si los assets salen del dev server (hot-file vivo), False en build. Las apps
        # gatean en la plantilla lo que SOLO va en build (speculation rules, @view-transition) sin
        # replicar la convención del hot-file. Uso: `{% if not assets_dev() %}…{% endif %}`.
        "assets_dev": assets_dev,
        # `env_script()`: el <script> de window.__ENV (runtime-config del shell) sin copiar el tag ni el
        # `| safe` en cada plantilla — lee env_json del contexto.
        "env_script": _env_script,
        # `csp_nonce()`: el nonce de CSP de la request para un <script> propio pegado en la plantilla.
        "csp_nonce": _csp_nonce,
    }
