"""Expand contatos with the full student profile from public sign-up.

Adds the fields collected by the native public sign-up form to the existing
contatos table (issue 22), including health data (condicoes, lesoes,
medicamentos) gathered under explicit consent (consentimento). Mirrors
kairos.contatos.models.Contato using only portable SQLAlchemy types, so the
same migration works on SQLite (MVP) and PostgreSQL later. All new columns
are nullable: records created by the coach's manual quick-add leave them
NULL, no fabricated defaults (except consentimento, which defaults to False
for existing rows — absence of consent, never invented consent).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contatos", sa.Column("idade", sa.Integer(), nullable=True))
    op.add_column(
        "contatos", sa.Column("sexo", sa.String(length=30), nullable=True)
    )
    op.add_column("contatos", sa.Column("objetivo", sa.Text(), nullable=True))
    op.add_column(
        "contatos", sa.Column("objetivos_secundarios", sa.Text(), nullable=True)
    )
    op.add_column(
        "contatos",
        sa.Column("prazo_desejado", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "contatos",
        sa.Column("frequencia_desejada", sa.String(length=20), nullable=True),
    )
    op.add_column("contatos", sa.Column("condicoes", sa.Text(), nullable=True))
    op.add_column("contatos", sa.Column("lesoes", sa.Text(), nullable=True))
    op.add_column(
        "contatos", sa.Column("medicamentos", sa.Text(), nullable=True)
    )
    op.add_column(
        "contatos",
        sa.Column(
            "nivel_condicionamento", sa.String(length=20), nullable=True
        ),
    )
    op.add_column(
        "contatos",
        sa.Column(
            "consentimento",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "contatos", sa.Column("origem", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("contatos") as batch_op:
        batch_op.drop_column("origem")
        batch_op.drop_column("consentimento")
        batch_op.drop_column("nivel_condicionamento")
        batch_op.drop_column("medicamentos")
        batch_op.drop_column("lesoes")
        batch_op.drop_column("condicoes")
        batch_op.drop_column("frequencia_desejada")
        batch_op.drop_column("prazo_desejado")
        batch_op.drop_column("objetivos_secundarios")
        batch_op.drop_column("objetivo")
        batch_op.drop_column("sexo")
        batch_op.drop_column("idade")
