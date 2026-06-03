"""Tests de negociación de contenido (prefers_html / negotiate), SIN BD.

`prefers_html` se prueba con Requests fabricados (solo el header Accept); el camino JSON de
`negotiate` con un TestClient. El camino HTML lo ejercita el Demo (necesita un template real).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from milpa.Core.View import negotiate, prefers_html


def _request(accept: str) -> Request:
    headers = [(b"accept", accept.encode())] if accept else []
    return Request({"type": "http", "headers": headers})


@pytest.mark.parametrize(
    ("accept", "expected"),
    [
        ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", True),  # navegador
        ("text/html", True),
        ("text/html, application/json", True),  # html antes que json
        ("application/json", False),
        ("application/json, text/html", False),  # json antes que html
        ("*/*", False),  # curl: sin text/html => JSON
        ("", False),  # sin header => JSON
    ],
)
def test_prefers_html(accept: str, expected: bool) -> None:
    assert prefers_html(_request(accept)) is expected


def test_negotiate_returns_json_when_client_wants_json() -> None:
    app = FastAPI()

    @app.get("/n")
    def n(request: Request) -> Response:
        return negotiate(request, {"a": 1, "b": "x"}, "irrelevant", data_key="payload")

    client = TestClient(app)
    response = client.get("/n", headers={"accept": "application/json"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"a": 1, "b": "x"}
