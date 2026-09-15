"""Business rules (service layer) for the "agenda" (scheduled sessions)
domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.

``create_sessao``/``cancel_sessao`` are the natural hook points for a future
Google Calendar sync (an isolated ``agenda/sync.py``); this module does not
know about Google — the database stays the source of truth.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from kairos.db import session_scope
from kairos.agenda.models import SessaoAgendada
from kairos.alunos.models import Aluno
from kairos.treinos.models import Treino

logger = logging.getLogger(__name__)

TIPOS_VALIDOS = ("individual", "grupo")


class ValidationError(Exception):
    """Raised when user-supplied data is invalid.

    The exception message is in Portuguese and ready for display.
    """


def _normalize(value: Optional[str]) -> Optional[str]:
    """Strip a raw string; empty or whitespace-only becomes None."""
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _parse_date_required(value: Optional[str]) -> datetime.date:
    """Parse a required ISO "YYYY-MM-DD" string into a date.

    Raises :class:`ValidationError` when the value is missing or invalid.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Data é obrigatória.")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Data inválida.")


def _parse_time_required(value: Optional[str]) -> datetime.time:
    """Parse a required "HH:MM" (or ISO) string into a time.

    Raises :class:`ValidationError` when the value is missing or invalid.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Hora é obrigatória.")
    try:
        return datetime.time.fromisoformat(value)
    except ValueError:
        raise ValidationError("Hora inválida.")


def _parse_duracao(value: Optional[str]) -> Optional[int]:
    """Parse an optional duration (minutes).

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when the
    value is not a valid integer or is not positive.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        duracao = int(value)
    except ValueError:
        raise ValidationError("Duração inválida.")
    if duracao <= 0:
        raise ValidationError("Duração deve ser positiva.")
    return duracao


def _parse_treino_id_optional(value: Optional[str]) -> Optional[int]:
    """Parse an optional workout id: empty -> None, else an integer.

    Ownership (the treino belongs to the same student) is checked later, inside
    the database session. Raises :class:`ValidationError` on a non-integer.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValidationError("Treino inválido.")


def _parse_tipo(value: Optional[str]) -> str:
    """Parse a required session type, must be one of :data:`TIPOS_VALIDOS`.

    Raises :class:`ValidationError` when missing or not a valid type.
    """
    value = _normalize(value)
    if value is None or value not in TIPOS_VALIDOS:
        raise ValidationError("Tipo inválido.")
    return value


def _to_dict(sessao: SessaoAgendada) -> Dict[str, Any]:
    """Extract a SessaoAgendada's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": sessao.id,
        "aluno_id": sessao.aluno_id,
        "data": sessao.data,
        "hora": sessao.hora,
        "duracao_min": sessao.duracao_min,
        "tipo": sessao.tipo,
        "observacao": sessao.observacao,
        "treino_id": sessao.treino_id,
        "created_at": sessao.created_at,
    }


