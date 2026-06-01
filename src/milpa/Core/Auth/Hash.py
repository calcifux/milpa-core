"""Facade de hashing de passwords (≈ `Hash` de Laravel).

Hashea con **argon2id** (el recomendado hoy) y verifica además **bcrypt** — para que un
proyecto que MIGRA de Laravel pueda validar los passwords existentes (Laravel usa bcrypt) sin
re-hashear a todos de golpe. El prefijo `$2y$` de Laravel se normaliza a `$2b$` (mismo hash).
"""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

# El PRIMER hasher se usa para hashear (argon2id); todos se prueban al verificar (bcrypt para
# hashes migrados de Laravel).
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def _normalize(hashed: str) -> str:
    """Laravel marca sus bcrypt con `$2y$`; Python con `$2b$`. El hash es idéntico — solo el
    prefijo cambia — así que normalizamos para que `bcrypt` lo acepte."""
    if hashed.startswith("$2y$"):
        return "$2b$" + hashed[4:]
    return hashed


class Hash:
    """Punto de entrada único para hashear/verificar passwords."""

    @staticmethod
    def make(password: str) -> str:
        """Devuelve el hash argon2id de `password`."""
        return _password_hash.hash(password)

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        """True si `password` corresponde a `hashed` (argon2 o bcrypt/Laravel)."""
        return _password_hash.verify(password, _normalize(hashed))
