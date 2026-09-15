"""Create the mensagens table.

Mirrors kairos.mensagens.models.Mensagem using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
``mensagens`` stores messages exchanged between a student and the coach;
``autor`` holds "coach" or "aluno" (validated at the service layer, not the
database). ``lida`` defaults to false at the database level, not to a
fabricated "read" state. No derived columns are stored here.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mensagens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "aluno_id",
            sa.Integer(),
            sa.ForeignKey("alunos.id"),
            nullable=False,
        ),
        sa.Column("autor", sa.String(length=10), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column(
            "lida", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mensagens_aluno_id"), "mensagens", ["aluno_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mensagens_aluno_id"), table_name="mensagens")
    op.drop_table("mensagens")
