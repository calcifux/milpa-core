"""Seeder del demo: ~100 usuarios con datos de Faker + ROLES variados (para probar RBAC/ABAC a
fondo) + muchas notas de Ana (para el scroll infinito). Idempotente.

Muestra que un seeder puede usar FACTORIES (datos con Faker) y/o ir A MANO — milpa no obliga.
Aquí: los logins conocidos van con email/rol fijos (a mano) y el resto del dato lo pone Faker;
el volumen se crea con `count(...)`. Todos los usuarios usan password "password".
"""

from __future__ import annotations

from sqlalchemy import select

from milpa.Core.Database import current_session
from milpa.Core.Database.Seeder import Seeder
from milpa.Models.User import User
from milpa.Modules.Demo.Factories import NoteFactory, UserFactory


class DemoSeeder(Seeder):
    def run(self) -> None:
        if current_session().execute(select(User).limit(1)).first() is not None:
            return  # ya sembrado: no duplicar

        users = UserFactory()
        # Logins conocidos (a mano: email/rol fijos; el nombre lo pone Faker).
        users.create(name="Admin Demo", email="admin@demo.test", roles="admin")
        ana = users.create(name="Ana López", email="ana@demo.test", roles="editor")
        beto = users.create(name="Beto Ramírez", email="beto@demo.test", roles="")

        # 97 con Faker (nombres reales) y roles variados (total 100), para RBAC, búsqueda y scroll.
        users.count(60)  # normales
        users.count(20, roles="viewer")
        users.count(12, roles="editor")
        users.count(5, roles="admin")

        # Notas de Ana con Faker (para el scroll) + una a mano de Beto.
        NoteFactory().count(23, owner_id=ana.id)
        NoteFactory().create(owner_id=beto.id, title="Idea de Beto", body="Probar milpa este finde")
