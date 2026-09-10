"""Create the reconhecimentos_nivel table.

Mirrors kairos.nivel.models.ReconhecimentoNivel using only portable
SQLAlchemy types, so the same migration works on SQLite (MVP) and PostgreSQL
later. ``reconhecimentos_nivel`` stores the student's self-recognized level
(Fundacao/Construcao/Dominio/Maestria, architecture rules 11-14): the level
is never granted or ranked by the system, only recognized by the student.
The allowed set of values for ``nivel`` is validated at the service layer,
not the database. ``nota`` stays nullable, since a recognition may carry no
note and no field is ever backfilled with a fabricated default (rule 6).
There is NO unique constraint on aluno_id: each row is one recognition in
the student's history, and the current level is the most recent row.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reconhecimentos_nivel",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("nivel", sa.String(length=20), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reconhecimentos_nivel_aluno_id"),
        "reconhecimentos_nivel",
        ["aluno_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reconhecimentos_nivel_aluno_id"), table_name="reconhecimentos_nivel"
    )
    op.drop_table("reconhecimentos_nivel")
