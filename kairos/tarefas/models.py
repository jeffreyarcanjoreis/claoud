"""ORM models for the "tarefas" (coach's task list) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

No derived columns are stored here.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Tarefa(Base):
    """A task or reminder for the coach, shown on the Início screen."""

    __tablename__ = "tarefas"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    prazo: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    concluida: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Tarefa(id={self.id!r}, titulo={self.titulo!r}, "
            f"concluida={self.concluida!r})"
        )
