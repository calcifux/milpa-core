# PWA

Convertir un surco en **PWA** (instalable, con offline) son dos one-liners en el controller.
milpa arma el manifest **en runtime** y sirve el Service Worker con los headers correctos; el
surco aporta su Service Worker (Serwist) y sus iconos. Vive en `milpa/Core/View/Pwa.py` y se
apoya en los helpers de Vite — así que también es **opt-in**: una app sin PWA no llama nada de
esto.

Para el modelo de surcos y `window.__ENV` ver [Microfrontends (surcos)](30-microfrontends-surcos.md).

## Forma tradicional vs. estilo milpa

**Forma tradicional:** cada app copia ~40 líneas de plomería — un `manifest.json` hardcodeado
(que truena tras un reverse proxy porque `start_url`/`scope` quedaron fijos) y la ruta del
`sw.js` a mano.

**Estilo milpa:** dos one-liners en el controller. El framework arma el resto en runtime —
`start_url`/`scope` con el prefijo real del deploy e iconos auto-descubiertos del build:

```python
from milpa.Core.View import Pwa

@Get("/manifest.webmanifest")
def manifest(self, request: Request) -> Response:
    return Pwa.webmanifest(
        request,
        prefix="/spa",
        app="demo-spa",
        background_color="#0A0A0A",
        theme_color="#FF6B1A",
    )

@Get("/sw.js")
def sw(self) -> FileResponse:
    return Pwa.service_worker(app="demo-spa")
```

## `Pwa.webmanifest()`: el manifest en runtime

```python
def webmanifest(
    request: Request,
    *,
    prefix: str,
    theme_color: str,
    background_color: str,
    app: str | None = None,
    name: str | None = None,
    short_name: str | None = None,
    description: str = "",
    display: str = "standalone",
    extra: Mapping[str, object] | None = None,
) -> Response
```

Lo importante es que el manifest se arma **en runtime** (por eso lo sirve el backend y no es un
estático del frontend): `start_url` y `scope` llevan el **prefijo real del deploy** (el
`root_path` ASGI). Bajo una sub-ruta de reverse proxy salen correctos **sin rebuild** —
`start_url` cae dentro de `scope`, como exige el estándar.

| Parámetro | Para qué |
|-----------|----------|
| `request` | De ahí sale el `root_path` (prefijo del deploy) para `start_url`/`scope`. |
| `prefix` | Dónde vive el surco (p. ej. `"/spa"`). Compone `start_url` y `scope` (ambos `<base><prefix>/` — con barra final: el in-scope del W3C compara prefijos de ruta). |
| `theme_color` / `background_color` | Colores de la PWA (obligatorios). |
| `app` | Qué surco — desambigua en multi-app (los iconos salen de su build). |
| `name` / `short_name` | Nombres; si los omites, se derivan de `app` y `APP_NAME`. |
| `description` / `display` | Descripción y modo (`standalone` por default). |
| `extra` | Agrega o sobrescribe claves del manifest (p. ej. `orientation`, `shortcuts`). |

Devuelve un `Response` con `media_type="application/manifest+json"`.

### Convención de iconos

Los iconos se **auto-descubren del build** por convención (carpeta `icons/` del surco). El
patrón de nombre es `icons/icon-<size>[-maskable].png`:

```
public/icons/
  icon-192.png
  icon-512.png
  icon-192-maskable.png      # safe-zone para que Android no recorte las orillas
  icon-512-maskable.png
  apple-touch-icon.png       # va aparte, en el <link> del template
```

Los normales se listan primero; los `-maskable` después, con su `"purpose": "maskable"`. El
archivo maskable va **aparte** (con safe-zone): Android recorta los maskable, así que reusar el
normal perdería las orillas. Las URLs salen por `vite_asset()`, de modo que heredan `ASSET_URL`
(CDN/sub-ruta) solas. Una carpeta sin iconos es legal: el manifest sale con `icons: []` y el
navegador lo avisa.

El `apple-touch-icon.png` no entra al manifest; se referencia desde el template con
`vite_asset()`:

```jinja2
<link rel="apple-touch-icon" href="{{ vite_asset('icons/apple-touch-icon.png', app='demo-spa') }}">
```

## `Pwa.service_worker()`: el SW con `no-cache`

```python
def service_worker(app: str | None = None, *, filename: str = "sw.js") -> FileResponse
```

