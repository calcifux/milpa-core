"""Kernel web del framework. Re-exporta la app factory `create_app` para que
los entrypoints (p. ej. `jornal serve`) la levanten con
`uvicorn.run("milpa.Core.Http.Http:create_app", factory=True)`.
"""

from __future__ import annotations

from milpa.Core.Http.Http import create_app
from milpa.Core.Http.RateLimit import rate_limit
from milpa.Core.Http.Routing import Controller, Delete, Get, Patch, Post, Put, api_version

__all__ = ["Controller", "Delete", "Get", "Patch", "Post", "Put", "api_version", "create_app", "rate_limit"]
