# Vite y assets

milpa trae un **asset-pipeline opt-in** estilo `laravel-vite`: milpa es **dueña del shell
HTML** (Jinja) y **Vite** se encarga del pipeline del frontend — HMR en dev, chunks
hasheados en prod. Vive en `milpa/Core/View/Vite.py` y se expone como un puñado de
globals de Jinja: `vite()`, `vite_asset()`, `vite_react_refresh()` y el `asset()` de
toda la vida.

Es **opt-in de verdad**: si no detecta ninguna app Vite, la feature **muere en paz** —
no se monta nada y `vite()` en un template truena con una instrucción clara (tenet:
nunca fallar en silencio). Un proyecto que solo renderiza HTML con Jinja ni se entera de
que esto existe.

## Los helpers de Jinja

Cuatro globals quedan disponibles en **todos** los templates (los registra el
`TemplateEngine`):

| Global | Qué emite |
|--------|-----------|
| `vite('src/main.jsx')` | El bloque `<link>`/`<script>` del entry (la directiva `@vite` de Laravel). |
| `vite_asset('icons/icon-192.png')` | URL pública de un archivo de `public/` de la app (sin hash). |
| `vite_react_refresh()` | Preámbulo de react-refresh (`@viteReactRefresh`); **solo** en dev. |
| `asset('welcome.css')` | URL de un estático bajo `/static` (con el prefijo `ASSET_URL` antepuesto). |

```jinja2
<head>
    {{ vite_react_refresh() }}   {# va ANTES de vite(); no-op en prod #}
    {{ vite('src/main.jsx') }}
</head>
```

`vite()` y compañía devuelven `Markup` (HTML confiable generado por el Core): el
autoescape de Jinja no lo toca.

!!! note "`vite_react_refresh()` es solo para React"
    El preámbulo de react-refresh aplica únicamente a apps React. Una app Vue, Svelte o
    vanilla simplemente **no lo llama** (el template del surco `tablero`, vanilla JS, no
    lo incluye). En prod es no-op (cadena vacía).

## Dev vs. prod: cómo decide el modo

`vite()` no tiene flag de "modo". Lee el estado del frontend y decide solo, igual que
Laravel:

```
vite('src/main.jsx')
        │
        ▼
  ¿existe el HOT-FILE de la app?  (lo escribe el dev server al arrancar)
   ├── sí → DEV  → cliente HMR de Vite + el entry desde el dev server (otro puerto)
   └── no → PROD → lee dist/.vite/manifest.json y emite <link>/<script> HASHEADOS
```

- **DEV** — existe el **hot-file** de la app (`<app>/hot`). Lo escribe su dev server de
  Vite al arrancar (`vite-plugin-milpa`) y lo borra al apagarse; el archivo **contiene la
  URL del dev server** (p. ej. `http://localhost:5173`). `vite()` emite
  `<script type="module">` apuntando ahí: **la página la sirve milpa** y **los módulos
  (con HMR) los sirve Vite** — el navegador habla con ambos puertos, mismo origen para el
  HTML.

- **PROD** — no hay hot-file: `vite()` lee `dist/.vite/manifest.json` (el `build.manifest`
  de Vite) y emite los `<link rel="stylesheet">` + `<script type="module">` **hasheados**,
  servidos por milpa (el mount opt-in de `Core/Http/Http.py`). El manifest se cachea por
  `mtime`: se relee solo si hubo rebuild.

No tocas nada para cambiar de uno a otro: levantas `pnpm --filter <surco> dev` (aparece
el hot-file → dev) o corres `pnpm -r build` y apagas el dev server (desaparece el
hot-file → prod).

!!! note "Qué se cachea y qué no"
    La **estructura** de apps (`resolve_apps()`: qué surcos existen y su ruta de build) se
    **cachea** para no reescanear el filesystem en cada `vite()`/`vite_asset()` de una página
    (una página con varios entries escaneaba el disco una vez por llamada). Pero el **estado
    dev/build** —la presencia VIVA del hot-file— se lee **siempre** por render: por eso
    levantar o apagar el dev server cambia el modo **sin reiniciar** el proceso. Es
    independiente del cache del manifest (ese se invalida por `mtime`). Si creas un surco
    nuevo **en caliente** (con el proceso ya arrancado), no aparecerá hasta reiniciar o llamar
    `clear_apps_cache()` (el escape para tooling); el dev típico reinicia al tocar un `.py`.

