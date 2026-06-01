"""Módulo Demo: app de ejemplo corrible (usuarios + notas) sobre SQLite.

Muestra TODO el stack: auth dual (JWT API + sesión cookie/CSRF), RBAC (@Roles) + ABAC
(Gate/policies "solo el dueño edita su nota"), routing class-based (@Controller) y vistas
HTMX/Alpine. Quickstart: `jornal migrate run` → `jornal db:seed` → `jornal serve`.
"""
