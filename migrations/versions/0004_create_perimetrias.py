"""Create the perimetrias table.

Mirrors kairos.avaliacoes.models.Perimetria using only portable SQLAlchemy
types, so the same migration works on SQLite (MVP) and PostgreSQL later.
Every row must have a value: valor is NOT NULL (a measurement without data
simply does not exist as a row). No derived columns (delta) are stored here.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "perimetrias",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "avaliacao_id",
            sa.Integer(),
            sa.ForeignKey("avaliacoes.id"),
            nullable=False,
        ),
        sa.Column("segmento", sa.String(length=50), nullable=False),
        sa.Column("valor", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "avaliacao_id", "segmento", name="uq_perimetria_avaliacao_segmento"
        ),
    )
    op.create_index(
        "ix_perimetrias_avaliacao_id", "perimetrias", ["avaliacao_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_perimetrias_avaliacao_id", table_name="perimetrias")
    op.drop_table("perimetrias")
