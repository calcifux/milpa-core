# Eventos y Observers

Los eventos en milpa siguen el patrón **Events / Listeners** de Laravel: un hecho de
dominio ("se registró un usuario", "se creó una nota") se dispara **explícitamente** y uno o
varios **Observers** reaccionan. Es notificación **1:N fire-and-forget**: el código que dispara
el evento no espera retorno ni sabe quién escucha.

```python
from milpa.Core.Events import dispatch
dispatch(UserRegistered(user_id=7, name="Calcifux", email="calcifux@example.com"))
```

!!! warning "NO es un model-observer de Eloquent"
    milpa **no** ata esto a la base de datos. El evento **no** se dispara por un `commit`;
    lo disparas **tú** con `dispatch(...)` desde donde ocurra el hecho de negocio (controller,
    service). Así controlas exactamente cuándo y con qué datos se notifica.

## El evento: un `@dataclass` de primitivos

Un evento es solo un `@dataclass` con campos **primitivos planos** (str, int, listas de
str, ids). Nada de instancias ORM ni sesiones de BD. La razón es el transporte: si hay
broker, el evento viaja como kwargs JSON y se **reconstruye en el worker** con
`Evento(**kwargs)` — y eso solo funciona con primitivos serializables (mismo contrato que
`SerializesModels` de Laravel y que los Mailables encolados).

```python
# app/Modules/Example/Events.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class UserRegistered:
    """Se registró un usuario nuevo. Lo observa NotifyAdminOnUserRegistered."""
    user_id: int
    name: str
    email: str

@dataclass
class NoteCreated:
    """Se creó una nota. Lo observa NotifyOwnerOnNoteCreated (con i18n)."""
    note_id: int
    title: str
    owner_id: int
    owner_email: str
    locale: str = "es"
```

!!! tip "Empaca en el evento lo que el observer necesitará lejos del request"
    Un observer puede correr en el worker, **sin request**: allá no hay
    `Accept-Language` ni sesión del usuario. Por eso `NoteCreated` lleva `owner_email` y
    `locale` **dentro del evento** — el observer no podría resolverlos en el worker. Si
    necesitas datos de BD que sí puedes leer por id, pasa el id y consúltalo en `handle()`.

## El Observer: subclase con `observes` + `handle()`

Un Observer hereda de la ABC `Observer` (`milpa/Core/Events/Observer.py`), fija el atributo
de clase `observes = TipoDeEvento` y sobreescribe `handle(self, event)`:

```python
# app/Modules/Example/Observers/NotifyOwnerOnNoteCreated.py
from __future__ import annotations
from milpa.Core.Events import Observer
from milpa.Core.Mail import Mail
from app.Modules.Example.Events import NoteCreated
from app.Modules.Example.Mail.NoteCreatedMailable import NoteCreatedMailable

class NotifyOwnerOnNoteCreated(Observer):
    observes = NoteCreated

    def handle(self, event: object) -> None:
        assert isinstance(event, NoteCreated)  # dispatch ya filtró por tipo; narrow para mypy
        Mail.send(NoteCreatedMailable(title=event.title, locale=event.locale), to=[event.owner_email])
```

| Atributo / método | Para qué | Laravel |
|-------------------|----------|---------|
| `observes` (ClassVar) | Tipo de evento que escucha. Match por tipo **exacto** (sin herencia). `None` = escucha **todos** los eventos. | `$listen` en `EventServiceProvider` |
| `handle(self, event)` | Reacciona al evento. Por defecto no hace nada. | `handle(Event $event)` |

Relación **1:N**: varios Observers pueden declarar `observes = NoteCreated` y todos
corren. El `event` que llega a `handle()` ya está filtrado por tipo (de ahí el `assert
isinstance` para que mypy lo afine).

!!! note "Un Observer SÍ puede leer la BD"
    Lo que evitamos es **atarlo** a la BD (no es un model-observer). Pero `handle()` es código
    normal: puede consultar repositorios, mandar correo, etc. El observer
    `NotifyAdminOnUserRegistered` del demo, por ejemplo, lee los usuarios con rol admin y les
    manda un correo.

## Disparar el evento: `dispatch(evento)`

`dispatch` vive en `milpa/Core/Events`. Recibe la **instancia** del evento y la entrega a cada
Observer cuyo `observes` matchee (o sea `None`):

```python
from milpa.Core.Events import dispatch
from app.Modules.Example.Events import UserRegistered

dispatch(UserRegistered(user_id=7, name="Calcifux", email="calcifux@example.com"))
```

Así se ve en el `ApiController` del demo, justo después de crear el usuario:

```python
@Post("/register", status_code=201)
def register(self, body: RegisterInput) -> dict[str, Any]:
    created = UserService().register(body.name, body.email, body.password)
    # Evento de dominio → el Observer NotifyAdminOnUserRegistered avisa al admin (auto).
    dispatch(UserRegistered(user_id=int(created["id"]), name=body.name, email=body.email))
    return created
```

Y al crear una nota, empacando el `locale` del request en el evento:

```python
@Post("/notes", status_code=201)
def create_note(self, body: NoteInput, user: Authenticatable = _JwtUser) -> dict[str, Any]:
    created = NoteService().create(user.get_auth_identifier(), body.title, body.body)
    owner = cast("User", user)
    dispatch(
        NoteCreated(
            note_id=int(created["id"]),
            title=str(created["title"]),
            owner_id=owner.get_auth_identifier(),
            owner_email=owner.email,
            locale=current_locale(),   # se captura aquí; el worker no lo tendría
        )
    )
    return created
```

