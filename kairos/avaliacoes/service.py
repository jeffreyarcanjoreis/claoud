"""Business rules (service layer) for the "avaliacoes" (student assessments)
domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.

Derived values (delta between assessments, BMI) are computed on demand by
:func:`get_avaliacao_detail` and never persisted (issue 05).
"""

import datetime
import decimal
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select

from kairos.db import session_scope
from kairos.avaliacoes.models import Avaliacao, Perimetria

logger = logging.getLogger(__name__)

_METRIC_FIELDS = ("peso", "altura", "gordura_pct", "massa_magra", "massa_gorda")

PERIMETRIA_SEGMENTOS = [
    ("pescoco", "Pescoço"),
    ("ombros", "Ombros"),
    ("peitoral", "Peitoral"),
    ("cintura", "Cintura"),
    ("abdomen", "Abdómen"),
    ("quadril", "Quadril"),
    ("coxa_d", "Coxa D"),
    ("coxa_e", "Coxa E"),
    ("panturrilha_d", "Panturrilha D"),
    ("panturrilha_e", "Panturrilha E"),
    ("braco_d_relaxado", "Braço D (relaxado)"),
    ("braco_d_contraido", "Braço D (contraído)"),
]


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


def _parse_number(
    value: Optional[str], field_label: str
) -> Optional[decimal.Decimal]:
    """Parse an optional decimal measurement, accepting comma or dot.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when the
    value is not a valid number or is negative. Zero is a valid value.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        number = decimal.Decimal(value.replace(",", "."))
    except decimal.InvalidOperation:
        raise ValidationError(f"{field_label} inválido.")
    if number < 0:
        raise ValidationError(f"{field_label} não pode ser negativo.")
    return number


def _to_dict(avaliacao: Avaliacao) -> Dict[str, Any]:
    """Extract an Avaliacao's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": avaliacao.id,
        "aluno_id": avaliacao.aluno_id,
        "data": avaliacao.data,
        "peso": avaliacao.peso,
        "altura": avaliacao.altura,
        "gordura_pct": avaliacao.gordura_pct,
        "massa_magra": avaliacao.massa_magra,
        "massa_gorda": avaliacao.massa_gorda,
        "created_at": avaliacao.created_at,
    }


