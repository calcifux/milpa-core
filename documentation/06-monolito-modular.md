# Monolito modular

milpa es un **monolito modular**: un solo despliegue, pero dividido en módulos
independientes sobre un kernel compartido. Es el punto medio entre el monolito
espagueti y los microservicios prematuros.

```
            ┌───────────────────────────────────────────────┐
            │  milpa/Core   (el framework: HTTP, Console, DB,  │
            │             Mail, Cron, i18n, …)               │
            └───────────────────────────────────────────────┘
                    ▲                       ▲
                    │ usan el kernel        │
        ┌───────────┴──────┐     ┌──────────┴───────────┐
        │ app/Modules/A    │     │ app/Modules/B        │   ←  NO se importan entre sí
        └──────────────────┘     └──────────────────────┘
                    ▲                       ▲
                    └───────── comparten ───┘
            app/Models · app/Dictionaries · app/Resources
```

## Las dos reglas (fronteras forzadas)

`import-linter` (guardrail de CI, `uv run lint-imports`) impone dos contratos:

1. **El kernel no depende de los módulos.** `milpa.Core`, `app.Models`, `app.Dictionaries`
   no pueden importar `app.Modules`.
2. **Los módulos son independientes entre sí.** `app.Modules.A` no importa `app.Modules.B`.

¿Por qué? Para que cada módulo sea **extraíble** a un microservicio sin desenredar
imports cruzados, y para que el kernel sea **reutilizable** tal cual en otro proyecto.

Si dos módulos necesitan compartir algo, ese algo sube al kernel compartido
(`app/Models`, `app/Dictionaries`, o un servicio en `milpa/Core`).

## Auto-discovery: cómo el framework te encuentra

El kernel **no importa los módulos estáticamente** (eso violaría la frontera). En su
lugar, el `Registry` (`milpa/Core/Registry/Registry.py`) los descubre escaneando el
filesystem con `pkgutil`. Por eso agregar un módulo es solo **crear su carpeta**: no se
edita ningún archivo central.

El discovery **importa todo el árbol de cada módulo** (recursivo): por cada módulo presente
corre `import_submodules(package, recursive=True)`, que baja a los sub-paquetes (saltando
nombres que empiezan con `_`). Por eso **dónde** pongas un `@job`, un `@cron_task`, un
`Observer`, un `@handles(...)` o una Policy dentro del módulo **da igual**: si está en el
árbol, se importa y su decorador/subclase se registra solo. El encarpetado es libre.

| Qué | Función del Registry | Cuándo corre | Sugerencia de lectura |
|-----|----------------------|--------------|------------|
| Routers HTTP | `iter_routers()` | en `create_app()` | `@Controller` bajo `Modules/X/Http/` |
| Estáticos | `iter_static_mounts()` | en `create_app()` | existe `Modules/X/Resources/Static/` → se monta en `/static/x` |
| Comandos CLI | `iter_cli_apps()` | en `jornal` | `@console_command` bajo `Modules/X/Console/Commands/` |
| Jobs y crons | `import_all_tasks()` | al configurar Celery | `@job` y `@cron_task` en cualquier parte del módulo (p. ej. `Jobs/…` / `Crons/…`) |
| Beat schedule | `collect_beat_schedule()` | en `schedule work` | `@cron_task(schedule=…)` (+ los `Console/Kernel.py`) |
| Seeders | `import_all_seeders()` | en `db seed` | subclases de `Seeder` (p. ej. `Seeders/…`) |
| Observers | `import_all_observers()` | al despachar eventos | subclases de `Observer` (p. ej. `Observers/…`) |
| Handlers (Mediator) | `import_all_handlers()` | al resolver un comando | `@handles(Cmd)` (p. ej. `Handlers/…`) |
| Policies | `import_all_policies()` | al autorizar | políticas RBAC/ABAC (p. ej. `Policies/…`) |
| Modelos | `import_all_models()` | en el lifespan | un modelo por archivo en `app/Models` |

> **Las cinco `import_all_*` hacen lo mismo.** `import_all_tasks`, `import_all_seeders`,
> `import_all_observers`, `import_all_handlers` e `import_all_policies` son hoy **alias** del
> mismo gesto: por cada módulo, `import_submodules(package, recursive=True)`. Siguen
> existiendo como cinco nombres por **claridad del call-site** (en el código se lee *qué* se
> va a buscar). Son idempotentes: `sys.modules` cachea, así que llamarlas de más no recarga
> nada. (`import_all_models` queda aparte: importa el paquete de `app/Models`, no el árbol de
> módulos; `collect_beat_schedule` tampoco cambió.)

`module_packages()` es la base: lista los paquetes bajo `app/Modules/` (ignora los que
empiezan con `_`).

> El discovery es **dinámico** (por strings/filesystem), no por imports estáticos. Por
> eso `Core` puede descubrir módulos sin "importarlos" y sin romper la frontera
> Core ↛ Modules (que es sobre imports estáticos). La recursión no cambia eso: sigue siendo
> discovery por string, no una arista estática `import app.Modules...`.

