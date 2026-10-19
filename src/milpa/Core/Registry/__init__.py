"""Registry del monolito modular: descubre y ensambla los módulos presentes en
app/Modules/ (escaneo del filesystem). Re-exporta la API pública para que los
entrypoints (`milpa/Core/Http`, `CeleryApp`) sigan importando con
`from milpa.Core.Registry import ...`.

El barrido de módulos, comandos, crons y seeders es de tequio (`milpa.Core.Registry.Registry` es el
mismo módulo, ver `milpa.Core`); lo de la web (rutas, policies, estáticos) es de milpa (`WebRegistry.py`).
"""

from __future__ import annotations

from milpa.Core.Registry.Registry import (
    collect_beat_schedule,
    import_all_handlers,
    import_all_models,
    import_all_observers,
    import_all_seeders,
    import_all_tasks,
    iter_cli_apps,
    module_packages,
)
from milpa.Core.Registry.WebRegistry import (
    import_all_policies,
    iter_fallback_routes,
    iter_routers,
    iter_static_mounts,
)

__all__ = [
    "collect_beat_schedule",
    "import_all_handlers",
    "import_all_models",
    "import_all_observers",
    "import_all_policies",
    "import_all_seeders",
    "import_all_tasks",
    "iter_cli_apps",
    "iter_fallback_routes",
    "iter_routers",
    "iter_static_mounts",
    "module_packages",
]
