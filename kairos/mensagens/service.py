"""Business rules (service layer) for the "mensagens" (student-coach
messaging) domain.

Receives raw values, normalizes and validates them (architecture rule 6:
empty means NULL, never a silent fake default), and persists through
:func:`kairos.db.session_scope`. Error messages are in Portuguese, ready to
be shown to the coach or the student (architecture rule 10); code and
identifiers stay in English.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update

from kairos.db import session_scope
from kairos.mensagens.models import Mensagem

logger = logging.getLogger(__name__)

AUTORES_VALIDOS = ("coach", "aluno")


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


def _autor_oposto(lado: str) -> Optional[str]:
    """Return the opposite side of the conversation.

    "aluno" -> "coach", "coach" -> "aluno". Returns None for any other,
    unrecognized value.
    """
    if lado == "aluno":
        return "coach"
    if lado == "coach":
        return "aluno"
    return None


def _to_dict(m: Mensagem) -> Dict[str, Any]:
    """Extract a Mensagem's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": m.id,
        "aluno_id": m.aluno_id,
        "autor": m.autor,
        "texto": m.texto,
        "lida": m.lida,
        "created_at": m.created_at,
    }


def enviar_mensagem(aluno_id: int, autor: str, texto: str) -> Dict[str, Any]:
    """Create a new Mensagem and return its saved fields.

    Raises :class:`ValidationError` (message in Portuguese) when ``autor``
    is not one of :data:`AUTORES_VALIDOS` or when ``texto`` is empty;
    nothing is persisted in that case.
    """
    if autor not in AUTORES_VALIDOS:
        raise ValidationError("Autor inválido.")

    parsed_texto = _normalize(texto)
    if parsed_texto is None:
        raise ValidationError("A mensagem não pode ficar vazia.")

    m = Mensagem(
        aluno_id=aluno_id,
        autor=autor,
        texto=parsed_texto,
        lida=False,
    )

    with session_scope() as session:
        session.add(m)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(m)  # loads server-generated values (created_at)
        result = _to_dict(m)

    logger.info("Mensagem created: aluno_id=%s autor=%s", aluno_id, autor)
    return result


def listar_conversa(aluno_id: int) -> List[Dict[str, Any]]:
    """Return an Aluno's full conversation, oldest first.

    Ordered by created_at ascending, tie-broken by id ascending. Primitives
    are extracted while the session is still open, so no attribute access
    happens on detached instances (DetachedInstanceError). Read-only: no
    log.
    """
    with session_scope() as session:
        query = (
            select(Mensagem)
            .where(Mensagem.aluno_id == aluno_id)
            .order_by(Mensagem.created_at.asc(), Mensagem.id.asc())
        )
        mensagens = session.execute(query).scalars().all()
        return [_to_dict(m) for m in mensagens]


def marcar_lidas(aluno_id: int, por: str) -> int:
    """Mark as read the messages addressed to ``por``.

    ``por="aluno"`` marks the coach's unread messages; ``por="coach"`` marks
    the student's unread messages (the recipient is always the opposite
    side of the message's author). Returns how many rows were affected.

    Raises :class:`ValidationError` when ``por`` is not one of
    :data:`AUTORES_VALIDOS`. Logs only when at least one message was
    marked.
    """
    autor_alvo = _autor_oposto(por)
    if autor_alvo is None:
        raise ValidationError("Destinatário inválido.")

    with session_scope() as session:
        query = (
            update(Mensagem)
            .where(
                Mensagem.aluno_id == aluno_id,
                Mensagem.autor == autor_alvo,
                Mensagem.lida == False,  # noqa: E712
            )
            .values(lida=True)
        )
        result = session.execute(query)
        n = result.rowcount

    if n:
        logger.info("Mensagens marcadas lidas: aluno_id=%s por=%s n=%s", aluno_id, por, n)
    return n


def contar_nao_lidas(aluno_id: int, para: str) -> int:
    """Return how many unread messages are addressed to ``para``.

    The recipient's author is the opposite side of ``para`` (see
    :func:`_autor_oposto`). Since this is used for UI counters, an
    unrecognized ``para`` defensively returns 0 instead of raising. Read-
    only: no log.
    """
    autor_alvo = _autor_oposto(para)
    if autor_alvo is None:
        return 0

    with session_scope() as session:
        query = select(func.count()).where(
            Mensagem.aluno_id == aluno_id,
            Mensagem.autor == autor_alvo,
            Mensagem.lida == False,  # noqa: E712
        )
        return session.execute(query).scalar_one()


def ultima_do_coach(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Return the most recent coach message for an Aluno, or None.

    Ordered by created_at descending, tie-broken by id descending. Read-
    only: no log.
    """
    with session_scope() as session:
        query = (
            select(Mensagem)
            .where(Mensagem.aluno_id == aluno_id, Mensagem.autor == "coach")
            .order_by(Mensagem.created_at.desc(), Mensagem.id.desc())
        )
        m = session.execute(query).scalars().first()
        if m is None:
            return None
        return _to_dict(m)


def alunos_com_nao_lidas() -> Dict[int, int]:
    """Return a map of aluno_id to how many unread student messages await
    the coach.

    Considers messages with ``autor="aluno"`` and ``lida=False``, grouped
    by aluno_id. Read-only: no log. Used for the unread badge in the
    coach's student list.
    """
    with session_scope() as session:
        query = (
            select(Mensagem.aluno_id, func.count())
            .where(Mensagem.autor == "aluno", Mensagem.lida == False)  # noqa: E712
            .group_by(Mensagem.aluno_id)
        )
        return dict(session.execute(query).all())
