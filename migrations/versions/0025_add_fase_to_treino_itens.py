"""Add the fase column to treino_itens.

Adds ``fase``, the phase of the session in the method (Preparacao,
Aquecimento, Skill, Apice, Volta a calma). The allowed set of values is
validated at the service layer, not the database (architecture rule 4 —
only portable SQLAlchemy types here). The column is nullable: an item
without a phase assigned stays NULL, meaning "sem fase", never a fabricated
default that looks like real data (architecture rule 6).

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("treino_itens", sa.Column("fase", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("treino_itens", "fase")
