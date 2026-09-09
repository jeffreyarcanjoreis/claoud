"""Create the checkins table.

Mirrors kairos.checkin.models.CheckinDiario using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
``checkins`` stores one daily check-in per student; every self-report field
besides ``aluno_id`` and ``data`` stays nullable, since a check-in may
answer only part of the form and no field is ever backfilled with a
fabricated default. Allowed values for ``sono_qualidade``/``humor`` and the
numeric ranges (sono_horas 0-24, estresse/energia/dor_intensidade 0-10) are
validated at the service layer, not the database. A unique constraint on
(aluno_id, data) enforces at most one check-in per student per day.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("sono_horas", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("sono_qualidade", sa.String(length=20), nullable=True),
        sa.Column("estresse", sa.Integer(), nullable=True),
        sa.Column("energia", sa.Integer(), nullable=True),
        sa.Column("humor", sa.String(length=20), nullable=True),
        sa.Column("dor_local", sa.Text(), nullable=True),
        sa.Column("dor_intensidade", sa.Integer(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aluno_id", "data", name="uq_checkins_aluno_data"),
    )
    op.create_index(
        op.f("ix_checkins_aluno_id"), "checkins", ["aluno_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_checkins_aluno_id"), table_name="checkins")
    op.drop_table("checkins")
