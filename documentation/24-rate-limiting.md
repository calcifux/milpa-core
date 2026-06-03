# Rate limiting

milpa **no reinventa** el límite de peticiones: SlowAPI (sobre `limits`) ya resuelve
ventanas, estrategias y backends (memoria/Redis). milpa solo lo envuelve para que (1)
escribas un decorador milpa-branded por ruta en vez de acoplarte al singleton de SlowAPI,
y (2) el `429` salga en **RFC 9457** igual que TODO error del framework. Es el equivalente
a `@throttle` de DRF, pero declarativo y con el mismo sobre de error.

```python
from milpa.Core.Http import Controller, Post, rate_limit
from fastapi import Request

@Controller("/api", tags=["demo-api"])
class ApiController:
    @Post("/login")
    @rate_limit("5/minute")        # máx 5 intentos/min por IP
    def login(self, request: Request, body: LoginInput) -> dict[str, str]:
        ...
```

## El decorador `@rate_limit`

`@rate_limit` (en `milpa/Core/Http/RateLimit.py`) marca una ruta con un límite:

```python
def rate_limit(limit_value: str, *, key_func=None, **kwargs): ...
```

- `limit_value`: la sintaxis de SlowAPI/`limits` — `"5/minute"`, `"100/hour"`,
  `"10/second"` o combinaciones (`"10/second;1000/day"`).
- `key_func`: por quién se cuenta. **Por default = la IP del cliente**
  (`get_remote_address`). Pásale otra función para limitar por usuario, por API key, etc.
- `**kwargs`: el resto se reenvía a `limiter.limit` de SlowAPI (`per_method`,
  `exempt_when`, `cost`, …).

### Dos reglas que SlowAPI EXIGE

Estas dos no son opcionales; si las omites, el límite no engancha o el índice de
parámetros se descuadra:

1. **El handler DEBE tener `request: Request` en su firma.** SlowAPI lee el contexto
   (IP, estado de la ventana) de ese `Request`. Sin él, falla al enganchar.

2. **El decorador de verbo (`@Post`/`@Get`/…) va ARRIBA de `@rate_limit`.** El verbo
   registra la ruta; `@rate_limit` solo la marca debajo.

```python
@Post("/login")            # ✅ el verbo va ARRIBA
@rate_limit("5/minute")    #    @rate_limit debajo
def login(self, request: Request, body: LoginInput) -> dict[str, str]:
    ...
```

!!! note "Por qué funciona en controllers class-based"
    `@rate_limit` **no envuelve la función en el cuerpo de la clase** (ahí la firma aún
    lleva `self`, y SlowAPI contaría `self` como primer parámetro, descuadrando el índice
    de `request`). En su lugar **marca** la ruta vía `add_route_wrapper`, y el `@Controller`
    aplica el límite de SlowAPI al **bound method** (firma ya sin `self`). Por eso es
    idéntico en estilo función o en `@Controller`, sin que tengas que pensarlo.

## El `429` en RFC 9457

