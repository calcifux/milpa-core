"""Tests del runtime-config del shell (Core/Http/Shell.py) — sin BD, sin servidor.

El Request se fabrica con un scope ASGI mínimo: lo único que estos helpers leen es
`root_path` (el prefijo del deploy tras un reverse proxy con sub-ruta).
"""

from __future__ import annotations

import json

from starlette.requests import Request

from milpa.Core.Config import settings
from milpa.Core.Http.Shell import base_path, runtime_env_json, shell_context


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


def test_runtime_env_extra_agrega_y_sobrescribe() -> None:
    env = json.loads(runtime_env_json(_request(), {"FEATURE_X": True, "APP_NAME": "otro"}))

    assert env["FEATURE_X"] is True
    assert env["APP_NAME"] == "otro"  # extra GANA: el surco decide su __ENV


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
