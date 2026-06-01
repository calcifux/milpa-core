"""Tests del routing class-based (@Controller/@Get), sin red salvo TestClient.

Cubre la maquinaria en aislamiento (montando el router que arma @Controller) y la integración
real (que create_app auto-monta el CatsController del módulo Example, conviviendo con los
controllers función-style).
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from milpa.Core.Http import Controller, Get, Post
from milpa.Core.Http.Http import create_app
from milpa.Core.Http.Routing import ROUTER_ATTR


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


def test_class_based_controller_is_auto_mounted_by_registry() -> None:
    # Integración: el CatsController del módulo Example se auto-monta vía create_app,
    # conviviendo con los routers función-style del mismo módulo.
    client = TestClient(create_app())
    assert client.get("/example/cats/").json() == ["Michi", "Pelusa"]
    assert client.get("/example/cats/0").json() == {"index": 0, "name": "Michi"}
    # Y el función-style sigue montado:
    assert client.get("/example/ping").json()["status"] == "ok"
