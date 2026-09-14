"""Add variacao columns to treino_itens.

Adds ``variacao_base``, ``variacao_regressao`` and ``variacao_progressao``,
free-text descriptions the coach writes for a workout item — the base
variation, one step back (regressão) and one step forward (progressão). The
columns are nullable: an item without a described variation stays NULL,
meaning "sem registro", never a fabricated default that looks like real data
(architecture rule 6). Only portable SQLAlchemy types are used here
(architecture rule 4 — switching to PostgreSQL must require configuration
only).

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "treino_itens", sa.Column("variacao_base", sa.Text(), nullable=True)
    )
    op.add_column(
        "treino_itens", sa.Column("variacao_regressao", sa.Text(), nullable=True)
    )
    op.add_column(
        "treino_itens", sa.Column("variacao_progressao", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("treino_itens", "variacao_progressao")
    op.drop_column("treino_itens", "variacao_regressao")
    op.drop_column("treino_itens", "variacao_base")
