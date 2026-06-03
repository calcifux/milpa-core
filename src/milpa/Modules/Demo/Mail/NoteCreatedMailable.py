"""Confirmación AUTOMÁTICA al dueño: "tu nota fue creada". MULTILINGÜE (i18n).

Lo manda el observer NotifyOwnerOnNoteCreated cuando se dispara `NoteCreated`. El subject y el
cuerpo salen del catálogo (`demo/NoteCreated.{es,en}.yml`) en el `locale` que viajó en el evento
(el del Accept-Language del request original; el worker no lo vería de otro modo). Contrasta con
NewUserAdminMailable, que es monolingüe.
"""

from __future__ import annotations

from milpa.Core.Mail import MailContent
from milpa.Core.Translate import t as translate
from milpa.Modules.Demo.Mail.DemoMailable import DemoMailable


class NoteCreatedMailable(DemoMailable):
    """Correo i18n al dueño de la nota recién creada."""

    def __init__(self, title: str, locale: str = "es") -> None:
        self._title = title
        self._locale = locale

    def build(self) -> MailContent:
        subject = translate("demo/NoteCreated.subject", {"title": self._title}, self._locale)
        return self._signed(
            subject=subject,
            template="demo/emails/note_created.html.j2",
            # `locale` explícito en el contexto: gana sobre el current_locale() que inyecta el
            # Mailer, así el template traduce en el idioma del evento aunque corra en el worker.
            context={"title": self._title, "locale": self._locale},
        )
