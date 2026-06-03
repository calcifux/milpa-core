# Errores y RFC 9457 (nunca falla en silencio)

milpa tiene un **tenet** que atraviesa todo el framework: **nunca falla en silencio**.
Un error que se traga —un `except: pass`, un parámetro ignorado, un `return None`
ambiguo— es deuda que se cobra a las 3am, cuando algo "no jala" y no hay rastro de por
qué. La regla es simple: **log-or-throw**. Todo error o se lanza (y un handler lo
convierte en una respuesta limpia) o se loguea (con una pista accionable). Nada se traga.

Eso se concreta en tres bordes:

- **Web** — TODO error HTTP sale en **RFC 9457 (`application/problem+json`)**: una sola
  forma para dominio, validación, auth y bugs.
- **CLI** — el borde de error de `jornal` distingue error esperado (mensaje limpio) de
  bug inesperado (conciso + traceback al log).
- **Lógica** — un bug (ability sin policy, handler sin registrar) **truena rápido**
  (fail-fast); un fallo best-effort en remoto **deja rastro observable**, nunca silencio.

## El tenet en tres modos

| Modo | Cuándo | Qué hace |
|------|--------|----------|
| **fail-fast** | Es un BUG de programación/config (ability sin `@policy`, comando sin handler). | Truena ya, con un error claro que apunta al fix. |
| **log-or-throw** | Error de negocio esperado ("no existe", "ya existe"). | Lo lanzas como `DomainError`; el handler lo rinde en RFC 9457. |
| **best-effort OBSERVABLE** | Operación que puede degradarse sin romper el request (cobro secundario, Gate en modo no-estricto). | Sigue, pero **loguea** lo que decidió y por qué. Nunca en silencio. |

La diferencia entre milpa y un `try/except` casero: aquí **no decides en cada `catch`**
si loguear o no. El borde (handler HTTP, borde del CLI) ya lo hace, de una forma, para
todo. Tú solo lanzas el error correcto desde donde ocurre.

## La jerarquía `DomainError`

Los errores de negocio viven en `milpa/Core/Errors`, **fuera** de `Http` a propósito: la
capa de persistencia (un `Repository.find_or_fail`) puede lanzarlos sin importar FastAPI
(respeta el layering "persistencia ↛ web"). Son neutrales al transporte: no saben que
existe el RFC ni el status HTTP como tal — solo llevan los datos que el handler mapea.

`DomainError` es la base. Cada subclase fija sus defaults (`status_code`, `error_code`,
`title`):

| Excepción | status | `error_code` | Significado |
|-----------|--------|--------------|-------------|
| `ResourceNotFoundError` | 404 | `resource_not_found` | El recurso pedido no existe. |
| `ConflictError` | 409 | `conflict` | Choque con el estado: duplicado, transición inválida. |
| `UnauthorizedError` | 401 | `unauthorized` | Falta autenticación / credencial inválida. |
| `ForbiddenError` | 403 | `forbidden` | Autenticado, pero sin permiso para esta acción. |
| `InvalidFilterError` | 422 | `invalid_filter` | El cliente pidió un filtro/orden fuera de la whitelist. |
| `HandlerNotFoundError` | 500 | `handler_not_found` | (BUG) Comando del Mediator sin `@handles`. |
| `UndefinedAbilityError` | 500 | `undefined_ability` | (BUG) Ability del Gate sin `@policy`. |

Las dos últimas son `500` a propósito: **no son errores de cliente, son bugs tuyos** —
por eso fail-fast en vez de un `4xx` que confundiría.

### Firma de `DomainError`

```python
class DomainError(Exception):
    status_code: int = 400
    error_code: str = "domain_error"
    title: str = "Domain error"

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        error_code: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
    ) -> None: ...
```

- `message` → `detail` del RFC: la explicación de **esta** ocurrencia.
- `details` → `errors` del RFC: datos opcionales (qué id, qué campo).
- `error_code` / `status_code` / `title`: override **por instancia** sin tener que
  subclasear para cada caso puntual.

### Forma tradicional vs. estilo milpa

**Forma tradicional** — el service conoce el transporte y traduce a mano cada caso a un
`HTTPException` (o, peor, devuelve `None` y el controller adivina):

```python
# En el service: acoplado a FastAPI, y el status se decide aquí abajo.
def find_note(note_id: int) -> Note:
    note = session.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="...")   # service ↛ web roto
    return note
```

**Estilo milpa** — el dominio lanza lo que SABE explicar ("no existe"); el borde decide
el transporte. Ejemplo real de `Modules/Demo/Services/NoteService.py`:

```python
from milpa.Core.Errors import ResourceNotFoundError

@staticmethod
def _find(note_id: int) -> Note:
    note = current_session().get(Note, note_id)
    if note is None:
        raise ResourceNotFoundError(f"Nota {note_id} no existe", details={"id": note_id})
    return note
```

Y en `Modules/Demo/Services/UserService.py`, un conflicto de duplicado:

