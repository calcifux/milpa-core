# Negociación de contenido

Una sola ruta, dos carriles: HTML si quien la llama es un navegador, JSON si es un
`fetch`/SPA o `curl`. milpa lo resuelve mirando el header `Accept` del request con dos
helpers de `milpa/Core/View`: `prefers_html()` (la decisión) y `negotiate()` (el render).
Es el equivalente al *content negotiation* de DRF, pero sin clases ni configuración: una
función.

```python
from milpa.Core.View import negotiate
return negotiate(request, data, "demo/notes", data_key="notes")
```

## El problema: una ruta o dos

### Forma tradicional

Sin negociación, terminas con **dos rutas paralelas** que producen lo mismo en formatos
distintos: una web (`GET /notes` → HTML) y una API (`GET /api/notes` → JSON). Las reglas
de negocio (qué notas, qué filtro, qué orden) se duplican o se factorizan a mano, y cada
formato es un endpoint separado que mantener.

### Estilo milpa

Una sola ruta sirve los dos carriles. El controller arma los datos **una vez** y delega
el "¿HTML o JSON?" a `negotiate()`, que lee el `Accept` del cliente:

```python
from fastapi import Request
from fastapi.responses import Response

from milpa.Core.Http import Controller, Get
from milpa.Core.View import negotiate
from app.Modules.Demo.Repositories.NoteRepository import NoteRepository
from app.Modules.Demo.Serializers import note_dict


@Controller("", tags=["demo"])
class NotesController:
    @Get("/notes")
    def notes(self, request: Request) -> Response:
        data = [note_dict(n) for n in NoteRepository().all()]
        return negotiate(request, data, "demo/notes", data_key="notes")
```

- Un navegador (`Accept: text/html,...`) recibe la vista `demo/notes` renderizada.
- Un `fetch` o `curl` (`Accept: application/json` o `*/*`) recibe el mismo `data` como
  JSON.

Fíjate que el handler recibe `request: Request` (FastAPI lo inyecta solo) y declara
`-> Response` como tipo de retorno, porque devuelve **o** `HTMLResponse` **o**
`JSONResponse` según el caso.

## `prefers_html(request)` — la decisión

```python
def prefers_html(request: Request) -> bool
```

Responde a una sola pregunta: **¿el cliente prefiere HTML sobre JSON?** Devuelve `True`
para HTML, `False` para JSON. La heurística es deliberadamente **KISS**: decide por la
**posición** de los tipos dentro del header `Accept` (no parsea los *q-values* completos
de la especificación; en la práctica alcanza):

1. Si `text/html` **no** está en el `Accept` → `False` (JSON).
2. Si `text/html` está pero `application/json` **no** → `True` (HTML).
3. Si están los dos → `True` solo si `text/html` aparece **antes** que `application/json`.

| Cliente | Header `Accept` típico | Resultado |
|---------|------------------------|-----------|
| Navegador | `text/html,application/xhtml+xml,...` | HTML |
| `fetch` de una SPA | `application/json` | JSON |
| `curl` (sin `-H`) | `*/*` | JSON |
| `curl -H "Accept: text/html"` | `text/html` | HTML |

Así, **sin configurar nada**, los dos clientes más comunes (navegador y `fetch`) caen en
el carril correcto. Puedes usar `prefers_html()` directo cuando quieras ramificar tú
mismo (por ejemplo, un 401: redirect a `/login` para el navegador, JSON para la API):

```python
from milpa.Core.View import prefers_html, view
from fastapi.responses import JSONResponse, RedirectResponse

if user is None:
    if prefers_html(request):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse({"detail": "No autenticado"}, status_code=401)
```

## `negotiate(...)` — el render

Lo habitual es no ramificar a mano sino dejar que `negotiate()` lo haga por ti:

```python
def negotiate(
    request: Request,
    data: Any,
    template: str,
    *,
    context: dict[str, object] | None = None,
    data_key: str = "data",
) -> Response
```

Su lógica es exactamente:

- Si `prefers_html(request)` → renderiza `template` (vía [`view()`](09-vistas.md)) con
  `data` puesto bajo la clave `data_key`, más el `context` extra que le pases.
- Si no → devuelve `data` como `JSONResponse`, pasándolo antes por `jsonable_encoder` de
  FastAPI (así soporta modelos **Pydantic**, dataclasses, dicts y listas sin convertir a
  mano).

### Parámetros

| Parámetro | Tipo | Para qué |
|-----------|------|----------|
| `request` | `Request` | De dónde se lee el `Accept`. |
| `data` | `Any` | El payload: lo que va como JSON, y lo que entra al template bajo `data_key`. |
| `template` | `str` | Nombre de la vista (namespaced por módulo, ej. `"demo/notes"`). Solo se usa en el carril HTML. |
| `context` | `dict \| None` | Variables **extra** del template (título, usuario, flags). Solo HTML. *Keyword-only.* |
| `data_key` | `str` | Clave bajo la que `data` llega al template (default `"data"`). *Keyword-only.* |

El `template` y el `context` solo importan en el carril HTML; en el carril JSON se
ignoran. Por eso `negotiate()` cuesta lo mismo que un endpoint JSON normal cuando el
cliente pide JSON: no toca Jinja.

### `data_key` y el `context`: cómo llega todo al template

En el carril HTML, `negotiate()` construye el contexto del template como
`{data_key: data, **context}`. Si llamas:

```python
return negotiate(
    request,
    data,
    "demo/notes",
    data_key="notes",
    context={"title": "Mis notas"},
)
```

…el template `demo/notes.html.j2` recibe `notes` (la lista) y `title`. Entonces:

```jinja
<h1>{{ title }}</h1>
<ul>
  {% for note in notes %}
    <li>{{ note.title }} — {{ note.excerpt }}</li>
  {% endfor %}
</ul>
```

Como `data` es la **misma** estructura que sale por JSON (aquí, dicts de `note_dict`,
que ya incluyen el campo computado `excerpt`), el HTML y el JSON nunca se desincronizan:
salen del mismo origen.

## Cuándo usar cada cosa

| Quieres… | Usa |
|----------|-----|
| Una ruta que sirva HTML o JSON con el mismo payload | `negotiate(...)` |
| Ramificar tú la respuesta (redirect vs. 401, partial HTMX vs. JSON) | `prefers_html(request)` + tu propia lógica |
| Solo HTML, sin negociar | [`view(...)`](09-vistas.md) directo |

En el demo, los dos carriles del dashboard (web por sesión-cookie y API por JWT) viven en
controllers **separados** (`WebController` y `ApiController`) a propósito, porque cada uno
tiene su propio mecanismo de auth y sus propias rutas. `negotiate()` es la herramienta
para el caso contrario: cuando **una sola ruta** debe contentar a ambos públicos sin
duplicar la consulta ni las reglas.

## Siguiente paso

[Vistas](09-vistas.md) — el helper `view()`, los layouts Jinja y el namespacing por
módulo en detalle.
