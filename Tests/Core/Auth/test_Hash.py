"""Tests del facade Hash: argon2id propio + verificación de bcrypt migrado de Laravel."""

from __future__ import annotations

import bcrypt

from milpa.Core.Auth import Hash


def test_make_uses_argon2id_and_round_trips() -> None:
    hashed = Hash.make("s3cret")
    assert hashed.startswith("$argon2id$")
    assert Hash.verify("s3cret", hashed)
    assert not Hash.verify("otro", hashed)


def test_verifies_laravel_bcrypt_with_2y_prefix() -> None:
    # Laravel almacena bcrypt con prefijo $2y$; simulamos uno y verificamos que normaliza.
    python_hash = bcrypt.hashpw(b"s3cret", bcrypt.gensalt()).decode()  # $2b$...
    laravel_hash = "$2y$" + python_hash[4:]
    assert laravel_hash.startswith("$2y$")
    assert Hash.verify("s3cret", laravel_hash)
    assert not Hash.verify("otro", laravel_hash)
