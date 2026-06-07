"""Tests unitarios del helper Vite (Core/View/Vite.py) — sin BD, sin red, sin npm.

El modo (dev vs prod) se decide por la EXISTENCIA del hot-file (modelo Laravel):
los tests lo materializan en `tmp_path` y apuntan `settings.vite_dist_dir` ahí
con `monkeypatch` (mismo patrón que los tests de Auth con `settings`).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from milpa.Core.Config import settings
from milpa.Core.View import Vite
from milpa.Core.View.TemplateEngine import TemplateEngine


@pytest.fixture(autouse=True)
def _clear_apps_cache() -> Iterator[None]:
    """resolve_apps() cachea la ESTRUCTURA de apps keyada por los settings de paths. Casi
    todos estos tests monkeypatchean esos paths apuntando a `tmp_path` (una key NUEVA por
    test, así que no se contaminan entre sí), pero limpiamos antes y después por higiene —
    y porque un test puede cambiar paths SIN tmp_path y compartir key con otro."""
    Vite.clear_apps_cache()
    yield
    Vite.clear_apps_cache()


# Manifest realista (shape de vite.dev/guide/backend-integration): un entry con su
# CSS propio + un chunk compartido importado que trae su propio CSS.
_MANIFEST: dict[str, dict[str, Any]] = {
    "src/main.jsx": {
        "file": "assets/main-AbC123.js",
        "src": "src/main.jsx",
        "isEntry": True,
        "imports": ["_shared-XyZ789.js"],
        "css": ["assets/main-DeF456.css"],
    },
    "_shared-XyZ789.js": {
        "file": "assets/shared-XyZ789.js",
        "css": ["assets/shared-GhI012.css"],
    },
}


def _setup_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest: dict[str, Any] | None = None) -> Path:
    """Crea un `dist/` con manifest en tmp_path y apunta settings ahí. Devuelve dist."""
    dist = tmp_path / "dist"
    (dist / ".vite").mkdir(parents=True)
    (dist / ".vite" / "manifest.json").write_text(json.dumps(manifest or _MANIFEST), encoding="utf-8")
    monkeypatch.setattr(settings, "vite_dist_dir", str(dist))
    return dist


# ─── PROD (sin hot-file): tags desde el manifest ────────────────────────────────


def test_prod_emite_css_y_script_hasheados_en_orden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)

    html = str(Vite.vite("src/main.jsx"))

    assert '<link rel="stylesheet" href="/vite/assets/main-DeF456.css">' in html
    assert '<link rel="stylesheet" href="/vite/assets/shared-GhI012.css">' in html  # CSS del import
    assert '<script type="module" src="/vite/assets/main-AbC123.js"></script>' in html
    # Orden documentado: TODOS los <link> antes del <script> del entry.
    assert html.rindex("<link") < html.index("<script")


def test_prod_respeta_vite_assets_url_custom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "vite_assets_url", "/assets-del-front")

    html = str(Vite.vite("src/main.jsx"))

    assert 'src="/assets-del-front/assets/main-AbC123.js"' in html


def test_prod_asset_url_prefija_todas_las_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ASSET_URL (deploy bajo sub-ruta de reverse proxy o CDN, = ASSET_URL de
    Laravel) se antepone a lo que EMITE vite() — el mount no cambia (el proxy
    stripea el prefijo antes de llegar a la app)."""
    _setup_build(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "asset_url", "/nombre-reverse")

    html = str(Vite.vite("src/main.jsx"))

    assert '<script type="module" src="/nombre-reverse/vite/assets/main-AbC123.js"></script>' in html
    assert '<link rel="stylesheet" href="/nombre-reverse/vite/assets/main-DeF456.css">' in html


def test_prod_asset_url_tolera_barra_final_y_cdn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "asset_url", "https://cdn.example.com/")  # barra final: no debe duplicarse

    html = str(Vite.vite("src/main.jsx"))

    assert 'src="https://cdn.example.com/vite/assets/main-AbC123.js"' in html


def test_dev_ignora_asset_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """En dev los módulos salen del dev server (hot-file): ASSET_URL no aplica."""
    _setup_build(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "asset_url", "/nombre-reverse")
    (tmp_path / "hot").write_text("http://localhost:5173", encoding="utf-8")

    html = str(Vite.vite("src/main.jsx"))

    assert "http://localhost:5173/src/main.jsx" in html
    assert "/nombre-reverse" not in html


def test_prod_entry_inexistente_truena_listando_disponibles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match=r"src/otro\.jsx.*src/main\.jsx"):
        Vite.vite("src/otro.jsx")


