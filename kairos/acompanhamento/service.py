"""Business rules (service layer) for the "acompanhamento" (session actually
held) domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from kairos.db import session_scope
from kairos.acompanhamento.models import SessaoRealizada

logger = logging.getLogger(__name__)

PRESENCA_VALIDAS = ("compareceu", "faltou", "remarcada")
DISPOSICOES_VALIDAS = ("ótima", "boa", "neutra", "baixa", "muito baixa")


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


def _parse_data_required(value: Optional[str]) -> datetime.date:
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


def _parse_presenca_required(value: Optional[str]) -> str:
    """Parse a required presence status, must be one of
    :data:`PRESENCA_VALIDAS`.

    Raises :class:`ValidationError` when missing or not a valid status.
    """
    value = _normalize(value)
    if value is None or value not in PRESENCA_VALIDAS:
        raise ValidationError("Presença inválida.")
    return value


def _parse_disposicao_optional(value: Optional[str]) -> Optional[str]:
    """Parse an optional disposition.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not one of :data:`DISPOSICOES_VALIDAS`.
    """
    value = _normalize(value)
    if value is None:
        return None
    if value not in DISPOSICOES_VALIDAS:
        raise ValidationError("Disposição inválida.")
    return value


def _to_dict(registro: SessaoRealizada) -> Dict[str, Any]:
    """Extract a SessaoRealizada's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": registro.id,
        "aluno_id": registro.aluno_id,
        "data": registro.data,
        "presenca": registro.presenca,
        "disposicao": registro.disposicao,
        "feedback": registro.feedback,
        "created_at": registro.created_at,
    }


def create_sessao_realizada(
    aluno_id: int,
    *,
    data: Optional[str] = None,
    presenca: Optional[str] = None,
    disposicao: Optional[str] = None,
    feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new SessaoRealizada from raw form values and return its
    saved fields.

    Raises :class:`ValidationError` (message in Portuguese) when the input
    is invalid; nothing is persisted in that case.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_data = _parse_data_required(data)
    parsed_presenca = _parse_presenca_required(presenca)
    parsed_disposicao = _parse_disposicao_optional(disposicao)
    parsed_feedback = _normalize(feedback)

    registro = SessaoRealizada(
        aluno_id=aluno_id,
        data=parsed_data,
        presenca=parsed_presenca,
        disposicao=parsed_disposicao,
        feedback=parsed_feedback,
    )

    with session_scope() as session:
        session.add(registro)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(registro)  # loads server-generated values (created_at)
        result = _to_dict(registro)

    logger.info(
        "SessaoRealizada created: id=%s aluno_id=%s", result["id"], result["aluno_id"]
    )
    return result


def list_sessoes_realizadas(aluno_id: int) -> List[Dict[str, Any]]:
    """Return an Aluno's held sessions, most recent first.

    Ordered by data descending, tie-broken by id descending. Primitives are
    extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError). Read-only: no
    log.
    """
    with session_scope() as session:
        query = (
            select(SessaoRealizada)
            .where(SessaoRealizada.aluno_id == aluno_id)
            .order_by(SessaoRealizada.data.desc(), SessaoRealizada.id.desc())
        )
        registros = session.execute(query).scalars().all()
        return [_to_dict(registro) for registro in registros]


def get_sessao_realizada(registro_id: int) -> Optional[Dict[str, Any]]:
    """Return a single SessaoRealizada by primary key as a plain dict, or
    None."""
    with session_scope() as session:
        registro = session.get(SessaoRealizada, registro_id)
        if registro is None:
            return None
        return _to_dict(registro)


def remover_sessao_realizada(registro_id: int) -> bool:
    """Remove a SessaoRealizada by primary key.

    Returns True when the record existed and was removed, False when it did
    not exist.
    """
    with session_scope() as session:
        registro = session.get(SessaoRealizada, registro_id)
        if registro is None:
            return False
        session.delete(registro)
        logger.info("SessaoRealizada removed: id=%s", registro_id)
        return True
