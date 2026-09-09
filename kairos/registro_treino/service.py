"""Business rules (service layer) for the "registro_treino" (student
post-workout log) domain.

Receives raw values (strings, numbers or None), normalizes and validates
them (architecture rule 6: empty means NULL, never a silent fake default),
and persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown (architecture rule 10); code and identifiers
stay in English.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from kairos.db import session_scope
from kairos.registro_treino.models import RegistroTreino
from kairos.treinos.models import Treino

logger = logging.getLogger(__name__)

SENSACAO_OPCOES = ("pessima", "ruim", "ok", "boa", "otima")
SENSACAO_LABELS = {
    "pessima": "Péssima",
    "ruim": "Ruim",
    "ok": "Ok",
    "boa": "Boa",
    "otima": "Ótima",
}


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


def _parse_rpe(value: Optional[Any]) -> Optional[int]:
    """Parse an optional RPE (perceived exertion) value, 0-10.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not a valid integer between 0 and 10 (inclusive).
    """
    if isinstance(value, str):
        value = _normalize(value)
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError("RPE deve ser de 0 a 10.")
    if number < 0 or number > 10:
        raise ValidationError("RPE deve ser de 0 a 10.")
    return number


def _parse_sensacao(value: Optional[str]) -> Optional[str]:
    """Parse an optional overall feeling ("sensação") against the fixed set
    of valid options.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not one of :data:`SENSACAO_OPCOES`.
    """
    value = _normalize(value)
    if value is None:
        return None
    if value not in SENSACAO_OPCOES:
        raise ValidationError("Sensação inválida.")
    return value


def _to_dict(
    r: RegistroTreino, treino_nome: Optional[str] = None
) -> Dict[str, Any]:
    """Extract a RegistroTreino's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": r.id,
        "aluno_id": r.aluno_id,
        "data": r.data,
        "treino_id": r.treino_id,
        "treino_nome": treino_nome,
        "rpe": r.rpe,
        "sensacao": r.sensacao,
        "sensacao_label": SENSACAO_LABELS.get(r.sensacao) if r.sensacao else None,
        "o_que_mudou": r.o_que_mudou,
        "dor_nova": r.dor_nova,
        "created_at": r.created_at,
    }


def _parse_treino_id(value: Optional[Any]) -> Optional[int]:
    """Parse an optional treino id, accepting int or numeric string.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not a valid integer.
    """
    if isinstance(value, str):
        value = _normalize(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError("Treino inválido.")


def registrar(
    aluno_id: int,
    *,
    data: Optional[datetime.date] = None,
    treino_id: Optional[Any] = None,
    rpe: Optional[Any] = None,
    sensacao: Optional[str] = None,
    o_que_mudou: Optional[str] = None,
    dor_nova: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new post-workout log entry for a student.

    Raw values are normalized and validated before anything touches the
    database; when invalid, :class:`ValidationError` (message in Portuguese)
    is raised and nothing is persisted. At least one of rpe, sensacao,
    o_que_mudou or dor_nova must be filled in, otherwise
    :class:`ValidationError` is raised (treino_id and data do not count as
    content).

    Unlike checkin, this is never an upsert: a student may log more than one
    entry for the same date, and a new RegistroTreino row is always created.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    if data is None:
        data = datetime.date.today()

    parsed_treino_id = _parse_treino_id(treino_id)
    parsed_rpe = _parse_rpe(rpe)
    parsed_sensacao = _parse_sensacao(sensacao)
    parsed_o_que_mudou = _normalize(o_que_mudou)
    parsed_dor_nova = _normalize(dor_nova)

    if all(
        value is None
        for value in (
            parsed_rpe,
            parsed_sensacao,
            parsed_o_que_mudou,
            parsed_dor_nova,
        )
    ):
        raise ValidationError("Preencha ao menos um campo do registro.")

    with session_scope() as session:
        treino = None
        if parsed_treino_id is not None:
            query = select(Treino).where(Treino.id == parsed_treino_id)
            treino = session.execute(query).scalar_one_or_none()
            if treino is None or treino.aluno_id != aluno_id:
                raise ValidationError("Treino inválido.")

        registro = RegistroTreino(
            aluno_id=aluno_id,
            data=data,
            treino_id=parsed_treino_id,
            rpe=parsed_rpe,
            sensacao=parsed_sensacao,
            o_que_mudou=parsed_o_que_mudou,
            dor_nova=parsed_dor_nova,
        )
        session.add(registro)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(registro)  # loads server-generated values (created_at)
        treino_nome = treino.nome if treino is not None else None
        result = _to_dict(registro, treino_nome)

    logger.info(
        "Registro de treino criado: aluno_id=%s data=%s", aluno_id, data
    )
    return result


def list_registros(aluno_id: int) -> List[Dict[str, Any]]:
    """Return a student's post-workout log history, most recent date first.

    Ordered by data descending, tie-broken by id descending. Includes the
    linked workout's name (treino_nome), when there is one, via an outer
    join (treino_id is optional). Primitives are extracted while the session
    is still open, so no attribute access happens on detached instances
    (DetachedInstanceError). Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(RegistroTreino, Treino.nome)
            .outerjoin(Treino, RegistroTreino.treino_id == Treino.id)
            .where(RegistroTreino.aluno_id == aluno_id)
            .order_by(RegistroTreino.data.desc(), RegistroTreino.id.desc())
        )
        rows = session.execute(query).all()
        return [_to_dict(registro, treino_nome) for registro, treino_nome in rows]


def get_registro(registro_id: int) -> Optional[Dict[str, Any]]:
    """Return a single RegistroTreino by primary key as a plain dict, or
    None when there is none.

    Includes the linked workout's name (treino_nome) via an outer join. The
    ownership check (whether this registro belongs to the requesting
    student) is the caller route's responsibility. Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(RegistroTreino, Treino.nome)
            .outerjoin(Treino, RegistroTreino.treino_id == Treino.id)
            .where(RegistroTreino.id == registro_id)
        )
        row = session.execute(query).first()
        if row is None:
            return None
        registro, treino_nome = row
        return _to_dict(registro, treino_nome)
