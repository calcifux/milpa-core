# Filtrado y paginación

Dos piezas que casi siempre van juntas en un listado: **filtrar** (qué filas) y
**paginar** (cuántas, en qué tramo). milpa las separa en dos primitivos componibles:

- `FilterQueryModel` — un modelo **Pydantic** que compila query-params (`?search=`,
  `?ordering=`, igualdades por columna) a condiciones SQLAlchemy.
- `Repository.paginate` / `cursor_paginate` / `count` — los métodos de paginación
  heredados del [Repository](18-repositorios-y-transacciones.md).

El filtro produce `where()` + `order_by()`; el repositorio los consume. Ninguno conoce
al otro: el `FilterQueryModel` es Pydantic puro + SQLAlchemy (sirve igual en la CLI), y
el repositorio acepta cualquier condición.

## El problema: el `if q:` escrito a mano

La forma tradicional arma el `where` a mano en cada controller (es lo que hace el módulo
`Demo` en `Modules/Demo/Http/ApiController.py`):

```python
from sqlalchemy import and_
from app.Models.Note import Note

@Get("/notes")
def list_notes(self, user: Authenticatable = _JwtUser, offset: int = 0, q: str = "") -> dict[str, Any]:
    where = Note.owner_id == user.get_auth_identifier()
    if q:
        where = and_(where, Note.title.ilike(f"%{q}%"))
    page = NoteRepository().paginate(offset=offset, limit=20, order_by=Note.id.desc(), where=where)
    return {"items": [note_dict(n) for n in page.items], "has_more": page.has_more, "next_offset": page.next_offset}
```

Funciona, pero el `if q:` se repite en cada listado, ordenar por columna del cliente te
obliga a un `match`/`if` frágil, y es fácil **olvidar** validar el campo de orden (y
abrir un `ORDER BY` arbitrario). El `FilterQueryModel` empaqueta ese patrón.

## `FilterQueryModel` — el filtro declarativo

Subclasea `FilterQueryModel` (`milpa/Core/Database/Filtering.py`), fija el modelo objetivo
en `sa_model` y declara los campos por los que se filtra:

```python
from milpa.Core.Database import FilterQueryModel
from app.Models.Note import Note

class NoteFilter(FilterQueryModel):
    sa_model = Note                      # modelo SQLAlchemy objetivo
    search_fields = ("title", "body")    # ?search= -> ILIKE OR sobre estas columnas
    order_fields = ("id", "title")       # ?ordering=-title -> ORDER BY (whitelist)

    owner_id: int | None = None          # ?owner_id=3 -> WHERE owner_id = 3 (igualdad)
```

`sa_model`, `search_fields` y `order_fields` son **config de clase** (`ClassVar`), no
campos Pydantic. Lo que declares como atributo Pydantic (`owner_id` arriba) **sí** es un
filtro: se parsea del query-string.

### Las tres partes

| Parte | En el query-string | Semántica |
|-------|--------------------|-----------|
| Campos declarados (`owner_id`, …) | `?owner_id=3` | **Igualdad exacta** por columna (`columna == valor`). |
| `search` (reservado) | `?search=hola` | `ILIKE '%hola%'` **OR** sobre todas las `search_fields`. |
| `ordering` (reservado) | `?ordering=-title` | `ORDER BY`; prefijo `-` = `DESC`. Solo campos de `order_fields`. |

Decisión KISS y **predecible**: cada campo declarado presente es igualdad exacta; para
texto parcial existe `search` (no se mezclan los dos modos). `search` y `ordering` son
nombres **reservados** del motor del DSL — no los declares como filtros.

## Compilar a SQLAlchemy: `where()` / `order_by()` / `apply()`

El filtro expone tres métodos. Los dos primeros producen lo que `paginate` espera; el
tercero los aplica a un `select(...)` propio.

### `where() -> condición | None`

AND de los filtros por-campo presentes + la búsqueda. Devuelve `None` si no se pidió
**ningún** filtro, para pasarlo tal cual a `paginate(where=...)`:

```python
NoteFilter().where()                          # -> None (sin filtros)
NoteFilter(owner_id=3).where()                # -> Note.owner_id == 3
NoteFilter(search="hola").where()             # -> Note.title ILIKE '%hola%' OR Note.body ILIKE '%hola%'
NoteFilter(owner_id=3, search="hola").where() # -> (owner_id == 3) AND (title ILIKE ... OR body ILIKE ...)
```

