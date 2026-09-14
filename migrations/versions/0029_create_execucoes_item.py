"""Create the execucoes_item table.

Mirrors kairos.execucao.models.ExecucaoItem using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
``execucoes_item`` stores one execution log entry per workout item per date
(grain enforced by the unique constraint on (treino_item_id, data)):
registering again on the same day is an upsert done at the service layer,
never a new row; different dates produce different rows, which is how the
history of an exercise is built. Every field besides ``treino_item_id``,
``data`` and ``feito`` stays nullable, since a field without data is NULL,
never a fabricated default (architecture rule 6). ``feito`` has no
server-side default: it is always set explicitly by the service.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execucoes_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("treino_item_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("feito", sa.Boolean(), nullable=False),
        sa.Column("carga_real", sa.String(length=40), nullable=True),
        sa.Column("reps_real", sa.String(length=40), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["treino_item_id"], ["treino_itens.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "treino_item_id", "data", name="uq_execucao_item_data"
        ),
    )
    op.create_index(
        op.f("ix_execucoes_item_treino_item_id"),
        "execucoes_item",
        ["treino_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_execucoes_item_treino_item_id"), table_name="execucoes_item"
    )
    op.drop_table("execucoes_item")
