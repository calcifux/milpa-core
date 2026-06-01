"""El controller de Example se AUTO-MONTA: al construir la app FastAPI, su ruta
queda registrada sin que nadie la liste (la descubre Registry.iter_routers).
"""

from __future__ import annotations

from milpa.Core.Http import create_app


def test_example_router_is_auto_mounted() -> None:
    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/example/ping" in paths
