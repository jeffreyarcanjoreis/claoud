"""Create the sessoes_realizadas table.

Mirrors kairos.acompanhamento.models.SessaoRealizada using only portable
SQLAlchemy types, so the same migration works on SQLite (MVP) and PostgreSQL
later. Optional fields (disposicao, feedback) stay nullable: no fabricated
defaults. No derived columns are stored here.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessoes_realizadas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("presenca", sa.String(length=20), nullable=False),
        sa.Column("disposicao", sa.String(length=20), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sessoes_realizadas_aluno_id",
        "sessoes_realizadas",
        ["aluno_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sessoes_realizadas_aluno_id", table_name="sessoes_realizadas")
    op.drop_table("sessoes_realizadas")
