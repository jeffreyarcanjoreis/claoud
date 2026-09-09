"""Create the registros_treino table.

Mirrors kairos.registro_treino.models.RegistroTreino using only portable
SQLAlchemy types, so the same migration works on SQLite (MVP) and PostgreSQL
later. ``registros_treino`` stores a student's self-reported log of a
workout they completed; ``treino_id`` is nullable because the student may
not know or record which planned workout they followed. Allowed values for
``sensacao`` and the 0-10 range for ``rpe`` are validated at the service
layer, not the database. Several logs per student per day are allowed, so
there is no unique constraint on (aluno_id, data).

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registros_treino",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column(
            "treino_id",
            sa.Integer(),
            sa.ForeignKey("treinos.id"),
            nullable=True,
        ),
        sa.Column("rpe", sa.Integer(), nullable=True),
        sa.Column("sensacao", sa.String(length=20), nullable=True),
        sa.Column("o_que_mudou", sa.Text(), nullable=True),
        sa.Column("dor_nova", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_registros_treino_aluno_id"),
        "registros_treino",
        ["aluno_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_registros_treino_aluno_id"), table_name="registros_treino")
    op.drop_table("registros_treino")
