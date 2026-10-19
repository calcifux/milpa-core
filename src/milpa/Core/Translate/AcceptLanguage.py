"""El idioma de una petición web, sacado del encabezado Accept-Language.

Es lo único de traducciones que solo existe con la web: `t()`, `current_locale()` y
`set_request_locale()` son de tequio (los usan también los correos del worker). Lo llama la capa HTTP
(`Core/Http/Http.py`) al entrar cada petición.
"""

from __future__ import annotations

from milpa.Core.Config import settings


def resolve_accept_language(header: str) -> str:
    """Resuelve el locale desde el header Accept-Language: toma el idioma de mayor
    `q`, reducido a su subtag primario ('es-MX' -> 'es'). Vacío/no parseable → cae
    al app_fallback_locale. (i18nice ya hace fallback si el catálogo no existe.)"""
    best_quality = -1.0
    best_locale = settings.app_fallback_locale
    for part in header.split(","):
        language, _, params = part.strip().partition(";")
        language = language.strip().lower()
        if not language or language == "*":
            continue
        quality = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        if quality > best_quality:
            best_quality = quality
            best_locale = language.split("-")[0]
    return best_locale
