"""Business rules (service layer) for the "nivel" (student self-recognized
level) domain.

Receives raw values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown (architecture rule 10); code and identifiers
stay in English.

The level is self-recognized by the student (architecture rules 11-14): this
module never grants, ranks or upgrades a level on its own. It only records
what the student recognized about themselves at a given moment, always as a
new row (never an upsert), so the full history is preserved and reviewable.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from kairos.db import session_scope
from kairos.nivel.models import ReconhecimentoNivel

logger = logging.getLogger(__name__)

NIVEL_OPCOES = ("fundacao", "construcao", "dominio", "maestria")

NIVEL_LABELS = {
    "fundacao": "I · Fundação",
    "construcao": "II · Construção",
    "dominio": "III · Domínio",
    "maestria": "IV · Maestria",
}

NIVEL_DESCRICOES = {
    "fundacao": "Aprendo a sentir, domino o simples.",
    "construcao": "Amplio a capacidade, com domínio crescente.",
    "dominio": "Tenho autonomia, refino, encaro desafios reais.",
    "maestria": "Alta capacidade e autorregulação — quase me conduzo.",
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


def _to_dict(r: ReconhecimentoNivel) -> Dict[str, Any]:
    """Extract a ReconhecimentoNivel's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": r.id,
        "aluno_id": r.aluno_id,
        "nivel": r.nivel,
        "nivel_label": NIVEL_LABELS.get(r.nivel),
        "nivel_descricao": NIVEL_DESCRICOES.get(r.nivel),
        "nota": r.nota,
        "created_at": r.created_at,
    }


def reconhecer(
    aluno_id: int,
    *,
    nivel: str,
    nota: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a new self-recognition of level for a student.

    ``nivel`` must be one of :data:`NIVEL_OPCOES`; otherwise
    :class:`ValidationError` is raised and nothing is persisted. ``nota`` is
    optional free text (rule 6: empty means NULL, never a fake default).

    This is never an upsert: a student may recognize a new level (or the
    same one again) at any moment, and a new ReconhecimentoNivel row is
    always created, preserving the full history of self-recognition.

    The existence of ``aluno_id`` is not checked here — that is the caller
    route's responsibility (404 handling).
    """
    if nivel not in NIVEL_OPCOES:
        raise ValidationError("Nível inválido.")

    parsed_nota = _normalize(nota)

    with session_scope() as session:
        reconhecimento = ReconhecimentoNivel(
            aluno_id=aluno_id,
            nivel=nivel,
            nota=parsed_nota,
        )
        session.add(reconhecimento)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(reconhecimento)  # loads server-generated values (created_at)
        result = _to_dict(reconhecimento)

    logger.info(
        "Nível reconhecido: aluno_id=%s nivel=%s", aluno_id, nivel
    )
    return result


def nivel_atual(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Return a student's most recently recognized level as a plain dict, or
    None when there is no recognition yet.

    Ordered by created_at descending, tie-broken by id descending. Read-only:
    no log.
    """
    with session_scope() as session:
        query = (
            select(ReconhecimentoNivel)
            .where(ReconhecimentoNivel.aluno_id == aluno_id)
            .order_by(
                ReconhecimentoNivel.created_at.desc(),
                ReconhecimentoNivel.id.desc(),
            )
        )
        reconhecimento = session.execute(query).scalars().first()
        if reconhecimento is None:
            return None
        return _to_dict(reconhecimento)


def list_reconhecimentos(aluno_id: int) -> List[Dict[str, Any]]:
    """Return a student's full self-recognition history, most recent first.

    Ordered by created_at descending, tie-broken by id descending. Primitives
    are extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError). Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(ReconhecimentoNivel)
            .where(ReconhecimentoNivel.aluno_id == aluno_id)
            .order_by(
                ReconhecimentoNivel.created_at.desc(),
                ReconhecimentoNivel.id.desc(),
            )
        )
        rows = session.execute(query).scalars().all()
        return [_to_dict(reconhecimento) for reconhecimento in rows]
