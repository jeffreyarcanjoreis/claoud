"""ORM models for the "financeiro" (student plan & value) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data). No derived
values (e.g. accrued revenue) are stored here.
"""

import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class PlanoAluno(Base):
    """The plan and monetary value of a single student.

    At most one plan per student (see aluno_id unique constraint).
    """

    __tablename__ = "planos_aluno"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alunos.id"), nullable=False, unique=True
    )
    formato: Mapped[str] = mapped_column(String(20), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ciclo_meses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inicio: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"PlanoAluno(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"formato={self.formato!r})"
        )


class Pagamento(Base):
    """A single monthly payment received from a student.

    At most one payment per student per competence (year/month), see the
    aluno_id/ano/mes unique constraint.
    """

    __tablename__ = "pagamentos"
    __table_args__ = (
        UniqueConstraint(
            "aluno_id", "ano", "mes", name="uq_pagamentos_aluno_competencia"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alunos.id"), nullable=False
    )
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    data_pagamento: Mapped[Optional[datetime.date]] = mapped_column(
        Date, nullable=True
    )
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Pagamento(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"ano={self.ano!r}, mes={self.mes!r})"
        )


class Despesa(Base):
    """A single business expense (not tied to a specific student)."""

    __tablename__ = "despesas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Despesa(id={self.id!r}, data={self.data!r}, "
            f"descricao={self.descricao!r})"
        )
