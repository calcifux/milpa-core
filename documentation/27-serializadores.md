# Serializadores (Pydantic v2)

Un **serializador** convierte un modelo SQLAlchemy en un `dict` JSON-able listo para la
respuesta. milpa no inventa nada nuevo: usa **Pydantic v2** (es el equivalente de un
*Serializer* de DRF o un *API Resource* de Laravel). El truco de estilo milpa es que el
serializador también declara **campos derivados** (`excerpt`, `is_admin`) que NO viven en
la tabla, sin que tengas que calcularlos a mano en cada endpoint.

```python
from app.Modules.Demo.Serializers import NoteOut

NoteOut.model_validate(note).model_dump()
# {'id': 1, 'title': '...', 'body': '...', 'owner_id': 7, 'archived': False, 'excerpt': '...'}
```

## El problema: el dict a mano por endpoint (forma tradicional)

Sin serializador, cada endpoint arma su propio `dict`. Parece inofensivo hasta que el
modelo crece o el mismo recurso aparece en tres rutas:

```python
# forma tradicional: el dict se repite (y se desincroniza) en cada endpoint
@router.get("/notes/{note_id}")
def show(note_id: int) -> dict:
    note = NoteRepository().find(note_id)
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "owner_id": note.owner_id,
        "archived": note.archived,
        # ¿y el excerpt? lo calculas aquí... y lo OLVIDAS en /notes (la lista)
        "excerpt": note.body[:80],
    }
```

Problemas: la forma del JSON vive en N lugares, los campos derivados se copian-pegan (o se
olvidan), y nada valida que `body` sea realmente un `str`.

## La solución: un modelo Pydantic (estilo milpa)

Defines la forma **una vez** en un `BaseModel`. El demo lo hace en
`src/milpa/Modules/Demo/Serializers.py`:

```python
from pydantic import BaseModel, ConfigDict, Field, computed_field


class NoteOut(BaseModel):
    """Serializador de una nota. `from_attributes` permite `model_validate(note)` (lee el ORM)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    owner_id: int
    archived: bool = False

    @computed_field  # type: ignore[prop-decorator]  # Pydantic v2: computed sobre @property
    @property
    def excerpt(self) -> str:
        """Vista previa del cuerpo (primeros 80 chars) — DERIVADO, no vive en la tabla."""
        text = self.body.strip()
        return text if len(text) <= 80 else f"{text[:80].rstrip()}…"
```

Cada endpoint que devuelva una nota usa este modelo y obtiene la misma forma, con `excerpt`
incluido siempre.

## `from_attributes`: leer del ORM con `model_validate`

`model_config = ConfigDict(from_attributes=True)` es lo que habilita construir el modelo
**directamente desde un objeto SQLAlchemy** (lee sus atributos por nombre). En Pydantic v1
esto se llamaba `orm_mode`.

```python
note = current_session().get(Note, note_id)   # instancia ORM
NoteOut.model_validate(note)                   # ← lee note.id, note.title, note.body, ...
```

Sin `from_attributes`, `model_validate` esperaría un `dict` y fallaría al recibir el objeto
ORM. Con él, el serializador "ve" el modelo como si fueran atributos.

## `computed_field`: campos derivados sin escribirlos a mano

Un `computed_field` es una `@property` que **se incluye en la salida** de `model_dump()`,
aunque no sea un campo de entrada ni una columna de la tabla. Se calcula a partir de los
otros campos.

`UserOut` lo usa para `is_admin`, derivado de la lista de `roles`:

```python
class UserOut(BaseModel):
    """Serializador de usuario: `roles` como lista + `is_admin` derivado (computed_field)."""

    id: int
    name: str
    email: str
    roles: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles
```

El orden de los decoradores importa: `@computed_field` va **encima** de `@property`. El
comentario `# type: ignore[prop-decorator]` silencia un falso positivo del type-checker con
ese stack de decoradores (es el patrón oficial de Pydantic v2).

`is_admin` y `excerpt` no se escriben en ningún endpoint: salen solos cada vez que
serializas. Cambias la regla en un único lugar (¿"superadmin" también cuenta?) y toda la API
queda consistente.

## `model_dump()`: del modelo al dict JSON-able

`model_dump()` aplana el modelo (campos + `computed_field`) a un `dict` con tipos JSON-able,
listo para que FastAPI lo serialice:

