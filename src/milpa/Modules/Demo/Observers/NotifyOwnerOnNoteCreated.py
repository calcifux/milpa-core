"""Observer: confirma al DUEÑO cuando se crea su nota.

Reacciona a `NoteCreated` (1:N). Manda el `NoteCreatedMailable` (i18n) al `owner_email` que viajó
en el evento, en el `locale` del evento. No toca BD: todo lo que necesita viene en el evento.
"""

from __future__ import annotations

from milpa.Core.Events import Observer
from milpa.Core.Mail import Mail
from milpa.Modules.Demo.Events import NoteCreated
from milpa.Modules.Demo.Mail.NoteCreatedMailable import NoteCreatedMailable


class NotifyOwnerOnNoteCreated(Observer):
    observes = NoteCreated

    def handle(self, event: object) -> None:
        assert isinstance(event, NoteCreated)  # dispatch ya filtró por tipo; narrow para mypy
        Mail.send(NoteCreatedMailable(title=event.title, locale=event.locale), to=[event.owner_email])
