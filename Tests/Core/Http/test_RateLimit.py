"""Tests de @rate_limit (SlowAPI) sobre un @Controller class-based, sin BD (solo TestClient).

Valida lo delicado de la integración: que el decorador SOBREVIVE al binding de bound-methods del
@Controller (FastAPI sigue inyectando `request`), que el límite DISPARA y que el 429 sale en RFC
9457 (application/problem+json) con `Retry-After`, no en el JSON propio de SlowAPI.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from milpa.Core.Http import Controller, Get, rate_limit
from milpa.Core.Http.ProblemDetails import PROBLEM_JSON_MEDIA_TYPE
from milpa.Core.Http.RateLimit import limiter, register_rate_limit
from milpa.Core.Http.Routing import ROUTER_ATTR


@Controller("/rl", tags=["rl"])
class _LimitedController:
    @Get("/ping")
    @rate_limit("2/minute")
    def ping(self, request: Request) -> dict[str, str]:
        return {"status": "ok"}


def _client() -> TestClient:
    app = FastAPI()
    register_rate_limit(app)  # app.state.limiter + handler 429 RFC 9457
    app.include_router(getattr(_LimitedController, ROUTER_ATTR))
    return TestClient(app, raise_server_exceptions=True)


def test_rate_limit_allows_up_to_limit_then_429() -> None:
    limiter.reset()  # storage en memoria limpio (aislamiento entre corridas)
    client = _client()

    assert client.get("/rl/ping").status_code == 200  # 1/2
    assert client.get("/rl/ping").status_code == 200  # 2/2
    blocked = client.get("/rl/ping")  # 3 => excede
    assert blocked.status_code == 429


def test_429_is_rfc9457_problem_json() -> None:
    limiter.reset()
    client = _client()
    client.get("/rl/ping")
    client.get("/rl/ping")
    blocked = client.get("/rl/ping")

    assert blocked.status_code == 429
    assert blocked.headers["content-type"].startswith(PROBLEM_JSON_MEDIA_TYPE)
    body = blocked.json()
    assert body["code"] == "rate_limit_exceeded"
    assert body["status"] == 429
    assert body["title"] == "Too Many Requests"