Sirve el Service Worker compilado (`<dist>/sw.js`) con el header **obligatorio**
`Cache-Control: no-cache`. La razón es de vida o muerte para una PWA: un SW cacheado = updates
que nunca llegan (el navegador revalida byte a byte contra esta respuesta). Si el build aún no
existe, truena con instrucción (`npm run build`).

> Declara la ruta del SW **antes** del catch-all del surco y **desde el prefijo del surco**
> (p. ej. `/spa/sw.js`), para que su scope cubra a la app.

## El Service Worker en el surco (Serwist)

El SW lo compila el surco con `@serwist/vite` (`src/sw.js` → `dist/sw.js`). El del demo es
offline-first en su forma mínima:

- **Precache del shell** — los chunks que genera Vite (vía el manifest que Serwist inyecta en
  `self.__SW_MANIFEST`) más el shell `/spa`: revisitas instantáneas y cold-start offline.
- **`NetworkOnly` para la API** — `/api/*` y `/status` **nunca** pasan por caché (regla
  explícita **antes** del catch-all). Sin esto, el runtime-caching de Serwist serviría datos
  stale de la API.
- **Fallback offline** — navegar sin red a algo no cacheado sirve `/spa` (el shell
  precacheado; el router del cliente resuelve la vista).

```js
// surcos/demo-spa/src/sw.js (resumen)
import {NetworkOnly, Serwist} from 'serwist';

// '/nombre-reverse/spa/sw.js' → '/nombre-reverse' ; '/spa/sw.js' → ''
const BASE = self.location.pathname.replace(/\/spa\/sw\.js$/, '');

const apiNetworkOnly = {
    matcher: ({url}) => url.pathname.startsWith(`${BASE}/api/`) || url.pathname === `${BASE}/status`,
    handler: new NetworkOnly(),
};
```

El SW no ve `window.__ENV` (corre en otro contexto), pero **su propia URL ya trae el prefijo**
(`…/<prefijo>/spa/sw.js`) — el `BASE` se deriva de ahí. Eso lo hace funcionar bajo sub-ruta de
proxy sin tocarlo.

## Registro manual del SW bajo sub-ruta

El registro del Service Worker se hace **a mano** (no `virtual:serwist`): bajo un subpath el
scope no se auto-deriva bien. Se hace solo en **prod** (en dev el SW serviría assets stale y
pelearía con el HMR), con URL y scope **explícitos** desde `BASE`:

```jsx
// surcos/demo-spa/src/main.jsx
const BASE = `${window.__ENV?.BASE_PATH ?? ''}/spa`;

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register(`${BASE}/sw.js`, {scope: `${BASE}/`});
    });
}
```

`BASE` sale de `window.__ENV.BASE_PATH` (inyectado por el shell) + `/spa`. El scope `<BASE>/`
limita el **control** del SW a la PWA (no toca el carril web de milpa). URL y scope se escriben
explícitos a propósito: `'./sw.js'` contra `/spa` **sin** barra final resolvería a `/sw.js` —
la trampa clásica del scope de los Service Workers.

## El demo `/spa` como referencia

El surco `demo-spa` (React 19 + react-router 7 + Serwist, identidad **StackCraft**) es la
referencia end-to-end. Su `SpaController` declara las cuatro rutas del carril SPA+PWA:

```python
@Controller("/spa", tags=["demo-spa"])
class SpaController:
    @Get("")
    def shell(self, request: Request) -> HTMLResponse:
        return view("demo/spa", shell_context(request))

    @Get("/manifest.webmanifest")          # one-liner: el manifest en runtime
    def manifest(self, request: Request) -> Response: ...

    @Get("/sw.js")                          # one-liner: el SW con no-cache
    def sw(self) -> FileResponse: ...

    @Get("/{path:path}")                    # catch-all SPA-fallback, acotado a /spa
    def shell_subruta(self, request: Request, path: str) -> HTMLResponse:
        return view("demo/spa", shell_context(request))
```

El catch-all devuelve el **mismo shell** para cualquier sub-ruta de `/spa`, así un deep-link
recarga bien (el server siempre responde el shell, el router del cliente resuelve la vista).
Está acotado al prefijo `/spa`: **no** se come `/api`. Las rutas de la PWA
(`/manifest.webmanifest`, `/sw.js`) van **antes** del catch-all para que hagan match primero.

## Siguiente paso

[Errores y RFC 9457](28-errores-y-rfc9457.md).
