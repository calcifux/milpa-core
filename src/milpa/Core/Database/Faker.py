"""Instancia de Faker con el locale CONFIGURADO (`FAKER_LOCALE` en .env; default es_MX).

`faker` es dependencia de DEV (factories/seeders/tests). Este módulo se importa SOLO desde código
que genera datos falsos —NO desde el runtime de la app— por eso `faker` no es dependencia del
core en producción (no lo jala `app.Core.Database.__init__`).
"""

from __future__ import annotations

from faker import Faker

from milpa.Core.Config import settings


def make_faker() -> Faker:
    """Una instancia nueva de Faker con el locale de `FAKER_LOCALE` (p. ej. es_MX / en_US)."""
    return Faker(settings.faker_locale)


# Instancia compartida lista para usar en las factories/seeders.
faker = make_faker()
