"""Create the perfis table.

Mirrors kairos.auth.models.Perfil using only portable SQLAlchemy types, so
the same migration works on SQLite (MVP) and PostgreSQL later. ``perfis``
maps a Supabase Auth user (user_id) to their role inside Kairos ("coach" or
"aluno"); no password is stored here — that lives in Supabase Auth. A unique
constraint on user_id enforces at most one profile per Supabase Auth user.
``aluno_id`` is nullable and only populated for "aluno" profiles once the
account is linked to a student (Fase 2); for "coach" it stays NULL.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "perfis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("papel", sa.String(length=20), nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_perfis_user_id"),
    )


def downgrade() -> None:
    op.drop_table("perfis")
