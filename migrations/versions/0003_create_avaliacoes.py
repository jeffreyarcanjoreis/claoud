"""Create the avaliacoes table.

Mirrors kairos.avaliacoes.models.Avaliacao using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
Optional fields are nullable: absent data is stored as NULL, never as a
fabricated default. No derived columns (delta, BMI) are stored here.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avaliacoes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("peso", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("altura", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("gordura_pct", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("massa_magra", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("massa_gorda", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_avaliacoes_aluno_id"), "avaliacoes", ["aluno_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_avaliacoes_aluno_id"), table_name="avaliacoes")
    op.drop_table("avaliacoes")