def test_prod_sin_manifest_truena_con_instruccion_de_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setattr(settings, "vite_dist_dir", str(dist))

    with pytest.raises(RuntimeError, match="npm run build"):
        Vite.vite("src/main.jsx")


def test_prod_react_refresh_es_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)

    assert str(Vite.vite_react_refresh()) == ""


def test_manifest_se_recachea_si_cambia_el_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El cache por mtime no debe servir un build viejo tras un rebuild."""
    dist = _setup_build(tmp_path, monkeypatch)
    Vite.vite("src/main.jsx")

    rebuilt = {"src/main.jsx": {"file": "assets/main-NUEVO.js", "isEntry": True}}
    manifest_file = dist / ".vite" / "manifest.json"
    manifest_file.write_text(json.dumps(rebuilt), encoding="utf-8")
    os.utime(manifest_file, (manifest_file.stat().st_atime, manifest_file.stat().st_mtime + 10))

    assert "main-NUEVO.js" in str(Vite.vite("src/main.jsx"))


# ─── DEV (hot-file presente): tags hacia el dev server ──────────────────────────


def test_dev_emite_cliente_hmr_y_entry_desde_el_dev_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)
    (tmp_path / "hot").write_text("http://localhost:5173\n", encoding="utf-8")  # <dist>/../hot

    html = str(Vite.vite("src/main.jsx"))

    assert '<script type="module" src="http://localhost:5173/@vite/client"></script>' in html
    assert '<script type="module" src="http://localhost:5173/src/main.jsx"></script>' in html
    assert "<link" not in html  # en dev el CSS lo inyecta Vite vía JS, no el backend


def test_dev_react_refresh_emite_preambulo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)
    (tmp_path / "hot").write_text("http://localhost:5173", encoding="utf-8")

    preamble = str(Vite.vite_react_refresh())

    assert "RefreshRuntime" in preamble
    assert "http://localhost:5173/@react-refresh" in preamble


def test_hot_file_explicito_gana_al_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)
    custom_hot = tmp_path / "otro-lugar" / "vite.hot"
    custom_hot.parent.mkdir()
    custom_hot.write_text("http://127.0.0.1:5999", encoding="utf-8")
    monkeypatch.setattr(settings, "vite_hot_file", str(custom_hot))

    assert "http://127.0.0.1:5999/@vite/client" in str(Vite.vite("src/main.jsx"))


# ─── Multi-app (microfrontends): auto-detección en VITE_APPS_DIR ────────────────


def _setup_app(public_root: Path, name: str, manifest: dict[str, Any] | None = None) -> Path:
    """Crea `public/<name>/.vite/manifest.json` (una app CONSTRUIDA, layout Laravel)."""
    build_dir = public_root / name
    (build_dir / ".vite").mkdir(parents=True)
    (build_dir / ".vite" / "manifest.json").write_text(json.dumps(manifest or _MANIFEST), encoding="utf-8")
    return build_dir


def _use_apps_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Apunta los DOS lados de la convención a tmp: fuentes (surcos/) y builds
    (public/). Devuelve public/ — donde _setup_app materializa apps construidas."""
    apps_root = tmp_path / "surcos"
    apps_root.mkdir()
    public_root = tmp_path / "public"
    public_root.mkdir()
    monkeypatch.setattr(settings, "vite_dist_dir", "")
    monkeypatch.setattr(settings, "vite_apps_dir", str(apps_root))
    monkeypatch.setattr(settings, "vite_public_dir", str(public_root))
    return public_root


def test_autodeteccion_una_app_namespacea_sus_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")

    html = str(Vite.vite("src/main.jsx"))  # única app → default, sin `app=`

    assert '<script type="module" src="/vite/tienda/assets/main-AbC123.js"></script>' in html


