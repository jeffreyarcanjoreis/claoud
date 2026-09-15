"""ORM models for the "acompanhamento" (session actually held) domain.

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class SessaoRealizada(Base):
    """A session that actually happened for a student, on a given date."""

    __tablename__ = "sessoes_realizadas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    presenca: Mapped[str] = mapped_column(String(20), nullable=False)
    disposicao: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"SessaoRealizada(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"data={self.data!r}, presenca={self.presenca!r})"
        )
