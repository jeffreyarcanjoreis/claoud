"""Business rules (service layer) for the "checkin" (student daily
check-in) domain.

Receives raw values (strings, numbers or None), normalizes and validates
them (architecture rule 6: empty means NULL, never a silent fake default),
and persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown (architecture rule 10); code and identifiers
stay in English.
"""

import datetime
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from kairos.db import session_scope
from kairos.checkin.models import CheckinDiario

logger = logging.getLogger(__name__)

QUALIDADE_SONO_OPCOES = ("ruim", "regular", "boa", "otima")
QUALIDADE_SONO_LABELS = {
    "ruim": "Ruim",
    "regular": "Regular",
    "boa": "Boa",
    "otima": "Ótima",
}

HUMOR_OPCOES = ("muito_baixo", "baixo", "neutro", "bom", "otimo")
HUMOR_LABELS = {
    "muito_baixo": "Muito baixo",
    "baixo": "Baixo",
    "neutro": "Neutro",
    "bom": "Bom",
    "otimo": "Ótimo",
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


def _parse_sono_horas(value: Optional[Any]) -> Optional[Decimal]:
    """Parse an optional sleep duration, in hours (accepting comma or dot).

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not a valid number between 0 and 24 (inclusive).
    """
    if isinstance(value, str):
        value = _normalize(value)
    if value is None:
        return None
    try:
        if isinstance(value, str):
            number = Decimal(value.replace(",", "."))
        else:
            number = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError("Horas de sono inválidas.")
    if number < 0 or number > 24:
        raise ValidationError("Horas de sono inválidas.")
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


def _to_dict(c: CheckinDiario) -> Dict[str, Any]:
    """Extract a CheckinDiario's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": c.id,
        "aluno_id": c.aluno_id,
        "data": c.data,
        "sono_horas": c.sono_horas,
        "sono_qualidade": c.sono_qualidade,
        "sono_qualidade_label": QUALIDADE_SONO_LABELS.get(c.sono_qualidade)
        if c.sono_qualidade
        else None,
        "estresse": c.estresse,
        "energia": c.energia,
        "humor": c.humor,
        "humor_label": HUMOR_LABELS.get(c.humor) if c.humor else None,
        "dor_local": c.dor_local,
        "dor_intensidade": c.dor_intensidade,
        "observacao": c.observacao,
        "created_at": c.created_at,
    }


def registrar_checkin(
    aluno_id: int,
    data: datetime.date,
    *,
    sono_horas: Optional[Any] = None,
    sono_qualidade: Optional[str] = None,
    estresse: Optional[Any] = None,
    energia: Optional[Any] = None,
    humor: Optional[str] = None,
    dor_local: Optional[str] = None,
    dor_intensidade: Optional[Any] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update (upsert) a student's check-in for a given date.

    Raw values are normalized and validated before anything touches the
    database; when invalid, :class:`ValidationError` (message in Portuguese)
    is raised and nothing is persisted. At least one field must be filled in,
    otherwise :class:`ValidationError` is raised.

    At most one CheckinDiario exists per (aluno_id, data) — see the unique
    constraint. When one already exists it is fully replaced with the given
    fields; otherwise a new one is created.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_sono_horas = _parse_sono_horas(sono_horas)
    parsed_sono_qualidade = _parse_opcao(
        sono_qualidade, QUALIDADE_SONO_OPCOES, "Qualidade do sono inválida."
    )
    parsed_estresse = _parse_escala_0_10(estresse, "Estresse")
    parsed_energia = _parse_escala_0_10(energia, "Energia")
    parsed_humor = _parse_opcao(humor, HUMOR_OPCOES, "Humor inválido.")
    parsed_dor_local = _normalize(dor_local)
    parsed_dor_intensidade = _parse_escala_0_10(
        dor_intensidade, "Intensidade da dor"
    )
    parsed_observacao = _normalize(observacao)

    if all(
        value is None
        for value in (
            parsed_sono_horas,
            parsed_sono_qualidade,
            parsed_estresse,
            parsed_energia,
            parsed_humor,
            parsed_dor_local,
            parsed_dor_intensidade,
            parsed_observacao,
        )
    ):
        raise ValidationError("Preencha ao menos um campo do check-in.")

    with session_scope() as session:
        query = select(CheckinDiario).where(
            CheckinDiario.aluno_id == aluno_id, CheckinDiario.data == data
        )
        checkin = session.execute(query).scalar_one_or_none()

        if checkin is None:
            checkin = CheckinDiario(aluno_id=aluno_id, data=data)
            session.add(checkin)

        checkin.sono_horas = parsed_sono_horas
        checkin.sono_qualidade = parsed_sono_qualidade
        checkin.estresse = parsed_estresse
        checkin.energia = parsed_energia
        checkin.humor = parsed_humor
        checkin.dor_local = parsed_dor_local
        checkin.dor_intensidade = parsed_dor_intensidade
        checkin.observacao = parsed_observacao

        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(checkin)  # loads server-generated values (created_at)
        result = _to_dict(checkin)

    logger.info("Checkin registrado: aluno_id=%s data=%s", aluno_id, data)
    return result


def get_checkin(aluno_id: int, data: datetime.date) -> Optional[Dict[str, Any]]:
    """Return a student's check-in for a given date as a plain dict, or None
    when there is none.

    Read-only: no log.
    """
    with session_scope() as session:
        query = select(CheckinDiario).where(
            CheckinDiario.aluno_id == aluno_id, CheckinDiario.data == data
        )
        checkin = session.execute(query).scalar_one_or_none()
        if checkin is None:
            return None
        return _to_dict(checkin)


def checkin_de_hoje(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Return a student's check-in for today as a plain dict, or None when
    there is none.

    Read-only: no log.
    """
    return get_checkin(aluno_id, datetime.date.today())


def list_checkins(aluno_id: int) -> List[Dict[str, Any]]:
    """Return a student's check-in history, most recent date first.

    Ordered by data descending, tie-broken by id descending. Primitives are
    extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError). Read-only: no
    log.
    """
    with session_scope() as session:
        query = (
            select(CheckinDiario)
            .where(CheckinDiario.aluno_id == aluno_id)
            .order_by(CheckinDiario.data.desc(), CheckinDiario.id.desc())
        )
        checkins = session.execute(query).scalars().all()
        return [_to_dict(c) for c in checkins]