def test_autodeteccion_app_en_dev_sin_build_cuenta_como_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`npm run dev` recién clonado (hot-file en surcos/, sin build en public/) DEBE funcionar."""
    _use_apps_dir(tmp_path, monkeypatch)
    source_dir = tmp_path / "surcos" / "tienda"
    source_dir.mkdir()
    (source_dir / "hot").write_text("http://localhost:5173", encoding="utf-8")

    html = str(Vite.vite("src/main.jsx"))

    assert "http://localhost:5173/@vite/client" in html


def test_multiapp_exige_nombrar_la_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")
    _setup_app(apps_root, "reportes")

    with pytest.raises(RuntimeError, match="reportes.*tienda"):
        Vite.vite("src/main.jsx")  # ambiguo: ¿cuál de las dos?

    html = str(Vite.vite("src/main.jsx", app="reportes"))
    assert 'src="/vite/reportes/assets/main-AbC123.js"' in html


def test_app_inexistente_truena_listando(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")

    with pytest.raises(RuntimeError, match="'inventario'.*tienda"):
        Vite.vite("src/main.jsx", app="inventario")


def test_vite_asset_namespacea_archivos_de_public(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")

    assert Vite.vite_asset("icons/icon-192.png") == "/vite/tienda/icons/icon-192.png"


def test_vite_asset_multiapp_hereda_asset_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")
    monkeypatch.setattr(settings, "asset_url", "/nombre-reverse")

    assert Vite.vite_asset("icons/icon-192.png") == "/nombre-reverse/vite/tienda/icons/icon-192.png"


# ─── Opt-in y uso desde templates ────────────────────────────────────────────────


def test_sin_nada_detectado_muere_con_instruccion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """'Ahí muere': sin VITE_DIST_DIR y sin apps en las carpetas convencionales."""
    monkeypatch.setattr(settings, "vite_dist_dir", "")
    monkeypatch.setattr(settings, "vite_apps_dir", str(tmp_path / "no-existe"))
    monkeypatch.setattr(settings, "vite_public_dir", str(tmp_path / "tampoco"))

    with pytest.raises(RuntimeError, match="VITE_APPS_DIR"):
        Vite.vite("src/main.jsx")


def test_carpeta_de_apps_vacia_tambien_muere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_apps_dir(tmp_path, monkeypatch)  # surcos/ existe pero sin apps

    assert Vite.resolve_apps() == {}
    with pytest.raises(RuntimeError, match="npm run"):
        Vite.vite("src/main.jsx")


def test_template_renderiza_vite_sin_escapar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Integración con Jinja: vite() devuelve Markup → el autoescape NO lo rompe."""
    _setup_build(tmp_path, monkeypatch)
    templates = tmp_path / "views"
    templates.mkdir()
    (templates / "shell.html.j2").write_text(
        "<head>{{ vite_react_refresh() }}{{ vite('src/main.jsx') }}</head>", encoding="utf-8"
    )
    engine = TemplateEngine(templates_dir=templates)

    html = engine.render("shell.html.j2", {})

    assert '<script type="module" src="/vite/assets/main-AbC123.js"></script>' in html
    assert "&lt;" not in html


def test_dev_vite_asset_sale_del_dev_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """vite_asset ramifica dev/prod IGUAL que vite(): en dev el public/ del surco lo
    sirve el dev server — la URL del mount (sin build) sería un 404 silencioso."""
    _setup_build(tmp_path, monkeypatch)
    (tmp_path / "hot").write_text("http://localhost:5173", encoding="utf-8")

    assert Vite.vite_asset("icons/icon-192.png") == "http://localhost:5173/icons/icon-192.png"


def test_prod_css_compartido_no_se_duplica_entre_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-entry: el CSS de un chunk compartido por dos entries se emite UNA vez
    (seen_css es del render completo, no por entry — como el @vite de Laravel)."""
    manifest = {
        "src/a.jsx": {"file": "assets/a-1.js", "isEntry": True, "imports": ["_shared-X.js"]},
        "src/b.jsx": {"file": "assets/b-1.js", "isEntry": True, "imports": ["_shared-X.js"]},
        "_shared-X.js": {"file": "assets/shared-X.js", "css": ["assets/shared-X.css"]},
    }
    _setup_build(tmp_path, monkeypatch, manifest=manifest)

    html = str(Vite.vite("src/a.jsx", "src/b.jsx"))

    assert html.count("assets/shared-X.css") == 1


def test_resolve_apps_con_dirs_vacios_no_escanea_el_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """VITE_PUBLIC_DIR=/VITE_APPS_DIR= (vacío = apagado): jamás escanear el cwd —
    Path('') es Path('.') y sin guard registraría apps fantasma del proyecto."""
    monkeypatch.chdir(tmp_path)
    fantasma = tmp_path / "fantasma" / ".vite"
    fantasma.mkdir(parents=True)
    (fantasma / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "vite_dist_dir", "")
    monkeypatch.setattr(settings, "vite_public_dir", "")
    monkeypatch.setattr(settings, "vite_apps_dir", "")

    assert Vite.resolve_apps() == {}


# ─── Cache de la ESTRUCTURA de apps (resolve_apps) — sin congelar el estado dev/build ───────


def test_resolve_apps_cachea_la_estructura(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dos llamadas seguidas con los MISMOS settings escanean el disco una sola vez: el
    segundo resolve_apps() sale del cache (no vuelve a llamar _scan_apps)."""
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")

    llamadas = {"n": 0}
    real_scan = Vite._scan_apps

    def _spy() -> dict[str, Path]:
        llamadas["n"] += 1
        return real_scan()

    monkeypatch.setattr(Vite, "_scan_apps", _spy)

    primera = Vite.resolve_apps()
    segunda = Vite.resolve_apps()

    assert primera == segunda
    assert llamadas["n"] == 1  # el segundo resolve_apps salió del cache


