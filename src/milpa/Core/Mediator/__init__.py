"""Mediator / command bus opt-in. Impórtalo desde aquí:

from milpa.Core.Mediator import handles, send
"""

from __future__ import annotations

from milpa.Core.Mediator.Mediator import (
    handles,
    registered_handlers,
    reset_handlers,
    send,
)

__all__ = [
    "handles",
    "registered_handlers",
    "reset_handlers",
    "send",
]
