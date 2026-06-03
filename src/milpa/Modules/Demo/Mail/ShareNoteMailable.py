"""Compartir una nota por correo: el correo MANUAL (on-demand), no por evento.

Lo manda directo el endpoint `POST /api/notes/{id}/share` con `Mail.send(...)` AHORA mismo —
contrasta con los automáticos por Observer. Mismo `Mailable`/layout firmado; lo que cambia es el
DISPARADOR (una acción explícita del usuario vs. un hecho de dominio observado).
"""

from __future__ import annotations

from milpa.Core.Mail import MailContent
from milpa.Modules.Demo.Mail.DemoMailable import DemoMailable


class ShareNoteMailable(DemoMailable):
    """Envía el contenido de una nota a un destinatario, de parte de quien la comparte."""

    def __init__(self, title: str, body: str, from_name: str) -> None:
        self._title = title
        self._body = body
        self._from_name = from_name

    def build(self) -> MailContent:
        return self._signed(
            subject=f"{self._from_name} te compartió una nota: {self._title}",
            template="demo/emails/share_note.html.j2",
            context={"title": self._title, "body": self._body, "from_name": self._from_name},
        )