def test_resolve_apps_no_congela_el_estado_dev_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El cache es de ESTRUCTURA, no de estado: con una app construida ya cacheada, crear el
    hot-file DESPUÉS hace que vite() emita tags de DEV — porque _dev_server_url no pasa por el
    cache. Prender el dev server cambia el modo sin invalidar nada."""
    _setup_build(tmp_path, monkeypatch)
    Vite.resolve_apps()  # cachea la estructura (modo build, sin hot)
    assert "<link" in str(Vite.vite("src/main.jsx"))  # build: emite los <link> hasheados

    (tmp_path / "hot").write_text("http://localhost:5173", encoding="utf-8")  # nace el dev server

    html = str(Vite.vite("src/main.jsx"))
    assert "http://localhost:5173/@vite/client" in html  # ahora DEV, aunque la estructura esté cacheada


def test_cache_se_invalida_al_cambiar_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cambiar VITE_APPS_DIR/VITE_PUBLIC_DIR da otra key → reescanea (no sirve la estructura
    de los paths viejos)."""
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")
    assert set(Vite.resolve_apps()) == {"tienda"}

    otro_public = tmp_path / "otro-public"
    otro_apps = tmp_path / "otro-surcos"
    otro_public.mkdir()
    otro_apps.mkdir()
    _setup_app(otro_public, "reportes")
    monkeypatch.setattr(settings, "vite_public_dir", str(otro_public))
    monkeypatch.setattr(settings, "vite_apps_dir", str(otro_apps))

    assert set(Vite.resolve_apps()) == {"reportes"}  # otra key → reescaneo, no la cacheada


def test_clear_apps_cache_fuerza_reescaneo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El escape para tooling/dev en caliente: una app que aparece con la MISMA key tras el
    primer escaneo queda oculta hasta clear_apps_cache()."""
    apps_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(apps_root, "tienda")
    assert set(Vite.resolve_apps()) == {"tienda"}

    _setup_app(apps_root, "nueva")  # carpeta nueva con la misma key
    assert set(Vite.resolve_apps()) == {"tienda"}  # cacheada: no la ve aún

    Vite.clear_apps_cache()
    assert set(Vite.resolve_apps()) == {"nueva", "tienda"}  # tras el escape, reescanea


# ─── assets_dev(): publica al template la decisión dev/build ────────────────────────────────


def test_assets_dev_true_con_hot_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)
    (tmp_path / "hot").write_text("http://localhost:5173", encoding="utf-8")

    assert Vite.assets_dev() is True


def test_assets_dev_false_en_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_build(tmp_path, monkeypatch)  # build sin hot-file

    assert Vite.assets_dev() is False


def test_assets_dev_false_sin_apps_no_truena(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A DIFERENCIA de vite() (que truena), assets_dev es TOLERANTE: sin apps detectadas
    devuelve False — un gate de speculation no debe reventar el render."""
    monkeypatch.setattr(settings, "vite_dist_dir", "")
    monkeypatch.setattr(settings, "vite_apps_dir", str(tmp_path / "no-existe"))
    monkeypatch.setattr(settings, "vite_public_dir", str(tmp_path / "tampoco"))

    assert Vite.assets_dev() is False  # no levanta RuntimeError


def test_assets_dev_multiapp_por_nombre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-app: una construida (build) y otra en dev (hot). assets_dev(app=...) refleja el
    estado de CADA una."""
    public_root = _use_apps_dir(tmp_path, monkeypatch)
    _setup_app(public_root, "tienda")  # construida
    source_dir = tmp_path / "surcos" / "reportes"
    source_dir.mkdir()
    (source_dir / "hot").write_text("http://localhost:5173", encoding="utf-8")  # en dev

    assert Vite.assets_dev(app="reportes") is True
    assert Vite.assets_dev(app="tienda") is False


def test_template_gatea_con_assets_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Integración con Jinja: el global assets_dev() gatea el bloque del template (el caso de
    uso real: emitir speculation rules SOLO en build)."""
    _setup_build(tmp_path, monkeypatch)
    templates = tmp_path / "views"
    templates.mkdir()
    (templates / "shell.html.j2").write_text("{% if assets_dev() %}DEV{% else %}BUILD{% endif %}", encoding="utf-8")
    engine = TemplateEngine(templates_dir=templates)

    assert engine.render("shell.html.j2", {}) == "BUILD"  # sin hot-file

    (tmp_path / "hot").write_text("http://localhost:5173", encoding="utf-8")
    assert engine.render("shell.html.j2", {}) == "DEV"  # con hot-file
