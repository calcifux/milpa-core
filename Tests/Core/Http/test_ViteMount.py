"""Tests del mount opt-in de assets Vite en create_app (Core/Http/Http.py) — sin BD.

El guard de VITE_PUBLIC_DIR vacío es de SEGURIDAD: Path("") es Path(".") y siempre
is_dir(), así que sin él un `VITE_PUBLIC_DIR=` en el .env montaría la RAÍZ del
proyecto (.env, secrets/, código fuente) en /vite vía StaticFiles. Vacío = apagado,
el mismo idioma que VITE_DIST_DIR/VITE_HOT_FILE/ASSET_URL.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from milpa.Core.Config import settings
from milpa.Core.Http.Http import create_app


def _tiene_mount_vite(app: FastAPI) -> bool:
    return any(getattr(route, "name", None) == "vite" for route in app.routes)


def test_public_dir_vacio_apaga_el_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """VITE_PUBLIC_DIR= (vacío) NO monta nada — jamás el cwd con sus secretos."""
    monkeypatch.chdir(tmp_path)  # un "proyecto" con secretos en la raíz
    (tmp_path / ".env").write_text("JWT_SECRET=super-secreto", encoding="utf-8")
    monkeypatch.setattr(settings, "vite_dist_dir", "")
    monkeypatch.setattr(settings, "vite_public_dir", "")

    app = create_app()

    assert not _tiene_mount_vite(app)


def test_public_dir_presente_si_monta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El caso feliz sigue vivo: con un public/ real el mount existe."""
    public = tmp_path / "public"
    public.mkdir()
    monkeypatch.setattr(settings, "vite_dist_dir", "")
    monkeypatch.setattr(settings, "vite_public_dir", str(public))

    app = create_app()

    assert _tiene_mount_vite(app)
