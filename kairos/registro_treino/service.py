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


def _parse_escala_0_10(value: Optional[Any], campo: str) -> Optional[int]:
    """Parse an optional 0-10 scale value.

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
        raise ValidationError(f"{campo} deve ser de 0 a 10.")
    if number < 0 or number > 10:
        raise ValidationError(f"{campo} deve ser de 0 a 10.")
    return number


def _parse_opcao(
    value: Optional[str], opcoes: tuple, erro: str
) -> Optional[str]:
    """Parse an optional value against a fixed set of valid options.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` (with the
    given ``erro`` message) when filled in but not one of ``opcoes``.
    """
    value = _normalize(value)
    if value is None:
        return None
    if value not in opcoes:
        raise ValidationError(erro)
    return value


def _to_dict(r: RegistroTreino) -> Dict[str, Any]:
    """Extract a RegistroTreino's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError). ``treino_nome``
    is not set here — callers that join with Treino (see
    :func:`list_registros` and :func:`get_registro`) add it afterwards.
    """
    return {
        "id": r.id,
        "aluno_id": r.aluno_id,
        "data": r.data,
        "treino_id": r.treino_id,
        "rpe": r.rpe,
        "sensacao": r.sensacao,
        "sensacao_label": SENSACAO_LABELS.get(r.sensacao) if r.sensacao else None,
        "o_que_mudou": r.o_que_mudou,
        "dor_nova": r.dor_nova,
        "created_at": r.created_at,
    }


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
    """Create a new RegistroTreino from raw values and return its saved
    fields.

    ``data`` defaults to today when not given. Raises :class:`ValidationError`
    (message in Portuguese) when the input is invalid; nothing is persisted
    in that case. At least one content field (rpe/sensacao/o_que_mudou/
    dor_nova) must be filled in. An assigned ``treino_id``, when given, must
    belong to the same student, checked inside the session.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_data = data if data is not None else datetime.date.today()
    parsed_rpe = _parse_escala_0_10(rpe, "RPE")
    parsed_sensacao = _parse_opcao(sensacao, SENSACAO_OPCOES, "Sensação inválida.")
    parsed_o_que_mudou = _normalize(o_que_mudou)
    parsed_dor_nova = _normalize(dor_nova)

    if isinstance(treino_id, str):
        treino_id = _normalize(treino_id)
    parsed_treino_id: Optional[int] = None
    if treino_id is not None:
        try:
            parsed_treino_id = int(treino_id)
        except (TypeError, ValueError):
            raise ValidationError("Treino inválido.")

    if all(
        value is None
        for value in (parsed_rpe, parsed_sensacao, parsed_o_que_mudou, parsed_dor_nova)
    ):
        raise ValidationError("Preencha ao menos um campo do registro.")

    with session_scope() as session:
        if parsed_treino_id is not None:
            query = select(Treino).where(
                Treino.id == parsed_treino_id, Treino.aluno_id == aluno_id
            )
            treino = session.execute(query).scalar_one_or_none()
            if treino is None:
                raise ValidationError("Treino inválido.")

        registro = RegistroTreino(
            aluno_id=aluno_id,
            data=parsed_data,
            treino_id=parsed_treino_id,
            rpe=parsed_rpe,
            sensacao=parsed_sensacao,
            o_que_mudou=parsed_o_que_mudou,
            dor_nova=parsed_dor_nova,
        )
        session.add(registro)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(registro)  # loads server-generated values (created_at)
        result = _to_dict(registro)

    logger.info(
        "Registro de treino criado: id=%s aluno_id=%s", result["id"], result["aluno_id"]
    )
    return result


def list_registros(aluno_id: int) -> List[Dict[str, Any]]:
    """Return a student's post-workout logs, most recent first.

    Ordered by data descending, tie-broken by id descending. Each item
    carries the linked workout's name (``treino_nome``), obtained via an
    outer join against Treino. Primitives are extracted while the session is
    still open, so no attribute access happens on detached instances
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
        result = []
        for registro, treino_nome in rows:
            item = _to_dict(registro)
            item["treino_nome"] = treino_nome
            result.append(item)
        return result


def get_registro(registro_id: int) -> Optional[Dict[str, Any]]:
    """Return a single RegistroTreino by primary key as a plain dict, or
    None when there is none.

    The dict carries the linked workout's name (``treino_nome``), obtained
    via an outer join against Treino. Ownership is not checked here — that
    is the caller route's responsibility. Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(RegistroTreino, Treino.nome)
            .outerjoin(Treino, RegistroTreino.treino_id == Treino.id)
            .where(RegistroTreino.id == registro_id)
        )
        row = session.execute(query).one_or_none()
        if row is None:
            return None
        registro, treino_nome = row
        item = _to_dict(registro)
        item["treino_nome"] = treino_nome
        return item
