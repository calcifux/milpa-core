"""Mailable de smoke para validar la infra completa contra Mailpit.

No tiene equivalente en el legacy: es nuestro propio Mailable mínimo que
ejercita Jinja2 + I18n + Mailer end-to-end. Se invoca desde el CLI con
`uv run python jornal mail test [--locale es|en] [--to ...]`.

Usa el layout SIN firma (`Emails/Trans/master.html.j2`). Para ejercitar el layout
firmado (footer + aviso de privacidad) ver [[MailableSignedCheck]].

Nombre `MailableCheck` (no `Test...`): pytest colecta clases `Test*`, y este es
un Mailable real con `__init__` parametrizado — el prefijo lo confundía. Con
este nombre NO se colecta y no necesitamos el truco `__test__ = False`.

Cuando empecemos a portar los Mailables reales (Reminder, Group, etc.) este
archivo se queda como referencia del patrón; cada Mailable de negocio vive en
su módulo (`app/Modules/<X>/Mail/<Algo>Mailable.py`).
"""

from __future__ import annotations

from pathlib import Path

from milpa.Core.Mail.Mailable import Mailable, MailContent
from milpa.Core.Translate import current_locale
from milpa.Core.Translate import t as translate


class MailableCheck(Mailable):
    """Mailable de prueba — saluda al destinatario y enumera la pila usada."""

    def __init__(
        self,
        name: str,
        logo_path: str | None = None,
        attachment_paths: list[str] | None = None,
    ):
        # Solo primitivos: el Celery task puede reinstanciarlo sin problema.
        # `logo_path` es la RUTA (str) a la imagen de marca; Core no conoce la
        # marca, solo embebe lo que el proyecto le pase (se mantiene genérico).
        # `attachment_paths` = LISTA de rutas a adjuntar (1 o N).
        # El locale NO se recibe: se lee del AMBIENTE (contextvar que fijo la
        # frontera HTTP/CLI; el worker lo restaura al encolar). Ver Core/Translate.
        self._name = name
        self._logo_path = logo_path
        self._attachment_paths = attachment_paths or []

    def build(self) -> MailContent:
        # El subject se traduce con el locale AMBIENTE (t() lo lee del contextvar).
        # `active_locale` es solo el valor a mostrar en el texto del subject.
        subject = translate("Emails/test.subject", {"active_locale": current_locale()})
        context: dict[str, object] = {
            "name": self._name,
            # El template del master usa contact_phone en el faq_message
            # (= `:contact_phone` del legacy). Hardcoded para el smoke. El `locale`
            # lo inyecta el Mailer en el render (no lo pasamos aca).
            "contact_phone": "+52 XX XXX XXXX",
        }
        inline_assets: dict[str, Path] = {}
        # Si hay logo y el archivo existe, lo embebemos por CID (= $message->embed()).
        # El template hace `<img src="cid:logo">` cuando `logo_cid` está en el contexto.
        if self._logo_path and Path(self._logo_path).is_file():
            context["logo_cid"] = "logo"
            inline_assets["logo"] = Path(self._logo_path)
        # Adjuntos: solo los que existan (los faltantes se ignoran para no
        # tirar el envío; el command loguea qué se adjuntó realmente).
        attachments = [Path(p) for p in self._attachment_paths if Path(p).is_file()]
        return MailContent(
            subject=subject,
            template="Emails/Trans/test.html.j2",
            context=context,
            inline_assets=inline_assets,
            attachments=attachments,
        )
