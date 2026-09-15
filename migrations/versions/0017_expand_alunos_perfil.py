"""Expand alunos with the full profile carried over from sign-up (lead->aluno).

Adds the fields captured during public sign-up (kairos.contatos) so a
contact's full profile survives conversion into a student, mirroring the
relevant subset of kairos.alunos.models.Aluno with only portable SQLAlchemy
types (switching from SQLite to PostgreSQL must require configuration only).
All new columns are nullable: a field without data stays NULL, never a
fabricated default that looks like real data.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alunos", sa.Column("contact", sa.String(length=200), nullable=True))
    op.add_column("alunos", sa.Column("sex", sa.String(length=30), nullable=True))
    op.add_column("alunos", sa.Column("age_reported", sa.Integer(), nullable=True))
    op.add_column(
        "alunos", sa.Column("weekly_frequency", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "alunos",
        sa.Column("conditioning_level", sa.String(length=20), nullable=True),
    )
    op.add_column("alunos", sa.Column("health_conditions", sa.Text(), nullable=True))
    op.add_column("alunos", sa.Column("medications", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.drop_column("medications")
        batch_op.drop_column("health_conditions")
        batch_op.drop_column("conditioning_level")
        batch_op.drop_column("weekly_frequency")
        batch_op.drop_column("age_reported")
        batch_op.drop_column("sex")
        batch_op.drop_column("contact")
