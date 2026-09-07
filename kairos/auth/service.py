"""Business rules (service layer) for the "auth" (login) domain.

Maps a Supabase Auth user (``user_id``) to a Kairos role ("coach" or
"aluno") through the ``Perfil`` record. Persists through
:func:`kairos.db.session_scope`. Error messages are in Portuguese, ready to
be shown to the user (architecture rule 10); code and identifiers stay in
English.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from kairos.auth.models import Perfil
from kairos.db import session_scope

logger = logging.getLogger(__name__)

PAPEIS_VALIDOS = ("coach", "aluno")


class ValidationError(Exception):
    """Raised when user-supplied data is invalid.

    The exception message is in Portuguese and ready for display.
    """


def _to_dict(p: Perfil) -> Dict[str, Any]:
    """Extract a Perfil's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": p.id,
        "user_id": p.user_id,
        "papel": p.papel,
        "aluno_id": p.aluno_id,
        "created_at": p.created_at,
    }


def get_perfil(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the Perfil for a given Supabase Auth user_id as a plain dict,
    or None when there is no record (user_id is unique). Read-only: no
    log.
    """
    with session_scope() as session:
        query = select(Perfil).where(Perfil.user_id == user_id)
        p = session.execute(query).scalar_one_or_none()
        if p is None:
            return None
        return _to_dict(p)


def get_perfil_by_aluno(aluno_id: int) -> Optional[Dict[str, Any]]:
    """Return the Perfil linked to a given Aluno id as a plain dict, or None
    when no Perfil is linked to that Aluno (aluno_id is unique). Read-only:
    no log.
    """
    with session_scope() as session:
        query = select(Perfil).where(Perfil.aluno_id == aluno_id)
        p = session.execute(query).scalar_one_or_none()
        if p is None:
            return None
        return _to_dict(p)


def existe_coach() -> bool:
    """Return True when at least one Perfil with papel="coach" exists.

    Read-only: no log.
    """
    with session_scope() as session:
        query = select(Perfil.id).where(Perfil.papel == "coach").limit(1)
        return session.execute(query).scalar_one_or_none() is not None


def criar_perfil(
    *,
    user_id: str,
    papel: str,
    aluno_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a new Perfil binding a Supabase Auth user to a Kairos role.

    Raises :class:`ValidationError` (message in Portuguese) when ``papel``
    is not one of :data:`PAPEIS_VALIDOS`; nothing is persisted in that
    case.
    """
    if papel not in PAPEIS_VALIDOS:
        raise ValidationError("Papel inválido.")

    p = Perfil(user_id=user_id, papel=papel, aluno_id=aluno_id)

    with session_scope() as session:
        session.add(p)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(p)  # loads server-generated values (created_at)
        result = _to_dict(p)

    logger.info("Perfil created: user_id=%s papel=%s", user_id, papel)
    return result


def resolver_papel_no_login(
    user_id: str, email: Optional[str] = None
) -> Optional[str]:
    """Resolve the Kairos role for a Supabase Auth user right after login.

    Decision order:

    1. If a Perfil already exists for ``user_id``, return its ``papel``.
    2. Otherwise, if there is no coach yet, this is the very first login of
       the system: create a Perfil with papel="coach" for this user and
       return "coach".
    3. Otherwise, when ``email`` is given, try to auto-link this login to an
       active Aluno with a matching e-mail that has no Perfil yet. When
       exactly one such Aluno is found, create a Perfil with papel="aluno"
       bound to it and return "aluno". When zero or more than one candidate
       is found (ambiguous e-mail, or the e-mail is missing/blank), nothing
       is created.
    4. Otherwise, return None — this user has no access in this phase.
    """
    perfil = get_perfil(user_id)
    if perfil is not None:
        return perfil["papel"]

    if not existe_coach():
        perfil = criar_perfil(user_id=user_id, papel="coach")
        return perfil["papel"]

    if email:
        from kairos.alunos.service import find_alunos_by_email

        candidatos = [
            aluno
            for aluno in find_alunos_by_email(email)
            if get_perfil_by_aluno(aluno["id"]) is None
        ]
        if len(candidatos) == 1:
            perfil = criar_perfil(
                user_id=user_id, papel="aluno", aluno_id=candidatos[0]["id"]
            )
            return perfil["papel"]

    return None
