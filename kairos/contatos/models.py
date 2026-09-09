"""ORM models for the "contatos" (lightweight contact follow-up) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

This module is deliberately isolated (rule 1). It started as the coach's
manual tracking of who still needs to be contacted, and now also receives
the full student profile submitted through the native public sign-up form —
including health data (conditions, injuries, medication) — collected under
the person's explicit consent (see the `consentimento` field, which must be
True before health fields are considered legitimate). Records created by the
coach's manual quick-add keep those fields NULL; only the public sign-up
form fills them in (see `origem`).

Hardening data protection (encryption at rest, access control) is deferred
until there is real hosting; today this runs on local SQLite only.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class Contato(Base):
    """A contact gathered either from the coach's manual follow-up list or
    from the native public sign-up form (full student profile, including
    health data, collected under explicit consent)."""

    __tablename__ = "contatos"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    contato: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'a_contatar'")
    )
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sexo: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    objetivo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objetivos_secundarios: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    prazo_desejado: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    frequencia_desejada: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    condicoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lesoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medicamentos: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nivel_condicionamento: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    consentimento: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    origem: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Contato(id={self.id!r}, nome={self.nome!r}, "
            f"status={self.status!r})"
        )
