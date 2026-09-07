"""Business rules (service layer) for the "tarefas" (coach's task list)
domain.

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
from kairos.tarefas.models import Tarefa

logger = logging.getLogger(__name__)

CATEGORIAS_VALIDAS = ("lembrete", "publicacao", "contato", "campanha")


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


def _parse_titulo_required(value: Optional[str]) -> str:
    """Parse a required title.

    Raises :class:`ValidationError` when missing or blank.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Título é obrigatório.")
    return value


def _parse_categoria_optional(value: Optional[str]) -> Optional[str]:
    """Parse an optional category, must be one of :data:`CATEGORIAS_VALIDAS`
    when filled in.

    Empty or whitespace-only values normalize to None (rule 6: no data means
    NULL, not a fake default). Raises :class:`ValidationError` when filled in
    but not one of :data:`CATEGORIAS_VALIDAS`.
    """
    value = _normalize(value)
    if value is None:
        return None
    if value not in CATEGORIAS_VALIDAS:
        raise ValidationError("Categoria inválida.")
    return value


def _parse_prazo_optional(value: Optional[str]) -> Optional[datetime.date]:
    """Parse an optional ISO "YYYY-MM-DD" string into a date.

    Empty or whitespace-only values normalize to None. Raises
    :class:`ValidationError` when filled in but not a valid date.
    """
    value = _normalize(value)
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Prazo inválido.")


def _to_dict(t: Tarefa) -> Dict[str, Any]:
    """Extract a Tarefa's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": t.id,
        "titulo": t.titulo,
        "categoria": t.categoria,
        "prazo": t.prazo,
        "concluida": t.concluida,
        "created_at": t.created_at,
    }


def create_tarefa(
    *,
    titulo: Optional[str] = None,
    categoria: Optional[str] = None,
    prazo: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Tarefa from raw form values and return its saved
    fields.

    Raises :class:`ValidationError` (message in Portuguese) when the input
    is invalid; nothing is persisted in that case.
    """
    parsed_titulo = _parse_titulo_required(titulo)
    parsed_categoria = _parse_categoria_optional(categoria)
    parsed_prazo = _parse_prazo_optional(prazo)

    t = Tarefa(
        titulo=parsed_titulo,
        categoria=parsed_categoria,
        prazo=parsed_prazo,
    )

    with session_scope() as session:
        session.add(t)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(t)  # loads server-generated values (created_at, concluida)
        result = _to_dict(t)

    logger.info("Tarefa created: id=%s", result["id"])
    return result


def list_tarefas_abertas() -> List[Dict[str, Any]]:
    """Return open (not-yet-completed) tasks, soonest deadline first.

    Ordered by prazo ascending with tasks without a deadline last, tie-broken
    by id ascending. Primitives are extracted while the session is still
    open, so no attribute access happens on detached instances
    (DetachedInstanceError). Read-only: no log.
    """
    with session_scope() as session:
        query = (
            select(Tarefa)
            .where(Tarefa.concluida == False)  # noqa: E712
            .order_by(Tarefa.prazo.asc().nullslast(), Tarefa.id.asc())
        )
        tarefas = session.execute(query).scalars().all()
        return [_to_dict(t) for t in tarefas]


def get_tarefa(tarefa_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Tarefa by primary key as a plain dict, or None."""
    with session_scope() as session:
        t = session.get(Tarefa, tarefa_id)
        if t is None:
            return None
        return _to_dict(t)


def concluir_tarefa(tarefa_id: int) -> bool:
    """Mark a Tarefa as completed.

    Returns True when the record existed and was updated, False when it did
    not exist.
    """
    with session_scope() as session:
        t = session.get(Tarefa, tarefa_id)
        if t is None:
            return False
        t.concluida = True
        logger.info("Tarefa concluded: id=%s", tarefa_id)
        return True


def remover_tarefa(tarefa_id: int) -> bool:
    """Remove a Tarefa by primary key.

    Returns True when the record existed and was removed, False when it did
    not exist.
    """
    with session_scope() as session:
        t = session.get(Tarefa, tarefa_id)
        if t is None:
            return False
        session.delete(t)
        logger.info("Tarefa removed: id=%s", tarefa_id)
        return True
