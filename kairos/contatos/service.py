"""Business rules (service layer) for the "contatos" (lightweight contact
follow-up) domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.

Two write paths create a Contato:

- :func:`create_contato` — the coach's manual quick-add (``origem="manual"``),
  keeping the extended profile fields NULL.
- :func:`create_cadastro` — the native public sign-up form (``origem="cadastro"``),
  filling in the full student profile (including health data) under the
  person's explicit consent.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from kairos.contatos.models import Contato
from kairos.db import session_scope

logger = logging.getLogger(__name__)

STATUS_VALIDOS = ("a_contatar", "conversando", "virou_aluno", "sem_interesse")

STATUS_LABELS = {
    "a_contatar": "A contatar",
    "conversando": "Conversando",
    "virou_aluno": "Virou aluno",
    "sem_interesse": "Sem interesse",
}

# Statuses that still need coach attention and show up in the follow-up
# list. The remaining statuses in STATUS_VALIDOS are terminal.
STATUS_ABERTOS = ("a_contatar", "conversando")

NIVEIS_CONDICIONAMENTO = ("sedentario", "iniciante", "intermediario", "avancado")

NIVEL_LABELS = {
    "sedentario": "Sedentário",
    "iniciante": "Iniciante",
    "intermediario": "Intermediário",
    "avancado": "Avançado",
}

SEXO_OPCOES = ("masculino", "feminino", "outro", "nao_informado")

SEXO_LABELS = {
    "masculino": "Masculino",
    "feminino": "Feminino",
    "outro": "Outro",
    "nao_informado": "Prefiro não informar",
}

FREQUENCIA_OPCOES = ("1-2", "3-4", "5+")

FREQUENCIA_LABELS = {
    "1-2": "1 a 2 dias",
    "3-4": "3 a 4 dias",
    "5+": "5+ dias",
}

ORIGEM_LABELS = {
    "cadastro": "Cadastro",
    "manual": "Manual",
}


class ValidationError(Exception):
    """Raised when user-supplied data is invalid.

    The exception message is in Portuguese and ready for display.
    """


class AlunoDuplicado(Exception):
    """Raised by :func:`converter_contato_em_aluno` when an Aluno with the
    same name already exists and the caller did not opt in to force the
    conversion anyway.

    Carries the existing Aluno's id and name so the caller can show a
    confirmation prompt without an extra lookup.
    """

    def __init__(self, aluno_existente_id: int, aluno_existente_nome: str) -> None:
        super().__init__("Já existe um aluno com esse nome.")
        self.aluno_existente_id = aluno_existente_id
        self.aluno_existente_nome = aluno_existente_nome


def _normalize(value: Optional[str]) -> Optional[str]:
    """Strip a raw string; empty or whitespace-only becomes None."""
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _parse_nome_required(value: Optional[str]) -> str:
    """Parse a required name.

    Raises :class:`ValidationError` when missing or blank.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Nome é obrigatório.")
    return value


def _parse_contato_required(value: Optional[str]) -> str:
    """Parse a required contact (e-mail/telefone).

    Raises :class:`ValidationError` when missing or blank.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Contato é obrigatório.")
    return value


def _parse_idade_optional(value: Any) -> Optional[int]:
    """Parse an optional age.

    Empty becomes None. When present, must be an integer between 1 and 120
    (inclusive); otherwise raises :class:`ValidationError`.
    """
    if isinstance(value, str):
        value = _normalize(value)
    if value is None:
        return None
    try:
        idade = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Idade inválida.")
    if idade <= 0 or idade > 120:
        raise ValidationError("Idade inválida.")
    return idade


def _parse_opcao_optional(
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


def _to_dict(c: Contato) -> Dict[str, Any]:
    """Extract a Contato's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": c.id,
        "nome": c.nome,
        "contato": c.contato,
        "status": c.status,
        "observacao": c.observacao,
        "idade": c.idade,
        "sexo": c.sexo,
        "objetivo": c.objetivo,
        "objetivos_secundarios": c.objetivos_secundarios,
        "prazo_desejado": c.prazo_desejado,
        "frequencia_desejada": c.frequencia_desejada,
        "condicoes": c.condicoes,
        "lesoes": c.lesoes,
        "medicamentos": c.medicamentos,
        "nivel_condicionamento": c.nivel_condicionamento,
        "consentimento": c.consentimento,
        "origem": c.origem,
        "created_at": c.created_at,
    }


