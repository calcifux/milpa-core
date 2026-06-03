# Versionado de la API

Una API pública no se reescribe: **evoluciona**. Cuando un endpoint necesita cambiar su
forma de respuesta, no puedes romper a los clientes que ya consumen la versión anterior.
milpa resuelve esto con **versionado por URL-path** (el mismo enfoque que DRF / Django
REST framework): declaras la versión en el `@Controller` y el framework antepone el
prefijo (`/v1`, `/v2`, …), agrupa la versión en Swagger y la expone al handler.

```python
from milpa.Core.Http import Controller, Get, api_version

@Controller("/reports", version="v1", tags=["reports"])
class ReportsV1Controller:
    @Get("/notes")
    def notes(self, request: Request) -> dict:
        return {"version": api_version(request), "total": 0}
```

Eso publica `GET /v1/reports/notes`. Cuando llegue v2, **agregas** un controller nuevo;
no tocas el v1.

## `version=` en `@Controller`

El parámetro `version` de `@Controller` (`milpa/Core/Http/Routing.py`) versiona la ruta por
URL. Su firma:

```python
def Controller(
    prefix: str = "",
    *,
    tags: Sequence[str] | None = None,
    dependencies: Sequence[Any] | None = None,
    version: str | None = None,
) -> Callable[[C], C]: ...
```

Cuando pasas `version="v1"`, milpa hace tres cosas por ti:

1. **Antepone el prefijo**: el path efectivo pasa a `/{version}{prefix}`. Con
   `@Controller("/reports", version="v1")`, la ruta `@Get("/notes")` se monta en
   `/v1/reports/notes`.
2. **Agrupa en Swagger**: añade `version` a los `tags` del router, así `/docs` agrupa los
   endpoints por versión (verás un bloque `v1` y otro `v2`).
3. **Expone la versión al handler**: registra una dependency de router que fija
   `request.state.api_version`, legible con `api_version(request)` (ver abajo).

Sin `version`, `@Controller` se comporta igual que siempre: el prefijo es el que pasas y
no hay tag de versión. El versionado es **opt-in**.

| Declaración | Path montado | Tag en Swagger |
|-------------|--------------|----------------|
| `@Controller("/reports")` | `/reports/...` | — |
| `@Controller("/reports", version="v1")` | `/v1/reports/...` | `v1` |
| `@Controller("/reports", version="v2", tags=["reports"])` | `/v2/reports/...` | `reports`, `v2` |

## Leer la versión en el handler: `api_version(request)`

Dentro del endpoint puedes saber con qué versión te están pegando. `api_version` lee
`request.state.api_version` (lo fijó la dependency que `@Controller(version=...)` montó):

```python
def api_version(request: Request) -> str | None:
    return getattr(request.state, "api_version", None)
```

Devuelve la cadena de versión (`"v1"`, `"v2"`, …) o `None` si la ruta **no** está
versionada. Sirve para ramificar lógica, marcar deprecación en la respuesta o loguear qué
versión consumen tus clientes. Recibe el `Request` de Starlette, así que pide `request`
en tu método:

```python
from fastapi import Request
from milpa.Core.Http import Controller, Get, api_version

@Controller("/reports", version="v1", tags=["reports"])
class ReportsController:
    @Get("/notes")
    def notes(self, request: Request) -> dict:
        return {"version": api_version(request)}   # -> "v1"
```

También puedes inyectarlo como dependency tipada si prefieres no manejar `request` a mano:

```python
from typing import Annotated
from fastapi import Depends

def notes(self, version: Annotated[str | None, Depends(api_version)]) -> dict:
    return {"version": version}
```

## Evolucionar sin romper: v1 y v2 conviven

La regla de oro del versionado: **una versión publicada no cambia su contrato**. Si v1
devuelve `{"total": N}`, devolverá `{"total": N}` para siempre. Cuando necesitas más
datos, no editas v1: **declaras un controller v2** apuntando al mismo recurso. Como el
prefijo lo distingue (`/v1/...` vs. `/v2/...`), ambos se auto-montan y conviven sin
colisionar.

### Forma tradicional vs. estilo milpa

