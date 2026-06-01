"""Tests de la task `mail.send`: política de reintentos ante fallos transitorios.

Sin redis ni SMTP reales: el resolver del Mailable y el mailer se monkeypatchean
con fakes, y los reintentos se ejercitan en modo `task_always_eager` (síncrono, sin
worker), con el backoff anulado para que el test no duerma. Mismo patrón de fakes +
monkeypatch del resto de la suite (cero BD/red).
"""

from __future__ import annotations

import smtplib
from typing import Any

from pytest import MonkeyPatch

from milpa.Core.CeleryApp import celery_app
from milpa.Core.Config import settings
from milpa.Core.Mail import Tasks
from milpa.Core.Mail.Mailable import MailContent
from milpa.Core.Mail.Tasks import send_mail_task


class _FakeMailable:
    """Mailable mínimo. El resolver se monkeypatchea para devolver esta clase, así no
    dependemos de importar un Mailable real por ruta dotted."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def build(self) -> MailContent:
        return MailContent(subject=f"Hola {self.kwargs.get('name', '')}", template="t.j2")


class _RecordingMailer:
    """Mailer fake: registra cada envío y falla las primeras `fail_times` veces con un
    error TRANSITORIO (simula un SMTP que se cae y luego se recupera)."""

    def __init__(self, fail_times: int = 0) -> None:
        self.calls: list[tuple[MailContent, list[str]]] = []
        self._fail_times = fail_times

    def send(
        self,
        content: MailContent,
        *,
        to: list[str],
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> None:
        self.calls.append((content, to))
        if len(self.calls) <= self._fail_times:
            raise smtplib.SMTPServerDisconnected("SMTP caído (transitorio)")


def _patch_resolver_and_mailer(monkeypatch: MonkeyPatch, mailer: _RecordingMailer) -> None:
    monkeypatch.setattr(Tasks, "default_mailer", mailer)
    monkeypatch.setattr(Tasks, "_resolve_mailable_class", lambda _path: _FakeMailable)


def _force_eager_without_sleeping(monkeypatch: MonkeyPatch, *, max_retries: int) -> None:
    """Ejecuta la task en el acto (sin worker) y anula el backoff para no dormir."""
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(send_mail_task, "max_retries", max_retries)
    monkeypatch.setattr(send_mail_task, "retry_backoff", False)
    monkeypatch.setattr(send_mail_task, "retry_jitter", False)
    monkeypatch.setattr(send_mail_task, "default_retry_delay", 0)


def test_mail_send_task_has_retry_policy() -> None:
    """La task declara reintentos SOLO para errores transitorios, con backoff + jitter
    (defaults framework-wide vía retry_policy/.env)."""
    assert send_mail_task.max_retries == settings.task_max_retries
    assert smtplib.SMTPException in send_mail_task.autoretry_for
    assert ConnectionError in send_mail_task.autoretry_for
    assert TimeoutError in send_mail_task.autoretry_for
    assert send_mail_task.retry_backoff == settings.task_retry_backoff
    assert send_mail_task.retry_backoff_max == settings.task_retry_backoff_max
    assert send_mail_task.retry_jitter is True


def test_mail_send_task_happy_path_sends_once(monkeypatch: MonkeyPatch) -> None:
    """Camino feliz: reinstancia el Mailable y manda exactamente una vez."""
    mailer = _RecordingMailer()
    _patch_resolver_and_mailer(monkeypatch, mailer)

    send_mail_task(
        mailable_class_path="x.Y",
        mailable_kwargs={"name": "Memo"},
        to=["a@example.com"],
    )

    assert len(mailer.calls) == 1
    content, to = mailer.calls[0]
    assert to == ["a@example.com"]
    assert content.subject == "Hola Memo"


def test_mail_send_task_retries_until_exhausted(monkeypatch: MonkeyPatch) -> None:
    """SMTP siempre caído: reintenta hasta max_retries y la task queda en FALLO."""
    _force_eager_without_sleeping(monkeypatch, max_retries=2)
    mailer = _RecordingMailer(fail_times=99)
    _patch_resolver_and_mailer(monkeypatch, mailer)

    result = send_mail_task.apply(kwargs={"mailable_class_path": "x.Y", "mailable_kwargs": {}, "to": ["a@example.com"]})

    # 1 intento + 2 reintentos = 3 ejecuciones; agotados los reintentos, la task falla.
    assert len(mailer.calls) == 3
    assert result.failed()


def test_mail_send_task_recovers_within_budget(monkeypatch: MonkeyPatch) -> None:
    """SMTP se recupera dentro del presupuesto de reintentos: el correo SÍ se envía."""
    _force_eager_without_sleeping(monkeypatch, max_retries=3)
    mailer = _RecordingMailer(fail_times=2)  # falla 2 veces, al 3er intento envía
    _patch_resolver_and_mailer(monkeypatch, mailer)

    result = send_mail_task.apply(kwargs={"mailable_class_path": "x.Y", "mailable_kwargs": {}, "to": ["a@example.com"]})

    assert len(mailer.calls) == 3
    assert result.successful()
