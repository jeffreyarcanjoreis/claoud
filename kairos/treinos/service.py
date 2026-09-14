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

FASE_OPCOES = ("preparacao", "aquecimento", "skill", "apice", "volta_a_calma")
FASE_LABELS = {
    "preparacao": "Preparação",
    "aquecimento": "Aquecimento",
    "skill": "Skill",
    "apice": "Ápice",
    "volta_a_calma": "Volta à calma",
}
FASE_PERGUNTAS = {
    "preparacao": "Quem chegou hoje?",
    "aquecimento": "O corpo está aqui agora?",
    "skill": "Este corpo está pronto?",
    "apice": "Qual o limite de hoje?",
    "volta_a_calma": "O que mudou?",
}

VARIACAO_OPCOES = ("base", "regressao", "progressao")
VARIACAO_LABELS = {
    "base": "Base",
    "regressao": "Regressão",
    "progressao": "Progressão",
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
        "video_filename": exercicio.video_filename,
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


def _parse_fase(value: Optional[str]) -> Optional[str]:
    """Parse an optional workout phase: empty -> None ("Sem fase"), else must
    be one of :data:`FASE_OPCOES`."""
    value = _normalize(value)
    if value is None:
        return None
    if value not in FASE_OPCOES:
        raise ValidationError("Fase inválida.")
    return value


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
            select(
                TreinoItem,
                Exercicio.nome,
                Exercicio.grupo_muscular,
                Exercicio.video_filename,
            )
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
                "fase": item.fase,
                "fase_label": FASE_LABELS.get(item.fase) if item.fase else None,
                "video_filename": video_filename,
                "variacao_base": item.variacao_base,
                "variacao_regressao": item.variacao_regressao,
                "variacao_progressao": item.variacao_progressao,
                "variacao_escolhida": item.variacao_escolhida,
                "variacao_escolhida_label": (
                    VARIACAO_LABELS.get(item.variacao_escolhida)
                    if item.variacao_escolhida
                    else None
                ),
            }
            for item, exercicio_nome, grupo_muscular, video_filename in rows
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
    fase: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an exercise (with optional séries/reps/carga/fase) to a workout.

    Raises :class:`ValidationError` when no valid exercise is chosen, the
    chosen exercise does not exist, or ``fase`` is not one of
    :data:`FASE_OPCOES`. The workout's existence/ownership is the caller
    route's responsibility (404).
    """
    parsed_exercicio_id = _parse_exercicio_id_required(exercicio_id)
    parsed_series = _parse_series(series)
    parsed_reps = _normalize(reps)
    parsed_carga = _normalize(carga)
    parsed_observacao = _normalize(observacao)
    parsed_fase = _parse_fase(fase)

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
            fase=parsed_fase,
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
            "fase": item.fase,
            "fase_label": FASE_LABELS.get(item.fase) if item.fase else None,
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


def update_item(
    item_id: int,
    *,
    series: Optional[str] = None,
    reps: Optional[str] = None,
    carga: Optional[str] = None,
    observacao: Optional[str] = None,
    fase: Optional[str] = None,
    variacao_base: Optional[str] = None,
    variacao_regressao: Optional[str] = None,
    variacao_progressao: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Edit a workout item's prescription, phase and variations (not its
    exercise or order).

    Raises :class:`ValidationError` when ``series`` or ``fase`` are invalid;
    nothing is persisted in that case — all validation happens before the
    session is touched. Returns None when the item does not exist (the caller
    route handles the 404).
    """
    parsed_series = _parse_series(series)
    parsed_fase = _parse_fase(fase)
    parsed_reps = _normalize(reps)
    parsed_carga = _normalize(carga)
    parsed_observacao = _normalize(observacao)
    parsed_variacao_base = _normalize(variacao_base)
    parsed_variacao_regressao = _normalize(variacao_regressao)
    parsed_variacao_progressao = _normalize(variacao_progressao)

    with session_scope() as session:
        item = session.get(TreinoItem, item_id)
        if item is None:
            return None

        item.series = parsed_series
        item.reps = parsed_reps
        item.carga = parsed_carga
        item.observacao = parsed_observacao
        item.fase = parsed_fase
        item.variacao_base = parsed_variacao_base
        item.variacao_regressao = parsed_variacao_regressao
        item.variacao_progressao = parsed_variacao_progressao
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
            "fase": item.fase,
            "fase_label": FASE_LABELS.get(item.fase) if item.fase else None,
            "variacao_base": item.variacao_base,
            "variacao_regressao": item.variacao_regressao,
            "variacao_progressao": item.variacao_progressao,
        }

    logger.info("TreinoItem updated: id=%s", item_id)
    return result


