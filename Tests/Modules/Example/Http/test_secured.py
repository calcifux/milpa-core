"""La dependency a nivel de router (middleware del módulo) gatea la ruta: sin el
header correcto → 401; con él → 200. Vía TestClient, sin levantar servidor.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from milpa.Core.Http import create_app


def test_router_dependency_gates_the_route() -> None:
    client = TestClient(create_app())
    assert client.get("/example/secured/ping").status_code == 401
    ok = client.get("/example/secured/ping", headers={"X-API-Key": "demo-secret"})
    assert ok.status_code == 200
    assert ok.json()["scope"] == "secured"
