"""Business rules (service layer) for the "treinos" domain.

Receives raw form values (strings or None), normalizes and validates them
(architecture rule 6: empty means NULL, never a silent fake default), and
persists through :func:`kairos.db.session_scope`. Error messages are in
Portuguese, ready to be shown to the coach (architecture rule 10); code and
identifiers stay in English.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select

from kairos.db import session_scope
from kairos.treinos.models import Exercicio, Treino, TreinoItem

logger = logging.getLogger(__name__)


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


def _parse_nome_required(value: Optional[str]) -> str:
    """Parse the required exercise name.

    Raises :class:`ValidationError` when the value is missing or blank.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Nome é obrigatório.")
    return value


def _to_dict(exercicio: Exercicio) -> Dict[str, Any]:
    """Extract an Exercicio's fields into a dict of primitives.

    Must be called while the session is still open, so no attribute access
    happens on a detached instance (DetachedInstanceError).
    """
    return {
        "id": exercicio.id,
        "nome": exercicio.nome,
        "grupo_muscular": exercicio.grupo_muscular,
        "observacao": exercicio.observacao,
        "created_at": exercicio.created_at,
    }


def create_exercicio(
    *,
    nome: Optional[str] = None,
    grupo_muscular: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Exercicio from raw form values and return its saved fields.

    Raises :class:`ValidationError` (message in Portuguese) when the input is
    invalid; nothing is persisted in that case — all validation happens before
    anything is added to the session.
    """
    parsed_nome = _parse_nome_required(nome)
    parsed_grupo = _normalize(grupo_muscular)
    parsed_observacao = _normalize(observacao)

    exercicio = Exercicio(
        nome=parsed_nome,
        grupo_muscular=parsed_grupo,
        observacao=parsed_observacao,
    )

    with session_scope() as session:
        session.add(exercicio)
        session.flush()  # assigns the primary key and applies server defaults
        session.refresh(exercicio)  # loads server-generated values (created_at)
        result = _to_dict(exercicio)

    logger.info("Exercicio created: id=%s nome=%s", result["id"], result["nome"])
    return result


def list_exercicios() -> List[Dict[str, Any]]:
    """Return every exercise in the library, ordered by name (case-insensitive).

    ``func.lower`` keeps the ordering case-insensitive across SQLite and
    PostgreSQL (rule 4). Primitives are extracted while the session is still
    open, so no attribute access happens on detached instances
    (DetachedInstanceError). Read-only: no log.
    """
    with session_scope() as session:
        query = select(Exercicio).order_by(
            func.lower(Exercicio.nome), Exercicio.id.asc()
        )
        exercicios = session.execute(query).scalars()
        return [_to_dict(exercicio) for exercicio in exercicios]


def get_exercicio(exercicio_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Exercicio by primary key as a plain dict, or None."""
    with session_scope() as session:
        exercicio = session.get(Exercicio, exercicio_id)
        if exercicio is None:
            return None
        return _to_dict(exercicio)


def count_exercicios() -> int:
    """Return how many exercises exist in the library. Read-only: no log."""
    with session_scope() as session:
        return session.execute(
            select(func.count()).select_from(Exercicio)
        ).scalar()


# --------------------------------------------------------------------------- #
# Treinos (workouts / planilhas)                                              #
# --------------------------------------------------------------------------- #

def _parse_exercicio_id_required(value: Optional[str]) -> int:
    """Parse the required exercise id chosen from the library.

    Raises :class:`ValidationError` when missing or not an integer.
    """
    value = _normalize(value)
    if value is None:
        raise ValidationError("Selecione um exercício.")
    try:
        return int(value)
    except ValueError:
        raise ValidationError("Exercício inválido.")


def _parse_series(value: Optional[str]) -> Optional[int]:
    """Parse an optional number of sets: empty -> None, else a positive int."""
    value = _normalize(value)
    if value is None:
        return None
    try:
        series = int(value)
    except ValueError:
        raise ValidationError("Séries inválido.")
    if series <= 0:
        raise ValidationError("Séries deve ser positivo.")
    return series


def _treino_to_dict(treino: Treino) -> Dict[str, Any]:
    return {
        "id": treino.id,
        "aluno_id": treino.aluno_id,
        "nome": treino.nome,
        "observacao": treino.observacao,
        "created_at": treino.created_at,
    }


def create_treino(
    aluno_id: int,
    *,
    nome: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new (empty) Treino for a student and return its saved fields.

    Raises :class:`ValidationError` when the name is missing; the student's
    existence is the caller route's responsibility (404).
    """
    parsed_nome = _parse_nome_required(nome)
    parsed_observacao = _normalize(observacao)

    treino = Treino(
        aluno_id=aluno_id, nome=parsed_nome, observacao=parsed_observacao
    )
    with session_scope() as session:
        session.add(treino)
        session.flush()
        session.refresh(treino)
        result = _treino_to_dict(treino)

    logger.info(
        "Treino created: id=%s aluno_id=%s", result["id"], result["aluno_id"]
    )
    return result


def list_treinos(aluno_id: int) -> List[Dict[str, Any]]:
    """Return a student's workouts, ordered by name (case-insensitive), each
    with how many exercises it has. Read-only: no log."""
    with session_scope() as session:
        rows = session.execute(
            select(Treino, func.count(TreinoItem.id))
            .outerjoin(TreinoItem, TreinoItem.treino_id == Treino.id)
            .where(Treino.aluno_id == aluno_id)
            .group_by(Treino.id)
            .order_by(func.lower(Treino.nome), Treino.id.asc())
        ).all()
        return [
            {
                "id": treino.id,
                "nome": treino.nome,
                "observacao": treino.observacao,
                "item_count": item_count,
            }
            for treino, item_count in rows
        ]


def get_treino(treino_id: int) -> Optional[Dict[str, Any]]:
    """Return a single Treino (without its items) as a plain dict, or None."""
    with session_scope() as session:
        treino = session.get(Treino, treino_id)
        if treino is None:
            return None
        return _treino_to_dict(treino)


def get_treino_detail(treino_id: int) -> Optional[Dict[str, Any]]:
    """Return a Treino with its ordered items (joined to each exercise's name
    and muscle group), or None. Read-only: no log."""
    with session_scope() as session:
        treino = session.get(Treino, treino_id)
        if treino is None:
            return None

        rows = session.execute(
            select(TreinoItem, Exercicio.nome, Exercicio.grupo_muscular)
            .join(Exercicio, TreinoItem.exercicio_id == Exercicio.id)
            .where(TreinoItem.treino_id == treino_id)
            .order_by(TreinoItem.ordem.asc(), TreinoItem.id.asc())
        ).all()

        itens = [
            {
                "id": item.id,
                "exercicio_id": item.exercicio_id,
                "exercicio_nome": exercicio_nome,
                "grupo_muscular": grupo_muscular,
                "ordem": item.ordem,
                "series": item.series,
                "reps": item.reps,
                "carga": item.carga,
                "observacao": item.observacao,
            }
            for item, exercicio_nome, grupo_muscular in rows
        ]

        result = _treino_to_dict(treino)
        result["itens"] = itens
        return result


def add_item_to_treino(
    treino_id: int,
    *,
    exercicio_id: Optional[str] = None,
    series: Optional[str] = None,
    reps: Optional[str] = None,
    carga: Optional[str] = None,
    observacao: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an exercise (with optional séries/reps/carga) to a workout.

    Raises :class:`ValidationError` when no valid exercise is chosen or the
    chosen exercise does not exist. The workout's existence/ownership is the
    caller route's responsibility (404).
    """
    parsed_exercicio_id = _parse_exercicio_id_required(exercicio_id)
    parsed_series = _parse_series(series)
    parsed_reps = _normalize(reps)
    parsed_carga = _normalize(carga)
    parsed_observacao = _normalize(observacao)

    with session_scope() as session:
        if session.get(Exercicio, parsed_exercicio_id) is None:
            raise ValidationError("Exercício não encontrado.")

        next_ordem = session.execute(
            select(func.coalesce(func.max(TreinoItem.ordem), 0)).where(
                TreinoItem.treino_id == treino_id
            )
        ).scalar()

        item = TreinoItem(
            treino_id=treino_id,
            exercicio_id=parsed_exercicio_id,
            ordem=next_ordem + 1,
            series=parsed_series,
            reps=parsed_reps,
            carga=parsed_carga,
            observacao=parsed_observacao,
        )
        session.add(item)
        session.flush()
        session.refresh(item)
        result = {
            "id": item.id,
            "treino_id": item.treino_id,
            "exercicio_id": item.exercicio_id,
            "ordem": item.ordem,
            "series": item.series,
            "reps": item.reps,
            "carga": item.carga,
            "observacao": item.observacao,
        }

    logger.info(
        "TreinoItem added: id=%s treino_id=%s", result["id"], result["treino_id"]
    )
    return result


def get_item(item_id: int) -> Optional[Dict[str, Any]]:
    """Return a single TreinoItem as a plain dict, or None (for ownership
    checks in the route)."""
    with session_scope() as session:
        item = session.get(TreinoItem, item_id)
        if item is None:
            return None
        return {"id": item.id, "treino_id": item.treino_id}


def remove_item(item_id: int) -> bool:
    """Remove one exercise from a workout. Returns True when it existed."""
    with session_scope() as session:
        item = session.get(TreinoItem, item_id)
        if item is None:
            return False
        session.delete(item)
        logger.info("TreinoItem removed: id=%s", item_id)
        return True


def delete_treino(treino_id: int) -> bool:
    """Delete a workout and all its items. Returns True when it existed."""
    with session_scope() as session:
        treino = session.get(Treino, treino_id)
        if treino is None:
            return False
        session.execute(
            delete(TreinoItem).where(TreinoItem.treino_id == treino_id)
        )
        session.delete(treino)
        logger.info("Treino deleted: id=%s", treino_id)
        return True