### `order_by() -> cláusula | None`

Lee `ordering`; `None` si no se pidió. Prefijo `-` = `DESC`, sin prefijo = `ASC`:

```python
NoteFilter(ordering="title").order_by()   # -> Note.title.asc()
NoteFilter(ordering="-title").order_by()  # -> Note.title.desc()
```

### `apply(statement) -> statement`

Para queries **custom** fuera del repositorio: encadena `where()` + `order_by()` sobre
un `select(...)` y devuelve el statement:

```python
from sqlalchemy import select

stmt = NoteFilter(owner_id=3, ordering="-id").apply(select(Note))
# -> select(Note).where(Note.owner_id == 3).order_by(Note.id.desc())
```

## El estilo milpa: el filtro como dependency

En un controller, declara el filtro como parámetro `Query()` y deja que Pydantic parsee
el query-string. El controller queda sin un solo `if`:

```python
from typing import Annotated
from fastapi import Query
from milpa.Core.Http import Controller, Get
from app.Modules.Demo.Repositories.NoteRepository import NoteRepository
from app.Modules.Demo.Serializers import note_dict

@Controller("/api", tags=["demo-api"])
class ApiController:
    @Get("/notes")
    def list_notes(self, filters: Annotated[NoteFilter, Query()], offset: int = 0) -> dict[str, Any]:
        page = NoteRepository().paginate(
            offset=offset,
            limit=20,
            where=filters.where(),
            order_by=filters.order_by() or Note.id.desc(),   # fallback a orden estable
        )
        return {"items": [note_dict(n) for n in page.items], "has_more": page.has_more, "next_offset": page.next_offset}
```

`GET /api/notes?owner_id=3&search=factura&ordering=-id&offset=20` queda servido sin
ramificar a mano. Es el equivalente al trío de DRF (`DjangoFilterBackend` +
`SearchFilter` + `OrderingFilter`), pero como **un** modelo Pydantic.

> **Nota:** pásale siempre un `order_by` (aunque el cliente no pida `ordering`). Sin
> orden explícito, el `offset/limit` no es determinista — ver "orden estable" abajo.

## Nunca falla en silencio: ordering inválido → `422`

Si el cliente pide un `ordering` **fuera** de `order_fields`, `order_by()` **no lo
ignora**: lanza `InvalidFilterError` (`milpa/Core/Errors`):

```python
NoteFilter(ordering="password").order_by()   # order_fields = ("id", "title")
# raise InvalidFilterError("No se puede ordenar por 'password'.",
#                          details={"field": "password", "allowed": ["id", "title"]})
```

