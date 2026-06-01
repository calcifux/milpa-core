"""Infraestructura de envío de correo (= CÓMO se manda).

Aquí viven el ABC `Mailable`, el `Mailer` (SMTP/MIME), la facade `Mail` y la task
`mail.send` de Celery. El motor de templates (Jinja2) vive en `app/Core/View`
(es compartido con las vistas web); los Mailables demo viven en `Modules/Example`.

NO aquí: los servicios de DOMINIO del correo (resolución de destinatarios, reglas
de quién recibe qué). Eso es propio de cada proyecto y vive en su módulo
(p. ej. `app/Modules/<Modulo>/Services/MailService`), no en el framework.

Punto de entrada recomendado: la facade `Mail` (`Mail.send` / `Mail.queue`),
re-exportada aquí. Importarla NO jala Celery/redis (eso es perezoso en `queue`).
"""

from milpa.Core.Mail.Mail import Mail
from milpa.Core.Mail.Mailable import Mailable, MailContent

__all__ = ["Mail", "Mailable", "MailContent"]
