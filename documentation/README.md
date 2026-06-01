# Documentación de milpa

**milpa** es un microframework de Python 3.14 para construir monolitos modulares,
inspirado en la ergonomía de **Laravel** y la disciplina de capas de **Spring**.
Junta FastAPI (HTTP), Celery (tareas/crons), SQLAlchemy 2.0 (datos) y Typer (consola)
detrás de una estructura opinada y un kernel reutilizable.

Esta documentación está pensada para leerse en orden, como la de Laravel: empieza por
"Primeros pasos", luego "Conceptos de arquitectura", y profundiza por tema.

> Filosofía en una línea: el kernel (`app/Core`) es el framework; lo tuyo vive en
> `app/Modules`, `app/Models`, `app/Dictionaries` y `app/Resources`. Tú escribes
> features; el framework descubre y conecta solo.

## Primeros pasos

1. [Introducción](01-introduccion.md) — qué es milpa y su filosofía.
2. [Instalación](02-instalacion.md) — `uv` o pip, drivers de BD.
3. [Configuración](03-configuracion.md) — `.env` y la clase `Settings`.
4. [Estructura de directorios](04-estructura-directorios.md) — qué hay y dónde.

## Conceptos de arquitectura

5. [Ciclo de vida de la petición](05-ciclo-de-vida.md) — `create_app`, lifespan, middlewares, locale.
6. [Monolito modular](06-monolito-modular.md) — Core vs Modules, auto-discovery, fronteras.

## Lo básico

7. [Rutas y controladores](07-rutas-y-controladores.md) — FastAPI por módulo, auto-montaje.
8. [Consola (`jornal`)](08-consola-jornal.md) — comandos, grupos, crear los tuyos.
9. [Vistas](09-vistas.md) — Jinja2, namespacing, `view()`.

## Profundizando

10. [Correo](10-correo.md) — `Mailable`, `Mailer`, drivers, adjuntos, encolado.
11. [Colas y tareas](11-colas-y-tareas.md) — Celery, broker-agnóstico, `queue work`.
12. [Programación de tareas (cron)](12-programacion-cron.md) — `@cron_task`, `schedule run/work`.
13. [Localización (i18n)](13-localizacion-i18n.md) — `t()`, locale ambiente, monolingüe vs i18n.
14. [Logging](14-logging.md) — Loguru, JSON, niveles.
15. [Autenticación](15-autenticacion.md) — validar tokens OAuth2 de Laravel Passport.

## Base de datos

16. [Configuración del motor](16-base-de-datos.md) — engine agnóstico, `DATABASE_URL`, zona horaria.
17. [Modelos](17-modelos.md) — SQLAlchemy, auto-discovery, mixins (timestamps, soft delete).
18. [Repositorios y transacciones](18-repositorios-y-transacciones.md) — `Repository[Model, Id]`, `@transactional`.

---

## Mapa mental Laravel → milpa

| Laravel | milpa |
|---------|-------|
| `artisan` | `jornal` |
| `php artisan serve` | `jornal serve` |
| `php artisan queue:work` | `jornal queue work` |
| `php artisan schedule:run` | `jornal schedule run` |
| `$schedule->command(...)->everyFiveMinutes()` | `@cron_task(schedule=every_five_minutes())` |
| `Mail::to(...)->send(new X)` | `Mail.send(X(...), to=[...])` |
| `Mailable` | `Mailable` (ABC con `build()`) |
| Eloquent Model | modelo SQLAlchemy (`app/Models`) |
| `$table->timestamps()` | `TimestampMixin` |
| `SoftDeletes` | `SoftDeleteMixin` |
| Repository / Service | `Repository[Model, Id]` / service `@transactional` |
| `__('key')` | `t("key")` |
| `config()` / `.env` | `settings` / `.env` |
| Service Provider auto-discovery | auto-discovery por convención (Registry) |
