"""Add the optional treino_id link to sessoes_agendadas.

A scheduled session may point to the workout (treino) assigned to that day, so
the coach can open "the training done that day" from the agenda. The column is
nullable: a session without an assigned workout is NULL (rule 6), never a
fabricated default.

A plain nullable column is added (no DB-level FK): the ORM model declares the
relationship for joins, and the service enforces that a chosen treino belongs
to the same student. This keeps the migration portable and simple across SQLite
(MVP) and PostgreSQL.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessoes_agendadas", sa.Column("treino_id", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sessoes_agendadas", "treino_id")
