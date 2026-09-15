"""ORM models for the "auth" (login) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

``perfis`` maps a Supabase Auth user to their role inside Kairos. It does not
store a password: the password lives in Supabase Auth, outside this
database. ``aluno_id`` links a "aluno" profile to its Aluno record; it stays
NULL for a "coach" profile (and for a "aluno" profile until Fase 2 wires the
account to a student).
"""

import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Perfil(Base):
    """A Supabase Auth user mapped to a Kairos role ("coach" or "aluno")."""

    __tablename__ = "perfis"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    papel: Mapped[str] = mapped_column(String(20), nullable=False)
    aluno_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("alunos.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Perfil(id={self.id!r}, user_id={self.user_id!r}, "
            f"papel={self.papel!r})"
        )
