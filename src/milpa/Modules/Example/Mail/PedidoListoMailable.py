"""Ejemplo de Mailable MONOLINGÜE: el caso de "cuándo NO usar i18n".

Todo el texto va hardcodeado en el idioma del proyecto (español): el subject es
un string literal y el template no llama `t()` ni extiende los layouts compartidos
(`master`/`mastersigned`, que sí usan i18n). NO toca locale para nada.

Es el default estilo Laravel/Spring: una app es monolingüe salvo que el dev decida
traducir. Contrasta con `MailableSignedCheck` (multilingüe: usa `t()` + el locale
ambiente que viene del header Accept-Language). Mismo `Mail.send`/`Mail.queue` para
ambos; la diferencia es solo si el Mailable usa `t()` o escribe el texto directo.
"""

from __future__ import annotations

from milpa.Core.Mail.Mailable import Mailable, MailContent


class PedidoListoMailable(Mailable):
    """Avisa que un pedido está listo. Texto fijo en español, sin i18n."""

    def __init__(self, cliente: str, folio: str):
        # Solo primitivos (serializable para la cola, igual que cualquier Mailable).
        self._cliente = cliente
        self._folio = folio

    def build(self) -> MailContent:
        # Subject LITERAL (sin translate) y template con texto fijo (sin t()).
        # Ni `locale` ni catálogos YAML: esta app/correo es de un solo idioma.
        # `template` usa el mismo nombrado de vistas que view() (convencion Jinja, "/"):
        #   "example/mail/pedido_listo" -> prefijo "example" = MODULO -> su carpeta de vistas
        #     -> app/Modules/Example/Resources/Views/mail/pedido_listo.html.j2
        #   (los layouts de correo COMPARTIDOS van sin prefijo: "Emails/Trans/master.html.j2").
        return MailContent(
            subject=f"Tu pedido {self._folio} ya está listo",
            template="example/mail/pedido_listo.html.j2",
            context={"cliente": self._cliente, "folio": self._folio},
        )
