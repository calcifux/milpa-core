"""Kernel web del framework (milpa): construye la app FastAPI y AUTO-MONTA los
endpoints de los módulos (`Registry.iter_routers`).

Vive en Core porque es maquinaria GENÉRICA y reusable (idéntica en cualquier
proyecto): no importa Modules de forma estática — el discovery es dinámico. Se
levanta con `jornal serve` (uvicorn en modo --factory). Agregar endpoints = crear
un controller con `router = APIRouter(...)` en `Modules/<X>/Http/`; se monta solo.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header
from fastapi.staticfiles import StaticFiles
from loguru import logger

from milpa.Core.Config import settings
from milpa.Core.Database import Base, engine
from milpa.Core.Http.ExceptionHandler import register_exception_handlers
from milpa.Core.Http.Middleware import register_middlewares
from milpa.Core.Http.RateLimit import register_rate_limit
from milpa.Core.Logging import setup_logging
from milpa.Core.Registry import (
    import_all_handlers,
    import_all_models,
    import_all_observers,
    import_all_policies,
    iter_routers,
    iter_static_mounts,
    module_packages,
)
from milpa.Core.Translate import resolve_accept_language, set_request_locale


async def _use_request_locale(accept_language: str = Header(default="")) -> None:
    """Dependency GLOBAL (corre en TODOS los controllers): fija el locale del request
    desde Accept-Language; si no viene, cae al app_fallback_locale. Así el i18n queda
    resuelto por default sin que cada dev lo recuerde — milpa endurece FastAPI.

    DEBE ser async: una dependency sync corre en threadpool y su contextvar.set() no
    llegaría al endpoint. Async corre en el contexto del request, que run_in_threadpool
    copia al handler (sync o async)."""
    set_request_locale(resolve_accept_language(accept_language))


def _module_names() -> list[str]:
    """Nombres cortos de los módulos descubiertos (solo para mostrar)."""
    return [package.rsplit(".", 1)[-1] for package in module_packages()]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Registra los modelos compartidos (app.Models) en Base.metadata.
    import_all_models()
    # Descubre los patrones opt-in de cada módulo: Observers (los dispara Events.dispatch),
    # Handlers (los resuelve Mediator.send) y Policies (las registra en el Gate, @policy).
    # Importar != ejecutar: solo llena sus registros; nada corre hasta que el código actúa.
    import_all_observers()
    import_all_handlers()
    import_all_policies()
    # Compartimos BD con esquema legacy: solo crea tablas si se activa explícito.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    logger.info(
        "{app} arrancó | módulos: {modules}",
        app=settings.app_name,
        modules=_module_names() or "(ninguno)",
    )
    yield


def create_app() -> FastAPI:
    """App factory: logging + FastAPI + auto-montaje de los routers de los módulos.

    Es una FÁBRICA (no un `app` global) para mejor testabilidad y para que uvicorn
    la levante con `--factory` (cada arranque/test obtiene una instancia fresca)."""
    setup_logging()
    # Dependency GLOBAL: resuelve el locale del request (Accept-Language → fallback)
    # para TODOS los controllers, automático.
    app = FastAPI(title=settings.app_name, lifespan=_lifespan, dependencies=[Depends(_use_request_locale)])

    # Stack base de middlewares (CORS/TrustedHost/GZip) según Settings.
    register_middlewares(app)

    # Handlers globales: TODOS los errores (dominio, validación 422, HTTPException, 500)
    # salen en RFC 9457 (application/problem+json), una sola forma para el cliente.
    register_exception_handlers(app)

    # Rate limiting (SlowAPI): expone el limiter en app.state y traduce el 429 a RFC 9457.
    # Se registra DESPUÉS para que su handler (RateLimitExceeded) gane sobre el de HTTPException.
    register_rate_limit(app)

    # Auto-montaje: cada APIRouter descubierto en Modules/<X>/Http/ se incluye.
    for router in iter_routers():
        app.include_router(router)

    # Auto-montaje de estáticos: cada Modules/<X>/Resources/Static/ se sirve en
    # "/static/<x>" (namespaced por módulo, como las vistas). Así un módulo trae
    # su propio CSS/JS/imágenes sin tocar Core. `name` único para url_for().
    for url_path, directory in iter_static_mounts():
        module_slug = url_path.rsplit("/", 1)[-1]
        app.mount(url_path, StaticFiles(directory=directory), name=f"static-{module_slug}")

    # Estáticos COMPARTIDOS de la app: app/Resources/Static/ -> "/static" (CSS/JS de
    # toda la app, p. ej. el welcome.css del layout base). Se monta DESPUÉS de los
    # per-módulo para que "/static/<x>/..." haga match primero (Starlette: gana el
    # primer match). parents[2] desde app/Core/Http/Http.py = app/.
    # "/static": las del USUARIO (USER_STATIC_DIR) si están configuradas; si no, las del
    # framework (src/milpa/Resources/Static, p. ej. el welcome.css del layout base).
    shared_static = (
        Path(settings.user_static_dir)
        if settings.user_static_dir
        else Path(__file__).resolve().parents[2] / "Resources" / "Static"
    )
    if shared_static.is_dir():
        app.mount("/static", StaticFiles(directory=str(shared_static)), name="static")

    # Builds de Vite del FRONTEND (asset-pipeline estilo laravel-vite; OPT-IN, ver
    # Core/View/Vite.py). El public/ del proyecto (donde cada surco deja su build
    # en "public/<app>") se monta COMPLETO en VITE_ASSETS_URL — UN mount para todas
    # las apps, como el public/ de Laravel. Con VITE_DIST_DIR explicito se monta ese
    # dist directo. Sin nada detectado no se monta (la feature muere en paz). Los
    # <link>/<script> hasheados los emite el helper vite() en el template Jinja.
    assets_root = settings.vite_assets_url.rstrip("/")
    # VITE_ASSETS_URL="/" (o vacío) dejaría assets_root="" — y mount("") en Starlette
    # es un CATCH-ALL en la raíz: taparía /status y degradaría los errores RFC 9457
    # a 404 planos de estático. Los assets siempre viven bajo su propio prefijo.
    if assets_root and settings.vite_dist_dir:
        explicit_dist = Path(settings.vite_dist_dir)
        if explicit_dist.is_dir():
            app.mount(assets_root, StaticFiles(directory=str(explicit_dist)), name="vite")
    elif assets_root:
        # El guard de vacío importa: Path("") es Path(".") y SIEMPRE is_dir() — sin él,
        # VITE_PUBLIC_DIR= montaría la RAÍZ del proyecto (.env, secrets/, .git/) en
        # /vite. Vacío = apagado, el mismo idioma que VITE_DIST_DIR/VITE_HOT_FILE.
        public_root = Path(settings.vite_public_dir)
        if settings.vite_public_dir and public_root.is_dir():
            app.mount(assets_root, StaticFiles(directory=str(public_root)), name="vite")

    @app.get("/status")
    async def root() -> dict[str, object]:
        return {"servicio": settings.app_name, "modulos": _module_names(), "status": "ok"}

    return app
