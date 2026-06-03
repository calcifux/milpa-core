# Mediator (command bus)

El **Mediator** de milpa es un *command bus* **1:1**: mapea un TIPO de comando a UN
handler y delega. Un comando es una **intención** que tú envías explícitamente con
`send(...)` y de la que **esperas un resultado**. Es el patrón con el que sacas un caso de
uso del controller para reusarlo **transport-neutral**: el MISMO `send(...)` corre desde
HTTP, desde la CLI o desde un Job, sin duplicar la lógica.

```python
from milpa.Core.Mediator import send
from app.Modules.Demo.Commands import ArchiveNote

result = send(ArchiveNote(note_id=7, actor_id=1))
```

Es un patrón **opt-in del estilo milpa**: nadie te obliga a usarlo. Si tu controller solo
va a llamar a un service, llama al service — no metas un comando de adorno. El Mediator
gana su lugar cuando **el mismo caso de uso entra por más de un transporte**.

## Las tres piezas

| Pieza | Qué es | Dónde vive |
|-------|--------|------------|
| **Comando** | Un dataclass con los datos de la intención (solo datos, sin lógica). | `Modules/<X>/Commands.py` |
| **Handler** | Una clase con `.handle(command)` que ejecuta el caso de uso y **devuelve** algo. | `Modules/<X>/Handlers/` |
| **`send(command)`** | La facade: busca el handler del tipo y lo ejecuta, devolviendo su resultado. | `milpa.Core.Mediator` |

### El comando: solo datos

Un comando es un `@dataclass` que describe **qué** quieres hacer, no **cómo**. Del módulo
`Demo` (`Modules/Demo/Commands.py`):

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArchiveNote:
    """Archivar una nota. `actor_id` = quién la archiva (para el chequeo ABAC en el handler)."""

    note_id: int
    actor_id: int
```

No tiene métodos ni dependencias: es el sobre que viaja al handler.

### El handler: una clase con `.handle()`

Un handler es **cualquier clase con un método `.handle(command)`** — no hay base genérica
que heredar. Lo marcas con `@handles(Comando)` y, al importarse, se auto-registra. Del
módulo `Demo` (`Modules/Demo/Handlers/ArchiveNoteHandler.py`):

```python
from __future__ import annotations

from typing import Any

from milpa.Core.Auth import Gate
from milpa.Core.Database import current_session, transactional
from milpa.Core.Errors import ResourceNotFoundError
from milpa.Core.Mediator import handles
from app.Models.Note import Note
from app.Models.User import User
from app.Modules.Demo.Commands import ArchiveNote
from app.Modules.Demo.Serializers import note_dict


@handles(ArchiveNote)
class ArchiveNoteHandler:
    """Marca `archived=True` si el actor puede gestionar la nota (dueño o moderador)."""

    @transactional
    def handle(self, command: ArchiveNote) -> dict[str, Any]:
        note = current_session().get(Note, command.note_id)
        if note is None:
            raise ResourceNotFoundError(f"Nota {command.note_id} no existe", details={"id": command.note_id})
        actor = current_session().get(User, command.actor_id)  # None => la policy deniega (403)
        Gate.authorize("note.update", note, user=actor)  # ABAC: dueño o moderador
        note.archived = True
        return note_dict(note)
```

El handler concentra el caso de uso completo: carga el recurso y el actor, **autoriza**
con el Gate (ABAC) y muta. Devuelve el dict serializado **antes** del commit, así evita el
objeto *detached* del `expire_on_commit`.

### `send(command)`: enviar y recibir

```python
from milpa.Core.Mediator import send

send(command: object) -> Any
```

`send` busca el handler registrado para `type(command)`, lo instancia y llama a su
`.handle(command)`, **devolviendo el resultado**. Es **síncrono**. Se llama `send` (no
`dispatch`) a propósito: marca que aquí **envías** una intención 1:1 y **esperas
retorno**, a diferencia de los eventos.

## El decorador `@handles`

```python
from milpa.Core.Mediator import handles

@handles(ArchiveNote)
class ArchiveNoteHandler:
    def handle(self, command: ArchiveNote) -> dict[str, Any]: ...
```

`@handles(Comando)` registra el mapeo `Comando -> Handler` en el momento en que el módulo
del handler se importa. El registro es **1:1**: un comando, un handler. No hay
multi-handler, pipelines ni *behaviors* — eso sería un MediatR completo (un framework
dentro del framework), y milpa lo deja fuera a propósito (KISS).

## Caso de uso transport-neutral: el MISMO `send`

Aquí está el corazón del patrón. El caso de uso "archivar nota" vive en **un solo lugar**
(el handler) y entra por **dos transportes** con la **misma** línea `send(ArchiveNote(...))`.

### Desde HTTP

En el endpoint `POST /api/notes/{note_id}/archive` (`Modules/Demo/Http/ApiController.py`):

```python
from milpa.Core.Mediator import send
from app.Modules.Demo.Commands import ArchiveNote

@Post("/notes/{note_id}/archive")
def archive_note(self, note_id: int, user: Authenticatable = _JwtUser) -> dict[str, Any]:
    # Mediator: MISMO comando que `jornal demo archive` (caso de uso transport-neutral).
    result: dict[str, Any] = send(ArchiveNote(note_id=note_id, actor_id=user.get_auth_identifier()))
    return result
```

### Desde la CLI

El command `demo archive <note_id> <actor_id>`
(`Modules/Demo/Console/Commands/ArchiveNoteCommand.py`) **no reimplementa nada**: envía el
mismo comando.

```python
from __future__ import annotations

