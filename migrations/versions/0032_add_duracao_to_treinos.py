"""Add the duracao_min column to treinos.

Adds ``duracao_min``, the optional duration (in minutes) of a workout session.
The column is nullable: a treino without a recorded duration stays NULL,
meaning "sem registro", never a fabricated default that looks like real data
(architecture rule 6). Only portable SQLAlchemy types are used here
(architecture rule 4 — switching to PostgreSQL must require configuration
only).

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("treinos", sa.Column("duracao_min", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("treinos", "duracao_min")
