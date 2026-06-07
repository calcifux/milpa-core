"""Tests del scaffolder `milpa new` (Core/Console/Scaffold.py) — sin BD, puro filesystem.

Cubren el contrato base (skeleton renderizado, placeholder sustituido, idempotencia)
y el `--demo` completo: módulo backend con imports reescritos + el FRONTEND
(`_skeleton_demo`: surcos Vite + workspace pnpm raíz) con sus binarios INTACTOS
(los PNG de la PWA no pasan por read_text — regla .tmpl=texto / resto=bytes).
"""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import pytest

from milpa.Core.Console.Scaffold import new_project


def test_new_project_renderiza_skeleton_y_sustituye_nombre(tmp_path: Path) -> None:
    dest = new_project("granja", parent=tmp_path)

    assert dest == tmp_path / "granja"
    pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "granja" in pyproject
    assert "__PROJECT__" not in pyproject
    assert (dest / ".env").is_file()  # listo para arrancar sin pasos extra
    assert not list(dest.rglob("*.tmpl"))  # ningún .tmpl se fuga al proyecto


def test_pyproject_pin_milpa_core_0_6_y_pythonpath(tmp_path: Path) -> None:
    """El pyproject RENDERIZADO ancla el proyecto a milpa-core>=0.6.0 (el release) y deja el
    `pythonpath` de pytest para que los Tests importen `app.*` desde la raíz del proyecto."""
    dest = new_project("granja", parent=tmp_path)

    pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "milpa-core>=0.6.0" in pyproject  # pin del skeleton al release (D3)
    assert "pythonpath" in pyproject  # [tool.pytest.ini_options] pythonpath = ["."]


def test_new_project_no_sobrescribe_destino_con_contenido(tmp_path: Path) -> None:
    (tmp_path / "ocupado").mkdir()
    (tmp_path / "ocupado" / "algo.txt").write_text("mío", encoding="utf-8")

    with pytest.raises(FileExistsError):
        new_project("ocupado", parent=tmp_path)


def test_demo_materializa_backend_con_imports_reescritos(tmp_path: Path) -> None:
    dest = new_project("granja", parent=tmp_path, demo=True)

    spa_controller = dest / "app" / "Modules" / "Demo" / "Http" / "SpaController.py"
    assert spa_controller.is_file()
    content = spa_controller.read_text(encoding="utf-8")
    assert "milpa.Modules." not in content  # reescrito a app.Modules


def test_demo_materializa_frontend_surcos(tmp_path: Path) -> None:
    """El --demo entrega la contraparte frontend de los controllers: surcos Vite
    + workspace pnpm raíz, con el placeholder del nombre resuelto."""
    dest = new_project("granja", parent=tmp_path, demo=True)

    root_pkg = (dest / "package.json").read_text(encoding="utf-8")
    assert '"granja-frontends"' in root_pkg
    workspace = (dest / "pnpm-workspace.yaml").read_text(encoding="utf-8")
    assert '"surcos/*"' in workspace
    # El override link: viaja COMENTADO (camino de desarrollo del plugin); el
    # default es consumir vite-plugin-milpa publicado en npm.
    assert "# overrides:" in workspace
    assert "\noverrides:" not in workspace
    assert (dest / ".nvmrc").is_file()
    # Surco React (PWA) y surco vanilla — cada uno con su package.json propio.
    assert (dest / "surcos" / "demo-spa" / "vite.config.js").is_file()
    assert (dest / "surcos" / "tablero" / "vite.config.js").is_file()
    spa_pkg = (dest / "surcos" / "demo-spa" / "package.json").read_text(encoding="utf-8")
    assert '"vite-plugin-milpa"' in spa_pkg  # consume el plugin PUBLICADO (registry)
    assert "workspace:*" not in spa_pkg  # nunca el protocolo del monorepo
    # El router file-based con la página de segmento dinámico ([id] sobrevive el render).
    assert (dest / "surcos" / "demo-spa" / "src" / "modules" / "tienda" / "pages" / "productos" / "[id].jsx").is_file()


def test_demo_copia_binarios_intactos(tmp_path: Path) -> None:
    """Los iconos PNG de la PWA deben quedar BYTE-idénticos al origen del paquete:
    un render de texto los corrompería (la regla es .tmpl=plantilla, resto=bytes)."""
    dest = new_project("granja", parent=tmp_path, demo=True)

    rel = Path("surcos/demo-spa/public/icons/icon-192.png")
    generated = (dest / rel).read_bytes()
    with as_file(files("milpa").joinpath("_skeleton_demo")) as skeleton_demo:
        original = (Path(skeleton_demo) / rel).read_bytes()

    assert generated == original
    assert generated[:8] == b"\x89PNG\r\n\x1a\n"  # firma PNG: no se corrompió
