"""ORM models for the "mensagens" (student-coach messaging) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

``autor`` stores who wrote the message ("coach" or "aluno"); validating the
allowed values is a service-layer concern, not a database constraint.

No derived columns are stored here.
"""

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Mensagem(Base):
    """A message exchanged between a student and the coach."""

    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    autor: Mapped[str] = mapped_column(String(10), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    lida: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Mensagem(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"autor={self.autor!r}, lida={self.lida!r})"
        )
