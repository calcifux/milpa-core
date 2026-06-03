"""demo: add archived to notes

Revision ID: a7c1d9e2f4b8
Revises: c35b0c89ce97
Create Date: 2026-06-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificadores de la revisión, usados por Alembic.
revision: str = "a7c1d9e2f4b8"
down_revision: str | None = "c35b0c89ce97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `archived` lo agregó el comando ArchiveNote (Mediator) al modelo Note. server_default=false
    # para que las filas existentes (BD migrada/legacy) tomen valor sin violar NOT NULL; el modelo
    # usa default=False client-side, el server_default cubre el backfill de lo ya creado.
    op.add_column("notes", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("notes", "archived")
