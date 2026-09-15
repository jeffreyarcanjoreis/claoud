"""Add the foto column to alunos.

Mirrors kairos.alunos.models.Aluno's new "foto" field: the file name of the
student's photo, nullable. No value means no photo (architecture rule 6),
never a fabricated default. Uses batch mode on downgrade for portability
with SQLite, which does not support a plain DROP COLUMN on older versions.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alunos", sa.Column("foto", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.drop_column("foto")
