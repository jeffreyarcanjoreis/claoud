"""Add the frente column to alunos.

Adds ``frente``, the student's main frente in the method (Performance,
Saude Integrada, or Longevidade). The allowed set of values is validated
at the service layer, not the database (architecture rule 4 — only
portable SQLAlchemy types here). The column is nullable: a student
without a frente assigned stays NULL, meaning "sem registro", never a
fabricated default that looks like real data (architecture rule 6).

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alunos", sa.Column("frente", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("alunos", "frente")
