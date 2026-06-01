"""Controller de EJEMPLO para correos: un endpoint por caso de uso, para saber
QUE usar y CUANDO. Se auto-monta solo (Registry.iter_routers recolecta el `router`).

Casos cubiertos:
  - /sync             -> Mail.send SINCRONO (sin redis/worker; respuesta confirma envio).
  - /queue            -> Mail.queue a la cola POR DEFECTO (requiere `queue work`).
  - /queue-named      -> Mail.queue a una cola con NOMBRE (requiere `queue work --queue=emails`).
  - /attachment       -> encolado + PDF adjunto POR BYTES (sin archivo en disco).
  - /attachment-path  -> encolado + adjunto POR RUTA de un archivo persistente (no se borra).
  - /attachment-file  -> encolado + PDF adjunto POR ARCHIVO temporal + cleanup opt-in.
  - /plain            -> Mail.send simple (MailableCheck), sin firma ni adjuntos.

Idioma: AUTOMATICO. La dependency global de FastAPI ya fijo el locale (del header
Accept-Language) en el contextvar; el render lo usa solo, y al encolar `Mail.queue`
captura ese locale y el worker lo restaura. Por eso aqui NO se toca el locale.

El logo va por la ruta convencional del proyecto (capa de Modules, no Core).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from milpa.Core.CeleryApp import QueueUnavailableError
from milpa.Core.Mail import Mail
from milpa.Modules.Example.Mail.MailableAttachmentCheck import MailableAttachmentCheck
from milpa.Modules.Example.Mail.MailableCheck import MailableCheck
from milpa.Modules.Example.Mail.MailableSignedCheck import MailableSignedCheck
from milpa.Modules.Example.Mail.PedidoListoMailable import PedidoListoMailable

router = APIRouter(prefix="/example/mail", tags=["example-mail"])

# Ruta convencional del logo de marca (capa de proyecto). Si no existe, el Mailable
# simplemente no embebe logo (no truena).
_LOGO = "src/milpa/Resources/Images/Emails/logo.png"
# Cola con nombre de ejemplo (= ->onQueue('emails') de Laravel).
_NAMED_QUEUE = "emails"
# Archivo PERSISTENTE del proyecto para adjuntar por ruta SIN borrarlo.
_SAMPLE_PDF = "src/milpa/Resources/Files/Emails/sample.pdf"


def _recipients(to: str) -> list[str]:
    """Convierte 'a@x.com,b@y.com' en lista, descartando vacios."""
    return [recipient.strip() for recipient in to.split(",") if recipient.strip()]


def _queue_or_503(mailable: Any, *, to: list[str], init_kwargs: dict[str, Any], queue: str | None = None) -> None:
    """Encola traduciendo un broker caido a un 503 limpio (no un 500 tecnico)."""
    try:
        Mail.queue(mailable, to=to, queue=queue, init_kwargs=init_kwargs)
    except QueueUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/sync")
def mail_sync(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """SINCRONO (Mail.send): arma y manda YA por SMTP. NO usa redis ni worker.

    Cuando usarlo: sin broker disponible, o cuando necesitas que la respuesta HTTP
    confirme el envio (bloquea hasta que SMTP responde). Para no bloquear, usa /queue.
    """
    Mail.send(MailableSignedCheck(name=name, logo_path=_LOGO), to=_recipients(to))
    return {"mode": "sync", "to": _recipients(to)}


@router.get("/queue")
def mail_queue(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """ENCOLADO a la cola POR DEFECTO (Mail.queue). No bloquea: responde al instante.

    Cuando usarlo: el caso normal en produccion (el envio corre en el worker).
    Requiere redis + `queue work`. Si el broker esta caido -> 503.
    """
    mailable = MailableSignedCheck(name=name, logo_path=_LOGO)
    _queue_or_503(mailable, to=_recipients(to), init_kwargs={"name": name, "logo_path": _LOGO})
    return {"mode": "queue", "queue": "(por defecto)", "to": _recipients(to)}


@router.get("/queue-named")
def mail_queue_named(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """ENCOLADO a una cola con NOMBRE (= ->onQueue('emails')). Para separar cargas.

    Cuando usarlo: cuando quieres dedicar un worker a ciertos correos. Requiere
    `queue work --queue=emails` consumiendo esa cola; si no, el mensaje se queda ahi.
    """
    mailable = MailableSignedCheck(name=name, logo_path=_LOGO)
    _queue_or_503(mailable, to=_recipients(to), init_kwargs={"name": name, "logo_path": _LOGO}, queue=_NAMED_QUEUE)
    return {"mode": "queue", "queue": _NAMED_QUEUE, "to": _recipients(to)}


@router.get("/attachment")
def mail_attachment_bytes(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """ENCOLADO + PDF adjunto POR BYTES (sin archivo en disco). Recomendado.

    Cuando usarlo: cuando generas el PDF/XML en memoria (p. ej. un reporte). No crea
    temporales, no hay que limpiar nada, y los bytes no engordan la cola (build()
    corre en el worker). El logo va inline por CID.
    """
    mailable = MailableAttachmentCheck(name=name, logo_path=_LOGO, as_file=False)
    init_kwargs = {"name": name, "logo_path": _LOGO, "as_file": False}
    _queue_or_503(mailable, to=_recipients(to), init_kwargs=init_kwargs)
    return {"mode": "queue", "attachment": "bytes", "to": _recipients(to)}


@router.get("/attachment-path")
def mail_attachment_path(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """ENCOLADO + adjunto POR RUTA de un archivo que YA existe, sin borrarlo.

    Cuando usarlo: adjuntar un asset PERSISTENTE del proyecto (un PDF fijo, un
    catalogo, etc.). Se pasa en attachment_paths y NO se declara en cleanup_paths,
    asi que el framework lo adjunta y lo deja intacto (= ->attach($path) de Laravel).
    """
    mailable = MailableSignedCheck(name=name, logo_path=_LOGO, attachment_paths=[_SAMPLE_PDF])
    init_kwargs = {"name": name, "logo_path": _LOGO, "attachment_paths": [_SAMPLE_PDF]}
    _queue_or_503(mailable, to=_recipients(to), init_kwargs=init_kwargs)
    return {"mode": "queue", "attachment": "ruta (no se borra)", "file": _SAMPLE_PDF}


@router.get("/attachment-file")
def mail_attachment_file(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """ENCOLADO + PDF adjunto POR ARCHIVO temporal + cleanup OPT-IN.

    Cuando usarlo: cuando el PDF YA vive como archivo en disco. El Mailable lo declara
    en cleanup_paths y el Mailer lo borra tras enviar (en su finally). El framework
    NUNCA borra adjuntos que no declares. Mira el log del worker: 'temporal borrado'.
    """
    mailable = MailableAttachmentCheck(name=name, logo_path=_LOGO, as_file=True)
    init_kwargs = {"name": name, "logo_path": _LOGO, "as_file": True}
    _queue_or_503(mailable, to=_recipients(to), init_kwargs=init_kwargs)
    return {"mode": "queue", "attachment": "file+cleanup", "to": _recipients(to)}


@router.get("/plain")
def mail_plain(to: str = "test@yopmail.com", name: str = "Calcifux") -> dict[str, Any]:
    """SINCRONO sin firma ni logo (MailableCheck): el correo mas simple posible.

    Cuando usarlo: para ver el layout base (master) sin footer firmado ni adjuntos.
    """
    Mail.send(MailableCheck(name=name), to=_recipients(to))
    return {"mode": "sync", "template": "master", "to": _recipients(to)}


@router.get("/monolingual")
def mail_monolingual(to: str = "test@yopmail.com", cliente: str = "Calcifux") -> dict[str, Any]:
    """MONOLINGUE: subject + template hardcodeados, SIN i18n (no t(), no locale).

    Cuando usarlo: app de un solo idioma. Ignora Accept-Language por completo; el
    texto va fijo en el Mailable y en su template (no extiende los layouts con t()).
    Mismo Mail.send/Mail.queue que los demas; la unica diferencia es no usar i18n.
    """
    Mail.send(PedidoListoMailable(cliente=cliente, folio="A-001"), to=_recipients(to))
    return {"mode": "sync", "i18n": "no", "to": _recipients(to)}