Cuando se excede el límite, SlowAPI lanza `RateLimitExceeded`. milpa lo traduce a su
sobre estándar (`application/problem+json`), **el mismo** que cualquier otro error del
framework (ver [Rutas y controladores](07-rutas-y-controladores.md#manejo-de-errores-rfc-9457-problem-details)):

```json
{
  "type": "about:blank",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Límite de peticiones excedido (5 per 1 minute).",
  "code": "rate_limit_exceeded"
}
```

El cliente ramifica en `code: "rate_limit_exceeded"` (estable). El handler global
(`register_rate_limit`, montado por `create_app`) inyecta además `Retry-After` y los
headers `X-RateLimit-*` que SlowAPI ya calculó para esa ruta — **si** los headers están
activados (ver abajo).

## Configuración (Settings)

Los campos viven en `milpa/Core/Config/Settings.py`. El `limiter` es un singleton del
proceso que los lee **una vez al importar**:

| Setting | Default | Para qué |
|---------|---------|----------|
| `rate_limit_enabled` | `True` | Activa los `@rate_limit`. En `False`, **TODOS son no-op** (útil en tests/local). |
| `rate_limit_default` | `""` | Límite **global** opcional para toda la app (ej. `"200/minute"`). Vacío = solo cuentan los `@rate_limit` por ruta. |
| `rate_limit_storage_uri` | `"memory://"` | Backend de conteo. `memory://` (por proceso) o `redis://host:6379` en prod. |
| `rate_limit_headers` | `False` | Inyecta `X-RateLimit-*` + `Retry-After` en las respuestas. Off por default. |

### `memory://` vs. Redis en producción

`memory://` cuenta **por proceso**. Basta en local o con un solo worker, pero en
producción multi-worker la memoria **no se comparte**: el límite efectivo se multiplica
por el número de workers (cada uno cuenta su propia ventana). Para un límite real y
compartido, apunta a Redis:

```bash
# .env (prod multi-worker)
RATE_LIMIT_STORAGE_URI=redis://localhost:6379
```

### Headers off por default (estilo milpa)

`rate_limit_headers` viene **apagado** a propósito. SlowAPI EXIGE un `response: Response`
en cada handler limitado para inyectar los `X-RateLimit-*`, y los endpoints estilo milpa
devuelven `dict` (no `Response`). Mantenerlo off deja las firmas limpias.

Si quieres los headers, **enciéndelo y añade `response: Response` a tus rutas limitadas**:

```python
from fastapi import Request, Response

@Post("/login")
@rate_limit("5/minute")
def login(self, request: Request, response: Response, body: LoginInput) -> dict[str, str]:
    ...
```

```bash
# .env
RATE_LIMIT_HEADERS=true
```

Con eso, tanto las respuestas exitosas como el `429` salen con los headers completos.

## Forma tradicional vs. estilo milpa

| | Forma tradicional (SlowAPI directo) | Estilo milpa |
|---|---|---|
| Decorador | `@limiter.limit("5/minute")` acoplado al singleton | `@rate_limit("5/minute")` milpa-branded |
| Class-based | Choca con `self` (índice de `request` descuadrado) | Funciona igual (envuelve el bound method) |
| Error `429` | JSON propio de SlowAPI | RFC 9457 (`code: rate_limit_exceeded`), como TODO error |
| Apagado global | Quitar decoradores a mano | `rate_limit_enabled = False` (todos no-op) |

## Ejemplo real: login anti fuerza-bruta

El módulo `Demo` limita el login del carril API
(`app/Modules/Demo/Http/ApiController.py`) para frenar ataques de diccionario: máximo 5
intentos por minuto por IP. Al sexto, el cliente recibe el `429` en RFC 9457.

```python
from fastapi import Request
from milpa.Core.Auth import Auth
from milpa.Core.Errors import UnauthorizedError
from milpa.Core.Http import Controller, Post, rate_limit

@Controller("/api", tags=["demo-api"])
class ApiController:
    @Post("/login")
    @rate_limit("5/minute")  # anti fuerza-bruta: máx 5 intentos/min por IP
    def login(self, request: Request, body: LoginInput) -> dict[str, str]:
        token = Auth.attempt(body.email, body.password)
        if token is None:
            raise UnauthorizedError("Credenciales inválidas.")
        return {"access_token": token, "token_type": "bearer"}
```

Pruébalo en local (con `rate_limit_enabled = True`, el default):

```bash
# El 6º intento en menos de un minuto devuelve 429 (RFC 9457)
for i in $(seq 1 6); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/login \
    -H "Content-Type: application/json" \
    -d '{"email":"x@example.com","password":"mal"}'
done
# 401 401 401 401 401 429
```

Observa que limitar por IP protege incluso cuando las credenciales son inválidas (el
`401`): el `@rate_limit` corre **antes** de la lógica del handler, así que ni siquiera se
toca la BD a partir del 6º intento.

## Siguiente paso

[Autenticación](15-autenticacion.md).
