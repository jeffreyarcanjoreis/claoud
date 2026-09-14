"""Add the video_filename column to exercicios.

Adds ``video_filename``, the on-disk name of the exercise's optional
demonstration video (uploaded and stored locally, same pattern as student
photos). The column is nullable: an exercise without a video stays NULL,
meaning "sem registro", never a fabricated default that looks like real
data (architecture rule 6). Only portable SQLAlchemy types are used here
(architecture rule 4 — switching to PostgreSQL must require configuration
only).

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exercicios", sa.Column("video_filename", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("exercicios", "video_filename")
