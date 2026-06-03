"""Observer: avisa a los admins cuando se registra un usuario nuevo.

Reacciona a `UserRegistered` (1:N). Consulta los usuarios con rol admin y les manda el
`NewUserAdminMailable`. Usa `Mail.send` (síncrono): la adaptabilidad de transporte ya ocurre a
nivel del OBSERVER (corre en el worker si hay broker, si no síncrono) — encolar el correo aquí
sería encolar dentro de un task. Hace una lectura a BD (`@auto_session` abre scope si no hay): un
observer PUEDE leer la BD; lo que evitamos es ATARLO a ella (no es un model-observer de Eloquent).
"""

from __future__ import annotations

from milpa.Core.Events import Observer
from milpa.Core.Mail import Mail
from milpa.Modules.Demo.Events import UserRegistered
from milpa.Modules.Demo.Mail.NewUserAdminMailable import NewUserAdminMailable
from milpa.Modules.Demo.Repositories.UserRepository import UserRepository


class NotifyAdminOnUserRegistered(Observer):
    observes = UserRegistered

    def handle(self, event: object) -> None:
        assert isinstance(event, UserRegistered)  # dispatch ya filtró por tipo; narrow para mypy
        admin_emails = [user.email for user in UserRepository().all() if "admin" in user.get_roles()]
        if not admin_emails:
            return  # sin admins a quién avisar (p. ej. antes del primer seed)
        Mail.send(NewUserAdminMailable(name=event.name, email=event.email), to=admin_emails)
