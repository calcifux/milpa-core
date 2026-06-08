"""Unit tests de la fachada pública (sin BD). Espeja src/milpa/__init__.py.

Dos contratos:
  1. `import milpa` a secas es LIBRE de efectos colaterales (no instancia Celery, no
     arrastra el kernel web de FastAPI ni toca el Core / lee Settings) — se verifica en un
     subproceso limpio, porque el proceso de pytest ya trae medio framework importado por
     los demás tests.
  2. Cada símbolo de `__all__` resuelve vía `__getattr__` (PEP 562) al MISMO objeto que
     exporta su módulo canónico, y la fachada se mantiene en sync con `_EXPORTS`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest

import milpa

# Sonda que corre en un intérprete limpio: importa la fachada y falla RUIDOSO si eso
# arrastró Celery, el kernel web (FastAPI) o cualquier submódulo de milpa (incluido
# Core.Config, que es lo que leería tu .env). La pereza es el contrato.
_PROBE = """
import sys

import milpa

cargados = [
    m for m in sys.modules
    if m == "celery" or m.startswith("celery.")
    or m == "fastapi" or m.startswith("fastapi.")
    or m.startswith("milpa.")
    if m != "milpa"
]
assert not cargados, f"import milpa arrastro side effects: {cargados}"
"""


def test_import_milpa_no_tiene_efectos_colaterales() -> None:
    src = str(Path(__file__).resolve().parents[2] / "src")
    resultado = subprocess.run(
        [sys.executable, "-c", _PROBE],
        env={**os.environ, "PYTHONPATH": src},
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_all_esta_ordenado_y_en_sync_con_exports() -> None:
    assert list(milpa.__all__) == sorted(milpa._EXPORTS), "__all__ debe listar exactamente _EXPORTS, ordenado"


def test_cada_simbolo_resuelve_al_objeto_de_su_modulo_canonico() -> None:
    for nombre in milpa.__all__:
        canonico = getattr(import_module(milpa._EXPORTS[nombre]), nombre)
        assert getattr(milpa, nombre) is canonico, f"milpa.{nombre} no es el objeto canónico"


def test_acceso_cachea_en_el_modulo() -> None:
    vars(milpa).pop("job", None)  # fuerza el camino de __getattr__
    _ = milpa.job
    assert "job" in vars(milpa)  # el segundo acceso ya no pasa por __getattr__


def test_atributo_inexistente_levanta_attribute_error() -> None:
    with pytest.raises(AttributeError, match="no_existe"):
        _ = milpa.no_existe  # mypy no se queja: con __getattr__ el atributo tipa como Any


def test_dir_lista_la_fachada_completa() -> None:
    assert set(milpa.__all__) <= set(dir(milpa))


# Snapshot CONGELADO de la superficie pública al cortar 1.0.0 (el "juramento" del ADR 20 §2.5).
# Desde 1.0, un símbolo público NO se elimina sin deprecación + bump MAJOR. Agregar símbolos en un
# minor es libre (el test solo exige que este conjunto siga siendo SUBCONJUNTO del actual); quitar
# uno hace ROJO el CI. Al cortar 2.0 se actualiza este snapshot a la nueva superficie soportada.
_PUBLIC_API_1_0_0: frozenset[str] = frozenset(
    {
        "Auth",
        "Authenticatable",
        "AuthenticatableMixin",
        "Base",
        "Can",
        "Clock",
        "ConflictError",
        "Controller",
        "CurrentUser",
        "CursorPage",
        "Delete",
        "DomainError",
        "Factory",
        "Fallback",
        "FixedClock",
        "Gate",
        "Get",
        "Hash",
        "Job",
        "Mail",
        "MailContent",
        "Mailable",
        "Observer",
        "Page",
        "Patch",
        "Pipe",
        "Pipeline",
        "Post",
        "Put",
        "Pwa",
        "QueueUnavailableError",
        "Repository",
        "ResourceNotFoundError",
        "Roles",
        "Scope",
        "Seeder",
        "Settings",
        "SoftDeleteMixin",
        "SystemClock",
        "TimestampMixin",
        "TokenPrincipal",
        "api_version",
        "authenticated",
        "auto_session",
        "broker_guard",
        "celery_app",
        "console_command",
        "cron",
        "cron_task",
        "current_locale",
        "current_session",
        "daily",
        "daily_at",
        "dispatch",
        "every_fifteen_minutes",
        "every_five_minutes",
        "every_minute",
        "every_minutes",
        "every_ten_minutes",
        "every_thirty_minutes",
        "faker",
        "get_current_token",
        "guarded",
        "handles",
        "hourly",
        "hourly_at",
        "job",
        "monthly",
        "negotiate",
        "policy",
        "prefers_html",
        "rate_limit",
        "require_any_scope",
        "require_roles",
        "require_scopes",
        "resolve_accept_language",
        "retry_policy",
        "send",
        "session_scope",
        "set_request_locale",
        "set_revocation_check",
        "settings",
        "shell_context",
        "t",
        "transactional",
        "view",
        "weekly",
    }
)


def test_superficie_publica_1_0_0_no_se_rompe() -> None:
    """Contrato SemVer duro de la fachada (ADR 20): ningún símbolo público de 1.0.0 puede
    desaparecer dentro de la serie 1.x. Si este test truena, QUITASTE algo público sin deprecar +
    bump MAJOR — exactamente lo que el ADR prohíbe. Agregar símbolos nuevos (minor) NO lo rompe."""
    eliminados = _PUBLIC_API_1_0_0 - set(milpa.__all__)
    assert not eliminados, (
        f"Superficie pública 1.0.0 rota — símbolos eliminados sin major: {sorted(eliminados)}. "
        "Quitar API pública exige deprecación + bump MAJOR (ver docs/20_versioning_stability_deprecation)."
    )
