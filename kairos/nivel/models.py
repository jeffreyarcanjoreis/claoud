"""ORM models for the "nivel" (student self-recognized level) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

The allowed set of values for ``nivel`` (fundacao/construcao/dominio/
maestria) is validated at the service layer, not the database.

The level is self-recognized by the student (architecture rules 11-14): the
system never grants or ranks a level, it only records what the student
recognized about themselves at that moment. Because of that, there is NO
unique constraint on aluno_id: each row is one recognition in the student's
history, and the current level is simply the most recent row for that
student. Reviewing and changing the recognized level over time is expected,
not an error to be prevented by a constraint.
"""

import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class ReconhecimentoNivel(Base):
    """A single self-recognition of level submitted by a student.

    A student may have several rows over time (see module docstring); there
    is no uniqueness constraint on aluno_id. The most recent row is the
    student's current recognized level.
    """

    __tablename__ = "reconhecimentos_nivel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    nivel: Mapped[str] = mapped_column(String(20), nullable=False)
    nota: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"ReconhecimentoNivel(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"nivel={self.nivel!r})"
        )
