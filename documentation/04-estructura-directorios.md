# Estructura de directorios

```
app/
  Core/            # EL FRAMEWORK (genérico, reutilizable)
    Config/        #   Settings (pydantic-settings, lee .env)
    Console/       #   kernel de consola (Typer) + comandos base
    CeleryApp/     #   app de Celery + dispatch (broker-agnóstico)
    Cron/          #   @cron_task + helpers de cadencia (scheduler estilo Laravel)
    Database/      #   Base, Session, Repository, @transactional, mixins
    Http/          #   create_app() FastAPI + middlewares + frontera de locale
    Mail/          #   Mailable + Mailer (smtp/log/null) + facade Mail + task Celery
    Translate/     #   i18n (i18nice, YAML)
    View/          #   motor de templates (Jinja2) + helper view()
    Auth/          #   validación de tokens OAuth2 de Laravel Passport
    Registry/      #   auto-discovery de routers, tasks, crons, estáticos, CLI
  Models/          # modelos SQLAlchemy COMPARTIDOS (auto-discovery; vacío en el base)
  Dictionaries/    # constantes de dominio (auto-discovery por submódulo)
  Modules/
    Example/       # módulo de ejemplo (plantilla de cómo construir uno)
  Resources/       # vistas/lang/estáticos COMPARTIDOS del proyecto
surcos/            # (opt-in) microfrontends Vite, uno por vertical (workspace pnpm)
public/            # (opt-in) builds de los surcos (public/<app>); milpa lo sirve en /vite
Tests/             # tests unitarios (espeja app/ 1:1, sin BD)
documentation/     # esta documentación (pública)
secrets/           # llaves locales (contenido ignorado por git)
jornal             # entrypoint de consola (el "artisan") en la raíz
start.sh / stop.sh # arranque/paro daemonizado de uvicorn (PID + logs)
docker-compose.yml # SOLO infra: redis + mailpit (+ rabbitmq opcional)
pyproject.toml     # deps, extras de drivers, config de ruff/mypy/pytest/import-linter
```

## Las tres capas

### 1. El kernel — `milpa/Core`

Es **el framework**. Genérico, sin sabor de dominio, reutilizable entre proyectos.
Cada subcarpeta es un subsistema (espejo de los "componentes" de Laravel):

| Carpeta | Equivalente Laravel | Doc |
|---------|---------------------|-----|
| `Config` | `config()` + `.env` | [Configuración](03-configuracion.md) |
| `Http` | Kernel HTTP + middleware | [Ciclo de vida](05-ciclo-de-vida.md) |
| `Console` | Kernel de consola / artisan | [Consola](08-consola-jornal.md) |
| `Database` | Eloquent + migraciones | [Base de datos](16-base-de-datos.md) |
| `Mail` | Mail + Mailables | [Correo](10-correo.md) |
| `Cron` | Task Scheduling | [Cron](12-programacion-cron.md) |
| `CeleryApp` | Queues | [Colas y tareas](11-colas-y-tareas.md) |
| `Translate` | Localization | [i18n](13-localizacion-i18n.md) |
| `View` | Blade / Views | [Vistas](09-vistas.md) |
| `Auth` | Auth / Passport | [Autenticación](15-autenticacion.md) |
| `Registry` | Service Provider auto-discovery | [Monolito modular](06-monolito-modular.md) |

**Regla:** `Core` nunca importa de `Modules`. Lo fuerza `import-linter`.

### 2. El kernel compartido de dominio — `app/Models`, `app/Dictionaries`, `app/Resources`

Lo que comparten varios módulos:

- `app/Models/` — modelos SQLAlchemy. Auto-descubiertos con `pkgutil` (SQLAlchemy
  necesita verlos todos para resolver relaciones por string). Un modelo por archivo.
- `app/Dictionaries/` — clases de constantes de dominio. Se importan por submódulo
  (`from app.Dictionaries.MiDict import MiDict`); no necesitan auto-discovery.
- `app/Resources/` — vistas (`Views/`), traducciones (`Lang/`), estáticos (`Static/`),
  imágenes y archivos COMPARTIDOS por todo el proyecto.

### 3. Los módulos — `app/Modules/<Nombre>`

Tus features. Cada módulo es autocontenido e independiente de los demás. El **encarpetado
es libre**: el discovery importa **todo el árbol** del módulo, así que sueltas la pieza
donde te quede y milpa la descubre. Ninguna carpeta es obligatoria. La **convención que
producen los generadores `make:*`** —una carpeta por concern— es solo una de las formas de
organizarse:

```
app/Modules/Example/
  Http/            # @Controller (rutas; se auto-montan en create_app())
  Jobs/            # @job (background on-demand)
  Crons/           # @cron_task (agendados)
  Observers/       # subclases de Observer (reaccionan a eventos)
  Handlers/        # @handles(Cmd) del Mediator
  Policies/        # políticas de autorización (RBAC/ABAC)
  Mail/            # Mailables del módulo
  Console/
    Commands/      # @console_command (de su path se deduce el grupo CLI)
  Resources/       # Lang/, Views/, Static/ propios (namespaced)
```

!!! note "Este layout es una PROPUESTA, no una imposición"
    El demo (y lo que generan los `make:*`) sigue esta convención —carpeta por concern,
    `Jobs/ExportNotesJob.py`, `Mail/InvoiceMailable.py`, …— para que se lea de un vistazo.
    Pero el discovery **no la exige**: importa **todo el árbol** del módulo. Si prefieres
    aplanar (`Jobs.py`) o agrupar de otra manera, funciona igual —la pieza se descubre
    mientras lleve su decorador o herede de su base—. Para una prueba de concepto puedes
    escribir **todo de corrido en un solo archivo** (job + cron + observer + handler +
    command + policy juntos) y milpa registra todo. La **única** convención con peso es
    `Console/Commands/`, de cuyo path se deduce el grupo CLI de cada `@console_command`. El
    guardrail `test_FreeLayoutDiscovery` fija esta libertad.

!!! info "El `Http/` también se importa fuera de la web — pero ahí solo se registra"
    El barrido recursivo importa `Http/` de cada módulo también en el CLI y el worker. Es
    una decisión consciente: ahí los decoradores de ruta (`@Controller`, `@Get`, …) **solo
    se registran**, no sirven nada — quien sirve es la capa web (`create_app()`, vía
    `iter_routers()`). Importar un controller fuera del proceso web no levanta una ruta.

Ver [Monolito modular](06-monolito-modular.md) para el detalle de cómo se descubre y
monta cada cosa, y [Rutas y controladores](07-rutas-y-controladores.md) para crear el
primero.

## Siguiente paso

[Ciclo de vida de la petición](05-ciclo-de-vida.md).
