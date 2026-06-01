"""Controller CLASS-BASED de ejemplo (estilo Spring), auto-montado por el Registry.

Muestra `@Controller` + `@Get/@Post` CONVIVIENDO con los controllers función-style del mismo
módulo (`controller.py` usa `router = APIRouter()`). Ambos estilos se descubren y montan solos.
"""

from __future__ import annotations

from pydantic import BaseModel

from milpa.Core.Http import Controller, Get, Post

_CATS: list[str] = ["Michi", "Pelusa"]


class CatInput(BaseModel):
    name: str


@Controller("/example/cats", tags=["example-cats"])
class CatsController:
    @Get("/")
    def index(self) -> list[str]:
        """Lista los gatos (demo en memoria)."""
        return list(_CATS)

    @Get("/{index}")
    def show(self, index: int) -> dict[str, object]:
        """Un gato por índice; muestra binding de path param tipado."""
        name = _CATS[index] if 0 <= index < len(_CATS) else None
        return {"index": index, "name": name}

    @Post("/", status_code=201)
    def store(self, body: CatInput) -> dict[str, str]:
        """Crea un gato (demo): muestra body Pydantic + status_code."""
        return {"created": body.name}
