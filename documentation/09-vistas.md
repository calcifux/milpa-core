# Vistas

milpa renderiza HTML con **Jinja2**. El motor (`milpa/Core/View/TemplateEngine.py`) y el
helper `view()` (`milpa/Core/View/View.py`) son el equivalente a Blade: layouts con
herencia, namespacing por módulo y un par de globals útiles.

## El helper `view()`

```python
def view(template: str, context: dict[str, object] | None = None) -> HTMLResponse
```

Renderiza un template y devuelve un `HTMLResponse` (listo para FastAPI). El sufijo
`.html.j2` es opcional.

```python
from fastapi.responses import HTMLResponse
from milpa.Core.View import view

@router.get("/welcome", response_class=HTMLResponse)
def welcome() -> HTMLResponse:
    return view("example/welcome", {"nombre": "Calcifux"})
```

## Dónde viven los templates y cómo se nombran

Hay dos raíces, combinadas por un loader de Jinja:

| Nombre que pasas | Se resuelve a |
|------------------|----------------|
| `"index"` | `app/Resources/Views/index.html.j2` (compartido) |
| `"Emails/Trans/master"` | `app/Resources/Views/Emails/Trans/master.html.j2` (compartido) |
| `"example/welcome"` | `app/Modules/Example/Resources/Views/welcome.html.j2` (módulo) |

El **prefijo** de los templates de módulo es el nombre del módulo en minúsculas. Es el
equivalente al `example::welcome` de Laravel. El descubrimiento es automático
(`_module_views_dirs()` escanea `Modules/<X>/Resources/Views`); no registras nada.

## Herencia de layouts

Como en Blade, los templates extienden un layout base:

```jinja2
{# app/Modules/Example/Resources/Views/welcome.html.j2 #}
{% extends "index.html.j2" %}

{% block title %}{{ app_name }} — Example{% endblock %}

{% block content %}
  <h1>{{ t("example.Greeting.hello") }}</h1>
  <p>Hola {{ nombre }}.</p>
{% endblock %}
```

## Globals disponibles en todos los templates

El `TemplateEngine` registra tres globals:

| Global | Qué es |
|--------|--------|
| `t` | La función de traducción (ver [i18n](13-localizacion-i18n.md)). `{{ t("clave", {...}) }}` |
| `app_name` | El `APP_NAME` del `.env`. Útil en footers/títulos. |
| `asset` | URL de un estático: `{{ asset('welcome.css') }}` → `/static/welcome.css`. |

## `StrictUndefined`: las variables faltantes revientan

El motor usa `StrictUndefined` y autoescape de HTML. Si un template referencia una
variable que no está en el contexto, lanza `UndefinedError` (mejor que renderizar vacío
en silencio, sobre todo en correos). Para valores opcionales, usa `default`:

```jinja2
{{ sender_name | default('', true) }}
{% if logo_cid is defined %}<img src="cid:{{ logo_cid }}">{% endif %}
```

## Estáticos

Los estáticos de un módulo (`Modules/<X>/Resources/Static/`) se montan en `/static/<x>`;
los compartidos (`app/Resources/Static/`) en `/static`. Refiérelos con `asset()`:

```jinja2
<link rel="stylesheet" href="{{ asset('welcome.css') }}">
```

## Frontend con Vite (opt-in)

Para un frontend con bundling (HMR en dev, chunks hasheados en prod) o microfrontends,
milpa trae un asset-pipeline opt-in estilo `laravel-vite`, con los globals `vite()`,
`vite_asset()` y `vite_react_refresh()`. Ver [Vite y assets](29-vite-y-assets.md) y
[Microfrontends (surcos)](30-microfrontends-surcos.md).

## Vistas y correo

El mismo motor renderiza los correos. Los Mailables apuntan a un `template` con la misma
convención de nombres (compartido o namespaced por módulo). Ver [Correo](10-correo.md).

## Siguiente paso

[Correo](10-correo.md).
