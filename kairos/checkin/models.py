"""ORM models for the "checkin" (student daily check-in) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

Allowed values for ``sono_qualidade`` (ruim/regular/boa/otima) and ``humor``
(muito_baixo/baixo/neutro/bom/otimo), as well as the 0-24 range for
``sono_horas`` and the 0-10 ranges for ``estresse``, ``energia`` and
``dor_intensidade``, are validated at the service layer, not the database.

No derived columns are stored here.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class CheckinDiario(Base):
    """A single day's check-in submitted by a student.

    At most one check-in per student per date (see __table_args__).
    """

    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("aluno_id", "data", name="uq_checkins_aluno_data"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id"), nullable=False, index=True
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sono_horas: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 1), nullable=True
    )
    sono_qualidade: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    estresse: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    energia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    humor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    dor_local: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dor_intensidade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"CheckinDiario(id={self.id!r}, aluno_id={self.aluno_id!r}, "
            f"data={self.data!r})"
        )