```python
UserOut(id=7, name="Calcifux", email="c@example.com", roles=["admin"]).model_dump()
# {'id': 7, 'name': 'Calcifux', 'email': 'c@example.com',
#  'roles': ['admin'], 'is_admin': True}
```

## Funciones de fachada: `note_dict` / `user_dict`

El demo expone dos helpers que envuelven el modelo Pydantic. Son la **API estable** que usan
los call sites: si mañana cambias `NoteOut`, los servicios y controllers no se enteran.

```python
def note_dict(note: Note) -> dict[str, Any]:
    """Dict JSON-able de una nota (vía NoteOut/Pydantic v2; incluye `excerpt` computado)."""
    return NoteOut.model_validate(note).model_dump()


def user_dict(user: User) -> dict[str, Any]:
    """Dict JSON-able de un usuario (vía UserOut; `roles` lista + `is_admin` computado)."""
    return UserOut(id=user.id, name=user.name, email=user.email, roles=user.get_roles()).model_dump()
```

Nota el contraste entre los dos:

- **`note_dict`** usa `model_validate(note)` porque `NoteOut` tiene `from_attributes=True` y
  los campos coinciden 1-a-1 con las columnas.
- **`user_dict`** construye el modelo **a mano** (`UserOut(id=..., roles=...)`) porque la
  columna `roles` del modelo es un CSV (`"admin,editor"`) y hay que convertirla a lista con
  `user.get_roles()`. El serializador no adivina esa transformación; tú la haces al
  construirlo.

## Cuándo serializar: con la sesión aún abierta

Llama al serializador **mientras la sesión de BD sigue abierta**, no después. En milpa eso
significa: en lecturas `@auto_session` los escalares ya cargados son accesibles aun con el
objeto *detached*; en escrituras `@transactional`, **antes del commit**. Por eso
`NoteService.create` serializa justo después del `flush()` y devuelve ya el `dict`:

```python
class NoteService:
    @transactional
    def create(self, owner_id: int, title: str, body: str) -> dict[str, Any]:
        note = Note(owner_id=owner_id, title=draft.title, body=draft.body)
        current_session().add(note)
        current_session().flush()   # asigna PK
        return note_dict(note)       # ← serializa ANTES del commit (evita DetachedInstanceError)
```

Serializar después del commit puede toparse con `DetachedInstanceError` si tocas un atributo
que SQLAlchemy expiró. Regla práctica: el service devuelve el `dict`, no el objeto ORM. Ver
[Repositorios y transacciones](18-repositorios-y-transacciones.md).

## Uso real en los endpoints del demo

En `Modules/Demo/Http/ApiController.py` los serializadores se usan tanto para un recurso
como para listas. La forma del JSON nunca se escribe en el controller:

```python
from app.Modules.Demo.Serializers import note_dict, user_dict

@Get("/me")
def me(self, user: Authenticatable = _JwtUser) -> dict[str, Any]:
    return user_dict(cast("User", user))   # incluye is_admin computado

@Get("/notes")
def list_notes(self, user: Authenticatable = _JwtUser, offset: int = 0, q: str = "") -> dict[str, Any]:
    page = NoteRepository().paginate(offset=offset, limit=_API_PER_PAGE,
                                     order_by=Note.id.desc(), where=where)
    # serializa CADA item de la página; el excerpt sale solo en cada uno
    return {"items": [note_dict(n) for n in page.items],
            "has_more": page.has_more, "next_offset": page.next_offset}
```

## Tradicional vs. estilo milpa

| Aspecto | Forma tradicional (dict a mano) | Estilo milpa (serializador Pydantic) |
|---------|---------------------------------|--------------------------------------|
| Forma del JSON | Repetida en cada endpoint | Declarada **una vez** en un `BaseModel` |
| Campos derivados | Copiados/olvidados por endpoint | `computed_field`: salen solos |
| Leer del ORM | Acceso manual atributo por atributo | `model_validate(obj)` con `from_attributes` |
| Validación de tipos | Ninguna | La de Pydantic v2 |
| Punto de cambio | N archivos | El serializador (+ el helper `*_dict`) |

## Siguiente paso

Combina serializadores con la paginación de los repositorios: ver
[Repositorios y transacciones](18-repositorios-y-transacciones.md).
