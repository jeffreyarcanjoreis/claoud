"""Create the tarefas table.

Mirrors kairos.tarefas.models.Tarefa using only portable SQLAlchemy types, so
the same migration works on SQLite (MVP) and PostgreSQL later. Optional
fields (categoria, prazo) stay nullable: no fabricated defaults. No derived
columns are stored here.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tarefas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("categoria", sa.String(length=20), nullable=True),
        sa.Column("prazo", sa.Date(), nullable=True),
        sa.Column(
            "concluida", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("tarefas")