def create_avaliacao(
    aluno_id: int,
    *,
    data: Optional[str] = None,
    peso: Optional[str] = None,
    altura: Optional[str] = None,
    gordura_pct: Optional[str] = None,
    massa_magra: Optional[str] = None,
    massa_gorda: Optional[str] = None,
    perimetria: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a new Avaliacao from raw form values and return its saved fields.

    ``perimetria`` is an optional map of segment key -> raw value (comma or
    dot accepted). Only segments listed in :data:`PERIMETRIA_SEGMENTOS` are
    considered; keys outside that list are ignored. A segment left empty
    does not create a row (rule 6: no data means NULL, not a fake zero row).

    Raises :class:`ValidationError` (message in Portuguese) when the input
    is invalid; nothing is persisted in that case — including when a
    perimetria value is invalid or negative, all validation (antropometric
    and perimetria) happens before anything is added to the session, so the
    Avaliacao itself is never partially saved.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    parsed_data = _parse_date_required(data)
    parsed_peso = _parse_number(peso, "Peso")
    parsed_altura = _parse_number(altura, "Altura")
    parsed_gordura_pct = _parse_number(gordura_pct, "% de gordura")
    parsed_massa_magra = _parse_number(massa_magra, "Massa magra")
    parsed_massa_gorda = _parse_number(massa_gorda, "Massa gorda")

    perimetria = perimetria or {}
    parsed_perimetria: List[tuple] = []
    for key, label in PERIMETRIA_SEGMENTOS:
        valor = _parse_number(perimetria.get(key), f"Perímetro {label}")
        if valor is not None:
            parsed_perimetria.append((label, valor))

    avaliacao = Avaliacao(
        aluno_id=aluno_id,
        data=parsed_data,
        peso=parsed_peso,
        altura=parsed_altura,
        gordura_pct=parsed_gordura_pct,
        massa_magra=parsed_massa_magra,
        massa_gorda=parsed_massa_gorda,
    )

    with session_scope() as session:
        session.add(avaliacao)
        session.flush()  # assigns the primary key and applies server defaults
        for label, valor in parsed_perimetria:
            session.add(
                Perimetria(avaliacao_id=avaliacao.id, segmento=label, valor=valor)
            )
        session.refresh(avaliacao)  # loads server-generated values (created_at)
        result = _to_dict(avaliacao)

    logger.info("Avaliacao created: id=%s aluno_id=%s", result["id"], result["aluno_id"])
    return result


def list_avaliacoes(aluno_id: int) -> List[Dict[str, Any]]:
    """Return an Aluno's Avaliacoes in reverse chronological order.

    Ordered by data descending, tie-broken by id descending. Primitives are
    extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError).
    """
    with session_scope() as session:
        query = (
            select(Avaliacao)
            .where(Avaliacao.aluno_id == aluno_id)
            .order_by(Avaliacao.data.desc(), Avaliacao.id.desc())
        )
        avaliacoes = session.execute(query).scalars()
        return [_to_dict(avaliacao) for avaliacao in avaliacoes]


def avaliacao_series(aluno_id: int) -> List[Dict[str, Any]]:
    """Return an Aluno's Avaliacoes as a chronological (ascending) series.

    Ordered by data ascending, tie-broken by id ascending. Each item is
    ``{data, peso, massa_magra, gordura_pct, imc}``: peso, massa_magra and
    gordura_pct are the raw stored value (Decimal) or None when NULL — never
    converted to 0. imc is computed on demand via :func:`_calcular_imc`
    (None when peso or altura is missing), never read from a column.

    Primitives are extracted while the session is still open, so no
    attribute access happens on detached instances (DetachedInstanceError).
    Returns an empty list when the aluno has no avaliacoes. Read-only: no
    log.
    """
    with session_scope() as session:
        query = (
            select(Avaliacao)
            .where(Avaliacao.aluno_id == aluno_id)
            .order_by(Avaliacao.data.asc(), Avaliacao.id.asc())
        )
        avaliacoes = session.execute(query).scalars()
        return [
            {
                "data": avaliacao.data,
                "peso": avaliacao.peso,
                "massa_magra": avaliacao.massa_magra,
                "gordura_pct": avaliacao.gordura_pct,
                "imc": _calcular_imc(avaliacao.peso, avaliacao.altura),
            }
            for avaliacao in avaliacoes
        ]


def get_avaliacao(avaliacao_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Avaliacao by primary key as a plain dict, or None."""
    with session_scope() as session:
        avaliacao = session.get(Avaliacao, avaliacao_id)
        if avaliacao is None:
            return None
        return _to_dict(avaliacao)


def _calcular_imc(
    peso: Optional[decimal.Decimal], altura: Optional[decimal.Decimal]
) -> Optional[decimal.Decimal]:
    """Compute BMI (IMC) from peso (kg) and altura (cm), rounded to 1 decimal.

    Returns None when peso or altura is missing, or when altura is zero
    (would cause a division by zero). Never persisted — always computed on
    demand (architecture rule: derived values are calculated, not stored).
    """
    if peso is None or altura is None:
        return None
    if altura == 0:
        return None
    altura_m = altura / decimal.Decimal(100)
    imc = peso / (altura_m * altura_m)
    return imc.quantize(decimal.Decimal("0.1"), rounding=decimal.ROUND_HALF_UP)


def get_avaliacao_detail(avaliacao_id: int) -> Optional[Dict[str, Any]]:
    """Return an Avaliacao's detail: its fields, per-metric deltas, IMC and
    perimetria (with per-segment delta).

    Deltas and BMI are computed here on demand — never stored (rule of the
    "avaliacoes" domain: derived values live only in this function's
    output). The "previous" assessment of the same student is the one with
    the greatest ``data`` earlier than this one; ties (same ``data``) are
    broken by the smaller ``id`` being considered earlier.

    ``perimetria`` is a list, in canonical order, of ``{segmento, valor,
    delta}`` for each segment measured in this assessment. ``delta`` is the
    current value minus the same segment's value in the previous assessment
    when both exist; None when the segment has no previous measurement or
    there is no previous assessment. Nothing is guessed or invented — only
    segments actually measured in this assessment appear.

    Returns None if ``avaliacao_id`` does not exist. Read-only: no log.
    """
    with session_scope() as session:
        avaliacao = session.get(Avaliacao, avaliacao_id)
        if avaliacao is None:
            return None
        current = _to_dict(avaliacao)

        query = (
            select(Avaliacao)
            .where(
                Avaliacao.aluno_id == current["aluno_id"],
                or_(
                    Avaliacao.data < current["data"],
                    and_(
                        Avaliacao.data == current["data"],
                        Avaliacao.id < current["id"],
                    ),
                ),
            )
            .order_by(Avaliacao.data.desc(), Avaliacao.id.desc())
            .limit(1)
        )
        previous_avaliacao = session.execute(query).scalars().first()
        previous = (
            _to_dict(previous_avaliacao) if previous_avaliacao is not None else None
        )
        previous_id = previous["id"] if previous is not None else None

    deltas: Dict[str, Optional[decimal.Decimal]] = {}
    for field in _METRIC_FIELDS:
        current_value = current[field]
        previous_value = previous[field] if previous is not None else None
        if current_value is not None and previous_value is not None:
            deltas[field] = current_value - previous_value
        else:
            deltas[field] = None

    perim_atual = list_perimetria(current["id"])
    perim_ant = (
        {r["segmento"]: r["valor"] for r in list_perimetria(previous_id)}
        if previous_id is not None
        else {}
    )
    perimetria: List[Dict[str, Any]] = []
    for r in perim_atual:
        seg = r["segmento"]
        val = r["valor"]
        delta = (val - perim_ant[seg]) if seg in perim_ant else None
        perimetria.append({"segmento": seg, "valor": val, "delta": delta})

    return {
        "id": current["id"],
        "aluno_id": current["aluno_id"],
        "data": current["data"],
        "peso": current["peso"],
        "altura": current["altura"],
        "gordura_pct": current["gordura_pct"],
        "massa_magra": current["massa_magra"],
        "massa_gorda": current["massa_gorda"],
        "deltas": deltas,
        "has_previous": previous is not None,
        "imc": _calcular_imc(current["peso"], current["altura"]),
        "perimetria": perimetria,
    }


def list_perimetria(avaliacao_id: int) -> List[Dict[str, Any]]:
    """Return an Avaliacao's perimetria measurements in canonical order.

    Ordered by the segment's position in :data:`PERIMETRIA_SEGMENTOS` (the
    fixed, coach-facing order), not by insertion or id. Primitives are
    extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError). Read-only: no
    log.
    """
    order_index = {label: position for position, (_, label) in enumerate(PERIMETRIA_SEGMENTOS)}

    with session_scope() as session:
        query = select(Perimetria).where(Perimetria.avaliacao_id == avaliacao_id)
        medidas = session.execute(query).scalars()
        result = [
            {"segmento": medida.segmento, "valor": medida.valor} for medida in medidas
        ]

    result.sort(key=lambda item: order_index.get(item["segmento"], len(order_index)))
    return result