## Dev vs build desde el template

A veces el template necesita saber **en qué modo está** para emitir algo solo en uno de los
dos. El caso canónico —el que motivó este helper— son las **speculation rules** y las
**view transitions cross-document**: en **dev** los módulos vienen del dev server (otro
origen), y un documento **prerendereado** bloquea subrecursos cross-site → se ve un flashazo.
Esas etiquetas deben emitirse **solo en build**.

El global `assets_dev()` publica esa decisión (la misma que `vite()` toma por dentro):

| Llamada | Devuelve |
|---------|----------|
| `assets_dev()` | `True` si los assets salen del dev server (hot-file vivo), `False` en build. |
| `assets_dev(app='tienda')` | Lo mismo, para una app concreta en multi-app. |

```jinja2
{% if not assets_dev() %}
    <script type="speculationrules">{ "prerender": [{ "where": { "href_matches": "/*" } }] }</script>
{% endif %}
```

A diferencia de `vite()` (que **truena** si no hay apps), `assets_dev()` es **tolerante**: sin
nada detectado devuelve `False` —"no hay dev server" es, correctamente, "no es dev"— para no
tumbar el render de una página que ni usa Vite. La parte dev/build se lee **en vivo** (no pasa
por el cache de la estructura), así prender/apagar el dev server cambia el resultado al toque.

!!! tip "Reemplaza la convención manual del hot-file"
    Antes, una app que quería este gate replicaba a mano la convención
    (`any(surcos/*/hot)`). Ahora la detección la **publica el Core** y el surco solo llama
    `assets_dev()`. Si lo necesitas también en el **cliente** (JS gateando speculation rules),
    pásalo a `window.__ENV` por el `extra` de `shell_context(request, {"ASSETS_DEV": assets_dev()})`.

## El helper `asset()` y `ASSET_URL`

`asset('welcome.css')` construye la URL de un estático servido bajo `/static`
(`{{ asset('welcome.css') }}` → `/static/welcome.css`). La novedad es que ahora
**antepone `ASSET_URL`**: si configuras `ASSET_URL=https://cdn.tudominio.com`, el mismo
template emite `https://cdn.tudominio.com/static/welcome.css` sin que toques el HTML.

`ASSET_URL` afecta por igual a `asset()`, `vite()` y `vite_asset()`. Ver la sección de
deploy más abajo.

## Settings de Vite

Todo se configura en `.env` (lo lee `milpa/Core/Config/Settings.py`). Los defaults son
los del layout que genera `milpa new`, así que en un proyecto recién creado no tienes que
tocar nada.

| Variable | Default | Para qué |
|----------|---------|----------|
| `VITE_APPS_DIR` | `surcos` | Carpeta de las **fuentes** de los microfrontends (uno por vertical). |
| `VITE_PUBLIC_DIR` | `public` | Carpeta `public/` del proyecto: el build de cada surco cae en `public/<app>`. |
| `VITE_ASSETS_URL` | `/vite` | Raíz **pública** de los assets: cada app se sirve en `<assets_url>/<app>`. |
| `VITE_DIST_DIR` | `""` | Override **explícito** para una-sola-app: apunta directo al `dist/` (ignora la auto-detección). |
| `VITE_HOT_FILE` | `""` | Hot-file del modo una-sola-app. Vacío ⇒ `<dist>/../hot`. |
| `ASSET_URL` | `""` | Prefijo público de `asset()`/`vite()`/`vite_asset()` (CDN o sub-ruta de proxy). DEBE coincidir con el del build. |

!!! warning "`ASSET_URL` y `VITE_ASSETS_URL` no son lo mismo"
    `VITE_ASSETS_URL` (default `/vite`) es **dónde milpa monta el `public/`** —la ruta
    interna donde viven los assets—. `ASSET_URL` es el **prefijo que se antepone** a las
    URLs emitidas (CDN o sub-ruta de reverse proxy). El primero casi nunca se cambia; el
    segundo es la palanca de deploy. `VITE_ASSETS_URL` **debe coincidir con el `base` del
    `vite.config`** del frontend (los chunks se referencian entre sí con esa base — lo
    deriva `vite-plugin-milpa` solo).

## Modo una-sola-app vs. multi-app

milpa soporta dos topologías. La detección es por convención (`resolve_apps()`):