!!! info "El barrido también importa `Http/` en el CLI y el worker"
    Decisión consciente: `import_submodules(..., recursive=True)` baja por **todo** el árbol,
    incluido `Http/`, también fuera del proceso web. Ahí los decoradores de ruta
    (`@Controller`, `@Get`, …) **solo se registran** — no sirven nada. Quien sirve es
    `create_app()` (vía `iter_routers()` / `iter_fallback_routes()`). Importar un controller
    en el CLI o el worker no levanta una ruta; es discovery, no arranque.

## Estructura de un módulo: encarpetado libre

Aquí está el cambio de filosofía: **el encarpetado dentro de un módulo es LIBRE**. El
discovery importa **todo el árbol** del módulo, así que como sea que el programador organice
su aplicación, a milpa le da igual. Puedes seguir la convención de los generadores (una
carpeta por concern), aplanar todo en archivos sueltos (`Jobs.py`, `Crons.py`,
`Observers.py`, `Handlers.py`, …), agruparlos de otra manera, o mezclar: mientras la pieza
viva en el árbol del módulo y lleve su decorador o herede de la base correcta, **se descubre
sola**. No vamos a luchar contra quien escribe **todo de corrido** en un solo archivo para
una prueba de concepto: eso también funciona. El guardrail `test_FreeLayoutDiscovery` (y el
test "de corrido") fijan esa libertad.

milpa **propone** —no obliga— una lectura, **la que producen los generadores `make:*`**:

- `Console/Commands/` — la **única convención con peso real**: de su path se **deduce el
  grupo CLI** del `@console_command` (`app.Modules.Billing...` → grupo `billing`).
- `Http/` / `Jobs/` / `Crons/` / `Observers/` / `Handlers/` / `Policies/` / `Mail/` /
  `Resources/` — **sugerencias de lectura** (las carpetas que crean los `make:*`, un archivo
  por clase), para que un humano ubique de un vistazo qué hace cada cosa. El discovery no las
  exige.

```
app/Modules/Billing/
  Console/Commands/CloseCommand.py   # ← convención PROPUESTA para automontar el command
  Http/BillingController.py          # @Controller — se importa porque está en el árbol
  Jobs/NightlyCloseJob.py            # @job
  Crons/NightlyCloseCron.py          # @cron_task
  Observers/OnClosed.py              # subclase(s) de Observer
  Handlers/ClosePeriodHandler.py     # @handles(...)
  Policies/InvoicePolicy.py          # política RBAC/ABAC
  Mail/… · Resources/Lang/billing/… · Resources/Views/… · Resources/Static/…
```

> Lo mismo aplica si prefieres aplanar todo en `Modules/Billing/__init__.py` o en un solo
> `module.py`: el `import_submodules(..., recursive=True)` baja por el árbol y lo encuentra
> igual. **Organiza tu app como quieras.**

`MODULES_PACKAGE=app.Modules` (en el `.env`) es lo único que milpa necesita saber: el
paquete punteado donde escanear tus módulos. Cambiarlo reubica TODO el discovery sin tocar
el kernel.

## Crear un módulo

1. Crea la carpeta. La forma más rápida es copiar `app/Modules/Example` y renombrar, o usar
   los generadores `make:*` (que crean la carpeta de **convención propuesta**):

   ```
   app/Modules/Billing/
     Http/
       BillingController.py # @Controller — la ruta queda viva sola
     Jobs/
       NightlyClose.py      # @job o @cron_task
     Mail/
       InvoiceMailable.py   # class InvoiceMailable(Mailable)
     Console/
       Commands/
         CloseCommand.py    # @console_command(name="close")  → "jornal billing close"
     Resources/
       Lang/billing/...     # namespaced por el nombre del módulo
       Views/...
       Static/...
   ```

   Recuerda: la carpeta es solo un punto de partida cómodo. Como el discovery importa todo el
   árbol, luego puedes mover esos archivos o aplanarlos sin registrar nada a mano.

2. Arranca y verifica que aparece:

   ```bash
   uv run python jornal serve
   curl http://localhost:8000/status
   # {"servicio": "...", "modulos": ["Example", "Billing"], "status": "ok"}
   ```

No editas el kernel para nada. Los routers, comandos, jobs, crons, observers, handlers,
policies, vistas, traducciones y estáticos del módulo se descubren solos.

## El kernel compartido de dominio

Tres carpetas que **sí** comparten los módulos (no son módulos, son kernel de dominio):

- `app/Models/` — modelos SQLAlchemy. Auto-import con `pkgutil` (SQLAlchemy necesita
  verlos todos). Ver [Modelos](17-modelos.md).
- `app/Dictionaries/` — constantes de dominio; import por submódulo.
- `app/Resources/` — vistas/lang/estáticos compartidos. Ver [Vistas](09-vistas.md) e
  [i18n](13-localizacion-i18n.md).

## Siguiente paso

[Rutas y controladores](07-rutas-y-controladores.md).
