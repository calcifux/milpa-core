# Contribuir a milpa

¡Gracias por tu interés en contribuir! Este documento explica cómo levantar el proyecto
en local, las convenciones que seguimos y cómo enviar un Pull Request con las mejores
probabilidades de merge.

> Si vas a tocar un subsistema, lee primero su página en
> [`documentation/`](documentation/README.md): ahí está el "cómo funciona".

## Inicio rápido

```bash
git clone https://github.com/calcifux/milpa.git
cd milpa
uv sync                     # crea el venv y resuelve deps (incluye las de dev)
cp .env.example .env        # ajusta al menos DATABASE_URL
uv run pytest               # si la suite pasa, ya puedes desarrollar
```

Si no usas `uv`, ver [documentation/02-instalacion.md](documentation/02-instalacion.md)
(opción pip). Con `uv`, antepón `uv run` a los comandos; con el venv activo, omítelo.

> **¿Quieres ver algo funcionando ya?** Corre el demo (sqlite, sin infra):
> ```bash
> uv run python jornal migrate run && uv run python jornal db seed && uv run python jornal serve
> # http://127.0.0.1:8000  ·  admin@demo.test / password
> ```
> Auth dual (JWT + sesión/CSRF), RBAC + ABAC, búsqueda + scroll infinito, factories con Faker.

## Requisitos

- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)** (recomendado) como gestor de entorno y deps
- **Docker NO** es necesario para los tests: son unitarios y **sin base de datos** (usan
  fakes y monkeypatch, no servicios vivos). Docker solo hace falta para correr la app de
  verdad (Redis + Mailpit), no para contribuir/testear.
- **Git** con auth SSH o HTTPS a GitHub

## Estructura del repo

```
app/
  Core/          ← EL FRAMEWORK (kernel genérico, reutilizable)
  Models/        ← modelos SQLAlchemy compartidos (auto-discovery)
  Dictionaries/  ← constantes de dominio compartidas
  Modules/       ← los módulos del proyecto (independientes entre sí)
  Resources/     ← vistas/lang/estáticos compartidos
Tests/           ← espeja app/ 1:1; tests unitarios sin BD
documentation/   ← guía estilo Laravel (pública)
jornal           ← entrypoint de consola (el "artisan")
```

Detalle en [documentation/04-estructura-directorios.md](documentation/04-estructura-directorios.md).

## Las dos fronteras (no las rompas)

`import-linter` las fuerza en CI:

1. **El kernel no depende de los módulos**: `app.Core` / `app.Models` / `app.Dictionaries`
   no importan `app.Modules`.
2. **Los módulos son independientes entre sí**: `app.Modules.A` no importa `app.Modules.B`.

Si dos módulos necesitan compartir algo, ese algo sube al kernel compartido. Ver
[documentation/06-monolito-modular.md](documentation/06-monolito-modular.md).

## Ramas y commits

- `main` siempre verde. No hagas push directo; abre un PR.
- Ramas de feature: `feat/mail-cc-bcc`, `fix/cron-lock-timeout`, `docs/install-guide`.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `ci:`, `chore:`.

## Estilo de código

- Identificadores en **inglés**; comentarios y docstrings en **español**, explicando el
  *porqué* (no abreviar).
- Sin emojis en código/comentarios/docstrings.
- Tipos completos: `mypy` corre en modo **estricto** sobre `app/` y `Tests/Core`.
- Un archivo por clase/responsabilidad (estilo Laravel/PascalCase en `app/`).
- Formato e imports los maneja **Ruff** (no formatees a mano).

## Guardrails (lo que valida CI)

Antes de abrir el PR, corre todo y déjalo verde:

```bash
uv run ruff format .        # formato        | --check  solo verifica (modo CI)
uv run ruff check .         # lint           | --fix    arregla lo auto-arreglable
uv run mypy                 # tipos (estricto)
uv run lint-imports         # fronteras entre módulos
uv run pytest               # tests (rápidos, sin BD)
```

Todo de una:

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
```

## Contribuir al Core

milpa es un **framework**: las contribuciones van al **kernel** (`app/Core`), a sus tests
(`Tests/Core`) y a la documentación. **No** se trata de crear módulos de negocio nuevos —
eso lo hace cada proyecto que *usa* milpa, en su propio repo. `app/Modules/Example` es
solo el módulo de **referencia/demo**: tócalo únicamente para demostrar una capacidad del
Core, no para meter features de dominio.

Al tocar el Core:

1. **Mantén el Core genérico.** Nada de dominio ni de un proyecto en particular (ni
   nombres, ni reglas de negocio): el kernel debe servir igual a cualquier proyecto. Si
   dudas si algo es "del framework" o "de un proyecto", probablemente no va en Core.
2. **Respeta la frontera `app.Core ↛ app.Modules`**: el kernel no importa módulos (el
   discovery es dinámico, no por imports estáticos). Lo valida `lint-imports`.
3. **Espeja la estructura por capas**: cada subsistema vive en `app/Core/<Subsistema>/`
   con un `__init__.py` que expone su API pública.
4. **Agrega tests** en `Tests/Core/...` (sin BD) y, si cambia comportamiento público,
   **documéntalo** en `documentation/`.

Para entender un subsistema antes de tocarlo, lee su página en
[documentation/](documentation/README.md).

## Tests

- Espeja `app/` en `Tests/` (misma ruta). Tests **unitarios y sin BD**: usa fakes y
  monkeypatch, no levantes Postgres/Redis.
- Los tests escriben su log en `logs/tests/` (lo fija `Tests/conftest.py`), no en
  `logs/app.log`.
- Corre uno solo: `uv run pytest Tests/Core/Mail/test_Mailer.py -x`.

## Checklist del PR

- [ ] `ruff format --check .` y `ruff check .` pasan
- [ ] `mypy` pasa (estricto)
- [ ] `lint-imports` pasa (no rompiste las fronteras)
- [ ] `pytest` pasa
- [ ] Subject en Conventional Commits
- [ ] Sin datos personales, secretos ni credenciales
- [ ] Si cambió comportamiento público, actualizaste `documentation/`

## Código de Conducta

Este proyecto adopta el [Código de Conducta](CODE_OF_CONDUCT.md) (Contributor Covenant
2.1). Al participar, aceptas cumplirlo.

## Licencia

Al contribuir aceptas que tu aporte queda bajo la [Licencia MIT](LICENSE).
