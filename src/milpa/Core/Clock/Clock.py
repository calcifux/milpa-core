"""Reloj de la app, INYECTABLE (estilo `java.time.Clock` de Spring), para los
cálculos de fechas de NEGOCIO en la zona configurada (TIMEZONE del .env).

No se importa suelto en el código de negocio (eso acopla y no se puede congelar
en tests): se recibe inyectado vía el Unit of Work (`self._database.clock.now()`).
En tests se inyecta un `FixedClock` (equivalente a `Carbon::setTestNow()`).

Para los timestamps de BD NO se usa esto: los pone la BD con func.now() y la
conexión ya corre en la zona de la app (ver Database/Session.py y Timestamp.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from milpa.Core.Config.Settings import settings


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Hora real en la zona de la app, NAIVE local (como guarda Eloquent/Carbon)."""

    def now(self) -> datetime:
        return datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)


class FixedClock:
    """Reloj congelado para tests (= Carbon::setTestNow). Siempre devuelve `moment`."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment
