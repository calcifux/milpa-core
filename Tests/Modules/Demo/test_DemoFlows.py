"""Tests EJECUTABLES de los flujos AUTO (evento → Observer → correo), SIN BD ni SMTP.

Cierra el gap pedagógico: prueban que `dispatch(UserRegistered/NoteCreated)` llega al Observer y
este invoca `Mail.send` con los datos correctos (el corazón auto-vs-manual del demo). La rama
encolada se fuerza a síncrono monkeypatcheando `enqueue_observer` (igual que test_EventDispatch);
los observers se re-registran con reload tras `reset_observers` para no depender del orden de la suite.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

import pytest
from pytest import MonkeyPatch

import milpa.Core.Events.Tasks as events_tasks
import milpa.Modules.Demo.Observers.NotifyAdminOnUserRegistered as admin_obs
import milpa.Modules.Demo.Observers.NotifyOwnerOnNoteCreated as owner_obs
from milpa.Core.CeleryApp import QueueUnavailableError
from milpa.Core.Events import Observer, dispatch, reset_observers
from milpa.Core.Mail import Mail
from milpa.Modules.Demo.Events import NoteCreated, UserRegistered
from milpa.Modules.Demo.Mail.NewUserAdminMailable import NewUserAdminMailable
from milpa.Modules.Demo.Mail.NoteCreatedMailable import NoteCreatedMailable
from milpa.Modules.Demo.Repositories.UserRepository import UserRepository


class _FakeUser:
    """Usuario fake para monkeypatchear UserRepository.all sin tocar BD."""

    def __init__(self, email: str, roles: list[str]) -> None:
        self.email = email
        self._roles = roles

    def get_roles(self) -> list[str]:
        return self._roles


def _no_broker(observer_cls: type[Observer], event: object) -> None:
    raise QueueUnavailableError("sin broker")  # fuerza el fallback síncrono del dispatch


@pytest.fixture(autouse=True)
def _clean_observers() -> Iterator[None]:
    reset_observers()
    yield
    reset_observers()


@pytest.fixture
def captured_mail(monkeypatch: MonkeyPatch) -> list[dict[str, Any]]:
    """Captura las llamadas a Mail.send (sin SMTP) y fuerza dispatch síncrono."""
    sent: list[dict[str, Any]] = []

    def _fake_send(mailable: Any, *, to: list[str], cc: Any = None, bcc: Any = None) -> None:
        sent.append({"mailable": mailable, "to": to})

    monkeypatch.setattr(Mail, "send", _fake_send)
    monkeypatch.setattr(events_tasks, "enqueue_observer", _no_broker)
    return sent


def test_note_created_emails_owner_in_event_locale(captured_mail: list[dict[str, Any]]) -> None:
    importlib.reload(owner_obs)  # re-registra NotifyOwnerOnNoteCreated tras el reset
    dispatch(NoteCreated(note_id=1, title="Mi nota", owner_id=7, owner_email="o@x.com", locale="es"))

    assert len(captured_mail) == 1
    call = captured_mail[0]
    assert call["to"] == ["o@x.com"]
    assert isinstance(call["mailable"], NoteCreatedMailable)
    assert call["mailable"].build().subject == "Tu nota «Mi nota» fue creada"


def test_observer_ignores_events_of_other_type(captured_mail: list[dict[str, Any]]) -> None:
    importlib.reload(owner_obs)  # solo el observer de NoteCreated está registrado
    dispatch(UserRegistered(user_id=1, name="X", email="x@x.com"))
    assert captured_mail == []  # observes=NoteCreated no matchea UserRegistered


def test_user_registered_emails_only_admins(monkeypatch: MonkeyPatch, captured_mail: list[dict[str, Any]]) -> None:
    importlib.reload(admin_obs)
    monkeypatch.setattr(
        UserRepository, "all", lambda self: [_FakeUser("admin@x.com", ["admin"]), _FakeUser("user@x.com", [])]
    )
    dispatch(UserRegistered(user_id=2, name="Ana", email="ana@x.com"))

    assert len(captured_mail) == 1
    assert captured_mail[0]["to"] == ["admin@x.com"]  # solo el admin, no el usuario normal
    assert isinstance(captured_mail[0]["mailable"], NewUserAdminMailable)


def test_user_registered_without_admins_sends_nothing(
    monkeypatch: MonkeyPatch, captured_mail: list[dict[str, Any]]
) -> None:
    importlib.reload(admin_obs)
    monkeypatch.setattr(UserRepository, "all", lambda self: [_FakeUser("user@x.com", [])])
    dispatch(UserRegistered(user_id=3, name="Beto", email="beto@x.com"))
    assert captured_mail == []  # sin admins → early-return, no envía (cubre esa rama)
