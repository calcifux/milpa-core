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


def test_make_observer_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_observer("Tasks", "NotifyAdmin")

    assert (tmp_path / "app" / "Modules" / "Tasks" / "Observers" / "NotifyAdminObserver.py").is_file()


def test_make_handler_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_handler("Tasks", "CompleteTask")

    assert (tmp_path / "app" / "Modules" / "Tasks" / "Handlers" / "CompleteTaskHandler.py").is_file()


def test_make_repository_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_repository("Tasks", "Task")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Repositories"
    assert (base / "TaskRepository.py").is_file()
    assert (base / "__init__.py").is_file()  # _ensure_pkg


def test_make_pipe_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_pipe("Tasks", "NormalizeTitle")

    assert (tmp_path / "app" / "Modules" / "Tasks" / "Pipes" / "NormalizeTitle.py").is_file()


def test_make_mailable_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_mailable("Tasks", "TaskReady")

    assert (tmp_path / "app" / "Modules" / "Tasks" / "Mail" / "TaskReadyMailable.py").is_file()


def test_make_job_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_job("Tasks", "SendReport")

    assert (tmp_path / "app" / "Modules" / "Tasks" / "Jobs" / "SendReport.py").is_file()


def test_make_service_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_service("Tasks", "CompleteTask")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Services"
    assert (base / "CompleteTaskService.py").is_file()
    assert (base / "__init__.py").is_file()  # _ensure_pkg


def test_make_policy_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_policy("Tasks", "Note")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Policies"
    assert (base / "NotePolicy.py").is_file()
    assert (base / "__init__.py").is_file()  # _ensure_pkg


def test_make_seeder_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_seeder("Tasks", "Task")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Seeders"
    assert (base / "TaskSeeder.py").is_file()
    assert (base / "__init__.py").is_file()  # _ensure_pkg


def test_make_factory_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_factory("Tasks", "Task")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Factories"
    assert (base / "TaskFactory.py").is_file()
    assert (base / "__init__.py").is_file()  # _ensure_pkg


def test_make_serializer_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_serializer("Tasks", "Task")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Serializers"
    assert (base / "TaskSerializer.py").is_file()
    assert (base / "__init__.py").is_file()  # _ensure_pkg


def test_make_view_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_view("Tasks", "index")

    target = tmp_path / "app" / "Modules" / "Tasks" / "Resources" / "Views" / "index.html.j2"
    assert target.is_file()
    assert not (target.parent / "__init__.py").exists()  # recurso de PATH, no paquete
    assert '{% extends "tasks/layout.html.j2" %}' in target.read_text(encoding="utf-8")


def test_make_lang_writes_to_app_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_dir", str(tmp_path / "app"))

    make_mod.make_lang("Tasks", "Messages")

    base = tmp_path / "app" / "Modules" / "Tasks" / "Resources" / "Lang" / "tasks"
    assert (base / "Messages.es.yml").is_file()
    assert (base / "Messages.en.yml").is_file()
    assert not (base / "__init__.py").exists()  # recurso de PATH, no paquete
