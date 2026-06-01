"""Controller de ejemplo — se AUTO-MONTA solo.

`Registry.iter_routers()` escanea `Modules/<X>/Http/` (recursivo), importa cada
controller y recolecta cualquier `APIRouter` a nivel de módulo. Por eso basta
declarar `router = APIRouter(...)` aquí; no hay que listarlo en ningún sitio.
Clónalo para CSD: `Modules/CSD/Http/CSDController.py` con su propio `router`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from milpa.Core.CeleryApp import QueueUnavailableError, broker_guard
from milpa.Core.View import view
from milpa.Modules.Example.Jobs.HelloJob import hello_world

router = APIRouter(prefix="/example", tags=["example"])


def _enqueue_hello(name: str) -> None:
    """Encola el job. Es BLOQUEANTE (I/O síncrono al broker). broker_guard traduce un
    broker caído a un error limpio. Reusado por la versión sync y la async."""
    with broker_guard():
        hello_world.delay(name=name)  # cola por defecto; consúmela con `jornal queue work`


@router.get("/ping")
def ping() -> dict[str, str]:
    """Endpoint de humo: confirma que el auto-montaje funciona (`jornal serve`)."""
    return {"module": "Example", "status": "ok"}


@router.get("/welcome", response_class=HTMLResponse)
def welcome() -> HTMLResponse:
    """Renderiza la vista del módulo (que hereda `index.html.j2`) y la sirve como HTML.
    `view()` envuelve el motor Jinja: el controller solo pide la vista por nombre."""
    # Nombre de vista estilo Jinja (ruta con "/", NO el "::" de Laravel):
    #   "example/welcome" -> prefijo "example" = nombre del MODULO (auto, minusculas)
    #                        -> app/Modules/Example/Resources/Views/welcome.html.j2
    # Una vista COMPARTIDA va sin prefijo: view("index") -> app/Resources/Views/index.html.j2
    # (= Laravel view("example::welcome"). Mapeo completo en app/Core/View/View.py.)
    return view("example/welcome")


@router.get("/hello")
def dispatch_hello(name: str = "mundo") -> dict[str, str]:
    """SYNC: encola el job (lo ejecuta el WORKER en background, NO aquí). FastAPI corre
    los endpoints `def` en un threadpool, así el `.delay()` bloqueante NO frena el event
    loop. Si el broker está caído → 503 limpio (no un 500 técnico)."""
    try:
        _enqueue_hello(name)
    except QueueUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return {"status": "encolado", "job": "example.hello", "name": name}


@router.get("/hello-async")
async def dispatch_hello_async(name: str = "mundo") -> dict[str, str]:
    """ASYNC: igual, pero `.delay()` es BLOQUEANTE → lo sacamos del event loop con
    `run_in_threadpool`. Llamar `hello_world.delay()` DIRECTO en un `async def` bloquearía
    el loop (mala práctica). Esta versión tiene sentido si el endpoint además hace `await`
    de otras cosas (DB async, HTTP); si solo encola, la versión sync de arriba es más simple."""
    try:
        await run_in_threadpool(_enqueue_hello, name)
    except QueueUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return {"status": "encolado", "job": "example.hello", "name": name, "mode": "async"}
