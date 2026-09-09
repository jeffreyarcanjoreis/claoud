"""Create the planos_aluno table.

Mirrors kairos.financeiro.models.PlanoAluno using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
Optional fields (ciclo_meses, inicio, observacao) stay nullable: no
fabricated defaults. A unique constraint on aluno_id enforces at most one
plan per student. No derived columns (e.g. accrued revenue) are stored here.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planos_aluno",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("formato", sa.String(length=20), nullable=False),
        sa.Column("valor", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("ciclo_meses", sa.Integer(), nullable=True),
        sa.Column("inicio", sa.Date(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aluno_id", name="uq_planos_aluno_aluno_id"),
    )


def downgrade() -> None:
    op.drop_table("planos_aluno")