```python
from milpa.Core.Errors import ConflictError

if self._email_taken(email):
    raise ConflictError("El email ya está registrado.", details={"email": email})
```

El controller **no atrapa** estos errores: los deja subir. Un service de dominio sin un
solo `import fastapi`.

## El borde web: RFC 9457 (Problem Details)

Todo error que sale de un endpoint se normaliza al sobre estándar de la industria:
[RFC 9457 *Problem Details for HTTP APIs*](https://www.rfc-editor.org/rfc/rfc9457), media
type `application/problem+json`. El cuerpo lo arma `build_problem()`
(`milpa/Core/Http/ProblemDetails.py`):

```json
{
  "type": "about:blank",
  "title": "Resource not found",
  "status": 404,
  "detail": "Nota 7 no existe",
  "code": "resource_not_found",
  "errors": { "id": 7 }
}
```

Campos del RFC (más dos extensiones de milpa):

| Campo | Origen | Para qué |
|-------|--------|----------|
| `type` | URI del tipo de problema. | `about:blank` por default; ver abajo. |
| `title` | `DomainError.title` | Resumen humano **estable** del tipo (no cambia por ocurrencia). |
| `status` | `DomainError.status_code` | El código HTTP, duplicado en el cuerpo por conveniencia. |
| `detail` | `DomainError.message` | Explicación de **esta** ocurrencia. |
| `code` *(extensión)* | `DomainError.error_code` | Código **estable, de máquina**: el cliente ramifica aquí. |
| `errors` *(extensión)* | `DomainError.details` | Datos opcionales; solo aparece si lo pasas. |

El `code` es la clave: un cliente **no** debe parsear el texto de `detail` (cambia, se
traduce). Ramifica en `code == "conflict"`, que es estable.

### `type`: `about:blank` o tu doc de errores

```python
def problem_type_uri(code: str) -> str:
    base = settings.problem_base_url.rstrip("/")
    if not base:
        return "about:blank"
    return f"{base}/{code.replace('_', '-')}"
```

Por default `about:blank` (RFC-correcto cuando no publicas páginas de error — no inventa
URLs que no resuelven). Si pones `PROBLEM_BASE_URL` en `.env`, el `type` apunta a
`<base>/<code-kebab>` (p. ej. `https://docs.tuapp.com/errors/resource-not-found`).

### Una sola forma para TODO

`register_exception_handlers()` (`milpa/Core/Http/ExceptionHandler.py`, ya montado por
`create_app`) instala **cuatro** handlers para que NINGÚN error escape del formato:

| Handler | Captura | Resultado |
|---------|---------|-----------|
| `DomainError` | Tus errores de negocio. | Su `status`/`title`/`code`/`detail`/`errors`. Es esperado: se loguea a **INFO**. |
| `RequestValidationError` | Validación de Pydantic/FastAPI (422). | `code: "validation_error"`, reagrupado por campo: `errors: {campo: [mensajes]}`. |
| `HTTPException` | Auth/infra/404/405 de Starlette/FastAPI. | `title`/`code` derivados del status (vía `http.HTTPStatus`). |
| catch-all `Exception` | Cualquier cosa NO prevista (bug, infra caída). | `500` genérico, `code: "internal_error"`. |

La validación de Pydantic merece nota: FastAPI por default devuelve `{"detail": [...]}`,
una forma distinta. milpa la reagrupa al **mismo shape** que todo lo demás, estilo
Laravel:

```json
{
  "type": "about:blank",
  "title": "Validation failed",
  "status": 422,
  "detail": "La solicitud no superó la validación.",
  "code": "validation_error",
  "errors": { "email": ["value is not a valid email address"], "rfc": ["Field required"] }
}
```

### El catch-all: fail-fast SIN filtrar internals

Una excepción no prevista **es un bug o infra caída**. El handler aplica las dos mitades
del tenet a la vez:

```python
async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    # No previsto: ES un bug o infra caída. Traceback COMPLETO al log; al cliente, un
    # 500 genérico SIN internals (nunca exponemos el mensaje real de la excepción).
    logger.exception("Unhandled exception | {t}", t=type(exc).__name__)
    return _problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="Error interno del servidor.",
        code="internal_error",
    )
```

- **No se traga**: `logger.exception` deja el traceback **completo** en el log (observable).
- **No fuga**: al cliente le llega un `500` genérico, **sin** el mensaje real de la
  excepción (ni rutas, ni nombres de tabla, ni stack).

## El borde del CLI (`jornal`)

El CLI tiene su propio borde de error, **simétrico** al handler HTTP. Vive en `run()` de
`milpa/Core/Console/Cli.py`, que envuelve toda la app de Typer:

```python
def run() -> None:
    setup_logging()
    try:
        app()
    except DomainError as error:
        raise SystemExit(_render_cli_error(error)) from None
    except Exception as error:  # borde final del CLI: nada escapa sin loguearse
        raise SystemExit(_render_cli_error(error)) from None
```

`pretty_exceptions_enable=False` en la app de Typer es deliberado: **nosotros**
controlamos el render, para no escupir el traceback crudo de Rich (con locals) ante un
error esperado. El render distingue los dos casos:

```python
def _render_cli_error(error: BaseException) -> int:
    console = Console()
    if isinstance(error, DomainError):
        console.print(f"[red]✗[/red] {error.message} [dim]({error.error_code})[/dim]")
        return 1
    logger.opt(exception=True).error("CLI | error inesperado ({t})", t=type(error).__name__)
    console.print(f"[red]✗[/red] Error interno ({type(error).__name__}). El detalle quedó en el log.")
    return 1
```

| Tipo de error | En consola | En el log | Exit code |
|---------------|-----------|-----------|-----------|
| **`DomainError`** (esperado) | Mensaje LIMPIO + su `error_code`, sin traceback. | (nada extra) | `1` |
| **Inesperado** (bug) | Conciso: `Error interno (X). El detalle quedó en el log.` | Traceback **completo** vía loguru. | `1` |

Ejemplo en consola de un error de dominio:

```
✗ Nota 7 no existe (resource_not_found)
```

Y de un bug inesperado (el detalle no se pierde, va al log):

```
✗ Error interno (KeyError). El detalle quedó en el log.
```

### `diagnose`: valores en el traceback solo en dev

El traceback que loguea el CLI (y toda la app) tiene un matiz de seguridad, controlado en
`setup_logging()` (`milpa/Core/Logging/Logging.py`):

```python
logger.add(
    sys.stderr,
    ...
    backtrace=True,
    # diagnose añade los VALORES de las variables al traceback (útil al depurar, pero FUGA
    # datos —tokens, passwords— en consola). Solo en local; en qa/prod, off (el archivo igual).
    diagnose=settings.app_env == "local",
)
```

- En `APP_ENV=local`: `diagnose=True` → el traceback en consola muestra los **valores** de
  las variables (depuras rápido).
- En qa/prod: `diagnose=False` → el traceback sigue, pero **sin** los valores (no fuga
  tokens ni passwords a la consola).

El sink de archivo siempre va con `diagnose=False`: nunca persiste valores sensibles a
disco, en ningún ambiente.

## Mensajes ACCIONABLES (sin verbosidad)

Un log que dice "permiso denegado" cuesta horas en prod ("¿por qué deniega?"). El tenet
exige **una pista clara que apunte al fix**, no un volcado verboso. El mejor ejemplo es el
**Gate** en modo no-estricto: cuando evalúas una ability que nadie registró, deniega
(secure-by-default) pero **dice exactamente qué falta y dónde**
(`milpa/Core/Auth/Authorization.py`):

```python
logger.warning(
    "Gate | ability {a!r} sin policy → DENIEGO. Defínela: @policy({a!r}) en Modules/<X>/Policies/ "
    "(se auto-descubre al arranque).",
    a=ability,
)
```

El warning no solo dice "denegado": dice **qué** (la ability), **qué falta** (`@policy`) y
**dónde** ponerlo (`Modules/<X>/Policies/`). Eso es accionable.

El mismo Gate, en modo estricto (`AUTH_STRICT_ABILITIES`, típico en dev/test), aplica
fail-fast en vez de log-and-deny: lanza `UndefinedAbilityError`, cuyo `message` ya trae la
pista:

```python
class UndefinedAbilityError(DomainError):
    status_code = 500
    error_code = "undefined_ability"
    title = "Undefined ability"

    def __init__(self, *, ability: str) -> None:
        super().__init__(
            f"La ability {ability!r} sin policy. Defínela: @policy({ability!r}) en Modules/<X>/Policies/ "
            f"(se auto-descubre al arranque).",
            details={"ability": ability},
        )
```

La misma idea cierra el círculo: el mismo bug, **fail-fast en dev** (truena al instante
para cazarlo ya) y **deny + warning observable en prod** (no rompe el request, pero deja
el rastro exacto). En ninguno de los dos casos falla en silencio.

## Receta

1. **En el dominio** (service/repository): lanza el `DomainError` que mejor describa el
   caso. No traduzcas a `HTTPException`. No devuelvas `None` ambiguo.
2. **En el controller**: no atrapes los `DomainError`; déjalos subir al handler global.
3. **Para clientes**: ramifica en `code` (estable), nunca en `detail` (cambia/se traduce).
4. **Bugs**: deja que truenen. El catch-all los loguea con traceback completo y devuelve un
   `500` limpio. No los escondas con un `except: pass`.
5. **Best-effort**: si algo puede degradarse sin romper, está bien — pero **loguea** qué
   decidiste y por qué. Best-effort sí; silencioso no.

## Siguiente paso

[Autenticación](15-autenticacion.md) — de dónde salen `ForbiddenError`/`UnauthorizedError`
y cómo el Gate los lanza.
