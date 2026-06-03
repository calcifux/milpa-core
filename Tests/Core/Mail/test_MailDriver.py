"""Tests del MAIL_DRIVER: los drivers `log`/`null` NUNCA abren una conexión SMTP.

Es lo que hace seguro el fallback cross-platform: sin red, sin sorpresas. Si el
Mailer intentara conectar con estos drivers, el fake `_boom` rompería el test.

Construimos un `MailContent` directo (sin depender de ningún Mailable concreto:
los Mailables demo viven en Modules/Demo, y este es un test de Core).
"""

from __future__ import annotations

import smtplib
from typing import Any

import pytest
from pytest import MonkeyPatch

from milpa.Core.Config import settings
from milpa.Core.Mail.Mailable import MailContent
from milpa.Core.Mail.Mailer import Mailer


def _boom(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("No debió abrirse una conexión SMTP con este driver.")


def _sample_content() -> MailContent:
    # Layout compartido de Core; renderiza con context vacío (StrictUndefined-safe).
    return MailContent(subject="smoke", template="Emails/Trans/master.html.j2", context={})


@pytest.mark.parametrize("driver", ["null", "array", "log"])
def test_non_smtp_drivers_never_open_a_connection(driver: str, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mail_driver", driver)
    monkeypatch.setattr(smtplib, "SMTP", _boom)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _boom)

    # No debe lanzar: el correo se descarta (null/array) o se escribe al log (log).
    Mailer().send(_sample_content(), to=["a@x.com"])
