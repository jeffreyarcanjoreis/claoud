"""Create the sessoes_agendadas table.

Mirrors kairos.agenda.models.SessaoAgendada using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
Optional fields (duracao_min, observacao) stay nullable: no fabricated
defaults. No derived columns are stored here.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessoes_agendadas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("hora", sa.Time(), nullable=False),
        sa.Column("duracao_min", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sessoes_agendadas_aluno_id",
        "sessoes_agendadas",
        ["aluno_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sessoes_agendadas_aluno_id", table_name="sessoes_agendadas")
    op.drop_table("sessoes_agendadas")