| Enfoque | Cómo |
|---------|------|
| **Forma tradicional** | Un `if request_version == "v2":` dentro del mismo handler, o duplicas la ruta a mano con `@router.get("/v1/notes")` y `@router.get("/v2/notes")` y armas el prefijo tú mismo. La versión se enreda con la lógica. |
| **Estilo milpa** | Un `@Controller` por versión. El prefijo y el tag los pone `version=`; cada clase es un contrato aislado y legible. Agregar v2 es agregar una clase, no editar v1. |

El estilo milpa mantiene cada versión como una unidad cerrada: lees `ReportsV2Controller`
y ves exactamente qué promete v2, sin `if` que mezclen comportamientos.

## Ejemplo real: `/v1/reports/notes` vs. `/v2/reports/notes`

El módulo `Demo` trae el versionado **en acción** en
`app/Modules/Demo/Http/ReportsController.py`: el mismo recurso (`/reports/notes`) en dos
versiones que conviven. v1 da un reporte básico; v2 lo evoluciona desglosando notas
archivadas/activas, **sin tocar v1**.

```python
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import and_

from milpa.Core.Auth import Authenticatable, guarded
from milpa.Core.Http import Controller, Get, api_version
from app.Models.Note import Note
from app.Modules.Demo.Repositories.NoteRepository import NoteRepository

_JwtUser = Depends(guarded("jwt"))


@Controller("/reports", version="v1", tags=["demo-versioned"])
class ReportsV1Controller:
    @Get("/notes")
    def notes_report(self, request: Request, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        """v1: reporte BÁSICO — solo el total de notas del usuario."""
        owner_id = user.get_auth_identifier()
        return {
            "version": api_version(request),
            "total": NoteRepository().count(where=Note.owner_id == owner_id),
        }


@Controller("/reports", version="v2", tags=["demo-versioned"])
class ReportsV2Controller:
    @Get("/notes")
    def notes_report(self, request: Request, user: Authenticatable = _JwtUser) -> dict[str, Any]:
        """v2: reporte EVOLUCIONADO — desglosa archivadas/activas. NO rompe a v1."""
        owner_id = user.get_auth_identifier()
        repo = NoteRepository()
        total = repo.count(where=Note.owner_id == owner_id)
        archived = repo.count(where=and_(Note.owner_id == owner_id, Note.archived.is_(True)))
        return {
            "version": api_version(request),
            "total": total,
            "archived": archived,
            "active": total - archived,
        }
```

Las dos clases viven en el mismo archivo, ambas detrás del mismo guard JWT, y el Registry
las monta automáticamente (igual que cualquier router; ver
[Rutas y controladores](07-rutas-y-controladores.md)). El cliente viejo sigue llamando a
`/v1` y el nuevo a `/v2`:

```bash
# Cliente v1 (contrato básico, intacto)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/reports/notes
# {"version":"v1","total":7}

# Cliente v2 (contrato evolucionado, aditivo)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v2/reports/notes
# {"version":"v2","total":7,"archived":2,"active":5}
```

En `/docs` los verás en dos grupos por su tag (`v1` y `v2` se agregan a los tags que ya
pasaste), de modo que Swagger documenta cada versión por separado.

## Buenas prácticas

- **No edites una versión publicada.** Cambios aditivos (campos nuevos en la respuesta)
  pueden ir en la misma versión; cambios que rompen (renombrar/quitar campos, cambiar
  tipos) exigen versión nueva.
- **Comparte la lógica, no la copies.** Como en el ejemplo, ambas versiones llaman al
  mismo `NoteRepository`. La versión solo cambia la **forma de la respuesta**, no
  reimplementa el dominio. Ver [Repositorios y transacciones](18-repositorios-y-transacciones.md).
- **Marca deprecación desde el handler.** Con `api_version(request)` puedes loguear o
  añadir un header/aviso cuando un cliente sigue en una versión vieja, sin tocar la lógica
  de negocio.
- **Versiona solo lo que es contrato público.** Endpoints internos o de health check
  (como `/status`) no necesitan versión.

## Siguiente paso

[Manejo de errores](07-rutas-y-controladores.md#manejo-de-errores-rfc-9457-problem-details).
