# Rutas y controladores

Las rutas son FastAPI puro. milpa solo añade el **auto-montaje**: declaras un
`APIRouter` en un controller de tu módulo y la app lo monta sola, sin registrarlo a mano.

## Un controller mínimo

```python
# app/Modules/Example/Http/controller.py
from fastapi import APIRouter

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/ping")
def ping() -> dict[str, str]:
    return {"module": "Example", "status": "ok"}
```

Eso es todo. `iter_routers()` (del Registry) escanea `Modules/<X>/Http/` de forma
recursiva, recoge **cualquier** variable `APIRouter` a nivel de módulo y `create_app()`
la incluye con `app.include_router(router)`. (Ver [Monolito modular](06-monolito-modular.md).)

Convenciones:

- Pon los controllers bajo `Modules/<Tu módulo>/Http/`.
- La variable del router debe estar a nivel de módulo (no dentro de una función).
- Puedes tener varios archivos y varios routers; se descubren todos (deduplicados por
  identidad).

## Controllers class-based (estilo Spring)

Si prefieres agrupar endpoints en una clase (≈ `@RestController` de Spring), usa `@Controller`
con `@Get/@Post/@Put/@Patch/@Delete` sobre los métodos. Se auto-monta igual que un `APIRouter`, y
**convive** con el estilo función de arriba:

```python
from app.Core.Http import Controller, Get, Post

@Controller("/cats", tags=["cats"])
class CatsController:
    @Get("/")
    def index(self) -> list[str]: ...

    @Get("/{cat_id}")
    def show(self, cat_id: int) -> dict[str, int]: ...   # path param tipado

    @Post("/", status_code=201)
    def store(self, body: CatInput) -> dict[str, str]: ...  # body Pydantic
```

Los decoradores de verbo aceptan los **mismos kwargs** que FastAPI (`status_code`, `response_model`,
`dependencies`, `summary`, …). `self` se resuelve solo (el controller se instancia una vez). Para
proteger métodos: inyecta el usuario con `CurrentUser`/`Depends(guarded("jwt"))`, o usa
`@Roles("admin")` / `@Can("note.create")` sobre el método (ver [Autenticación](15-autenticacion.md)).

## Renderizar una vista

Para devolver HTML (Jinja2) en vez de JSON, usa el helper `view()`:

```python
from fastapi.responses import HTMLResponse
from app.Core.View import view

@router.get("/welcome", response_class=HTMLResponse)
def welcome() -> HTMLResponse:
    return view("example/welcome")     # Modules/Example/Resources/Views/welcome.html.j2
```

El prefijo `example/` es el namespace del módulo. Ver [Vistas](09-vistas.md).

## Encolar trabajo desde una ruta

Un endpoint que dispara una task de Celery (no bloquea la respuesta):

```python
from app.Modules.Example.Jobs.HelloJob import hello_world

@router.get("/hello")
def dispatch_hello(name: str = "mundo") -> dict[str, str]:
    hello_world.delay(name=name)       # encola; lo procesa "jornal queue work"
    return {"queued": True, "name": name}
```

Ver [Colas y tareas](11-colas-y-tareas.md).

## Proteger rutas

### Con una dependency a nivel de router (del módulo)

Patrón idiomático para seguridad propia del módulo: una dependency en el `APIRouter`
corre **antes de cada ruta** del router y **viaja con el módulo** (no es global).

```python
# app/Modules/Example/Http/secured.py
from fastapi import APIRouter, Depends, Header, HTTPException, status

def require_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != "demo-secret":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida")

router = APIRouter(
    prefix="/example/secured",
    tags=["example"],
    dependencies=[Depends(require_api_key)],   # aplica a TODAS las rutas del router
)

@router.get("/ping")
def secured_ping() -> dict[str, str]:
    return {"module": "Example", "scope": "secured", "status": "ok"}
```

### Con tokens OAuth2 de Passport

Si migras desde Laravel y validas tokens de Passport, usa las dependencies de
`app/Core/Auth`. Ver [Autenticación](15-autenticacion.md):

```python
from app.Core.Auth import get_current_token, require_scopes, TokenPrincipal

@router.get("/profile")
def profile(principal: TokenPrincipal = Depends(get_current_token)) -> dict:
    return {"user_id": principal.user_id}

@router.post("/admin")
def admin(principal: TokenPrincipal = Depends(require_scopes("admin"))) -> dict:
    return {"ok": True}
```

## Dependency global vs. por router

| Alcance | Cómo | Cuándo |
|---------|------|--------|
| **Global** | `FastAPI(..., dependencies=[...])` en `create_app` | algo que aplica a TODA la app (ej. el locale) |
| **Por router** | `APIRouter(..., dependencies=[...])` | seguridad/reglas propias de un módulo |

Prefiere **por router** para que la lógica quede dentro del módulo (extraíble).

## Manejo de errores (RFC 9457 — Problem Details)

No traduzcas a mano cada error de negocio a `HTTPException` en el controller. Lanza un
**error de dominio** (`app/Core/Errors`) desde donde ocurra (service, repository) y un
**handler global** (`app/Core/Http/ExceptionHandler.py`, ya montado por `create_app`) lo
convierte al sobre JSON **estándar de la industria**: [RFC 9457 *Problem Details*](https://www.rfc-editor.org/rfc/rfc9457)
(`application/problem+json`).

```python
from app.Core.Errors import ResourceNotFoundError, DomainError

# En un service / repository (NO lo atrapes en el controller):
raise ResourceNotFoundError("La compañía 7 no existe", details={"id": 7})
# raise DomainError("Saldo insuficiente", error_code="insufficient_funds", status_code=402, title="Payment Required")
```

Respuesta (status según el error; aquí `404`), `Content-Type: application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Resource not found",
  "status": 404,
  "detail": "La compañía 7 no existe",
  "code": "resource_not_found",
  "errors": { "id": 7 }
}
```

- Mapeo del `DomainError` a los campos RFC: `title` (resumen estable del tipo), `status`,
  `detail` (= `message`, la ocurrencia), `code` (= `error_code`, **estable**, los clientes
  ramifican en él) y `errors` (= `details`, opcional).
- Subclases listas: `ResourceNotFoundError` (404), `ConflictError` (409),
  `UnauthorizedError` (401), `ForbiddenError` (403). O `DomainError` directo con
  `error_code`/`status_code`/`title` a mano.
- **`type`**: `about:blank` por default (RFC-correcto). Si publicas docs de errores, pon
  `PROBLEM_BASE_URL` en `.env` y el `type` apuntará a `<base>/<code>`.
- **Una sola forma para TODO**: la validación `422` de Pydantic sale igual
  (`code: "validation_error"`, con `errors: {campo: [mensajes]}`), los `HTTPException`
  (auth/404/405…) también, y cualquier excepción **no prevista** cae en el catch-all →
  `500` genérico (`code: "internal_error"`) con el **traceback completo al log** y **sin
  filtrar internals** en la respuesta.

## El endpoint `/status`

El único endpoint que registra el kernel directamente: devuelve el nombre del servicio,
los módulos montados y un `status: ok`. Útil para health checks.

## Siguiente paso

[Consola (`jornal`)](08-consola-jornal.md).
