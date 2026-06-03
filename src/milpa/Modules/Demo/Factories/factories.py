"""Factories del demo (User/Note) con datos de Faker. El locale es configurable
(`FAKER_LOCALE` en .env; default es_MX) — ver `milpa.Core.Database.Faker`.
"""

from __future__ import annotations

from typing import Any

from milpa.Core.Auth import Hash
from milpa.Core.Database import Factory
from milpa.Core.Database.Faker import faker
from milpa.Models.Note import Note
from milpa.Models.User import User

# Hash de "password" UNA sola vez (todos los usuarios del demo comparten el password).
_DEMO_PASSWORD = Hash.make("password")


class UserFactory(Factory[User]):
    model = User

    def definition(self) -> dict[str, Any]:
        return {
            "name": faker.name(),
            "email": faker.unique.email(),
            "password": _DEMO_PASSWORD,
            "roles": "",
        }


class NoteFactory(Factory[Note]):
    model = Note

    def definition(self) -> dict[str, Any]:
        return {
            "title": faker.sentence(nb_words=4).rstrip("."),
            "body": faker.paragraph(nb_sentences=2),
        }
