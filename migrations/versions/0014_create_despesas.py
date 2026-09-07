"""Create the despesas table.

Mirrors kairos.financeiro.models.Despesa using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
Optional fields (categoria, observacao) stay nullable: no fabricated
defaults. Expenses are not tied to a specific student.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "despesas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("descricao", sa.String(length=200), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=True),
        sa.Column("valor", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("despesas")
