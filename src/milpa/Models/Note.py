"""Modelo Note del demo: una nota con DUEÑO (`owner_id`) — para lucir el ABAC
("solo el dueño edita/borra su nota") vía Gate/policies."""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from milpa.Core.Database import Base, TimestampMixin


class Note(TimestampMixin, Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
