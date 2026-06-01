# Monolito modular

milpa es un **monolito modular**: un solo despliegue, pero dividido en módulos
independientes sobre un kernel compartido. Es el punto medio entre el monolito
espagueti y los microservicios prematuros.

```
            ┌───────────────────────────────────────────────┐
            │  app/Core   (el framework: HTTP, Console, DB,  │
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

1. **El kernel no depende de los módulos.** `app.Core`, `app.Models`, `app.Dictionaries`
   no pueden importar `app.Modules`.
2. **Los módulos son independientes entre sí.** `app.Modules.A` no importa `app.Modules.B`.

¿Por qué? Para que cada módulo sea **extraíble** a un microservicio sin desenredar
imports cruzados, y para que el kernel sea **reutilizable** tal cual en otro proyecto.

Si dos módulos necesitan compartir algo, ese algo sube al kernel compartido
(`app/Models`, `app/Dictionaries`, o un servicio en `app/Core`).

## Auto-discovery: cómo el framework te encuentra

El kernel **no importa los módulos estáticamente** (eso violaría la frontera). En su
lugar, el `Registry` (`app/Core/Registry/Registry.py`) los descubre escaneando el
filesystem con `pkgutil`. Por eso agregar un módulo es solo **crear su carpeta**: no se
edita ningún archivo central.

| Qué | Función del Registry | Cuándo corre | Convención |
|-----|----------------------|--------------|------------|
| Routers HTTP | `iter_routers()` | en `create_app()` | un `APIRouter` a nivel de módulo bajo `Modules/X/Http/` |
| Estáticos | `iter_static_mounts()` | en `create_app()` | existe `Modules/X/Resources/Static/` → se monta en `/static/x` |
| Comandos CLI | `iter_cli_apps()` | en `jornal` | `@console_command` bajo `Modules/X/Console/Commands/` |
| Tasks y crons | `import_all_tasks()` | al configurar Celery | `Modules/X/Jobs/` y `Console/Commands/` |
| Beat schedule | `collect_beat_schedule()` | en `celery beat` | crons `@cron_task` con `schedule=` |
| Modelos | `import_all_models()` | en el lifespan | un modelo por archivo en `app/Models` |

`module_packages()` es la base: lista los paquetes bajo `app/Modules/` (ignora los que
empiezan con `_`).

> El discovery es **dinámico** (por strings/filesystem), no por imports estáticos. Por
> eso `Core` puede descubrir módulos sin "importarlos" y sin romper la frontera
> Core ↛ Modules (que es sobre imports estáticos).

## Crear un módulo

1. Crea la carpeta. La forma más rápida es copiar `app/Modules/Example` y renombrar:

   ```
   app/Modules/Billing/
     Http/
       controller.py      # router = APIRouter(prefix="/billing", tags=["billing"])
     Jobs/
       NightlyClose.py    # @cron_task(...) o @celery_app.task(...)
     Mail/
       InvoiceMailable.py # class InvoiceMailable(Mailable)
     Console/
       Commands/
         CloseCommand.py  # @console_command(name="close")  → "jornal billing close"
     Resources/
       Lang/billing/...   # namespaced por el nombre del módulo
       Views/...
       Static/...
   ```

2. Arranca y verifica que aparece:

   ```bash
   uv run python jornal serve
   curl http://localhost:8000/status
   # {"servicio": "...", "modulos": ["Example", "Billing"], "status": "ok"}
   ```

No editas el kernel para nada. Los routers, comandos, crons, vistas, traducciones y
estáticos del módulo se descubren solos.

## El kernel compartido de dominio

Tres carpetas que **sí** comparten los módulos (no son módulos, son kernel de dominio):

- `app/Models/` — modelos SQLAlchemy. Auto-import con `pkgutil` (SQLAlchemy necesita
  verlos todos). Ver [Modelos](17-modelos.md).
- `app/Dictionaries/` — constantes de dominio; import por submódulo.
- `app/Resources/` — vistas/lang/estáticos compartidos. Ver [Vistas](09-vistas.md) e
  [i18n](13-localizacion-i18n.md).

## Siguiente paso

[Rutas y controladores](07-rutas-y-controladores.md).
