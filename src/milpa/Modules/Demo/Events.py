"""Eventos de DOMINIO del demo (= Events de Laravel). NO atados a la BD: se disparan
EXPLÍCITamente con `dispatch(NoteCreated(...))` desde el controller/servicio, no por un commit.

Contrato (ver [[Core/Events/Tasks]]): un evento es un `@dataclass` de PRIMITIVOS planos. Si hay
broker, viaja como kwargs JSON y el worker lo reconstruye con `Evento(**kwargs)`; sin broker corre
síncrono. Por eso NUNCA lleva instancias ORM ni sesiones — solo ids y strings.

Quién los observa: `Modules/Demo/Observers/` (1:N). Aquí solo se DECLARAN los hechos.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserRegistered:
    """Se registró un usuario nuevo. Lo observa NotifyAdminOnUserRegistered (avisa al admin)."""

    user_id: int
    name: str
    email: str


@dataclass
class NoteCreated:
    """Se creó una nota. Lo observa NotifyOwnerOnNoteCreated (confirma al dueño, con i18n).

    `owner_email` y `locale` viajan en el evento porque el observer puede correr en el worker
    (sin request): no podría resolver el email del dueño ni el locale del Accept-Language allá."""

    note_id: int
    title: str
    owner_id: int
    owner_email: str
    locale: str = "es"
