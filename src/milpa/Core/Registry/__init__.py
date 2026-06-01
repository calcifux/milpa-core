"""Registry del monolito modular: descubre y ensambla los módulos presentes en
app/Modules/ (escaneo del filesystem). Re-exporta la API pública para que los
entrypoints (`app/Core/Http`,
`app/Core/CeleryApp/CeleryApp.py`) sigan importando con
`from milpa.Core.Registry import ...`.
"""

from milpa.Core.Registry.Registry import (
    collect_beat_schedule,
    import_all_models,
    import_all_seeders,
    import_all_tasks,
    iter_cli_apps,
    iter_routers,
    iter_static_mounts,
    module_packages,
)

__all__ = [
    "collect_beat_schedule",
    "import_all_models",
    "import_all_seeders",
    "import_all_tasks",
    "iter_cli_apps",
    "iter_routers",
    "iter_static_mounts",
    "module_packages",
]