El [handler global](07-rutas-y-controladores.md#manejo-de-errores-rfc-9457-problem-details)
lo traduce al sobre RFC 9457 con status **422**:

```json
{
  "type": "about:blank",
  "title": "Invalid filter",
  "status": 422,
  "detail": "No se puede ordenar por 'password'.",
  "code": "invalid_filter",
  "errors": { "field": "password", "allowed": ["id", "title"] }
}
```

Por qué no ignorarlo: tragarse el parámetro deja al cliente **creyendo** que ordenó
cuando no pasó nada (un bug silencioso del lado del consumidor), y un `ORDER BY` abierto
a cualquier columna es una fuga. La whitelist `order_fields` es la **única** lista de
columnas ordenables, y el `errors` te devuelve esa lista para que te corrijas. Es el
tenet de milpa: **nunca falla en silencio**.

## Paginar: offset vs. cursor

El repositorio trae dos estrategias. Ninguna hace `COUNT` por página: ambas piden
`limit + 1` filas y deducen `has_more` (más barato que contar el total).

### `paginate` — por offset (scroll infinito)

```python
def paginate(self, *, offset=0, limit=20, order_by=None, where=None) -> Page[Model]: ...
```

Salta `offset` filas y trae `limit`. Devuelve un `Page` (frozen dataclass):

| Campo | Tipo | Para qué |
|-------|------|----------|
| `items` | `Sequence[Model]` | Las filas de esta página. |
| `has_more` | `bool` | ¿Hay más? (dedujo pidiendo `limit + 1`). |
| `next_offset` | `int` | El `?offset=` de la siguiente página (úsalo en el marcador HTMX). |

```python
page = NoteRepository().paginate(offset=0, limit=6, order_by=Note.id.desc(), where=Note.owner_id == 3)
page.items        # hasta 6 notas
page.has_more     # True si hay una 7.ª
page.next_offset  # 6  -> siguiente request: ?offset=6
```

Es lo que usa el dashboard del demo para el scroll infinito de notas
(`Modules/Demo/Http/WebController.py`).

### `cursor_paginate` — por cursor (keyset/seek)

```python
def cursor_paginate(self, *, cursor=None, limit=20, key=None, descending=False, where=None) -> CursorPage[Model]: ...
```

Avanza con un **marcador opaco** (base64) de la última fila en vez de un offset numérico.
`key` debe ser una columna **única y estable** (default: la PK `id`). Devuelve un
`CursorPage`:

| Campo | Tipo | Para qué |
|-------|------|----------|
| `items` | `Sequence[Model]` | Las filas de esta página. |
| `has_more` | `bool` | ¿Hay más? |
| `next_cursor` | `str \| None` | Marcador para el `?cursor=` siguiente; `None` = no hay más. |

```python
first = NoteRepository().cursor_paginate(limit=6, descending=True)
# siguiente página:
if first.next_cursor:
    nxt = NoteRepository().cursor_paginate(cursor=first.next_cursor, limit=6, descending=True)
```

Es el equivalente al `CursorPagination` de DRF.

### Cuál elegir

| | `paginate` (offset) | `cursor_paginate` (keyset) |
|---|---|---|
| Marcador | `next_offset` (número) | `next_cursor` (opaco) |
| Saltar a la página N | Sí (`?page=N`) | No (solo siguiente/anterior) |
| Costo a profundidad | El motor escanea `offset` filas (caro al fondo) | O(1) (no escanea: filtra por la llave) |
| Inserts concurrentes | **Salta/duplica** filas si insertan arriba | **Estable**: no salta ni duplica |
| Para | Tablas modestas, paginador numérico clásico | Feeds/listados grandes, tiempo real |

Regla práctica: paginador con números de página → `paginate`; scroll infinito o feed que
crece mientras lo lees → `cursor_paginate`.

## Orden estable: no pagines sin `order_by`

El `offset/limit` solo es determinista si las filas tienen un **orden total**. Sin
`order_by`, el motor puede devolverlas en cualquier orden y la página 2 puede repetir o
saltarse filas de la 1. Pasa siempre un orden estable (típicamente la PK):

```python
NoteRepository().paginate(offset=0, limit=20, order_by=Note.id.desc())   # estable
```

`cursor_paginate` lo resuelve por construcción: ordena por su columna-llave única. Si
necesitas ordenar por una columna **no única** (p. ej. `created_at`), ordena por una
llave compuesta que **incluya** la PK como desempate.

## `count()` — el total server-side

Cuando necesitas el **total** (un badge, "N resultados"), no traigas todas las filas para
contarlas. `count()` emite un `COUNT(*)` server-side:

```python
def count(self, *, where=None) -> int: ...
```

```python
# Forma tradicional (mal): hidrata TODAS las filas a memoria solo para len()
total = len(NoteRepository().all())

# Estilo milpa: COUNT(*) en el servidor, sin hidratar ORM
total = NoteRepository().count(where=Note.owner_id == 3)
```

El dashboard del demo lo usa para el contador de notas:

```python
notes_count = NoteRepository().count(where=Note.owner_id == user.get_auth_identifier())
```

`count()` acepta el mismo `where` que `paginate`, así que puedes reusar `filters.where()`:

```python
total = NoteRepository().count(where=filters.where())
page = NoteRepository().paginate(where=filters.where(), order_by=filters.order_by() or Note.id.desc())
```

## Resumen

- `FilterQueryModel` compila query-params a SQLAlchemy: `search` (ILIKE OR), `ordering`
  (whitelist), campos declarados (igualdad). Expone `where()`, `order_by()`, `apply()`.
- `ordering` fuera de `order_fields` lanza `InvalidFilterError` → `422` RFC 9457; **nunca
  se ignora en silencio**.
- `paginate` (offset, scroll) y `cursor_paginate` (keyset, estable) no hacen `COUNT`;
  para el total usa `count()` (server-side, no `len(all())`).
- Pagina **siempre** con un `order_by` estable.

## Siguiente paso

[Repositorios y transacciones](18-repositorios-y-transacciones.md).
