"""Tests de los comandos nuevos: route/db/make (registro, delegación y pureza de stubs). Sin BD."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest
import typer
from pytest import MonkeyPatch
from typer.testing import CliRunner

import milpa.Core.Console.Commands.DbCommands as db_mod
import milpa.Core.Console.Commands.MakeCommands as make_mod
import milpa.Core.Console.Commands.RouteCommands as route_mod
import milpa.Core.Console.Commands.SeedCommands as seed_mod
from milpa.Core.Console import build_cli_apps, registered_commands, reset_registry


@pytest.fixture
def fresh_registry() -> Iterator[None]:
    reset_registry()
    yield
    reset_registry()


def _apps() -> dict[str, typer.Typer]:
    return {group: sub_app for group, sub_app in build_cli_apps()}


def test_route_list_registered(fresh_registry: None) -> None:
    importlib.reload(route_mod)
    assert any(c.name == "list" for c in registered_commands().get("route", []))


def test_make_group_has_all_generators(fresh_registry: None) -> None:
    importlib.reload(make_mod)
    names = {c.name for c in registered_commands().get("make", [])}
    assert {"controller", "model", "module"} <= names


def test_db_fresh_registered(fresh_registry: None) -> None:
    importlib.reload(db_mod)
    assert any(c.name == "fresh" for c in registered_commands().get("db", []))


def test_route_list_output_includes_status_route(fresh_registry: None) -> None:
    importlib.reload(route_mod)
    result = CliRunner().invoke(_apps()["route"], ["list"])
    assert result.exit_code == 0
    assert "/status" in result.output


def test_db_fresh_delegates_downgrade_upgrade_seed(fresh_registry: None, monkeypatch: MonkeyPatch) -> None:
    importlib.reload(db_mod)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(db_mod, "run_downgrade", lambda rev: calls.append(("down", rev)))
    monkeypatch.setattr(db_mod, "run_upgrade", lambda rev: calls.append(("up", rev)))
    monkeypatch.setattr(seed_mod, "db_seed", lambda: calls.append(("seed",)))

    result = CliRunner().invoke(_apps()["db"], ["fresh", "--force"])

    assert result.exit_code == 0
    assert calls == [("down", "base"), ("up", "head"), ("seed",)]


def test_controller_stub_is_valid_milpa_controller() -> None:
    stub = make_mod.controller_stub("Blog")
    assert '@Controller("/blog", tags=["blog"])' in stub
    assert "class BlogController:" in stub
    assert '@Get("/")' in stub


def test_model_stub_is_valid_model() -> None:
    stub = make_mod.model_stub("Tag")
    assert "class Tag(TimestampMixin, Base):" in stub
    assert '__tablename__ = "tags"' in stub
