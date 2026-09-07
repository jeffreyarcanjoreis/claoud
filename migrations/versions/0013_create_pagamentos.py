"""Create the pagamentos table.

Mirrors kairos.financeiro.models.Pagamento using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
Optional fields (data_pagamento, observacao) stay nullable: no fabricated
defaults. A unique constraint on (aluno_id, ano, mes) enforces at most one
payment per student per competence.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pagamentos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "aluno_id", "ano", "mes", name="uq_pagamentos_aluno_competencia"
        ),
    )


def downgrade() -> None:
    op.drop_table("pagamentos")