## Transporte adaptativo: broker si hay, síncrono si no

Aquí está la decisión clave de diseño (KISS, sin flags por-observer): **si hay broker
disponible, el observer corre en el worker (async); si no, corre síncrono inline.** Tú no
eliges; lo decide el framework por observer:

```
dispatch(NoteCreated(...))
        │
        ▼
  ¿hay broker?
   ├── sí → encola task "events.handle" → el WORKER reconstruye observer + evento y corre handle()
   └── no → observer().handle(event)   (síncrono, en el acto)
```

El import de Celery es **perezoso** (igual que `Mail.queue`): un proyecto que nunca encola
observers no jala redis al arrancar. La rama encolada vive en `milpa/Core/Events/Tasks.py` y
solo se importa cuando hace falta.

!!! info "Best-effort por observer"
    Un observer que falla **no tumba al caller** ni a los demás observers: un efecto
    secundario no debe romper la operación de negocio. El comportamiento ante un error lo
    decide el flag `events_strict` (siguiente sección) — pero **nunca** falla en silencio.

## Auto-registro y discovery

No hay que registrar nada a mano (adiós al `EventServiceProvider`). Dos mecanismos:

1. **Auto-registro por subclase**: definir una clase que herede de `Observer` la mete sola
   en el registro interno (`__init_subclass__`), mismo patrón que los `Seeder`.
2. **Discovery por convención**: en el arranque, `create_app()` llama a
   `import_all_observers()`, que importa todos los módulos bajo `Modules/<X>/Observers/` de
   cada módulo. Importarlos es lo que dispara su auto-registro.

Por eso la convención es: **un Observer por archivo, dentro de `Modules/<Tu módulo>/Observers/`.**
Si lo pones en otro lado y nadie lo importa, `dispatch` no lo verá.

## El flag `events_strict`

Controla qué pasa cuando un observer **lanza una excepción** (definido en `milpa/Core/Config`,
default `False`):

| `events_strict` | Comportamiento ante un observer que falla | Cuándo |
|-----------------|-------------------------------------------|--------|
| `False` (default) | Loguea **ruidoso** (ERROR + traceback) y sigue. La operación de negocio no se rompe. | Producción |
| `True` | **Re-lanza** la excepción, para que el bug del observer truene fuerte de inmediato. | Dev / tests |

En ambos casos **nunca** se traga el error en silencio. Pon `EVENTS_STRICT=true` en `.env`
mientras desarrollas para cazar bugs en tus observers al instante.

## Forma tradicional vs. estilo milpa

**Forma tradicional** — el controller orquesta los efectos secundarios inline. Sabe del
correo, del admin, del transporte; mezcla la regla de negocio con sus consecuencias:

```python
@Post("/register", status_code=201)
def register(self, body: RegisterInput) -> dict[str, Any]:
    created = UserService().register(body.name, body.email, body.password)
    # El controller orquesta TODO el efecto secundario a mano:
    admin_emails = [u.email for u in UserRepository().all() if "admin" in u.get_roles()]
    Mail.queue(
        NewUserAdminMailable(name=body.name, email=body.email),
        to=admin_emails,
        init_kwargs={"name": body.name, "email": body.email},
    )
    return created
```

Agregar un segundo efecto (auditoría, webhook) significa tocar el controller otra vez.

**Estilo milpa** — el controller **anuncia el hecho** y se desentiende del resto. Quién
reacciona y cómo viaja (worker o síncrono) es problema del framework y de los Observers:

```python
@Post("/register", status_code=201)
def register(self, body: RegisterInput) -> dict[str, Any]:
    created = UserService().register(body.name, body.email, body.password)
    dispatch(UserRegistered(user_id=int(created["id"]), name=body.name, email=body.email))
    return created
```

Para sumar un efecto, **agregas un Observer** (un archivo nuevo en `Observers/` con
`observes = UserRegistered`) — sin tocar el controller. Eso es la inversión 1:N: el emisor
no conoce a sus consumidores.

## Eventos vs. Mediator vs. Jobs

milpa ofrece varios mecanismos opt-in; elige por intención:

| Patrón | Cardinalidad | ¿Devuelve? | Cuándo |
|--------|--------------|------------|--------|
| **Eventos / Observers** (`dispatch`) | 1:N | No (fire-and-forget) | "Pasó X" — notificar a N reacciones desacopladas. |
| **Mediator** (`send`) | 1:1 | Sí (resultado) | Una intención que **resuelves** y de la que esperas respuesta. |
| **Jobs** (`@job` + `.dispatch()`) | 1:1 | No | Un trabajo de background concreto que **siempre** quieres encolar. |

El Mediator enruta UNA intención a UN handler y te devuelve el resultado; los Eventos son
notificación 1:N donde no esperas retorno y el transporte lo decide el framework. Ver
[Colas y tareas](11-colas-y-tareas.md) para los Jobs.

## Probar Observers sin BD ni broker

Como los observers se ejecutan síncronos cuando no hay broker, un test puede disparar el
evento y verificar el efecto sin Celery. Para aislar el registro entre tests, milpa expone
helpers (espejo de los seeders):

```python
from milpa.Core.Events import dispatch, registered_observers, reset_observers
```

- `registered_observers()`: la lista de subclases de `Observer` registradas.
- `reset_observers()`: limpia el registro (**solo** para tests).

Con `EVENTS_STRICT=true` en el entorno de test, si un observer falla, el `dispatch` re-lanza
y el test truena (en vez de tragarse el error).

## Siguiente paso

[Mediator (Commands y Handlers)](20-mediator.md).
