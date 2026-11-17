"""Create the anexos_execucao table.

Mirrors kairos.execucao.models.AnexoExecucao using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
``anexos_execucao`` stores files (image or video) a student attached to a
workout item; several attachments per item are allowed. ``filename`` is the
server-generated name of the locally stored file and ``tipo`` is "imagem" or
"video" (validated at the service layer). ``observacao`` stays nullable: a
field without data is NULL, never a fabricated default (architecture rule 6).

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "anexos_execucao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("treino_item_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["treino_item_id"], ["treino_itens.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_anexos_execucao_treino_item_id"),
        "anexos_execucao",
        ["treino_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_anexos_execucao_treino_item_id"), table_name="anexos_execucao"
    )
    op.drop_table("anexos_execucao")
