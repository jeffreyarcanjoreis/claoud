"""ORM models for the "avaliacoes" (student assessments) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

Derived values (delta between assessments, BMI) are never stored here: they
are computed on demand from the raw measurements.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Avaliacao(Base):
    """A physical assessment of a student, taken on a given date."""

    __tablename__ = "avaliacoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    peso: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    altura: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    gordura_pct: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 1), nullable=True
    )
    massa_magra: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    massa_gorda: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Avaliacao(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"data={self.data!r})"
        )


class Perimetria(Base):
    """A single body-segment circumference measurement of an Avaliacao.

    One row per measured segment (e.g. "braco", "cintura"); at most one
    measurement per segment per assessment (see __table_args__). No derived
    columns: the delta between assessments is computed on demand.
    """

    __tablename__ = "perimetrias"
    __table_args__ = (
        UniqueConstraint(
            "avaliacao_id", "segmento", name="uq_perimetria_avaliacao_segmento"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    avaliacao_id: Mapped[int] = mapped_column(
        ForeignKey("avaliacoes.id"), nullable=False, index=True
    )
    segmento: Mapped[str] = mapped_column(String(50), nullable=False)
    valor: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"Perimetria(id={self.id!r}, avaliacao_id={self.avaliacao_id!r}, "
            f"segmento={self.segmento!r})"
        )
