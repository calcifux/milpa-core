"""Base de los correos del demo: la "plantilla general firmada".

Aporta la FIRMA común (`sender_*`) que consume el layout firmado COMPARTIDO del framework
(`Emails/Trans/mastersigned.html.j2` → header + content + footer firmado + aviso de privacidad).
Cada Mailable específico solo define `subject`, su `template` (que `{% extends %}` el firmado) y
su contexto propio. Así se demuestra tu idea: una plantilla general + correos específicos encima.

(En un proyecto real, `sender_*` vendría del remitente configurado, no hardcodeado.)
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from milpa.Core.Mail import Mailable, MailContent


class DemoMailable(Mailable):
    """Base abstracta de los correos del demo. NO implementa `build()` (las subclases sí);
    expone `_signed(...)` que inyecta la firma común en el contexto del layout firmado."""

    _SIGNER: ClassVar[dict[str, str]] = {
        "sender_name": "Equipo milpa",
        "sender_phone": "+52 55 0000 0000",
        "sender_email": "no-reply@milpa.dev",
        "sender_address": "CDMX, México",
    }
    # Logo de marca: el layout firmado (mastersigned) renderiza <img src="cid:logo"> si viene
    # `logo_cid`. Se EMBEBE por CID (no URL) para que se vea sin conexión y sin hotlinking.
    _LOGO: ClassVar[Path] = Path(__file__).resolve().parents[1] / "Resources" / "Static" / "logo.png"

    def _signed(self, *, subject: str, template: str, context: dict[str, object] | None = None) -> MailContent:
        """Arma un `MailContent` con la firma común + el LOGO embebido + el contexto del correo."""
        ctx: dict[str, object] = {**self._SIGNER, **(context or {})}
        inline: dict[str, Path] = {}
        if self._LOGO.is_file():  # best-effort: si falta el logo, el correo sale igual (sin marca)
            ctx["logo_cid"] = "logo"
            inline["logo"] = self._LOGO
        return MailContent(subject=subject, template=template, context=ctx, inline_assets=inline)
