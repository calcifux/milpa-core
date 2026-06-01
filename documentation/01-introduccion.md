# Introducción

**milpa** es un microframework de Python 3.14 para construir **monolitos modulares**.
No reinventa nada: ensambla cuatro piezas maduras del ecosistema Python detrás de una
estructura opinada y un kernel reutilizable.

| Pieza | Para qué |
|-------|----------|
| **FastAPI** | HTTP / API |
| **Celery** | tareas en background y crons |
| **SQLAlchemy 2.0** | acceso a datos (agnóstico del motor) |
| **Typer** | consola (`jornal`, el "artisan") |

## ¿Para quién es?

Para dos escenarios:

1. **Arrancar servicios nuevos** sin re-decidir la arquitectura cada vez (estructura,
   correo, colas, crons, i18n, persistencia: ya vienen resueltos y conectados).
2. **Migrar apps legacy de Laravel** a Python conservando los conceptos familiares:
   artisan, scheduler, mailables, soft-deletes, timestamps automáticos, validación de
   tokens de Passport.

## Filosofía

### El kernel es el framework

Todo lo genérico y reutilizable vive en `app/Core`. Lo específico de tu proyecto vive
**fuera** de `Core`:

- `app/Modules/<Nombre>/` — tus features (rutas, jobs, correos, servicios).
- `app/Models/` — tus modelos SQLAlchemy.
- `app/Dictionaries/` — tus constantes de dominio.
- `app/Resources/` — tus vistas, traducciones y estáticos compartidos.

Puedes copiar `app/Core` a otro proyecto y empezar de cero: es la "cosecha" reutilizable.

### Convención sobre configuración

El framework **descubre y conecta solo** lo que sueltas en su lugar:

- Sueltas un controller con un `APIRouter` bajo `Modules/X/Http/` → la API lo monta.
- Sueltas un `@cron_task` bajo `Modules/X/Jobs/` → el scheduler lo agenda.
- Sueltas un `@console_command` bajo `Modules/X/Console/Commands/` → `jornal` lo expone.
- Sueltas un modelo en `app/Models/` → SQLAlchemy lo registra.

No hay un archivo central que editar para "registrar" cada cosa. (Ver
[Monolito modular](06-monolito-modular.md).)

### Módulos independientes

Los módulos **no se importan entre sí**. Lo fuerza `import-linter` como contrato de CI.
Cada módulo es un microservicio en potencia: se puede extraer sin desenredar imports
cruzados. El kernel (`Core`) tampoco depende de los módulos.

### Monolingüe por default, i18n opt-in

Una app es de un solo idioma salvo que el dev decida traducir. El locale es **ambiente**
(se fija en la frontera HTTP desde `Accept-Language`) y se lee donde haga falta con
`t()`. (Ver [Localización](13-localizacion-i18n.md).)

### Persistencia estilo Spring Data

Repositorios tipados `Repository[Model, Id]` con CRUD heredado; escrituras en servicios
`@transactional` (commit/rollback automático); lecturas con `@auto_session`. La sesión
es **ambiente** (contextvar), no se inyecta por constructor. (Ver
[Repositorios y transacciones](18-repositorios-y-transacciones.md).)

## Calidad forzada

El proyecto trae cuatro guardrails que corren en local y en CI:

```bash
uv run ruff check .        # lint
uv run ruff format .       # formato
uv run mypy                # tipos (estricto)
uv run lint-imports        # fronteras entre módulos
uv run pytest              # tests (sin BD)
```

## Siguiente paso

[Instalación](02-instalacion.md).
