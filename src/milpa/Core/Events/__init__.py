"""Eventos / Observers opt-in (estilo Laravel Events/Listeners, NO atados a la BD).

Impórtalo desde aquí (surface SIN redis — la rama encolada vive en Tasks.py y se importa
perezosamente, así un proyecto que no encola observers no jala Celery/redis):

    from milpa.Core.Events import Observer, dispatch
"""

from __future__ import annotations

from milpa.Core.Events.Dispatch import dispatch
from milpa.Core.Events.Observer import Observer, registered_observers, reset_observers

__all__ = [
    "Observer",
    "dispatch",
    "registered_observers",
    "reset_observers",
]