def escolher_variacao(
    item_id: int, escolha: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Set (or clear) the student's own choice of "where I recognize myself
    today" among the workout item's variations.

    ``escolha`` is normalized (empty/whitespace -> None, meaning "rever":
    clear the choice, rule 6). When not None, it must be one of
    :data:`VARIACAO_OPCOES`, otherwise :class:`ValidationError` is raised
    before the session is touched. The chosen variation is not required to
    have a description from the coach — the student recognizes themself
    regardless; the UI is what only offers the described ones. Returns None
    when the item does not exist (the caller route handles the 404).
    """
    parsed_escolha = _normalize(escolha)
    if parsed_escolha is not None and parsed_escolha not in VARIACAO_OPCOES:
        raise ValidationError("Variação inválida.")

    with session_scope() as session:
        item = session.get(TreinoItem, item_id)
        if item is None:
            return None

        item.variacao_escolhida = parsed_escolha
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
            "fase": item.fase,
            "fase_label": FASE_LABELS.get(item.fase) if item.fase else None,
            "variacao_base": item.variacao_base,
            "variacao_regressao": item.variacao_regressao,
            "variacao_progressao": item.variacao_progressao,
            "variacao_escolhida": item.variacao_escolhida,
            "variacao_escolhida_label": (
                VARIACAO_LABELS.get(parsed_escolha) if parsed_escolha else None
            ),
        }

    logger.info(
        "TreinoItem variação escolhida: id=%s escolha=%s", item_id, parsed_escolha
    )
    return result


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


def agrupar_itens_por_fase(itens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group a workout's items (as returned by :func:`get_treino_detail`) into
    the canonical phase order.

    Every phase in :data:`FASE_OPCOES` is present, even with an empty item
    list. A trailing "Sem fase" group is appended only when there is at least
    one item without a phase. Item order within each group is preserved (they
    already arrive ordered by ``ordem``). Pure function: no database access,
    no log.
    """
    grupos = [
        {
            "fase": fase,
            "fase_label": FASE_LABELS[fase],
            "fase_pergunta": FASE_PERGUNTAS[fase],
            "itens": [item for item in itens if item["fase"] == fase],
        }
        for fase in FASE_OPCOES
    ]

    sem_fase = [item for item in itens if item["fase"] in (None, "")]
    if sem_fase:
        grupos.append(
            {
                "fase": None,
                "fase_label": "Sem fase",
                "fase_pergunta": None,
                "itens": sem_fase,
            }
        )

    return grupos


def set_apresentacao(treino_id: int, texto: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Set (or clear) a workout's apresentação (its ``observacao`` field).

    Empty/whitespace-only text is normalized to None ("sem registro"). Returns
    the updated workout as a dict, or None when it does not exist (the caller
    route handles the 404).
    """
    parsed_texto = _normalize(texto)

    with session_scope() as session:
        treino = session.get(Treino, treino_id)
        if treino is None:
            return None
        treino.observacao = parsed_texto
        session.flush()
        session.refresh(treino)
        result = _treino_to_dict(treino)

    logger.info("Apresentação do treino definida: id=%s", treino_id)
    return result


def mover_item(item_id: int, direcao: str) -> bool:
    """Move a workout item one step up or down within its phase.

    ``direcao`` must be ``"cima"`` or ``"baixo"``; anything else raises
    :class:`ValidationError` before the session is opened. Swaps ``ordem``
    with the immediate neighbour in the same treino and phase (``fase`` may
    be None, meaning "Sem fase"). Returns False when the item does not exist
    or when it is already at that end of its phase (no-op); returns True
    when the swap happened.
    """
    if direcao not in ("cima", "baixo"):
        raise ValidationError("Direção inválida.")

    with session_scope() as session:
        item = session.get(TreinoItem, item_id)
        if item is None:
            return False

        fase_filter = (
            TreinoItem.fase.is_(None) if item.fase is None else TreinoItem.fase == item.fase
        )

        if direcao == "cima":
            query = (
                select(TreinoItem)
                .where(
                    TreinoItem.treino_id == item.treino_id,
                    fase_filter,
                    TreinoItem.ordem < item.ordem,
                )
                .order_by(TreinoItem.ordem.desc())
                .limit(1)
            )
        else:
            query = (
                select(TreinoItem)
                .where(
                    TreinoItem.treino_id == item.treino_id,
                    fase_filter,
                    TreinoItem.ordem > item.ordem,
                )
                .order_by(TreinoItem.ordem.asc())
                .limit(1)
            )

        vizinho = session.execute(query).scalar_one_or_none()
        if vizinho is None:
            return False

        item.ordem, vizinho.ordem = vizinho.ordem, item.ordem
        session.flush()

    logger.info("TreinoItem moved: id=%s direcao=%s", item_id, direcao)
    return True


def set_exercicio_video(
    exercicio_id: int, file_bytes: bytes, content_type: str, original_filename: str
) -> Optional[Dict[str, Any]]:
    """Validate and store a new demonstration video for an exercise.

    Returns None when the exercise does not exist (the caller route handles
    the 404). Raises :class:`ValidationError` when the upload is invalid; in
    that case nothing changes, and the previous video (if any) remains
    intact — the old file is only deleted after the new one has been saved
    successfully.
    """
    # Imported lazily to avoid a circular import: kairos.treinos.videos
    # reuses ValidationError from this module.
    from kairos.treinos.videos import delete_video_file, save_video

    with session_scope() as session:
        exercicio = session.get(Exercicio, exercicio_id)
        if exercicio is None:
            return None

        old_filename = exercicio.video_filename
        new_filename = save_video(file_bytes, content_type, original_filename)

        exercicio.video_filename = new_filename
        session.flush()
        session.refresh(exercicio)
        result = _to_dict(exercicio)

    delete_video_file(old_filename)

    logger.info(
        "Exercicio video set: id=%s filename=%s", exercicio_id, new_filename
    )
    return result


def remove_exercicio_video(exercicio_id: int) -> bool:
    """Remove an exercise's demonstration video (field and file).

    Returns True when the exercise existed (regardless of whether it had a
    video), or False when it does not exist.
    """
    from kairos.treinos.videos import delete_video_file

    with session_scope() as session:
        exercicio = session.get(Exercicio, exercicio_id)
        if exercicio is None:
            return False

        old_filename = exercicio.video_filename
        exercicio.video_filename = None
        session.flush()

    delete_video_file(old_filename)

    logger.info("Exercicio video removed: id=%s", exercicio_id)
    return True
