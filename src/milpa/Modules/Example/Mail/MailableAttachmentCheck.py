"""Mailable de smoke para ADJUNTOS: signed + logo + un PDF "tonto" generado al vuelo.

Demuestra los DOS caminos de adjuntar, que conviven en el framework:

  • bytes en memoria (default, recomendado): el PDF se genera en `build()` y se
    manda como `DataAttachment` — sin tocar disco, sin temporales que limpiar. En
    encolado los bytes no viajan por la cola (build corre en el worker).

  • archivo en disco + cleanup OPT-IN (`as_file=True`): escribe el PDF a un
    temporal, lo adjunta POR RUTA y declara esa ruta en `cleanup_paths` → el Mailer
    la borra en su `finally` tras enviar. Es el ejemplo para el dev (jr) que arma el
    archivo y lo tira al /temp: así ve CÓMO pedir que se limpie. Si NO lo declara,
    el archivo se queda — el framework nunca borra adjuntos por su cuenta.

Hereda de [[MailableSignedCheck]] para reusar el layout firmado + logo + firmante.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from milpa.Core.Mail.Mailable import DataAttachment, MailContent
from milpa.Modules.Example.Mail.MailableSignedCheck import MailableSignedCheck


def _build_dummy_pdf_bytes() -> bytes:
    """Construye en memoria un PDF mínimo VÁLIDO de 1 página con texto (sin libs)."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 144] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 16 Tf 24 100 Td (milpa - dummy attachment) Tj ET"
    objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = b"%PDF-1.4\n"
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (index, body)
    xref_position = len(pdf)
    count = len(objects) + 1
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % count
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (count, xref_position)
    return pdf


def _write_temp_pdf(pdf_bytes: bytes) -> Path:
    """Escribe los bytes a un archivo temporal del SO y devuelve su ruta (delete=False).

    Simula al dev que arma el PDF y lo deja en /temp. El borrado NO es aquí: se
    delega al Mailer vía `cleanup_paths` (opt-in), tras el envío.
    """
    temp_file = tempfile.NamedTemporaryFile(prefix="milpa_demo_", suffix=".pdf", delete=False)
    try:
        temp_file.write(pdf_bytes)
    finally:
        temp_file.close()
    return Path(temp_file.name)


class MailableAttachmentCheck(MailableSignedCheck):
    """Smoke de adjuntos: hereda el layout firmado y suma un PDF generado al vuelo."""

    def __init__(self, name: str, logo_path: str | None = None, as_file: bool = False):
        # `as_file`: False = adjuntar por bytes (default); True = temporal en disco + cleanup.
        # El locale se lee del AMBIENTE (no se recibe). Ver Core/Translate.
        super().__init__(name=name, logo_path=logo_path)
        self._as_file = as_file

    def build(self) -> MailContent:
        # Reusamos el contenido firmado (subject + template + contexto + logo).
        content = super().build()
        pdf_bytes = _build_dummy_pdf_bytes()
        if self._as_file:
            # archivo en disco + cleanup OPT-IN declarado.
            temp_path = _write_temp_pdf(pdf_bytes)
            content.attachments.append(temp_path)
            content.cleanup_paths.append(temp_path)
        else:
            # bytes en memoria (sin archivo, sin cleanup).
            content.data_attachments.append(DataAttachment("demo.pdf", pdf_bytes, "application/pdf"))
        return content
