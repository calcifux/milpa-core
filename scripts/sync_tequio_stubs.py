"""Regenera el MAPA de tipos (`.pyi`) de lo que milpa toma de tequio.

Para qué: en ejecución, `milpa.Core.Database` ES el módulo de tequio (lo entrega el puente de
`milpa/Core/__init__.py`). Pero el editor (PhpStorm/PyCharm) y mypy no ejecutan nada: leen archivos.
Sin un archivo en `milpa/Core/Database/`, marcan en rojo `from milpa.Core.Database import Repository`.
Los `.pyi` son archivos de SOLO tipos: Python nunca los corre, el editor y mypy sí los leen.

Cuándo correrlo: cada vez que tequio agrega, quita o renombra algo en lo compartido. La prueba
`Tests/Core/test_TequioBridge.py` truena si el mapa se quedó atrás, con el comando para arreglarlo:

    uv run python scripts/sync_tequio_stubs.py

No edites los `.pyi` a mano: este script los vuelve a escribir.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILPA_CORE = ROOT / "src" / "milpa" / "Core"
sys.path.insert(0, str(ROOT / "src"))

from milpa.Core import SHARED_MODULES, SHARED_PACKAGES  # noqa: E402

HEADER = (
    '"""Mapa de tipos (generado por scripts/sync_tequio_stubs.py; no lo edites a mano).\n\n'
    "En ejecución este módulo ES `{tequio}` (ver milpa/Core/__init__.py); este archivo solo le dice\n"
    'al editor y a mypy qué nombres trae."""\n\n'
)


def _tequio_core_dir() -> Path:
    spec = importlib.util.find_spec("tequio.Core")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("No encuentro tequio instalado: corre `uv sync` primero.")
    return Path(next(iter(spec.submodule_search_locations)))


def shared_tequio_files() -> dict[str, Path]:
    """{'Database.Session': <archivo de tequio>, 'Database': <su __init__.py>, …} de lo compartido."""
    core = _tequio_core_dir()
    found: dict[str, Path] = {}
    for path in sorted(core.rglob("*.py")):
        relative = path.relative_to(core).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or "__pycache__" in parts:
            continue
        dotted = ".".join(parts)
        if parts[0] in SHARED_PACKAGES or dotted in SHARED_MODULES:
            found[dotted] = path
    return found


def _exported_names(source: str) -> list[str]:
    """Los nombres que el módulo de tequio EXPORTA: los de su `__all__` (si lo tiene) más los que define él
    mismo (funciones, clases, variables; también las privadas, que algunas pruebas usan). Lo que solo
    importa de otro lado no se exporta: mypy estricto lo rechaza (no es parte de ese módulo)."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    names.update(item.value for item in node.value.elts if isinstance(item, ast.Constant))
                elif isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return sorted(name for name in names if not (name.startswith("__") and name.endswith("__")))


def stub_for(dotted: str, source: Path) -> str:
    tequio_name = f"tequio.Core.{dotted}"
    names = _exported_names(source.read_text(encoding="utf-8"))
    lines = [HEADER.format(tequio=tequio_name), "from __future__ import annotations\n\n"]
    if names:
        lines.append(f"from {tequio_name} import (\n")
        lines.extend(f"    {name} as {name},\n" for name in names)
        lines.append(")\n")
    return "".join(lines)


def stub_path(dotted: str, source: Path) -> Path:
    parts = dotted.split(".")
    if source.name == "__init__.py":
        return MILPA_CORE.joinpath(*parts, "__init__.pyi")
    return MILPA_CORE.joinpath(*parts[:-1], f"{parts[-1]}.pyi")


def expected_stubs() -> dict[Path, str]:
    return {stub_path(dotted, source): stub_for(dotted, source) for dotted, source in shared_tequio_files().items()}


def exported_names_of_stub(path: Path) -> set[str]:
    """Los nombres que un `.pyi` del mapa re-exporta (lo usa la prueba para ver si el mapa está al día)."""
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ImportFrom) and node.module != "__future__":
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def main() -> None:
    expected = expected_stubs()
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # Un .pyi que ya no corresponde a nada de tequio se borra: si no, el editor ofrecería un módulo que no existe.
    for path in MILPA_CORE.rglob("*.pyi"):
        if path not in expected:
            path.unlink()
            print(f"borrado {path.relative_to(ROOT)}")
    # El orden de las importaciones lo deja ruff (el mismo revisor del CI), para que el CI no los marque.
    stubs = [str(path) for path in expected]
    subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "--quiet", "--select", "I", *stubs], check=True)
    subprocess.run([sys.executable, "-m", "ruff", "format", "--quiet", *stubs], check=True)
    print(f"mapa al día: {len(stubs)} archivos .pyi")


if __name__ == "__main__":
    main()
