"""Capa HTTP del módulo Example. Cualquier `APIRouter` a nivel de módulo bajo
`Modules/<X>/Http/` (recursivo) se auto-monta vía `Registry.iter_routers()` — no
hay que registrarlo en ningún lado. Crea un controller y listo.
"""
