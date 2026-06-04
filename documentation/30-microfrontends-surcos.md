# Microfrontends (surcos)

Un **surco** es una app Vite por vertical: cada equipo tiene **su** frontend, con **la
tecnología que quiera** (React, Vue, Svelte, vanilla — Vite las cubre todas), y milpa lo
sirve **same-origin**. El nombre sigue la metáfora del proyecto: en la milpa, cada surco
es una hilera propia que crece a su ritmo sin estorbar a la de al lado.

Los surcos viven en `surcos/` (`VITE_APPS_DIR`) y son **opt-in**: sin surcos detectados, la
feature no existe. Esta página cubre el modelo multi-app; para los helpers de Jinja y los
modos dev/prod ver [Vite y assets](29-vite-y-assets.md).

## Un surco por vertical, cada quien su stack

```
surcos/
  demo-spa/        # React 19 + react-router 7 + PWA (Serwist)
    src/main.jsx
    vite.config.js
    package.json
  tablero/         # vanilla JS, sin PWA
    src/main.js
    vite.config.js
    package.json
```

Cada surco es autocontenido: su `package.json`, su `vite.config.js`, sus dependencias. Un
equipo desarrolla React mientras el de al lado escribe vanilla JS; ninguno impone su stack
al otro. Y como `tablero` lo prueba, la **convención es del framework, no de la
tecnología** del frontend.

## Auto-detección por convención

milpa no lleva un registro de surcos. Los descubre por convención (`resolve_apps()` en
`milpa/Core/View/Vite.py`): una carpeta dentro de `surcos/` es un surco si tiene

- `public/<app>/.vite/manifest.json` — **build hecho** (`vite build` ya corrió), o
- `surcos/<app>/hot` — **dev corriendo** (su dev server está levantado).

Lo clave: **el hot-file es por surco**. Un equipo puede estar en dev con HMR mientras los
demás corren su build, **sin estorbarse**. `demo-spa` en `pnpm dev` y `tablero` ya
buildeado conviven sin problema.

En los templates, el kwarg `app` desambigua cuál surco resuelve cada `vite()`:

```jinja2
{{ vite('src/main.jsx', app='demo-spa') }}
```

## El workspace pnpm

Los surcos forman un **workspace pnpm** (no npm workspaces). El motivo: pnpm da
`node_modules` **por paquete** vía symlinks al store global, así que cada surco solo importa
lo que **declara** en su `package.json`. La phantom dependency truena en dev, no el día que
extraes el surco a su propio repo.

`pnpm-workspace.yaml` en la raíz:

```yaml
packages:
  - "surcos/*"

# pnpm 11 NO ejecuta los postinstall de las deps por default (anti supply-chain);
# cada uno se aprueba explícitamente aquí.
allowBuilds:
  esbuild: true

# pnpm exige una edad mínima de publicación antes de instalar (anti supply-chain);
# nuestro propio plugin se exime al salir del horno.
minimumReleaseAgeExclude:
  - vite-plugin-milpa@0.1.2

# ¿Desarrollar/parchar vite-plugin-milpa contra este repo SIN esperar release?
# Clónalo al lado y descomenta:
# overrides:
#   vite-plugin-milpa: link:../vite-plugin-milpa
```

Tres detalles deliberados:

- **`packages: ["surcos/*"]`** — cada carpeta de `surcos/` es un paquete del workspace.
- **`allowBuilds`** — pnpm 11 no corre los postinstall de las dependencias por default (medida
  anti supply-chain). `esbuild` (dependencia de Vite) necesita el suyo para dejar listo su
  binario nativo; se aprueba **explícito** aquí.
- **`overrides` con `link:` comentado** — por default los surcos usan el `vite-plugin-milpa`
  publicado en el registry. Si quieres **desarrollar o parchar el plugin** contra este repo
  sin esperar a un release, clonas `vite-plugin-milpa` al lado y descomentas el override:
  los surcos usarán tu copia local (`link:../vite-plugin-milpa`). Es el camino contributor.

### Comandos

Los requisitos del frontend son **opt-in** (un proyecto solo-Jinja no los necesita):

- **Node** `>=22.13` (el `.nvmrc` fija `22`: pnpm 11 usa `node:sqlite`; Vite 7 por sí
  solo corre desde 20.19, pero el workspace se opera con pnpm).
- **pnpm 11** (declarado en `packageManager`/`volta`).

```bash
pnpm install                     # instala TODO el workspace (desde la raíz)
pnpm --filter demo-spa dev       # levanta el dev server de un surco (HMR)
pnpm --filter tablero build      # buildea un surco
pnpm -r build                    # buildea todos los surcos
```

## `vite-plugin-milpa`: el pegamento

Cada `vite.config.js` es mínimo — todo el pegamento con milpa vive en el plugin npm
`vite-plugin-milpa` (publicado, `^0.1.2`). Lo único que escribes:

```js
// surcos/demo-spa/vite.config.js
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {milpa} from 'vite-plugin-milpa';

export default defineConfig({
    plugins: [
        react(),
        milpa({entry: 'src/main.jsx'}),
    ],
});
```

El surco `tablero` (vanilla, sin PWA) es aún más corto: `milpa({entry: 'src/main.js'})` a
secas. Qué hace el plugin:

- **`base`** — lo deriva de la carpeta del surco (`surcos/demo-spa` → `/vite/demo-spa/`), así
  los chunks se referencian entre sí con la base correcta. Honra `ASSET_URL` para deploy bajo
  sub-ruta/CDN.
