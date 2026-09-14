"""Business rules (service layer) for the "execucao" (per-exercise student
execution log) domain.

Receives raw values (strings, numbers or None), normalizes them (architecture
rule 6: empty means NULL, never a silent fake default), and persists through
:func:`kairos.db.session_scope`. Error messages are in Portuguese, ready to be
shown (architecture rule 10); code and identifiers stay in English.

The grain is one row per (treino_item_id, data): registering again on the
same day updates that day's row (upsert); different dates produce different
rows, which is how the history of an exercise is built over time (see
:mod:`kairos.execucao.models`).

:class:`ValidationError` is reused from :mod:`kairos.treinos.service` so the
workout domain keeps a single exception type, instead of one per module.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from kairos.db import session_scope
from kairos.execucao.models import ExecucaoItem
from kairos.treinos.models import TreinoItem
from kairos.treinos.service import ValidationError

logger = logging.getLogger(__name__)


def _normalize(value: Optional[str]) -> Optional[str]:
    """Strip a raw string; empty or whitespace-only becomes None."""
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _to_dict(execucao: ExecucaoItem) -> Dict[str, Any]:
    """Extract an ExecucaoItem's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": execucao.id,
        "treino_item_id": execucao.treino_item_id,
        "data": execucao.data,
        "feito": execucao.feito,
        "carga_real": execucao.carga_real,
        "reps_real": execucao.reps_real,
        "observacao": execucao.observacao,
        "created_at": execucao.created_at,
    }


def registrar_execucao(
    treino_item_id: int,
    *,
    feito: Optional[Any] = None,
    carga_real: Optional[str] = None,
    reps_real: Optional[str] = None,
    observacao: Optional[str] = None,
    data: Optional[datetime.date] = None,
) -> Dict[str, Any]:
    """Register (create or update) a student's execution of a workout item.

    ``data`` defaults to today. Raw values are normalized before anything
    touches the database (rule 6: empty means NULL); ``feito`` is coerced to
    a plain bool. Raises :class:`ValidationError` when ``treino_item_id``
    does not exist — nothing is persisted in that case.

    Upsert by (treino_item_id, data): registering again on the same day
    updates the existing row instead of creating a new one; different dates
    produce different rows (history, see :func:`list_execucoes`).
    """
    if data is None:
        data = datetime.date.today()

    parsed_feito = bool(feito)
    parsed_carga_real = _normalize(carga_real)
    parsed_reps_real = _normalize(reps_real)
    parsed_observacao = _normalize(observacao)

    with session_scope() as session:
        if session.get(TreinoItem, treino_item_id) is None:
            raise ValidationError("Exercício não encontrado.")

        query = select(ExecucaoItem).where(
            ExecucaoItem.treino_item_id == treino_item_id,
            ExecucaoItem.data == data,
        )
        execucao = session.execute(query).scalar_one_or_none()

        if execucao is None:
            execucao = ExecucaoItem(
                treino_item_id=treino_item_id,
                data=data,
                feito=parsed_feito,
                carga_real=parsed_carga_real,
                reps_real=parsed_reps_real,
                observacao=parsed_observacao,
            )
            session.add(execucao)
        else:
            execucao.feito = parsed_feito
            execucao.carga_real = parsed_carga_real
            execucao.reps_real = parsed_reps_real
            execucao.observacao = parsed_observacao

        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(execucao)  # loads server-generated values (created_at)
        result = _to_dict(execucao)

    logger.info(
        "Execução registrada: treino_item_id=%s data=%s feito=%s",
        treino_item_id,
        data,
        parsed_feito,
    )
    return result


def get_execucao(
    treino_item_id: int, data: Optional[datetime.date] = None
) -> Optional[Dict[str, Any]]:
    """Return the execution of a workout item on a given date (default
    today), or None when there is no record for that day. Read-only: no log.
    """
    if data is None:
        data = datetime.date.today()

    with session_scope() as session:
        query = select(ExecucaoItem).where(
            ExecucaoItem.treino_item_id == treino_item_id,
            ExecucaoItem.data == data,
        )
        execucao = session.execute(query).scalar_one_or_none()
        if execucao is None:
            return None
        return _to_dict(execucao)


def list_execucoes(treino_item_id: int) -> List[Dict[str, Any]]:
    """Return a workout item's execution history, most recent date first.

    Ordered by data descending, tie-broken by id descending. Read-only: no
    log.
    """
    with session_scope() as session:
        query = (
            select(ExecucaoItem)
            .where(ExecucaoItem.treino_item_id == treino_item_id)
            .order_by(ExecucaoItem.data.desc(), ExecucaoItem.id.desc())
        )
        rows = session.execute(query).scalars().all()
        return [_to_dict(execucao) for execucao in rows]


def execucoes_do_treino(
    treino_id: int, data: Optional[datetime.date] = None
) -> Dict[int, Dict[str, Any]]:
    """Return a map of treino_item_id -> execution dict for a given date
    (default today), covering every item of the given treino that has an
    execution recorded on that date. Read-only: no log.
    """
    if data is None:
        data = datetime.date.today()

    with session_scope() as session:
        query = (
            select(ExecucaoItem)
            .join(TreinoItem, ExecucaoItem.treino_item_id == TreinoItem.id)
            .where(TreinoItem.treino_id == treino_id, ExecucaoItem.data == data)
        )
        rows = session.execute(query).scalars().all()
        return {execucao.treino_item_id: _to_dict(execucao) for execucao in rows}


def progresso_sessao(
    treino_id: int, data: Optional[datetime.date] = None
) -> Dict[str, int]:
    """Return ``{"total": n, "feitos": n}`` for a treino on a given date
    (default today): total items in the treino, and how many of them have an
    execution marked as feito on that date. A treino without items returns
    ``{"total": 0, "feitos": 0}``. Read-only: no log.
    """
    if data is None:
        data = datetime.date.today()

    with session_scope() as session:
        total = session.execute(
            select(func.count(TreinoItem.id)).where(TreinoItem.treino_id == treino_id)
        ).scalar_one()

        feitos = session.execute(
            select(func.count(ExecucaoItem.id))
            .join(TreinoItem, ExecucaoItem.treino_item_id == TreinoItem.id)
            .where(
                TreinoItem.treino_id == treino_id,
                ExecucaoItem.data == data,
                ExecucaoItem.feito.is_(True),
            )
        ).scalar_one()

        return {"total": total, "feitos": feitos}