def create_contato(
    *,
    nome: Optional[str] = None,
    contato: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Contato from raw form values and return its saved
    fields.

    This is the coach's manual quick-add path (``origem="manual"``); the
    extended profile fields are left NULL.

    Raises :class:`ValidationError` (message in Portuguese) when the input
    is invalid; nothing is persisted in that case. Status is not accepted
    here: it is born from the column's server default ("a_contatar").
    """
    parsed_nome = _parse_nome_required(nome)
    parsed_contato = _normalize(contato)
    parsed_observacao = _normalize(observacao)

    c = Contato(
        nome=parsed_nome,
        contato=parsed_contato,
        observacao=parsed_observacao,
        origem="manual",
    )

    with session_scope() as session:
        session.add(c)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(c)  # loads server-generated values (created_at, status)
        result = _to_dict(c)

    logger.info("Contato created: id=%s", result["id"])
    return result


def create_cadastro(
    *,
    nome: Optional[str] = None,
    contato: Optional[str] = None,
    idade: Any = None,
    sexo: Optional[str] = None,
    objetivo: Optional[str] = None,
    objetivos_secundarios: Optional[str] = None,
    prazo_desejado: Optional[str] = None,
    frequencia_desejada: Optional[str] = None,
    condicoes: Optional[str] = None,
    lesoes: Optional[str] = None,
    medicamentos: Optional[str] = None,
    nivel_condicionamento: Optional[str] = None,
    consentimento: bool = False,
) -> Dict[str, Any]:
    """Create a new Contato from the native public sign-up form (full
    student profile, including health data) and return its saved fields.

    This is the public sign-up path (``origem="cadastro"``). Nome and
    contato are required; consentimento must be True (architecture rule 6 —
    health data is only legitimate under explicit consent). Raises
    :class:`ValidationError` (message in Portuguese) when the input is
    invalid; nothing is persisted in that case.
    """
    parsed_nome = _parse_nome_required(nome)
    parsed_contato = _parse_contato_required(contato)

    if consentimento is not True:
        raise ValidationError(
            "É preciso autorizar o uso dos dados para enviar o cadastro."
        )

    parsed_idade = _parse_idade_optional(idade)
    parsed_sexo = _parse_opcao_optional(sexo, SEXO_OPCOES, "Sexo inválido.")
    parsed_nivel = _parse_opcao_optional(
        nivel_condicionamento,
        NIVEIS_CONDICIONAMENTO,
        "Nível de condicionamento inválido.",
    )
    parsed_frequencia = _parse_opcao_optional(
        frequencia_desejada, FREQUENCIA_OPCOES, "Frequência desejada inválida."
    )

    parsed_objetivo = _normalize(objetivo)
    parsed_objetivos_secundarios = _normalize(objetivos_secundarios)
    parsed_prazo_desejado = _normalize(prazo_desejado)
    parsed_condicoes = _normalize(condicoes)
    parsed_lesoes = _normalize(lesoes)
    parsed_medicamentos = _normalize(medicamentos)

    c = Contato(
        nome=parsed_nome,
        contato=parsed_contato,
        idade=parsed_idade,
        sexo=parsed_sexo,
        objetivo=parsed_objetivo,
        objetivos_secundarios=parsed_objetivos_secundarios,
        prazo_desejado=parsed_prazo_desejado,
        frequencia_desejada=parsed_frequencia,
        condicoes=parsed_condicoes,
        lesoes=parsed_lesoes,
        medicamentos=parsed_medicamentos,
        nivel_condicionamento=parsed_nivel,
        consentimento=True,
        origem="cadastro",
    )

    with session_scope() as session:
        session.add(c)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(c)  # loads server-generated values (created_at, status)
        result = _to_dict(c)

    logger.info("Contato (cadastro) created: id=%s", result["id"])
    return result


def list_contatos_abertos() -> List[Dict[str, Any]]:
    """Return contacts still awaiting follow-up (status in
    :data:`STATUS_ABERTOS`), most recently created first.

    Ordered by created_at descending, tie-broken by id descending.
    Primitives are extracted while the session is still open, so no
    attribute access happens on detached instances
    (DetachedInstanceError). Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(Contato)
            .where(Contato.status.in_(STATUS_ABERTOS))
            .order_by(Contato.created_at.desc(), Contato.id.desc())
        )
        contatos = session.execute(query).scalars().all()
        return [_to_dict(c) for c in contatos]


