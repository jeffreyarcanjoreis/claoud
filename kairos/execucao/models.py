"""ORM models for the "execucao" (per-exercise execution log) domain.

Only portable SQLAlchemy types are used (architecture rule 4: switching from
SQLite to PostgreSQL must require configuration only). Optional fields are
truly nullable: a field without data is NULL in the database (rule 6 — data
is never invented by silent defaults that look like real data).

The grain is one row per workout item per date: a student marking/registering
an exercise again on the same day updates that day's row (upsert, done at the
service layer); different dates produce different rows, which is how the
history of an exercise is built over time. The unique constraint on
(treino_item_id, data) enforces this grain at the database level.

``feito`` has no server-side default: whether the student marked the item as
done is decided explicitly by the service, never fabricated by the database.
"""

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kairos.db import Base


class ExecucaoItem(Base):
    """One execution log entry for a workout item, on a single date.

    A student has at most one row per (treino_item_id, data): registering
    again on the same day updates the existing row instead of creating a
    new one (see module docstring); the history across dates is the
    sequence of rows for the same treino_item_id.
    """

    __tablename__ = "execucoes_item"
    __table_args__ = (
        UniqueConstraint("treino_item_id", "data", name="uq_execucao_item_data"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    treino_item_id: Mapped[int] = mapped_column(
        ForeignKey("treino_itens.id"), nullable=False, index=True
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    feito: Mapped[bool] = mapped_column(Boolean, nullable=False)
    carga_real: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    reps_real: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"ExecucaoItem(id={self.id!r}, treino_item_id={self.treino_item_id!r}, "
            f"data={self.data!r})"
        )