- **manifest** — habilita el `build.manifest` de Vite, que es lo que lee el helper `vite()`
  en prod.
- **hot-file** — escribe `surcos/<app>/hot` (con la URL del dev server) al arrancar `dev` y lo
  borra al apagarse. Es lo que `vite()` mira para saber si está en dev.
- **file-router runtime** — trae un router por archivos (`vite-plugin-milpa/router`), espejo
  del auto-montado de `Modules/<X>/Http` del backend (ver abajo).

> `vite-plugin-milpa@0.1.1` agregó chunks con nombre legible (en vez de hashes opacos), para
> que el manifest y el panel de red del navegador se lean fácil; `0.1.2` corrige el modo dev
> con PWA (el middleware de serwist tronaba en cada request). El piso es `^0.1.2`.

### El file-router (espejo del backend)

El router por archivos del plugin replica en el frontend la convención del backend: igual que
milpa auto-monta cada controller de `Modules/<X>/Http`, el surco descubre sus páginas por
convención de archivos. Tú solo le pasas los globs (porque `import.meta.glob` es compile-time
de Vite y resuelve relativo a **tu** código, no a `node_modules`):

```jsx
// surcos/demo-spa/src/router.jsx
import {buildRoutes as fileRoutes} from 'vite-plugin-milpa/router';

export function buildRoutes() {
    return fileRoutes({
        pages: import.meta.glob('./pages/**/*.jsx'),
        modules: import.meta.glob('./modules/*/pages/**/*.jsx'),
    });
}
```

La convención (espejo del backend):

| Archivo | Ruta |
|---------|------|
| `src/pages/**/*.jsx` | rutas "core" del shell (`/acerca`) |
| `src/modules/<m>/pages/**/*.jsx` | rutas del módulo `<m>` (`/<m>/...`) |
| `index.jsx` | la raíz de su carpeta |
| `[id].jsx` | segmento dinámico `:id` |
| `_layout.jsx` | layout del módulo (opcional) |

10 devs = 10 carpetas en `src/modules/`: cada quien dropea páginas en **su** módulo y la ruta
existe — nadie toca un router central ni pisa al vecino.

## El shell Jinja y `window.__ENV`

milpa es **dueña del shell HTML** de cada surco. El controller renderiza un template Jinja
propio y le pasa el contexto del shell con `shell_context(request)`
(`milpa/Core/Http/Shell.py`):

```python
from milpa.Core.Http import Controller, Get
from milpa.Core.Http.Shell import shell_context
from milpa.Core.View import view

@Controller("/tablero", tags=["demo-tablero"])
class TableroController:
    @Get("")
    def shell(self, request: Request) -> HTMLResponse:
        return view("demo/tablero", shell_context(request))
```

`shell_context(request)` devuelve el contexto que **todo** surco inyecta: `env_json` (el
`window.__ENV`) y `base_path` (para los `href` del propio template). En el template, el global
`env_script()` emite el `<script>` completo, seguro (el JSON ya viene con `<` escapado desde
el Core):

```jinja2
<head>
    {{ vite('src/main.js', app='tablero') }}
</head>
<body>
{{ env_script() }}   {# <script>window.__ENV = {...}</script> #}
<div id="tablero"></div>
</body>
```

`window.__ENV` trae siempre `APP_NAME`, `APP_ENV` y `BASE_PATH`; el surco puede agregar las
suyas pasando `extra` a `shell_context(request, {...})`. Esto es lo que `VITE_*`/`NEXT_PUBLIC_*`
**no pueden** dar sin rebuild: el backend lo inyecta al servir el shell, así que cambia por
entorno/deploy en **runtime**.

`BASE_PATH` (el `root_path` ASGI) es la **mitad runtime** del soporte para reverse proxy bajo
sub-ruta: el frontend deriva de ahí su basename, el registro del Service Worker y sus llamadas
a la API. La **mitad build-time** es `ASSET_URL` (ver [Vite y assets](29-vite-y-assets.md)).

```jsx
// surcos/demo-spa/src/main.jsx — el basename se ARMA en runtime
const BASE = `${window.__ENV?.BASE_PATH ?? ''}/spa`;
```

!!! tip "Pon `env_script()` ANTES de `vite()`-cargado"
    Ponlo en el `<body>` antes de que monten los módulos. Los `<script type="module">` son
    deferred por spec, así que `window.__ENV` ya existe cuando el frontend arranca.

## Forma tradicional vs. estilo milpa

| | Forma tradicional | Estilo milpa (surcos) |
|---|---|---|
| **Dónde corre el SPA** | Su propio servidor (segundo origen). | El backend sirve el shell — **mismo origen**. |
| **CORS** | Obligatorio (front y API en orígenes distintos). | **Cero** (todo same-origin). |
| **Config del front** | Congelada en build-time (`VITE_*`/`NEXT_PUBLIC_*`). | Runtime (`window.__ENV`) — cambia por deploy sin rebuild. |
| **Sub-ruta de proxy** | Rebuild por entorno. | `BASE_PATH` runtime + `ASSET_URL` build-time. |
| **Varios frontends** | Cada uno su deploy y su CORS. | Un surco por vertical, todos servidos por milpa. |

El surco trae lo bueno del microfrontend (cada equipo su stack, su repo extraíble) sin el
peaje del segundo origen: milpa sirve todos los shells same-origin e inyecta la config en
runtime.

## Siguiente paso

[PWA](31-pwa.md).
