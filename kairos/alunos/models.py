"""ORM models for the "alunos" (students) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).
"""

import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Aluno(Base):
    """A student coached through the Kairos system."""

    __tablename__ = "alunos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phase: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    plan_start: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    plan_end: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alert: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    age_reported: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weekly_frequency: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    conditioning_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    health_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    foto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"Aluno(id={self.id!r}, name={self.name!r}, status={self.status!r})"
