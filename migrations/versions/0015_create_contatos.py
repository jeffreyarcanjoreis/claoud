"""Create the contatos table.

Mirrors kairos.contatos.models.Contato using only portable SQLAlchemy types,
so the same migration works on SQLite (MVP) and PostgreSQL later. Optional
fields (contato, observacao) stay nullable: no fabricated defaults. This
table holds no health data — only the coach's manual follow-up of contacts
gathered from the Avaliação Inicial (Initial Assessment); the form answers
themselves stay in Google.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contatos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("contato", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'a_contatar'"),
        ),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("contatos")
