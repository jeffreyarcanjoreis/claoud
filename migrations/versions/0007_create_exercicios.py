"""Create the exercicios table (biblioteca de exercícios).

Mirrors kairos.treinos.models.Exercicio using only portable SQLAlchemy types,
so the same migration works on SQLite (MVP) and PostgreSQL later. The optional
fields (grupo_muscular, observacao) stay nullable: no fabricated defaults
(rule 6). No derived columns are stored here.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exercicios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("grupo_muscular", sa.String(length=60), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("exercicios")
