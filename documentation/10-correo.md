# Correo

El correo en milpa sigue el patrón **Mailable** de Laravel: una clase encapsula "qué
correo es" (asunto, template, contexto, adjuntos) y la facade `Mail` lo envía, síncrono
o encolado.

```python
from milpa.Core.Mail import Mail
Mail.send(WelcomeMailable(name="Calcifux"), to=["calcifux@example.com"])
```

## Anatomía: `Mailable` + `MailContent`

Un Mailable hereda de la ABC `Mailable` (`milpa/Core/Mail/Mailable.py`) e implementa
`build()`, que devuelve un `MailContent`:

```python
from milpa.Core.Mail.Mailable import Mailable, MailContent
from milpa.Core.Translate import t, current_locale

class WelcomeMailable(Mailable):
    def __init__(self, name: str):
        # SOLO primitivos serializables (ver "Encolar" más abajo).
        self._name = name

    def build(self) -> MailContent:
        return MailContent(
            subject=t("emails.welcome.subject", {"name": self._name}),
            template="mymodule/mail/welcome.html.j2",
            context={"name": self._name, "locale": current_locale()},
        )
```

`build()` arma el **payload puro** — no toca SMTP ni Jinja directamente.

### Campos de `MailContent`

| Campo | Tipo | Para qué | Laravel |
|-------|------|----------|---------|
| `subject` | `str` | Asunto (ya traducido por ti). | `->subject()` |
| `template` | `str` | Ruta del template Jinja (compartido o `modulo/...`). | `->view()` |
| `context` | `dict` | Variables del template. | `->with()` |
| `from_email` / `from_name` | `str \| None` | Remitente; si `None`, usa el default de settings. | `->from()` |
| `inline_assets` | `dict[str, Path]` | CID → ruta (imagen embebida). En HTML: `<img src="cid:logo">`. | `$message->embed()` |
| `attachments` | `list[Path]` | Adjuntos por ruta (archivos en disco). | `->attach()` |
| `data_attachments` | `list[DataAttachment]` | Adjuntos por **bytes** en memoria. | `->attachData()` |
| `cleanup_paths` | `list[Path]` | Rutas a borrar tras enviar (opt-in). | `File::delete()` en `finally` |

## Enviar: la facade `Mail`

### Síncrono — `Mail.send`

```python
Mail.send(mailable, *, to, cc=None, bcc=None)
```

Construye y manda **en el acto** por SMTP. No usa redis ni worker; bloquea hasta que
SMTP responde. Ideal para local sin broker, tests, o cuando necesitas confirmar el envío.

### Encolado — `Mail.queue`

```python
Mail.queue(mailable, *, to, cc=None, bcc=None, queue=None, init_kwargs=None)
```

Encola el envío en Celery (no bloquea). Parámetros:

- `queue`: cola de Celery (ej. `"emails"`); `None` = cola por defecto.
- `init_kwargs`: los argumentos primitivos para **reinstanciar** el Mailable en el
  worker. Deben coincidir con el `__init__`.

```python
mailable = WelcomeMailable(name="Calcifux")
Mail.queue(mailable, to=["calcifux@example.com"], queue="emails",
           init_kwargs={"name": "Calcifux"})
```

Si el broker está caído, `Mail.queue` lanza `QueueUnavailableError` (un mensaje claro,
no un 500 técnico). En un endpoint conviene traducirlo a un 503:

```python
from milpa.Core.CeleryApp import QueueUnavailableError

try:
    Mail.queue(mailable, to=to, init_kwargs={...})
except QueueUnavailableError as e:
    raise HTTPException(status_code=503, detail=str(e))
```

## El contrato del constructor: solo primitivos

Al encolar, el Mailable se **reinstancia en el worker** desde su dotted path +
`init_kwargs`, y **`build()` corre allí** (worker-side). Por eso el constructor solo
debe recibir primitivos serializables (str, int, listas de str, ids). Nada de sesiones
de BD ni clientes HTTP: no se serializan. Si necesitas más datos, pasa un id y recupéralo
en `build()`.

Ventaja: si `build()` genera bytes (un PDF), esos bytes **no viajan por la cola** — se
generan en el worker.

## Adjuntos

### Por bytes (recomendado)

Sin tocar disco, sin cleanup:

```python
from milpa.Core.Mail.Mailable import DataAttachment

content.data_attachments.append(
    DataAttachment("reporte.pdf", pdf_bytes, "application/pdf")
)
```

### Por archivo + cleanup opt-in

Si el PDF ya vive en disco como temporal, adjúntalo por ruta y **declara** su limpieza:

```python
content.attachments.append(temp_path)
content.cleanup_paths.append(temp_path)   # el Mailer lo borra tras enviar (finally)
```

El framework **nunca** borra un `attachments` por su cuenta: solo lo que declares en
`cleanup_paths`. Un asset persistente (un PDF fijo) va en `attachments` y NO en
`cleanup_paths`.

### Logo inline por CID

```python
content.inline_assets["logo"] = Path("app/Resources/Images/Emails/logo.png")
content.context["logo_cid"] = "logo"
```

En el template: `<img src="cid:logo">`. (El header SMTP usa `<logo>`; en el HTML va sin
ángulos.)

## Drivers (`MAIL_DRIVER`)

| Driver | Comportamiento |
|--------|----------------|
| `smtp` (default) | Envío real por SMTP, según `MAIL_*` y `MAIL_ENCRYPTION` (`""`/`tls`/`ssl`). |
| `log` | Loguea el correo completo, **no** lo envía. Útil en dev sin SMTP. |
| `null` / `array` | No-op: lo descarta. |

En local apunta `MAIL_HOST`/`MAIL_PORT` a **Mailpit** (`docker compose up -d`) y ve los
correos en `http://localhost:8025`.

## Monolingüe vs. i18n

| Caso | Patrón |
|------|--------|
| **i18n** | `subject` con `t()`, template que extiende los layouts y usa `t()`. El locale viene del ambiente (Accept-Language). |
| **Monolingüe** | `subject` literal, template con texto fijo (sin `t()`, sin `extends`). |

Una app es monolingüe salvo que decidas traducir. Ver [Localización](13-localizacion-i18n.md).
El locale se captura al encolar y se restaura en el worker, así el correo sale en el
idioma del request que lo disparó.

## Ejemplos del módulo `Example`

El módulo `Example` trae Mailables de referencia y endpoints en `/example/mail/*`:

| Mailable | Demuestra |
|----------|-----------|
| `MailableCheck` | Smoke básico, logo por CID, adjuntos por ruta, i18n. |
| `MailableSignedCheck` | Layout firmado (footer con datos del remitente + aviso de privacidad). |
| `MailableAttachmentCheck` | Adjunto por bytes vs. por archivo + cleanup. |
| `PedidoListoMailable` | Monolingüe: subject literal, template sin i18n. |

## Siguiente paso

[Colas y tareas](11-colas-y-tareas.md).
