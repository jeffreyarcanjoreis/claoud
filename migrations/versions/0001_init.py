"""Baseline revision for the Kairos migration pipeline.

This revision creates no schema objects. It exists so that every database
starts its Alembic history from a known revision ("0001"): stamping/upgrading
to it records the version in the database, and every future schema change
chains from here. All real tables arrive in later revisions.

Revision ID: 0001
Revises:
Create Date: 2026-07-20

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