def get_contato(contato_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Contato by primary key as a plain dict, or None."""
    with session_scope() as session:
        c = session.get(Contato, contato_id)
        if c is None:
            return None
        return _to_dict(c)


def get_contato_detail(contato_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Contato by primary key as a plain dict, including
    Portuguese display labels for its coded fields, or None.

    Adds ``status_label``, ``sexo_label``, ``nivel_label``,
    ``frequencia_label`` and ``origem_label`` on top of the fields returned
    by :func:`get_contato`; every label is None when the underlying coded
    field is None. Read-only: no log.
    """
    with session_scope() as session:
        c = session.get(Contato, contato_id)
        if c is None:
            return None
        data = _to_dict(c)
        data["status_label"] = STATUS_LABELS.get(c.status)
        data["sexo_label"] = SEXO_LABELS.get(c.sexo) if c.sexo else None
        data["nivel_label"] = (
            NIVEL_LABELS.get(c.nivel_condicionamento)
            if c.nivel_condicionamento
            else None
        )
        data["frequencia_label"] = (
            FREQUENCIA_LABELS.get(c.frequencia_desejada)
            if c.frequencia_desejada
            else None
        )
        data["origem_label"] = ORIGEM_LABELS.get(c.origem) if c.origem else None
        return data


def atualizar_status(contato_id: int, status: Optional[str]) -> bool:
    """Update a Contato's status.

    Raises :class:`ValidationError` (message in Portuguese) when status is
    not one of :data:`STATUS_VALIDOS`. Returns True when the record existed
    and was updated, False when it did not exist.
    """
    if status not in STATUS_VALIDOS:
        raise ValidationError("Status inválido.")

    with session_scope() as session:
        c = session.get(Contato, contato_id)
        if c is None:
            return False
        c.status = status
        logger.info("Contato status updated: id=%s status=%s", contato_id, status)
        return True


def remover_contato(contato_id: int) -> bool:
    """Remove a Contato by primary key.

    Returns True when the record existed and was removed, False when it did
    not exist.
    """
    with session_scope() as session:
        c = session.get(Contato, contato_id)
        if c is None:
            return False
        session.delete(c)
        logger.info("Contato removed: id=%s", contato_id)
        return True


def converter_contato_em_aluno(
    contato_id: int, force: bool = False
) -> Optional[int]:
    """Convert a Contato (lead) into an Aluno (student).

    Imported locally (not at module top) so the dependency direction —
    contatos depends on alunos, never the other way around — stays explicit
    and no import cycle can appear between the two domains.

    Fields with a dedicated Aluno column are mapped directly; the rest
    (objetivos_secundarios, prazo_desejado, observacao) have no matching
    column, so they are folded into the Aluno's free-text notes, one line
    per value that is actually present (architecture rule 6 — nothing
    invented), plus a line recording the conversion date.

    Returns None when the Contato does not exist. Unless ``force`` is True,
    raises :class:`AlunoDuplicado` when an Aluno with the same name already
    exists, before anything is created — this lets the caller ask the coach
    to confirm before creating a second record for the same person. Marks
    the Contato's status as "virou_aluno" after the Aluno is created.
    Returns the new Aluno's id.
    """
    from kairos.alunos.service import create_aluno, find_aluno_by_name

    contato = get_contato(contato_id)
    if contato is None:
        return None

    if not force:
        aluno_existente = find_aluno_by_name(contato["nome"])
        if aluno_existente is not None:
            raise AlunoDuplicado(
                aluno_existente_id=aluno_existente["id"],
                aluno_existente_nome=aluno_existente["name"],
            )

    notes_lines: List[str] = []
    if contato["objetivos_secundarios"]:
        notes_lines.append(
            "Objetivos secundários: " + contato["objetivos_secundarios"]
        )
    if contato["prazo_desejado"]:
        notes_lines.append("Prazo desejado: " + contato["prazo_desejado"])
    if contato["observacao"]:
        notes_lines.append("Observação: " + contato["observacao"])
    notes_lines.append(
        "Criado a partir do cadastro em "
        + datetime.date.today().strftime("%d/%m/%Y")
    )
    notes = "\n".join(notes_lines)

    idade = contato["idade"]
    age_reported = str(idade) if idade is not None else None

    # Only treat the contact as an e-mail when it looks like one (contains
    # "@" and no whitespace); a phone number must never be guessed into an
    # e-mail (architecture rule 6 — nothing invented).
    contato_valor = contato["contato"]
    email = (
        contato_valor
        if contato_valor and "@" in contato_valor and " " not in contato_valor
        else None
    )

    aluno = create_aluno(
        name=contato["nome"],
        contact=contato["contato"],
        email=email,
        sex=contato["sexo"],
        age_reported=age_reported,
        objective=contato["objetivo"],
        weekly_frequency=contato["frequencia_desejada"],
        conditioning_level=contato["nivel_condicionamento"],
        restrictions=contato["lesoes"],
        health_conditions=contato["condicoes"],
        medications=contato["medicamentos"],
        notes=notes,
        status="active",
    )

    atualizar_status(contato_id, "virou_aluno")

    logger.info(
        "Contato converted to aluno: contato_id=%s aluno_id=%s",
        contato_id,
        aluno["id"],
    )
    return aluno["id"]
