"""Ejemplo de "middleware del módulo" idiomático: una DEPENDENCY a nivel de router.

`APIRouter(dependencies=[Depends(...)])` corre la dependency ANTES de CADA ruta del
router (como un middleware acotado a este módulo). Si la dependency lanza, la ruta se
rechaza. Vive en el controller del módulo → no es global, no hay orden que cuidar, y
viaja con el módulo al extraerlo. Se auto-monta igual que cualquier otro controller.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """'Middleware' del módulo: exige el header X-API-Key. Lanza 401 si falta/no coincide.
    En real validarías un token (p. ej. app.Core.Auth.Passport); aquí es demo."""
    if x_api_key != "demo-secret":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida")


# dependencies a nivel ROUTER → aplica a TODAS las rutas de abajo (middleware del módulo).
router = APIRouter(prefix="/example/secured", tags=["example"], dependencies=[Depends(require_api_key)])


@router.get("/ping")
def secured_ping() -> dict[str, str]:
    """Solo responde si pasó `require_api_key` (header X-API-Key correcto)."""
    return {"module": "Example", "scope": "secured", "status": "ok"}
