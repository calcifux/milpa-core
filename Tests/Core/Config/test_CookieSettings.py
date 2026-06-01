"""Los nombres de cookies derivan del prefijo (`cookie_prefix`, default "milpa")
cuando no se fijan explícitos; un nombre explícito gana.

`_env_file=None` aísla del .env real; `database_url` es el único campo obligatorio.
"""

from __future__ import annotations

from milpa.Core.Config.Settings import Settings


def test_cookie_names_default_to_milpa_prefix() -> None:
    s = Settings(_env_file=None, database_url="sqlite://")
    assert s.cookie_prefix == "milpa"
    assert s.session_cookie == "milpa_session"
    assert s.csrf_cookie == "milpa_csrf"


def test_cookie_prefix_override_derives_both() -> None:
    s = Settings(_env_file=None, database_url="sqlite://", cookie_prefix="acme")
    assert s.session_cookie == "acme_session"
    assert s.csrf_cookie == "acme_csrf"


def test_explicit_cookie_names_win_over_prefix() -> None:
    s = Settings(
        _env_file=None, database_url="sqlite://", cookie_prefix="acme", session_cookie="sess", csrf_cookie="tok"
    )
    assert s.session_cookie == "sess"
    assert s.csrf_cookie == "tok"
