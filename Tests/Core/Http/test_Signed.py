"""Tests de los enlaces firmados (URL.signed / URL.temporary_signed / @Signed). Sin BD.

Lo que se protege es lo que un atacante intentaría con un enlace que le llegó (o que robó):
cambiarle un parámetro, estirarle el vencimiento, usarlo en otra ruta o para otro propósito, o
quitarle la firma. Y lo que se rompería en producción sin que nadie lo notara: que un proxy
reordene el query o que la app viva bajo un prefijo.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from milpa.Core.Config import settings
from milpa.Core.Http import Controller, Get
from milpa.Core.Http.ExceptionHandler import register_exception_handlers
from milpa.Core.Http.Routing import ROUTER_ATTR
from milpa.Core.Http.Signed import (
    URL,
    Signed,
    SigningKeyMissingError,
    require_signature,
)

_KEY = "llave-de-prueba-0123456789-abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def signing_key(monkeypatch: MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "url_signing_key", _KEY)
    monkeypatch.setattr(settings, "url_signing_previous_keys", "")
    yield


@Controller("/reportes", tags=["test"])
class _ReportController:
    @Get("/{report_id}")
    @Signed(purpose="report.download")
    def download(self, report_id: int) -> dict[str, int]:
        return {"report": report_id}


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(getattr(_ReportController, ROUTER_ATTR))

    @app.get("/plain", dependencies=[Depends(require_signature())])
    def plain() -> dict[str, bool]:
        return {"ok": True}

    return app


def _path_and_query(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def _with_query(url: str, **changes: str) -> str:
    parts = urlsplit(url)
    pairs = dict(parse_qsl(parts.query))
    pairs.update(changes)
    return f"{parts.path}?{urlencode(pairs)}"


# ============================================================ lo que pasa


def test_a_temporary_signed_link_opens() -> None:
    link = URL.temporary_signed("/reportes/42", timedelta(minutes=5), purpose="report.download")
    response = TestClient(_app()).get(link)

    assert response.status_code == 200
    assert response.json() == {"report": 42}


def test_the_domain_is_not_part_of_the_signature() -> None:
    """Se firma el path: el enlace con el dominio público funciona aunque la app lo reciba con
    otro Host (proxy, túnel). Es el parche de `forceRootUrl` que aquí no hace falta."""
    link = URL.temporary_signed(
        "/reportes/42", timedelta(minutes=5), purpose="report.download", base_url="https://pld.cliente.mx/"
    )
    assert link.startswith("https://pld.cliente.mx/reportes/42?")

    assert TestClient(_app()).get(_path_and_query(link)).status_code == 200


def test_reordering_the_query_does_not_break_it() -> None:
    link = URL.temporary_signed("/plain", timedelta(minutes=5), {"b": "2", "a": "1"})
    parts = urlsplit(link)
    reordered = "&".join(reversed(parts.query.split("&")))

    assert TestClient(_app()).get(f"{parts.path}?{reordered}").status_code == 200


def test_a_previous_key_still_verifies_after_rotation(monkeypatch: MonkeyPatch) -> None:
    old_link = URL.temporary_signed("/plain", timedelta(minutes=5))
    monkeypatch.setattr(settings, "url_signing_key", "llave-nueva-" + "x" * 40)
    monkeypatch.setattr(settings, "url_signing_previous_keys", _KEY)

    assert TestClient(_app()).get(old_link).status_code == 200


def test_a_link_mounted_under_a_root_path_still_verifies() -> None:
    link = URL.temporary_signed("/plain", timedelta(minutes=5))
    client = TestClient(_app(), root_path="/consola")

    assert client.get(f"/consola{link}").status_code == 200


# ============================================================ lo que no pasa


def test_changing_a_parameter_breaks_the_signature() -> None:
    link = URL.temporary_signed("/plain", timedelta(minutes=5), {"user": "7"})
    response = TestClient(_app()).get(_with_query(link, user="8"))

    assert response.status_code == 403
    assert response.json()["code"] == "invalid_signature"


def test_stretching_the_expiry_breaks_the_signature() -> None:
    link = URL.temporary_signed("/plain", timedelta(minutes=5))
    later = str(int(time.time()) + 10 * 365 * 24 * 3600)

    assert TestClient(_app()).get(_with_query(link, expires=later)).json()["code"] == "invalid_signature"


def test_an_expired_link_says_so() -> None:
    link = URL.temporary_signed("/plain", datetime.now(UTC) - timedelta(seconds=1))
    response = TestClient(_app()).get(link)

    assert response.status_code == 403
    assert response.json()["code"] == "signature_expired"


def test_a_signature_for_one_path_does_not_open_another() -> None:
    link = URL.temporary_signed("/reportes/1", timedelta(minutes=5), purpose="report.download")
    forged = _path_and_query(link).replace("/reportes/1?", "/reportes/2?")

    assert TestClient(_app()).get(forged).status_code == 403


def test_a_signature_for_one_purpose_does_not_serve_another() -> None:
    """Misma ruta, otro propósito: la llave de cada propósito es distinta."""
    link = URL.temporary_signed("/reportes/42", timedelta(minutes=5), purpose="account.activation")

    assert TestClient(_app()).get(link).json()["code"] == "invalid_signature"


def test_without_signature_or_with_two_it_is_rejected() -> None:
    link = URL.temporary_signed("/plain", timedelta(minutes=5))
    signature = dict(parse_qsl(urlsplit(link).query))["signature"]
    client = TestClient(_app())

    assert client.get("/plain").status_code == 403
    assert client.get(f"{link}&signature={signature}").status_code == 403


def test_an_unknown_key_does_not_verify(monkeypatch: MonkeyPatch) -> None:
    link = URL.temporary_signed("/plain", timedelta(minutes=5))
    monkeypatch.setattr(settings, "url_signing_key", "otra-llave-" + "y" * 40)

    assert TestClient(_app()).get(link).status_code == 403


# ============================================================ cómo se usa mal


def test_signing_without_a_key_fails_loudly(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "url_signing_key", "")
    with pytest.raises(SigningKeyMissingError, match="URL_SIGNING_KEY"):
        URL.temporary_signed("/plain", timedelta(minutes=5))


def test_reserved_parameters_and_relative_paths_are_rejected() -> None:
    with pytest.raises(ValueError):
        URL.temporary_signed("/plain", timedelta(minutes=5), {"expires": "1"})
    with pytest.raises(ValueError):
        URL.temporary_signed("plain", timedelta(minutes=5))
    with pytest.raises(ValueError):
        URL.temporary_signed("/plain", datetime.now() + timedelta(minutes=5))  # naive
