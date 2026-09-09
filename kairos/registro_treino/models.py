"""ORM models for the "registro_treino" (student post-workout log) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

The allowed range for ``rpe`` (0-10, perceived exertion) and the allowed
set of values for ``sensacao`` are validated at the service layer, not the
database.

Unlike ``checkin``, there is no unique constraint on (aluno_id, data): a
student may log more than one post-workout entry on the same day (e.g. two
sessions, or a correction), so several rows per student per day are valid.

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class RegistroTreino(Base):
    """A single post-workout log entry submitted by a student.

    A student may have several entries for the same date (see module
    docstring); there is no uniqueness constraint on (aluno_id, data).
    """

    __tablename__ = "registros_treino"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    treino_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("treinos.id"), nullable=True
    )
    rpe: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sensacao: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    o_que_mudou: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dor_nova: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"RegistroTreino(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"data={self.data!r})"
        )
