"""Scaffolder de proyectos: la lógica detrás de `milpa new <app>`.

Copia el skeleton EMBEBIDO (milpa/_skeleton, archivos `.tmpl`) y lo renderiza
(sustituye `__PROJECT__` por el nombre del proyecto, quita el sufijo `.tmpl`) para crear
un proyecto listo para correr. El skeleton se localiza con `importlib.resources`
(funciona instalado vía pip o en el repo), NUNCA con aritmética de `__file__`.
"""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

_PLACEHOLDER = "__PROJECT__"
_TMPL_SUFFIX = ".tmpl"


def new_project(name: str, *, parent: Path | None = None) -> Path:
    """Crea el proyecto `name` desde el skeleton embebido. Devuelve la ruta creada.

    Seguro/idempotente: si el destino ya existe y NO está vacío, lanza `FileExistsError`
    (nunca sobrescribe trabajo del usuario). Deja también un `.env` listo (copia del
    `.env.example` generado) para que el proyecto arranque sin pasos extra.
    """
    dest = (parent or Path.cwd()) / name
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"El destino '{dest}' ya existe y no está vacío.")

    source = files("milpa").joinpath("_skeleton")
    with as_file(source) as skeleton_dir:
        _render_tree(Path(skeleton_dir), dest, name)

    env_example = dest / ".env.example"
    env_file = dest / ".env"
    if env_example.is_file() and not env_file.exists():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _render_tree(skeleton_dir: Path, dest: Path, name: str) -> None:
    """Copia recursivamente el skeleton a `dest`: quita el sufijo `.tmpl` del nombre y
    sustituye el placeholder por `name` en el contenido de cada archivo."""
    for src in sorted(skeleton_dir.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(skeleton_dir)
        out_name = rel.name[: -len(_TMPL_SUFFIX)] if rel.name.endswith(_TMPL_SUFFIX) else rel.name
        out_path = dest / rel.parent / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = src.read_text(encoding="utf-8").replace(_PLACEHOLDER, name)
        out_path.write_text(content, encoding="utf-8")
