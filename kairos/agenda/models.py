"""ORM models for the "agenda" (scheduled sessions) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

No derived columns are stored here.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class SessaoAgendada(Base):
    """A session scheduled for a student, on a given date and time."""

    __tablename__ = "sessoes_agendadas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    hora: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    duracao_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Optional link to the workout assigned to this day (rule 6: NULL when unset).
    treino_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("treinos.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"SessaoAgendada(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"data={self.data!r}, hora={self.hora!r})"
        )
