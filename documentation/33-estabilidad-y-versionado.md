# Estabilidad, versionado y deprecación

Desde **1.0.0**, milpa (y tequio) se comprometen por escrito a un contrato de estabilidad. Esta página
es ese contrato — lo que puedes pinear con confianza y lo que no. La decisión detrás vive en el ADR 20.

## SemVer estricto desde 1.0

`MAJOR.MINOR.PATCH`:

| Parte | Qué puede cambiar | Ejemplo |
|---|---|---|
| **PATCH** (`1.0.1`) | fixes retrocompatibles | corrige un bug, sin tocar la superficie |
| **MINOR** (`1.1.0`) | features nuevas **retrocompatibles** + deprecaciones marcadas | agrega un comando, un parámetro opcional, una capacidad de `scan` |
| **MAJOR** (`2.0.0`) | el ÚNICO lugar donde algo público se rompe o se elimina | quita una API deprecada, cambia una firma |

**Dentro de una serie major nunca se rompe nada público.** Subir `1.4 → 1.9` jamás te obliga a tocar
código. Por eso puedes pinear con tranquilidad:

```toml
dependencies = ["milpa-core>=1,<2"]   # minor/patch seguros por contrato
```

## Qué es "API pública" (lo que el contrato protege)

1. **La fachada `import milpa`** — todo lo que sale del paquete top-level.
2. **Lo que aparece en estas guías de `documentation/`** — lo que tus apps importan de verdad: la sesión
   de ambiente y `@transactional`, los guards y `Gate` de Auth, los decoradores `@job`/`@cron_task`/
   `@observer`, los helpers de Http/Views, etc. **Si está documentado, es contrato.**
3. **El CLI `jornal`** — los comandos y flags documentados (`serve`, `queue work`, `schedule run/work`,
   `scan`, `new`, migraciones).
4. **Los settings de `.env` documentados** — `DATABASE_URL`, `QUEUE_NAMESPACE`, `CSP_REPORT_ONLY`, …
5. **El layout que genera `milpa new`** y sus puntos de extensión (encarpetado libre, `@capability`).

## Qué NO es público (puede cambiar sin aviso)

> **Regla práctica:** si no sale de `import milpa` y no está en una guía, **no lo importes desde tu app**.
> Si lo haces, aceptas que puede cambiar en cualquier release.

- Cualquier símbolo con prefijo `_` (es privado por convención).
- Módulos internos de `Core` no documentados en una guía.
- El formato de archivos generados (caches, `celerybeat-schedule`, artefactos de build).
- Las versiones exactas de las dependencias internas (se pinean por rango).

## Cómo se depreca algo

Nada público desaparece de golpe:

1. Se marca **deprecado en un minor** → emite `DeprecationWarning` (con el reemplazo en el mensaje) y se
   anota en el CHANGELOG bajo `### Deprecated`.
2. **Sigue funcionando** durante toda la serie major — una API deprecada en cualquier `1.x` vive **al
   menos hasta `2.0`**.
3. Se **elimina solo en el siguiente major**, y el CHANGELOG de ese major lista exactamente qué.

Corre tus tests con `-W error::DeprecationWarning` para enterarte temprano de lo que tendrás que migrar
antes del próximo major.

## Cómo leer el CHANGELOG

Sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/): `Added` / `Changed` / `Deprecated` /
`Removed` / `Fixed`. Lo que te obliga a actuar al actualizar vive en `Removed` y `Changed` — y solo
aparece en releases **major**.

## tequio

`tequio-core` (el subconjunto worker-only) lleva su **propio** número de versión y madura a su ritmo,
pero adopta **esta misma política** de estabilidad y deprecación.

## La garantía, en una frase

Desde 1.0, lo que sale de `import milpa` y lo que está documentado **no se rompe dentro de una serie
major** — y un snapshot en CI pone el build rojo si la fachada cambia sin un bump major. Pinea
`>=1,<2` y actualiza minors sin miedo.
