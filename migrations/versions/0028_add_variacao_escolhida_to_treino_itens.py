"""Add variacao_escolhida to treino_itens.

Adds ``variacao_escolhida``, the single current self-chosen variation for a
workout item — "base", "regressao" or "progressao" — recognized by the
student, not graded by the coach (architecture rules 11-14). The column is
nullable: an item without a choice stays NULL, meaning "ainda não me
reconheci", never a fabricated default that looks like real data
(architecture rule 6). Only a portable SQLAlchemy type is used here
(architecture rule 4 — switching to PostgreSQL must require configuration
only).

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "treino_itens",
        sa.Column("variacao_escolhida", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("treino_itens", "variacao_escolhida")
