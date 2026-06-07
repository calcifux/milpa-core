"""Instancia de Faker con el locale CONFIGURADO (`FAKER_LOCALE` en .env; default es_MX).

`faker` es dependencia de DEV (factories/seeders/tests), NO del runtime de producción.
Por eso el Faker real se carga PEREZOSO (defensa en profundidad): importar este módulo es
gratis; el error accionable sale solo al USARLO (`faker.name()`, etc.). Hoy el discovery del
core NO es recursivo, así que un `jornal list` en un wheel limpio no importa las factories;
pero el proxy perezoso blinda cualquier import futuro de una factory en runtime (o un seeder
arrastrado por discovery) contra el ModuleNotFoundError-en-duro al cargar el módulo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from milpa.Core.Config import settings

if TYPE_CHECKING:
    from faker import Faker

_FAKER_MISSING = (
    "Faker no está instalado y las factories/seeders lo necesitan. Es dependencia de "
    "DESARROLLO (no de producción): instálalo con `uv add faker` (ya viene en el dev-group "
    "del proyecto scaffoldeado, así que normalmente basta `uv sync`)."
)


def make_faker() -> Faker:
    """Una instancia nueva de Faker con el locale de `FAKER_LOCALE` (p. ej. es_MX / en_US)."""
    try:
        from faker import Faker
    except ImportError as error:  # pista accionable, no el ModuleNotFoundError pelón
        raise ModuleNotFoundError(_FAKER_MISSING) from error
    return Faker(settings.faker_locale)


class _LazyFaker:
    """Proxy perezoso del Faker compartido: el real se construye en el PRIMER uso
    (`faker.name()`, `faker.sentence()`, ...), no al importar. Así las factories pueden
    importarse en cualquier runtime sin arrastrar la dependencia de dev."""

    def __init__(self) -> None:
        self._real: Faker | None = None

    def __getattr__(self, name: str) -> Any:
        # __getattr__ solo corre para atributos NO encontrados (los métodos de Faker);
        # `_real` sí existe en la instancia, así que no se intercepta a sí mismo.
        if self._real is None:
            self._real = make_faker()
        return getattr(self._real, name)


# Instancia compartida lista para usar en las factories/seeders (perezosa).
faker = _LazyFaker()
