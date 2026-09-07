"""ORM models for the "treinos" domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data is
never invented by silent defaults that look like real data).

No derived columns are stored here.
"""

import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Exercicio(Base):
    """One exercise in the shared library (biblioteca de exercícios)."""

    __tablename__ = "exercicios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    grupo_muscular: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"Exercicio(id={self.id!r}, nome={self.nome!r})"


class Treino(Base):
    """A named workout (planilha) belonging to a student."""

    __tablename__ = "treinos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"Treino(id={self.id!r}, aluno_id={self.aluno_id!r}, nome={self.nome!r})"


class TreinoItem(Base):
    """One exercise inside a Treino, with optional séries/reps/carga.

    References an Exercicio from the library; the optional prescription fields
    stay nullable (rule 6 — no fabricated defaults).
    """

    __tablename__ = "treino_itens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    treino_id: Mapped[int] = mapped_column(
        ForeignKey("treinos.id"), nullable=False, index=True
    )
    exercicio_id: Mapped[int] = mapped_column(
        ForeignKey("exercicios.id"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    series: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reps: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    carga: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"TreinoItem(id={self.id!r}, treino_id={self.treino_id!r}, "
            f"exercicio_id={self.exercicio_id!r})"
        )
