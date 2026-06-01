"""Repositorio de usuarios (lecturas)."""

from __future__ import annotations

from sqlalchemy import select

from milpa.Core.Database import Repository
from milpa.Models.User import User


class UserRepository(Repository[User, int]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.session.execute(select(User).where(User.email == email)).scalars().first()
