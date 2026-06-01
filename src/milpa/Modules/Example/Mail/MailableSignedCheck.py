"""Mailable de smoke para el layout FIRMADO (`Emails/Trans/mastersigned.html.j2`).

Gemelo de [[MailableCheck]] pero ejercitando el layout con firma: además del
header + contenido, renderiza el footer firmado (`Emails/Trans/Footer/email_footer`)
con los datos del firmante (`sender_*`) y el aviso de privacidad
(`Emails/mastersigned.privacy_message`, que usa `%{app_name}`).

Sirve para verificar de un vistazo en Mailpit que: la herencia del layout
firmado funciona, los estilos (`Emails/Trans/Styles/basic`) se incluyen, y el footer
con datos del firmante + aviso legal genérico (sin marca) se ve bien.

Se invoca desde el CLI con `uv run python jornal mail test --signed`.

Nombre sin prefijo `Test*` por la misma razón que [[MailableCheck]]: evitar que
pytest intente colectarlo.
"""

from __future__ import annotations

from pathlib import Path

from milpa.Core.Mail.Mailable import Mailable, MailContent
from milpa.Core.Translate import current_locale
from milpa.Core.Translate import t as translate


class MailableSignedCheck(Mailable):
    """Mailable de prueba con firma — mismo cuerpo que MailableCheck + footer firmado."""

    def __init__(
        self,
        name: str,
        logo_path: str | None = None,
        attachment_paths: list[str] | None = None,
    ):
        # Solo primitivos: el Celery task puede reinstanciarlo sin problema.
        # `logo_path`: ruta (str) a la imagen de marca a embeber por CID.
        # `attachment_paths`: LISTA de rutas a adjuntar (1 o N).
        # El locale se lee del AMBIENTE (no se recibe). Ver Core/Translate.
        self._name = name
        self._logo_path = logo_path
        self._attachment_paths = attachment_paths or []

    def build(self) -> MailContent:
        subject = translate("Emails/test.subject", {"active_locale": current_locale()})
        context: dict[str, object] = {
            "name": self._name,
            # Datos del firmante que consume el footer (= `sender_*` del
            # legacy). Hardcoded para el smoke; en un Mailable real vienen
            # del remitente configurado. El aviso de privacidad usa
            # `%{app_name}`, que el i18n inyecta solo (APP_NAME del .env).
            "sender_name": self._name,
            "sender_phone": "+52 XX XXX XXXX",
            "sender_email": "remitente@example.com",
            "sender_address": "Calle Falsa 123, CDMX",
        }
        inline_assets: dict[str, Path] = {}
        # Logo embebido por CID (= $message->embed()) si la ruta existe.
        if self._logo_path and Path(self._logo_path).is_file():
            context["logo_cid"] = "logo"
            inline_assets["logo"] = Path(self._logo_path)
        # Adjuntos: solo los que existan (los faltantes se ignoran).
        attachments = [Path(p) for p in self._attachment_paths if Path(p).is_file()]
        return MailContent(
            subject=subject,
            template="Emails/Trans/testsigned.html.j2",
            context=context,
            inline_assets=inline_assets,
            attachments=attachments,
        )
