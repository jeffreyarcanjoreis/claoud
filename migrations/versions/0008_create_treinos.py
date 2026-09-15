"""Create the treinos and treino_itens tables (planilhas de treino).

A "treino" is a named workout belonging to a student; its "itens" are the
exercises in it (referencing the biblioteca de exercícios), each with optional
séries/reps/carga. Only portable SQLAlchemy types are used (rule 4). Optional
fields stay nullable: no fabricated defaults (rule 6). No derived columns.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "treinos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id", sa.Integer(), sa.ForeignKey("alunos.id"), nullable=False
        ),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_treinos_aluno_id", "treinos", ["aluno_id"], unique=False)

    op.create_table(
        "treino_itens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "treino_id", sa.Integer(), sa.ForeignKey("treinos.id"), nullable=False
        ),
        sa.Column(
            "exercicio_id",
            sa.Integer(),
            sa.ForeignKey("exercicios.id"),
            nullable=False,
        ),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("series", sa.Integer(), nullable=True),
        sa.Column("reps", sa.String(length=40), nullable=True),
        sa.Column("carga", sa.String(length=40), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_treino_itens_treino_id", "treino_itens", ["treino_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_treino_itens_treino_id", table_name="treino_itens")
    op.drop_table("treino_itens")
    op.drop_index("ix_treinos_aluno_id", table_name="treinos")
    op.drop_table("treinos")