import typer

from milpa.Core.Console import console_command
from milpa.Core.Mediator import send
from milpa.Core.Registry import import_all_handlers, import_all_policies
from app.Modules.Demo.Commands import ArchiveNote


@console_command(name="archive", help="Archiva una nota (vía Mediator; mismo comando que el API).")
def archive_note(note_id: int, actor_id: int) -> None:
    """Envía el comando ArchiveNote y reporta el resultado."""
    # La CLI no corre el lifespan web: registra a mano lo que el caso de uso necesita.
    import_all_handlers()  # handlers del Mediator (resuelve ArchiveNote -> ArchiveNoteHandler)
    import_all_policies()  # policies del Gate (el handler autoriza 'note.update' ABAC) — sin esto deniega
    result = send(ArchiveNote(note_id=note_id, actor_id=actor_id))
    typer.echo(f"Nota {result['id']} archivada (archived={result['archived']}).")
```

```bash
jornal demo archive 7 1
# Nota 7 archivada (archived=True).
```

Cambia la regla de autorización o el efecto de archivar **una vez**, en el handler, y
ambos transportes quedan al día. Eso es lo que el command bus compra.

### La CLI debe correr el discovery a mano

Detalle importante: la **CLI es un proceso aparte y NO pasa por el lifespan web**, que es
donde la app HTTP descubre handlers y policies. Por eso el command de consola los importa
explícitamente **antes** de enviar:

```python
from milpa.Core.Registry import import_all_handlers, import_all_policies

import_all_handlers()  # registra los @handles(...) → sin esto, HandlerNotFoundError
import_all_policies()  # registra las @policy(...) del Gate → sin esto, el ABAC deniega (403)
```

- `import_all_handlers()` recorre `Modules/<X>/Handlers/` para que los `@handles(...)` se
  registren (es lo que `send` consulta).
- `import_all_policies()` recorre `Modules/<X>/Policies/` para que el `Gate.authorize` del
  handler tenga su policy. Sin esto, el Gate deniega y el caso de uso falla con 403.

En HTTP no necesitas estas llamadas: el arranque de la app ya las ejecutó.

## `HandlerNotFoundError`: cuando falta el handler

Si envías un comando sin handler registrado, `send` lanza `HandlerNotFoundError`:

```python
handler_cls = _HANDLERS.get(type(command))
if handler_cls is None:
    raise HandlerNotFoundError(command_type=type(command).__name__)
```

No es un error de cliente: es un **bug de programación** (olvidaste `@handles(MiComando)`,
o el módulo no se descubrió — p. ej. la CLI sin `import_all_handlers()`). Por eso su
`status_code` es **500**, con `error_code = "handler_not_found"`. Los handlers globales lo
rinden como `application/problem+json` (RFC 9457) sin código de transporte nuevo, igual
que cualquier otro error de dominio. Ver
[Rutas y controladores](07-rutas-y-controladores.md#manejo-de-errores-rfc-9457-problem-details).

## Mediator vs. Observer

El Mediator convive con el patrón **Observer** (eventos de dominio), pero resuelven
problemas opuestos. No los confundas:

| | **Mediator** (`send`) | **Observer** (`dispatch`) |
|---|---|---|
| Relación | **1:1** — un comando, un handler | **1:N** — un evento, varios listeners |
| Retorno | **Sí**, `send` devuelve el resultado | **No**, los eventos no devuelven nada |
| Semántica | "Haz esto" (una **intención**) | "Esto pasó" (un **hecho**) |
| Facade | `send(comando)` | `dispatch(evento)` |
| Falta destinatario | `HandlerNotFoundError` (es un bug) | OK: cero listeners es válido |

Regla mental: si **esperas un resultado** y hay **un solo** responsable, es un comando
(`send`). Si solo **anuncias que algo ocurrió** y a varios les puede interesar reaccionar
(sin que tú esperes nada), es un evento (`dispatch`).

En el `Demo` los verás juntos: `create_note` **dispara** el evento `NoteCreated`
(`dispatch`, 1:N, el Observer confirma al dueño), mientras que `archive_note` **envía** el
comando `ArchiveNote` (`send`, 1:1, con retorno).

## Forma tradicional vs. estilo milpa

**Forma tradicional** — la lógica de "archivar" vive en el controller y se copia (o se
adapta) cuando la quieres también en la CLI:

```python
# En el controller HTTP...
note = repo.find_or_fail(note_id)
Gate.authorize("note.update", note, user=user)
note.archived = True
# ...y otra vez, casi igual, en el command de consola → dos copias que divergen.
```

**Estilo milpa** — el caso de uso vive en un handler y ambos transportes lo **envían**:

```python
result = send(ArchiveNote(note_id=note_id, actor_id=actor_id))
```

La autorización, la transacción y la mutación quedan en **un** sitio (`ArchiveNoteHandler`)
y se reusan tal cual desde HTTP, CLI o un Job.

## Introspección y tests

Para inspeccionar o probar el registro tienes dos helpers en `milpa.Core.Mediator`:

```python
from milpa.Core.Mediator import registered_handlers, reset_handlers

registered_handlers()   # dict {Comando: Handler} de lo registrado (introspección + tests)
reset_handlers()        # limpia el registro — SOLO para tests
```

## Siguiente paso

[Autenticación y autorización](15-autenticacion.md) (el Gate/ABAC que aplica el handler).
