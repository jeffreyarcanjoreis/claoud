"""Add feedback_coach column to anexos_execucao.

Adds ``feedback_coach``, the free-text feedback the coach leaves on a student's
attachment. The column is nullable: an attachment without feedback stays NULL,
meaning "sem feedback ainda", never a fabricated default that looks like real
data (architecture rule 6). Only portable SQLAlchemy types are used here
(architecture rule 4 — switching to PostgreSQL must require configuration
only).

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "anexos_execucao", sa.Column("feedback_coach", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("anexos_execucao", "feedback_coach")
