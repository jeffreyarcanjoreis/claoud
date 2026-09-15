"""Business rules (service layer) for the "alunos" (students) domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from kairos.db import session_scope
from kairos.alunos.models import Aluno
from kairos.avaliacoes.models import Avaliacao
from kairos.treinos.models import Treino
from kairos.agenda.models import SessaoAgendada
from kairos.acompanhamento.models import SessaoRealizada
from kairos.financeiro.models import PlanoAluno, Pagamento

logger = logging.getLogger(__name__)

VALID_STATUSES = ("active", "inactive")

# Kept independent from kairos.contatos (same option sets, duplicated on
# purpose) so this module never imports from kairos.contatos and no import
# cycle can appear between the two domains.
SEX_OPCOES = ("masculino", "feminino", "outro", "nao_informado")

SEX_LABELS = {
    "masculino": "Masculino",
    "feminino": "Feminino",
    "outro": "Outro",
    "nao_informado": "Prefiro não informar",
}

CONDITIONING_LEVELS = ("sedentario", "iniciante", "intermediario", "avancado")

CONDITIONING_LABELS = {
    "sedentario": "Sedentário",
    "iniciante": "Iniciante",
    "intermediario": "Intermediário",
    "avancado": "Avançado",
}

WEEKLY_FREQUENCIES = ("1-2", "3-4", "5+")

WEEKLY_FREQUENCY_LABELS = {
    "1-2": "1 a 2 dias",
    "3-4": "3 a 4 dias",
    "5+": "5+ dias",
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


def _normalize_email(value: Optional[str]) -> Optional[str]:
    """Strip and lowercase a raw e-mail string; empty or whitespace-only
    becomes None.

    Lowercasing keeps the matching deterministic (see
    :func:`find_alunos_by_email`).
    """
    if value is None:
        return None
    value = value.strip()
    return value.lower() if value else None


def _parse_date(value: Optional[str], error_message: str) -> Optional[datetime.date]:
    """Parse an ISO "YYYY-MM-DD" string into a date, or raise ValidationError."""
    value = _normalize(value)
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(error_message)


def _age_from(birth_date: Optional[datetime.date]) -> Optional[int]:
    """Return the age in full years as of today, or None when birth_date is None.

    A birthday that has not happened yet this year counts one year less.
    """
    if birth_date is None:
        return None
    today = datetime.date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _parse_age_reported(value: Optional[str]) -> Optional[int]:
    """Parse an optional self-reported age.

    Empty becomes None. When present, must be an integer between 1 and 120
    (inclusive); otherwise raises :class:`ValidationError`.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        age = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Idade inválida.")
    if age <= 0 or age > 120:
        raise ValidationError("Idade inválida.")
    return age


def _parse_opcao(
    value: Optional[str], opcoes: tuple, erro: str
) -> Optional[str]:
    """Parse an optional value constrained to a fixed set of options.

    Empty becomes None. When present, must be one of ``opcoes``; otherwise
    raises :class:`ValidationError` with the given ``erro`` message.
    """
    value = _normalize(value)
    if value is None:
        return None
    if value not in opcoes:
        raise ValidationError(erro)
    return value


def _to_dict(aluno: Aluno) -> Dict[str, Any]:
    """Extract an Aluno's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError). Includes the
    derived "age" key computed from birth_date.
    """
    return {
        "id": aluno.id,
        "name": aluno.name,
        "birth_date": aluno.birth_date,
        "objective": aluno.objective,
        "phase": aluno.phase,
        "plan_start": aluno.plan_start,
        "plan_end": aluno.plan_end,
        "restrictions": aluno.restrictions,
        "alert": aluno.alert,
        "status": aluno.status,
        "notes": aluno.notes,
        "foto": aluno.foto,
        "created_at": aluno.created_at,
        "age": _age_from(aluno.birth_date),
        "contact": aluno.contact,
        "sex": aluno.sex,
        "sex_label": SEX_LABELS.get(aluno.sex) if aluno.sex else None,
        "age_reported": aluno.age_reported,
        "weekly_frequency": aluno.weekly_frequency,
        "weekly_frequency_label": (
            WEEKLY_FREQUENCY_LABELS.get(aluno.weekly_frequency)
            if aluno.weekly_frequency
            else None
        ),
        "conditioning_level": aluno.conditioning_level,
        "conditioning_label": (
            CONDITIONING_LABELS.get(aluno.conditioning_level)
            if aluno.conditioning_level
            else None
        ),
        "health_conditions": aluno.health_conditions,
        "medications": aluno.medications,
        "email": aluno.email,
    }


