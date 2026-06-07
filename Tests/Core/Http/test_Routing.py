"""Tests del routing class-based (@Controller/@Get), sin red salvo TestClient.

Cubre la maquinaria en aislamiento (montando el router que arma @Controller) y la integración
real (que create_app auto-monta los @Controller class-based del módulo Demo, conviviendo con
cualquier router función-style).
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.requests import Request

from milpa.Core.Http import Controller, Fallback, Get, Post, api_version
from milpa.Core.Http.Http import create_app
from milpa.Core.Http.Routing import FALLBACKS_ATTR, ROUTER_ATTR


class _Item(BaseModel):
    name: str


def _flag() -> str:
    return "dep-ok"


@Controller("/things", tags=["things"])
class _ThingsController:
    @Get("/")
    def index(self) -> list[str]:
        return ["a", "b"]

    @Get("/{item_id}")
    def show(self, item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @Post("/", status_code=201)
    def store(self, body: _Item) -> dict[str, str]:
        return {"created": body.name}

    @Get("/with-dep/x")
    def with_dep(self, flag: str = Depends(_flag)) -> dict[str, str]:
        return {"flag": flag}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(getattr(_ThingsController, ROUTER_ATTR))
    return TestClient(app)


def test_controller_builds_a_router() -> None:
    assert getattr(_ThingsController, ROUTER_ATTR, None) is not None


def test_get_collection() -> None:
    assert _client().get("/things/").json() == ["a", "b"]


def test_get_with_typed_path_param() -> None:
    assert _client().get("/things/7").json() == {"item_id": 7}


def test_post_with_body_and_status_code() -> None:
    response = _client().post("/things/", json={"name": "milpa"})
    assert response.status_code == 201
    assert response.json() == {"created": "milpa"}


def test_route_level_dependency_resolves() -> None:
    assert _client().get("/things/with-dep/x").json() == {"flag": "dep-ok"}


@Controller("/notes", tags=["notes"], version="v1")
class _NotesV1Controller:
    @Get("/")
    def index(self, request: Request) -> dict[str, str | None]:
        return {"version": api_version(request)}


def _versioned_client() -> TestClient:
    app = FastAPI()
    app.include_router(getattr(_NotesV1Controller, ROUTER_ATTR))
    return TestClient(app)


def test_version_prepends_url_prefix() -> None:
    # La ruta vive bajo /v1/notes (URL-path versioning); sin /v1 da 404.
    assert _versioned_client().get("/v1/notes/").status_code == 200
    assert _versioned_client().get("/notes/").status_code == 404


def test_version_is_added_to_router_tags() -> None:
    router = getattr(_NotesV1Controller, ROUTER_ATTR)
    assert "v1" in router.tags
    assert "notes" in router.tags


def test_api_version_helper_reads_current_version_in_handler() -> None:
    assert _versioned_client().get("/v1/notes/").json() == {"version": "v1"}


def test_unversioned_controller_has_no_version() -> None:
    # En un controller sin version=, api_version(request) es None (no rompe).
    assert _client().get("/things/with-dep/x").status_code == 200


def test_class_based_controller_is_auto_mounted_by_registry() -> None:
    # Integración: los @Controller class-based del módulo Demo se auto-montan vía create_app
    # (sin listarlos en ningún lado), descubiertos por el Registry.
    paths = TestClient(create_app()).get("/openapi.json").json()["paths"]
    assert "/api/login" in paths  # ApiController  -> @Controller("/api")
    assert "/login" in paths  # WebController -> @Controller("")
    # API versioning (Fase 3) en acción: el MISMO recurso en dos versiones que conviven.
    assert "/v1/reports/notes" in paths  # ReportsV1Controller -> @Controller("/reports", version="v1")
    assert "/v2/reports/notes" in paths  # ReportsV2Controller -> @Controller("/reports", version="v2")


# ─── @Fallback: rutas que NO van al router del controller, sino al final de create_app ──────


@Controller("", tags=["spa"])
class _ShellController:
    @Get("/normal")
    def normal(self) -> dict[str, str]:
        return {"ruta": "normal"}

    @Fallback
    @Get("/{path:path}")
    def shell(self, path: str) -> dict[str, str]:
        return {"shell": path}


def test_fallback_no_se_monta_en_el_router_del_controller() -> None:
    # El router del controller expone SOLO la ruta normal; la @Fallback queda apartada.
    router = getattr(_ShellController, ROUTER_ATTR)
    router_paths = {route.path for route in router.routes}
    assert "/normal" in router_paths
    assert "/{path:path}" not in router_paths  # el catch-all NO está en el router normal


def test_fallback_conserva_path_methods_kwargs() -> None:
    # La metadata acumulada en cls.__milpa_fallbacks__ trae lo que create_app necesita para
    # montar la ruta idéntica al FINAL: (endpoint, path, methods, kwargs).
    fallbacks = getattr(_ShellController, FALLBACKS_ATTR)
    assert len(fallbacks) == 1
    _endpoint, path, methods, kwargs = fallbacks[0]
    assert path == "/{path:path}"  # prefijo "" + el path del @Get
    assert methods == ["GET"]
    assert isinstance(kwargs, dict)


def test_importar_fallback_no_truena() -> None:
    # Re-export de Core/Http: las apps hacen `from milpa.Core.Http import Fallback`.
    from milpa.Core.Http import Fallback as _imported

    assert _imported is Fallback
