"""Add email to alunos.

Adds an optional email column to kairos.alunos.models.Aluno using only
portable SQLAlchemy types (switching from SQLite to PostgreSQL must require
configuration only). The column is nullable: a student without a recorded
email stays NULL, never a fabricated default that looks like real data.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alunos", sa.Column("email", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("alunos", "email")