def _clean_fields(
    *,
    name: Optional[str],
    birth_date: Optional[str] = None,
    objective: Optional[str] = None,
    phase: Optional[str] = None,
    plan_start: Optional[str] = None,
    plan_end: Optional[str] = None,
    restrictions: Optional[str] = None,
    alert: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    contact: Optional[str] = None,
    sex: Optional[str] = None,
    age_reported: Optional[str] = None,
    weekly_frequency: Optional[str] = None,
    conditioning_level: Optional[str] = None,
    health_conditions: Optional[str] = None,
    medications: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize and validate raw form values shared by create and update.

    Empty strings become None, dates are parsed from ISO format, status
    falls back to "active" when absent. Raises :class:`ValidationError`
    (message in Portuguese, ready for display) when the input is invalid.
    """
    name = _normalize(name)
    if name is None:
        raise ValidationError("Nome é obrigatório.")

    parsed_birth_date = _parse_date(birth_date, "Data de nascimento inválida.")
    parsed_plan_start = _parse_date(plan_start, "Data de início do plano inválida.")
    parsed_plan_end = _parse_date(plan_end, "Data de término do plano inválida.")

    if (
        parsed_plan_start is not None
        and parsed_plan_end is not None
        and parsed_plan_end < parsed_plan_start
    ):
        raise ValidationError("Término do plano não pode ser anterior ao início.")

    status = _normalize(status)
    if status is None:
        status = "active"
    elif status not in VALID_STATUSES:
        raise ValidationError("Status inválido.")

    parsed_sex = _parse_opcao(sex, SEX_OPCOES, "Sexo inválido.")
    parsed_age_reported = _parse_age_reported(age_reported)
    parsed_weekly_frequency = _parse_opcao(
        weekly_frequency, WEEKLY_FREQUENCIES, "Frequência inválida."
    )
    parsed_conditioning_level = _parse_opcao(
        conditioning_level,
        CONDITIONING_LEVELS,
        "Nível de condicionamento inválido.",
    )

    return {
        "name": name,
        "birth_date": parsed_birth_date,
        "objective": _normalize(objective),
        "phase": _normalize(phase),
        "plan_start": parsed_plan_start,
        "plan_end": parsed_plan_end,
        "restrictions": _normalize(restrictions),
        "alert": _normalize(alert),
        "status": status,
        "notes": _normalize(notes),
        "contact": _normalize(contact),
        "sex": parsed_sex,
        "age_reported": parsed_age_reported,
        "weekly_frequency": parsed_weekly_frequency,
        "conditioning_level": parsed_conditioning_level,
        "health_conditions": _normalize(health_conditions),
        "medications": _normalize(medications),
        "email": _normalize_email(email),
    }


def create_aluno(
    *,
    name: Optional[str],
    birth_date: Optional[str] = None,
    objective: Optional[str] = None,
    phase: Optional[str] = None,
    plan_start: Optional[str] = None,
    plan_end: Optional[str] = None,
    restrictions: Optional[str] = None,
    alert: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    contact: Optional[str] = None,
    sex: Optional[str] = None,
    age_reported: Optional[str] = None,
    weekly_frequency: Optional[str] = None,
    conditioning_level: Optional[str] = None,
    health_conditions: Optional[str] = None,
    medications: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Aluno from raw form values and return its saved fields.

    Raises :class:`ValidationError` (message in Portuguese) when the input
    is invalid.
    """
    fields = _clean_fields(
        name=name,
        birth_date=birth_date,
        objective=objective,
        phase=phase,
        plan_start=plan_start,
        plan_end=plan_end,
        restrictions=restrictions,
        alert=alert,
        status=status,
        notes=notes,
        contact=contact,
        sex=sex,
        age_reported=age_reported,
        weekly_frequency=weekly_frequency,
        conditioning_level=conditioning_level,
        health_conditions=health_conditions,
        medications=medications,
        email=email,
    )

    aluno = Aluno(**fields)

    with session_scope() as session:
        session.add(aluno)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(aluno)  # loads server-generated values (created_at)
        result = _to_dict(aluno)

    logger.info("Aluno created: id=%s name=%s", result["id"], result["name"])
    return result


def update_aluno(
    aluno_id: int,
    *,
    name: Optional[str] = None,
    birth_date: Optional[str] = None,
    objective: Optional[str] = None,
    phase: Optional[str] = None,
    plan_start: Optional[str] = None,
    plan_end: Optional[str] = None,
    restrictions: Optional[str] = None,
    alert: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    contact: Optional[str] = None,
    sex: Optional[str] = None,
    age_reported: Optional[str] = None,
    weekly_frequency: Optional[str] = None,
    conditioning_level: Optional[str] = None,
    health_conditions: Optional[str] = None,
    medications: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Replace an existing Aluno's fields with raw form values.

    The edit form always submits the full profile, so this is a total
    replacement of the fields (not a partial patch), using the same
    normalization/validation as :func:`create_aluno`. Returns None when
    ``aluno_id`` does not exist. Raises :class:`ValidationError` (message in
    Portuguese) when the input is invalid.
    """
    fields = _clean_fields(
        name=name,
        birth_date=birth_date,
        objective=objective,
        phase=phase,
        plan_start=plan_start,
        plan_end=plan_end,
        restrictions=restrictions,
        alert=alert,
        status=status,
        notes=notes,
        contact=contact,
        sex=sex,
        age_reported=age_reported,
        weekly_frequency=weekly_frequency,
        conditioning_level=conditioning_level,
        health_conditions=health_conditions,
        medications=medications,
        email=email,
    )

    with session_scope() as session:
        aluno = session.get(Aluno, aluno_id)
        if aluno is None:
            return None
        for field, value in fields.items():
            setattr(aluno, field, value)
        session.flush()
        session.refresh(aluno)
        result = _to_dict(aluno)

    logger.info("Aluno updated: id=%s name=%s", result["id"], result["name"])
    return result


def list_alunos(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return Alunos ordered by name (case-insensitive) as plain dicts.

    When ``status`` is "active" or "inactive", only Alunos with that status
    are returned (filtered in the query). Any other value, including None,
    returns all Alunos — unknown filter values are ignored defensively.
    Each dict carries the same fields returned by :func:`create_aluno`.
    Primitives are extracted while the session is still open, so no attribute
    access happens on detached instances (DetachedInstanceError).
    """
    with session_scope() as session:
        query = select(Aluno).order_by(func.lower(Aluno.name))
        if status in VALID_STATUSES:
            query = query.where(Aluno.status == status)
        alunos = session.execute(query).scalars()
        return [_to_dict(aluno) for aluno in alunos]


def get_aluno(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Aluno by primary key as a plain dict, or None.

    The dict carries the same fields returned by :func:`create_aluno` and
    :func:`list_alunos`, including the derived "age" key.
    """
    with session_scope() as session:
        aluno = session.get(Aluno, aluno_id)
        if aluno is None:
            return None
        return _to_dict(aluno)


def count_alunos() -> Dict[str, int]:
    """Return the total number of Alunos and how many are active.

    Counts are computed by the database (no rows are loaded into memory).
    """
    with session_scope() as session:
        total = session.execute(select(func.count()).select_from(Aluno)).scalar_one()
        active = session.execute(
            select(func.count()).select_from(Aluno).where(Aluno.status == "active")
        ).scalar_one()
        return {"total": total, "active": active}


def set_aluno_foto(aluno_id: int, filename: Optional[str]) -> Optional[Dict[str, Any]]:
    """Set (or clear, with ``None``) the stored photo filename for an Aluno.

    Returns the updated Aluno as a dict, or None when ``aluno_id`` does not
    exist. Does not touch the file on disk; callers are responsible for
    saving/deleting the actual file (see :mod:`kairos.alunos.fotos`).
    """
    with session_scope() as session:
        aluno = session.get(Aluno, aluno_id)
        if aluno is None:
            return None
        aluno.foto = filename
        session.flush()
        session.refresh(aluno)
        result = _to_dict(aluno)

    logger.info("Aluno foto set: id=%s filename=%s", result["id"], filename)
    return result


def find_aluno_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Return the first Aluno whose name matches ``name``, or None.

    The comparison is case-insensitive. When ``name`` normalizes to None
    (empty or whitespace-only), the database is not queried and None is
    returned. The dict carries the same fields returned by
    :func:`create_aluno` and :func:`list_alunos`, including the derived
    "age" key.
    """
    name = _normalize(name)
    if name is None:
        return None

    with session_scope() as session:
        query = select(Aluno).where(func.lower(Aluno.name) == name.lower())
        aluno = session.execute(query).scalars().first()
        if aluno is None:
            return None
        return _to_dict(aluno)


def find_alunos_by_email(email: str) -> List[Dict[str, Any]]:
    """Return the active Alunos whose e-mail matches ``email``.

    The comparison is case-insensitive. Returns a list (not a single match)
    so callers can detect ambiguity when more than one active Aluno shares
    the same e-mail. When ``email`` normalizes to None (empty or
    whitespace-only), the database is not queried and an empty list is
    returned. Each dict carries the same fields returned by
    :func:`create_aluno` and :func:`list_alunos`. Read-only: no log.
    """
    normalized = _normalize_email(email)
    if normalized is None:
        return []

    with session_scope() as session:
        query = select(Aluno).where(
            Aluno.status == "active", func.lower(Aluno.email) == normalized
        )
        alunos = session.execute(query).scalars().all()
        return [_to_dict(aluno) for aluno in alunos]


def set_status(aluno_id: int, status: Optional[str]) -> Optional[Dict[str, Any]]:
    """Set an Aluno's status.

    Raises :class:`ValidationError` (message in Portuguese) when ``status``
    is not one of :data:`VALID_STATUSES`. Returns None when ``aluno_id``
    does not exist, otherwise the updated Aluno as a dict.
    """
    if status not in VALID_STATUSES:
        raise ValidationError("Status inválido.")

    with session_scope() as session:
        aluno = session.get(Aluno, aluno_id)
        if aluno is None:
            return None
        aluno.status = status
        session.flush()
        session.refresh(aluno)
        result = _to_dict(aluno)

    logger.info("Aluno status updated: id=%s status=%s", result["id"], status)
    return result


def arquivar_aluno(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Set an Aluno's status to "inactive" (archive). See :func:`set_status`."""
    return set_status(aluno_id, "inactive")


def reativar_aluno(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Set an Aluno's status to "active" (reactivate). See :func:`set_status`."""
    return set_status(aluno_id, "active")


def aluno_tem_historico(aluno_id: int) -> bool:
    """Return True when the Aluno has any dependent row in another domain.

    Checked tables: avaliacoes, treinos, sessoes_agendadas,
    sessoes_realizadas, planos_aluno and pagamentos (all foreign-keyed on
    aluno_id). Read-only: no log. Used to protect against silently losing
    data when deleting an Aluno (see :func:`excluir_aluno`).
    """
    with session_scope() as session:
        counts = [
            session.execute(
                select(func.count())
                .select_from(model)
                .where(model.aluno_id == aluno_id)
            ).scalar_one()
            for model in (
                Avaliacao,
                Treino,
                SessaoAgendada,
                SessaoRealizada,
                PlanoAluno,
                Pagamento,
            )
        ]
        return sum(counts) > 0


def excluir_aluno(aluno_id: int) -> str:
    """Permanently delete an Aluno, refusing when it would silently lose data.

    Returns one of:

    - ``"nao_encontrado"``: no Aluno with ``aluno_id`` exists.
    - ``"tem_historico"``: the Aluno has dependent rows in another domain
      (avaliações, treinos, sessões, planos ou pagamentos); nothing is
      deleted, protecting against data loss (architecture rule 6).
    - ``"ok"``: the Aluno row was deleted (and its photo file, if any, is
      removed from disk after the commit succeeds).
    """
    if get_aluno(aluno_id) is None:
        return "nao_encontrado"

    if aluno_tem_historico(aluno_id):
        return "tem_historico"

    with session_scope() as session:
        aluno = session.get(Aluno, aluno_id)
        if aluno is None:
            return "nao_encontrado"
        foto = aluno.foto
        session.delete(aluno)

    # Only remove the photo file after the row deletion has committed
    # successfully, so a failed commit never leaves an orphaned Aluno
    # pointing at a missing file.
    if foto:
        from kairos.alunos.fotos import delete_foto_file

        delete_foto_file(foto)

    logger.info("Aluno deleted: id=%s", aluno_id)
    return "ok"
