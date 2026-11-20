"""Add the arc proportion columns to treinos.

Adds five optional minute counters describing how a workout session was split
across the arc phases: ``min_preparacao``, ``min_aquecimento``, ``min_skill``,
``min_apice`` and ``min_volta_a_calma``. Every column is nullable: a treino
without a recorded proportion stays NULL, meaning "sem registro", never a
fabricated default that looks like real data (architecture rule 6). Only
portable SQLAlchemy types are used here (architecture rule 4 — switching to
PostgreSQL must require configuration only).

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("treinos", sa.Column("min_preparacao", sa.Integer(), nullable=True))
    op.add_column("treinos", sa.Column("min_aquecimento", sa.Integer(), nullable=True))
    op.add_column("treinos", sa.Column("min_skill", sa.Integer(), nullable=True))
    op.add_column("treinos", sa.Column("min_apice", sa.Integer(), nullable=True))
    op.add_column("treinos", sa.Column("min_volta_a_calma", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("treinos", "min_volta_a_calma")
    op.drop_column("treinos", "min_apice")
    op.drop_column("treinos", "min_skill")
    op.drop_column("treinos", "min_aquecimento")
    op.drop_column("treinos", "min_preparacao")
