"""HTTP routes (application layer) for the student-facing "area_aluno" domain.

Thin routes only: the auth gate already guarantees ``papel == "aluno"`` for
every request here (see :mod:`kairos.auth.middleware`). Every route reads
``aluno_id`` from the session (never from the URL) and only shows a detail
resource when it belongs to that same aluno; otherwise a generic "not found"
page is rendered (never 403, never another aluno's data). Displayed texts are
in Portuguese (architecture rule 10).
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse

from kairos.acompanhamento.service import list_sessoes_realizadas
from kairos.agenda.service import list_sessoes
from kairos.alunos.service import get_aluno
from kairos.auth.middleware import current_user
from kairos.avaliacoes.service import get_avaliacao, get_avaliacao_detail, list_avaliacoes
from kairos.treinos.service import get_treino, get_treino_detail, list_treinos
from kairos.web import templates

router = APIRouter()

_TIPO_LABELS = {"individual": "Individual", "grupo": "Grupo"}

_PRESENCA_LABELS = {
    "compareceu": "Compareceu",
    "faltou": "Faltou",
    "remarcada": "Remarcada",
}


def _aluno_id_da_sessao(request: Request) -> Optional[int]:
    """Return the logged-in aluno's id from the session, or None.

    Defensive: never trusts anything from the URL for identifying "which
    aluno" -- only the session (architecture: isolation of the aluno's own
    area).
    """
    return current_user(request).get("aluno_id")


def _nao_encontrado(request: Request) -> HTMLResponse:
    """Render the generic "not found" page for the aluno's area.

    Used both for resources that don't exist and for resources that belong
    to another aluno: from the requester's point of view, both are
    indistinguishable (never leak another aluno's data via a 403).
    """
    return templates.TemplateResponse(
        request,
        "area_aluno/nao_encontrado.html",
        {},
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _to_agendamento_display(s: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`list_sessoes`'s dicts for display."""
    return {
        "data": s["data"].strftime("%d/%m/%Y"),
        "hora": s["hora"].strftime("%H:%M"),
        "tipo_label": _TIPO_LABELS.get(s["tipo"], s["tipo"]),
        "treino_id": s.get("treino_id"),
        "treino_nome": s.get("treino_nome"),
    }


def _to_treino_display(t: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`list_treinos`'s dicts for display."""
    return {
        "id": t["id"],
        "nome": t["nome"],
        "item_count": t["item_count"],
    }


def _to_avaliacao_display(a: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`list_avaliacoes`'s dicts for display."""
    return {
        "id": a["id"],
        "data": a["data"].strftime("%d/%m/%Y"),
    }


def _to_sessao_realizada_display(r: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`list_sessoes_realizadas`'s dicts for display."""
    return {
        "data": r["data"].strftime("%d/%m/%Y"),
        "presenca_label": _PRESENCA_LABELS.get(r["presenca"], r["presenca"]),
        "disposicao": r["disposicao"].capitalize() if r["disposicao"] else None,
    }


@router.get("/aluno")
async def inicio(request: Request):
    """Render the student's own landing page: upcoming sessions, workouts,
    assessments and held-session history -- all scoped to the logged-in
    aluno."""
    aluno_id = _aluno_id_da_sessao(request)
    aluno = get_aluno(aluno_id) if aluno_id else None
    primeiro_nome = aluno["name"].split()[0] if aluno else None

    agendamentos: List[Dict[str, Any]] = []
    treinos: List[Dict[str, Any]] = []
    avaliacoes: List[Dict[str, Any]] = []
    sessoes_realizadas: List[Dict[str, Any]] = []

    if aluno_id:
        hoje = datetime.date.today()
        agendamentos = [
            _to_agendamento_display(s)
            for s in list_sessoes(aluno_id)
            if s["data"] >= hoje
        ]
        treinos = [_to_treino_display(t) for t in list_treinos(aluno_id)]
        avaliacoes = [_to_avaliacao_display(a) for a in list_avaliacoes(aluno_id)]
        sessoes_realizadas = [
            _to_sessao_realizada_display(r)
            for r in list_sessoes_realizadas(aluno_id)
        ]

    return templates.TemplateResponse(
        request,
        "area_aluno/inicio.html",
        {
            "primeiro_nome": primeiro_nome,
            "agendamentos": agendamentos,
            "treinos": treinos,
            "avaliacoes": avaliacoes,
            "sessoes_realizadas": sessoes_realizadas,
        },
    )


@router.get("/aluno/treinos/{treino_id}")
async def treino_detalhe(request: Request, treino_id: int):
    """Render one of the aluno's own workouts (read-only).

    404 (never 403) when the workout doesn't exist or belongs to another
    aluno.
    """
    aluno_id = _aluno_id_da_sessao(request)
    treino = get_treino(treino_id)
    if treino is None or treino["aluno_id"] != aluno_id:
        return _nao_encontrado(request)

    detalhe = get_treino_detail(treino_id)
    return templates.TemplateResponse(
        request, "area_aluno/treino_detalhe.html", {"treino": detalhe}
    )


@router.get("/aluno/avaliacoes/{avaliacao_id}")
async def avaliacao_detalhe(request: Request, avaliacao_id: int):
    """Render one of the aluno's own assessments (read-only).

    404 (never 403) when the assessment doesn't exist or belongs to another
    aluno.
    """
    aluno_id = _aluno_id_da_sessao(request)
    avaliacao = get_avaliacao(avaliacao_id)
    if avaliacao is None or avaliacao["aluno_id"] != aluno_id:
        return _nao_encontrado(request)

    detalhe = get_avaliacao_detail(avaliacao_id)
    return templates.TemplateResponse(
        request, "area_aluno/avaliacao_detalhe.html", {"avaliacao": detalhe}
    )