**Multi-app (default, microfrontends).** Las fuentes viven en `VITE_APPS_DIR` (`surcos/`)
y los builds en `VITE_PUBLIC_DIR` (`public/`). Una carpeta es "app" si tiene:

- `public/<app>/.vite/manifest.json` — **construida** (`vite build` ya corrió), o
- `surcos/<app>/hot` — **en dev** (su dev server está corriendo), aunque nunca se haya
  buildeado (primer `pnpm dev` recién clonado).

Cada app se sirve namespaced en `<assets_url>/<app>` (p. ej. `/vite/demo-spa`), igual que
los estáticos por módulo del backend. Con varias apps **desambiguas** con el kwarg `app`:

```jinja2
{{ vite('src/main.jsx', app='demo-spa') }}
{{ vite('src/main.js',  app='tablero') }}
```

Si llamas `vite('src/main.jsx')` sin `app` y hay más de una, **truena a propósito** con la
lista de apps disponibles (nunca adivina cuál querías).

**Una-sola-app (`VITE_DIST_DIR` explícito).** Apuntas directo al `dist/` y se ignora la
auto-detección — es el estilo Laravel clásico con el frontend en la raíz del proyecto. Se
monta en la raíz de `VITE_ASSETS_URL`, sin sub-ruta por app, y `vite('src/main.jsx')` (sin
`app`) ya no es ambiguo porque hay una sola:

```bash
VITE_DIST_DIR=public/vite
```

Para el detalle del modo multi-app (cada equipo su tecnología, workspace pnpm,
`vite-plugin-milpa`) ver [Microfrontends (surcos)](30-microfrontends-surcos.md).

## `vite_asset()`: archivos de `public/` sin hash

No todo pasa por el manifest hasheado de Vite. Los archivos que pones en el `public/` del
surco (iconos de la PWA, `robots.txt`, imágenes sueltas) van **sin hash** y solo se
namespacean:

```jinja2
<link rel="apple-touch-icon" href="{{ vite_asset('icons/apple-touch-icon.png', app='demo-spa') }}">
```

→ `/vite/demo-spa/icons/apple-touch-icon.png`. Hereda `ASSET_URL` solo (es la misma base
que `vite()`) y **ramifica dev/prod igual que `vite()`**: con el dev server corriendo la URL
sale de ahí (el `public/` del surco lo sirve Vite en su raíz; el build puede no existir aún).

## Deploy bajo sub-ruta o CDN

Aquí está la mitad **build-time** del soporte para reverse proxy y CDN. `ASSET_URL` se
antepone a todas las URLs de assets, y `vite-plugin-milpa` lee **la misma env var** al
buildear para derivar el `base` de los chunks. Por eso la regla:

> `ASSET_URL` en el `.env` de milpa **debe coincidir** con el `ASSET_URL` con el que se
> buildeó el frontend.

- **CDN:** `ASSET_URL=https://cdn.tudominio.com` → los assets se piden al CDN; el HTML lo
  sigue sirviendo milpa same-origin.
- **Sub-ruta de reverse proxy:** la app se sirve detrás de `/nombre-reverse`. Aquí entran
  dos piezas complementarias:
  - `ASSET_URL=/nombre-reverse` — la mitad **build-time** (los chunks se referencian con ese prefijo).
  - `BASE_PATH` (el `root_path` ASGI, que el proxy propaga vía `uvicorn --root-path`) — la
    mitad **runtime**: el frontend deriva de ahí su basename, el registro del Service Worker
    y sus llamadas a la API, **sin rebuild**. Lo inyecta el shell en `window.__ENV` (ver
    [Microfrontends (surcos)](30-microfrontends-surcos.md)).

En **dev**, `vite()` ignora `ASSET_URL`: los módulos salen del dev server vía el hot-file,
no del `public/` montado.

## Forma tradicional vs. estilo milpa

**Forma tradicional** — el SPA corre en su propio servidor (segundo origen), abres CORS y
la config del frontend queda **congelada en build-time** (lo que `VITE_*`/`NEXT_PUBLIC_*`
hornean no cambia sin rebuild).

**Estilo milpa** — el backend es **dueño del shell** (Jinja): mismo origen, **cero CORS**,
y la runtime-config (`window.__ENV`) se inyecta al servir la página, sin rebuild. Vite
solo se encarga de los assets; milpa, del HTML.

## Siguiente paso

[Microfrontends (surcos)](30-microfrontends-surcos.md).
