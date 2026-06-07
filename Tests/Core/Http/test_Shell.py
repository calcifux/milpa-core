"""Tests del runtime-config del shell (Core/Http/Shell.py) — sin BD, sin servidor.

El Request se fabrica con un scope ASGI mínimo: lo único que estos helpers leen es
`root_path` (el prefijo del deploy tras un reverse proxy con sub-ruta).
"""

from __future__ import annotations

import json

from pytest import MonkeyPatch
from starlette.requests import Request

from milpa.Core.Config import settings
from milpa.Core.Http.Shell import base_path, runtime_env_json, shell_context
from milpa.Core.View import Vite


def _request(root_path: str = "") -> Request:
    return Request(scope={"type": "http", "root_path": root_path, "headers": []})


def test_base_path_vacio_sirviendo_en_raiz() -> None:
    assert base_path(_request()) == ""


def test_base_path_con_prefijo_de_proxy_sin_barra_final() -> None:
    assert base_path(_request("/nombre-reverse/")) == "/nombre-reverse"


def test_runtime_env_trae_las_claves_del_framework() -> None:
    env = json.loads(runtime_env_json(_request("/pre")))

    assert env["APP_NAME"] == settings.app_name
    assert env["APP_ENV"] == settings.app_env
    assert env["BASE_PATH"] == "/pre"
    assert "ASSETS_DEV" in env  # dev/build entra por DEFAULT (no hay que pasarlo por extra)
    assert isinstance(env["ASSETS_DEV"], bool)


def test_runtime_env_assets_dev_refleja_el_estado_del_dev_server(monkeypatch: MonkeyPatch) -> None:
    """ASSETS_DEV = lo que `assets_dev()` decide (hay hot-file vivo => dev). Mockeamos la
    función (importada DIFERIDA en Shell desde Vite) en ambos sentidos."""
    monkeypatch.setattr(Vite, "assets_dev", lambda app=None: True)
    assert json.loads(runtime_env_json(_request()))["ASSETS_DEV"] is True

    monkeypatch.setattr(Vite, "assets_dev", lambda app=None: False)
    assert json.loads(runtime_env_json(_request()))["ASSETS_DEV"] is False


def test_runtime_env_extra_agrega_y_sobrescribe() -> None:
    env = json.loads(runtime_env_json(_request(), {"FEATURE_X": True, "APP_NAME": "otro"}))

    assert env["FEATURE_X"] is True
    assert env["APP_NAME"] == "otro"  # extra GANA: el surco decide su __ENV


def test_runtime_env_extra_puede_sobrescribir_assets_dev(monkeypatch: MonkeyPatch) -> None:
    """El surco conserva la última palabra: ASSETS_DEV por default, pero `extra` GANA."""
    monkeypatch.setattr(Vite, "assets_dev", lambda app=None: False)

    env = json.loads(runtime_env_json(_request(), {"ASSETS_DEV": True}))

    assert env["ASSETS_DEV"] is True


def test_runtime_env_escapa_menor_que_para_script_inline() -> None:
    """Un valor con `</script>` no puede cerrar el tag del shell."""
    raw = runtime_env_json(_request(), {"EVIL": "</script><script>alert(1)"})

    assert "</script>" not in raw
    assert "\\u003c" in raw


def test_shell_context_trae_env_json_y_base_path() -> None:
    context = shell_context(_request("/pre"))

    assert set(context) == {"env_json", "base_path"}
    assert context["base_path"] == "/pre"
    assert json.loads(str(context["env_json"]))["BASE_PATH"] == "/pre"
