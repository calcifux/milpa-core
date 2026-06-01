"""Guardrail: `make:*` debe escribir en el código del USUARIO (settings.app_dir),
NO en el paquete milpa instalado.

Regresión real: tras la Fase A, `make model` usaba `Path(__file__).parents[3]` y escribía
en `src/milpa/Models/` (el framework) en vez del `app/Models/` del proyecto. Este test lo
fija: monkeypatchea `app_dir` a un tmp y verifica que el archivo cae ahí.
"""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

import milpa.Core.Console.Commands.MakeCommands as make_mod
from milpa.Core.Config import settings


def test_make_model_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_model("Widget")

    assert (tmp_path / "app" / "Models" / "Widget.py").is_file(), (
        "make model debe escribir en settings.app_dir/Models, no en el paquete milpa"
    )


def test_make_module_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_module("Billing")

    base = tmp_path / "app" / "Modules" / "Billing"
    assert (base / "__init__.py").is_file()
    assert (base / "Http" / "BillingController.py").is_file()
