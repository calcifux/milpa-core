"""Aviso AUTOMÁTICO al admin: "se registró un usuario nuevo".

Lo manda el observer NotifyAdminOnUserRegistered (1:N) cuando se dispara `UserRegistered`.
Monolingüe (ES): es una notificación interna al equipo, no al usuario final → sin i18n.
"""

from __future__ import annotations

from milpa.Core.Mail import MailContent
from milpa.Modules.Demo.Mail.DemoMailable import DemoMailable


class NewUserAdminMailable(DemoMailable):
    """Correo al admin con los datos del usuario recién registrado."""

    def __init__(self, name: str, email: str) -> None:
        # Solo primitivos (serializable para la cola, igual que cualquier Mailable).
        self._name = name
        self._email = email

    def build(self) -> MailContent:
        return self._signed(
            subject=f"Nuevo usuario registrado: {self._name}",
            template="demo/emails/new_user_admin.html.j2",
            context={"new_user_name": self._name, "new_user_email": self._email},
        )
