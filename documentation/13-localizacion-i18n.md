# Localización (i18n)

milpa es **monolingüe por default, i18n opt-in**. Una app habla un solo idioma (el
`APP_FALLBACK_LOCALE`) salvo que decidas traducir. El locale es **ambiente**: se fija en
la frontera (HTTP) y se lee donde haga falta. Detrás está `i18nice` (fork mantenido de
`python-i18n`) envuelto en `milpa/Core/Translate`.

## Traducir: `t()`

```python
def t(key: str, variables: dict[str, Any] | None = None, locale: str | None = None) -> str
```

```python
from milpa.Core.Translate import t

t("Emails/master.welcome_message")                  # usa el locale ambiente
t("emails.reminder.subject", {"dias": 15})          # con placeholders
t("example.Greeting.hello", locale="en")            # locale explícito
```

- La **clave** acepta `/` o `.` como separador de namespace (se normaliza internamente).
- Los **placeholders** en el YAML usan sintaxis `%{nombre}`.
- `app_name` (de `APP_NAME`) **siempre** está disponible en las variables, así los
  catálogos pueden decir `%{app_name}` sin que lo pases.
- Si **falta la clave**, `t()` devuelve la propia clave (no lanza excepción). Así se ven
  los faltantes en QA sin romper el envío de un correo. (Igual que `__()` de Laravel.)

En templates Jinja, `t` es un global: `{{ t("clave", {...}) | safe }}`.

## El locale ambiente

```python
from milpa.Core.Translate import current_locale, set_request_locale
```

| Función | Qué hace |
|---------|----------|
| `current_locale() -> str` | El locale del request actual; fuera de un request cae a `APP_FALLBACK_LOCALE`. |
| `set_request_locale(locale)` | Fija el locale (lo llama la frontera HTTP). |
| `resolve_accept_language(header)` | Parsea `Accept-Language` (mayor `q`, reduce `es-MX` → `es`). |

### En HTTP es automático

La dependency global `_use_request_locale` (ver [Ciclo de vida](05-ciclo-de-vida.md))
corre en cada endpoint, lee `Accept-Language` y fija el locale. **No lo pasas tú**: `t()`
y `current_locale()` ya lo ven.

### Prioridad

```
locale explícito en t(...)  >  locale del request (contextvar)  >  APP_FALLBACK_LOCALE
```

### Fuera de HTTP (cron, worker, CLI)

No hay request, así que `current_locale()` cae al fallback. Si necesitas un idioma
concreto en background, captúralo donde sí lo tienes y pásalo. El correo encolado ya lo
hace: captura el locale al encolar y lo restaura en el worker antes de `build()` (ver
[Correo](10-correo.md)).

## Catálogos YAML

### Compartidos

Viven en `app/Resources/Lang/`. La raíz del YAML es el locale:

```yaml
# app/Resources/Lang/Emails/master.es.yml
es:
  welcome_message: 'Bienvenido a %{app_name}.'
  faq_message: 'Cualquier duda, escríbenos. %{app_name} · %{contact_phone}'
```

Nombre de archivo: `{namespace}.{locale}.yml`. La clave de uso combina carpeta + archivo
+ clave anidada: `t("Emails/master.welcome_message")`.

### Por módulo (namespaced)

Cada módulo trae sus catálogos bajo `Modules/<X>/Resources/Lang/<x>/`, donde `<x>` (el
nombre del módulo en minúsculas) actúa de **prefijo de namespace** para no chocar con
otros módulos:

```yaml
# app/Modules/Example/Resources/Lang/example/Greeting.es.yml
es:
  hello: "Hola desde el módulo Example"
```
```python
t("example.Greeting.hello")
```

El descubrimiento es automático (`_module_lang_dirs()` escanea `Modules/<X>/Resources/Lang`);
no registras directorios a mano.

## Configuración

| Setting | Default | Para qué |
|---------|---------|----------|
| `APP_FALLBACK_LOCALE` | `es` | Idioma por defecto cuando no se pasa locale. |

`i18nice` se configura solo: `file_format=yml`, `filename_format={namespace}.{locale}.{format}`,
`fallback=APP_FALLBACK_LOCALE`, y los directorios compartido + de cada módulo. Soporta
interpolación `%{x}`, pluralización (`one`/`many`/…) y referencias (`%{.otra_key}`).

## Monolingüe vs. multilingüe (cuándo NO usar i18n)

| | Monolingüe | Multilingüe |
|--|-----------|-------------|
| Texto | literal en el código/template | vía `t()` + catálogos YAML |
| Locale | se ignora | viene del ambiente (Accept-Language) |
| Ejemplo | `PedidoListoMailable` | `MailableSignedCheck` |

Empieza monolingüe; sube a `t()` solo cuando de verdad necesites más de un idioma.

## Siguiente paso

[Logging](14-logging.md).
