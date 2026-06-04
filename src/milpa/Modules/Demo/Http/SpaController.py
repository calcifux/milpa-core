"""Carril SPA del Demo: milpa sirve el SHELL de una app Vite (estilo laravel-vite).

Forma tradicional: el SPA corre en su propio servidor (segundo origen, CORS, env
vars congeladas en build-time) y cada app copia ~60 líneas de plomería (env_json,
manifest de la PWA, ruta del SW). Estilo milpa: el backend es dueño del shell Jinja
— mismo origen, runtime-config (`window.__ENV`) sin rebuild — y la plomería vive en
el Core: `shell_context()` (Core/Http/Shell) y `Pwa.webmanifest()`/
`Pwa.service_worker()` (Core/View/Pwa, iconos auto-descubiertos del build). Lo único
escrito a mano aquí son las DOS rutas del shell; las de la PWA son one-liners.

El catch-all devuelve el MISMO shell para cualquier sub-ruta: el router client-side
(react-router con basename runtime) decide qué renderizar — patrón SPA-fallback,
acotado al prefijo /spa (no se come /api). REVERSE PROXY bajo sub-ruta:
el prefijo llega por el `root_path` ASGI y se propaga solo
(BASE_PATH en __ENV, start_url/scope del manifest).
"""

from __future__ import annotations

from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.requests import Request

from milpa.Core.Http import Controller, Get
from milpa.Core.Http.Shell import shell_context
from milpa.Core.View import Pwa, view


@Controller("/spa", tags=["demo-spa"])
class SpaController:
    @Get("")
    def shell(self, request: Request) -> HTMLResponse:
        """El shell del SPA (ruta raíz del prefijo)."""
        return view("demo/spa", shell_context(request))

    @Get("/manifest.webmanifest")
    def manifest(self, request: Request) -> Response:
        """Manifest de la PWA — identidad StackCraft (Carbon/Forge);
        start_url/scope e iconos los arma el Core en runtime. ANTES del catch-all."""
        return Pwa.webmanifest(
            request,
            prefix="/spa",
            app="demo-spa",
            description="SPA de ejemplo montada en milpa estilo laravel-vite, instalable y con offline básico.",
            background_color="#0A0A0A",
            theme_color="#FF6B1A",
        )

    @Get("/sw.js")
    def sw(self) -> FileResponse:
        """El Service Worker, desde /spa para que su scope cubra a la app."""
        return Pwa.service_worker(app="demo-spa")

    @Get("/{path:path}")
    def shell_subruta(self, request: Request, path: str) -> HTMLResponse:
        """Mismo shell para CUALQUIER sub-ruta (/spa/acerca, /spa/estado, …): el
        deep-link recarga bien porque el server siempre responde el shell y el
        router del cliente resuelve la vista. `path` solo existe para el match."""
        del path  # solo participa en el routing; el shell es idéntico
        return view("demo/spa", shell_context(request))