def create_sessao(
    aluno_id: int,
    *,
    data: Optional[str] = None,
    hora: Optional[str] = None,
    tipo: Optional[str] = None,
    duracao_min: Optional[str] = None,
    observacao: Optional[str] = None,
    treino_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new SessaoAgendada from raw form values and return its saved
    fields.

    Raises :class:`ValidationError` (message in Portuguese) when the input
    is invalid; nothing is persisted in that case. An assigned ``treino_id``,
    when given, must belong to the same student, checked inside the session.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_data = _parse_date_required(data)
    parsed_hora = _parse_time_required(hora)
    parsed_tipo = _parse_tipo(tipo)
    parsed_duracao = _parse_duracao(duracao_min)
    parsed_observacao = _normalize(observacao)
    parsed_treino_id = _parse_treino_id_optional(treino_id)

    sessao = SessaoAgendada(
        aluno_id=aluno_id,
        data=parsed_data,
        hora=parsed_hora,
        duracao_min=parsed_duracao,
        tipo=parsed_tipo,
        observacao=parsed_observacao,
        treino_id=parsed_treino_id,
    )

    with session_scope() as session:
        if parsed_treino_id is not None:
            treino = session.get(Treino, parsed_treino_id)
            if treino is None or treino.aluno_id != aluno_id:
                raise ValidationError("Treino inválido.")
        session.add(sessao)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(sessao)  # loads server-generated values (created_at)
        result = _to_dict(sessao)
        aluno = session.get(Aluno, aluno_id)
        aluno_nome = aluno.name if aluno else None

    logger.info(
        "SessaoAgendada created: id=%s aluno_id=%s", result["id"], result["aluno_id"]
    )

    if aluno_nome:
        from kairos.tarefas.service import create_tarefa

        try:
            prazo = (parsed_data + datetime.timedelta(days=1)).isoformat()
            create_tarefa(
                titulo=f"Contatar {aluno_nome}", categoria="contato", prazo=prazo
            )
        except Exception as exc:
            logger.warning("Falha ao criar tarefa de contato pós-treino: %s", exc)

    return result


def list_sessoes(aluno_id: int) -> List[Dict[str, Any]]:
    """Return an Aluno's scheduled sessions in chronological (ascending)
    order.

    Ordered by data ascending, hora ascending, tie-broken by id ascending.
    Primitives are extracted while the session is still open, so no
    attribute access happens on detached instances (DetachedInstanceError).
    Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(SessaoAgendada, Treino.nome)
            .outerjoin(Treino, SessaoAgendada.treino_id == Treino.id)
            .where(SessaoAgendada.aluno_id == aluno_id)
            .order_by(
                SessaoAgendada.data.asc(),
                SessaoAgendada.hora.asc(),
                SessaoAgendada.id.asc(),
            )
        )
        rows = session.execute(query).all()
        result = []
        for sessao, treino_nome in rows:
            item = _to_dict(sessao)
            item["treino_nome"] = treino_nome
            result.append(item)
        return result


def get_sessao(sessao_id: int) -> Optional[Dict[str, Any]]:
    """Return a single SessaoAgendada by primary key as a plain dict, or
    None."""
    with session_scope() as session:
        sessao = session.get(SessaoAgendada, sessao_id)
        if sessao is None:
            return None
        return _to_dict(sessao)


def cancel_sessao(sessao_id: int) -> bool:
    """Cancel (remove) a SessaoAgendada by primary key.

    Returns True when the session existed and was removed, False when it
    did not exist.
    """
    with session_scope() as session:
        sessao = session.get(SessaoAgendada, sessao_id)
        if sessao is None:
            return False
        session.delete(sessao)
        logger.info("SessaoAgendada cancelled: id=%s", sessao_id)
        return True


def sessoes_de_hoje() -> List[Dict[str, Any]]:
    """Return today's scheduled sessions across all students.

    Ordered by hora ascending, tie-broken by id ascending. Each item carries
    the student's name alongside the session's primitive fields. Primitives
    are extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError). Read-only: no
    log.
    """
    with session_scope() as session:
        query = (
            select(SessaoAgendada, Aluno.name, Treino.nome)
            .join(Aluno, SessaoAgendada.aluno_id == Aluno.id)
            .outerjoin(Treino, SessaoAgendada.treino_id == Treino.id)
            .where(SessaoAgendada.data == datetime.date.today())
            .order_by(SessaoAgendada.hora.asc(), SessaoAgendada.id.asc())
        )
        rows = session.execute(query).all()
        return [
            {
                "aluno_id": sessao.aluno_id,
                "aluno_nome": aluno_name,
                "hora": sessao.hora,
                "tipo": sessao.tipo,
                "treino_id": sessao.treino_id,
                "treino_nome": treino_nome,
            }
            for sessao, aluno_name, treino_nome in rows
        ]


def contar_sessoes_de_hoje() -> int:
    """Return how many sessions are scheduled for today, across all
    students.

    Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(func.count())
            .select_from(SessaoAgendada)
            .where(SessaoAgendada.data == datetime.date.today())
        )
        return session.execute(query).scalar()
