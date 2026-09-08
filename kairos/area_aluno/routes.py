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
from fastapi.responses import FileResponse, HTMLResponse, Response

from kairos import config
from kairos.acompanhamento.service import get_sessao_realizada, list_sessoes_realizadas
from kairos.agenda.service import list_sessoes
from kairos.alunos.service import get_aluno
from kairos.auth.middleware import current_user
from kairos.avaliacoes.service import get_avaliacao, get_avaliacao_detail, list_avaliacoes
from kairos.financeiro.service import get_plano, pagamentos_do_aluno
from kairos.treinos.service import get_treino, get_treino_detail, list_treinos
from kairos.web import formatar_reais, templates

router = APIRouter()

_TIPO_LABELS = {"individual": "Individual", "grupo": "Grupo"}

_PRESENCA_LABELS = {
    "compareceu": "Compareceu",
    "faltou": "Faltou",
    "remarcada": "Remarcada",
}

_FORMATO_LABELS = {
    "individual": "Individual",
    "grupo": "Grupo",
    "digital": "Digital",
}

_FOTO_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
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
    """Format one of :func:`list_sessoes_realizadas`'s dicts for display.

    Includes ``id`` so the acompanhamento list can link to its own detail
    page.
    """
    return {
        "id": r["id"],
        "data": r["data"].strftime("%d/%m/%Y"),
        "presenca_label": _PRESENCA_LABELS.get(r["presenca"], r["presenca"]),
        "disposicao": r["disposicao"].capitalize() if r["disposicao"] else None,
    }


def _to_sessao_realizada_detail_display(r: Dict[str, Any]) -> Dict[str, Any]:
    """Format a :func:`get_sessao_realizada` dict for the detail page."""
    return {
        "data": r["data"].strftime("%d/%m/%Y"),
        "presenca_label": _PRESENCA_LABELS.get(r["presenca"], r["presenca"]),
        "disposicao": r["disposicao"].capitalize() if r["disposicao"] else None,
        "feedback": r["feedback"],
    }


def _to_plano_display(plano: Dict[str, Any]) -> Dict[str, Any]:
    """Format a :func:`get_plano` dict for display.

    Only formato/valor/ciclo/início are shown -- ``observacao`` may hold an
    internal coach note and is intentionally left out (isolation rule).
    """
    return {
        "formato_label": _FORMATO_LABELS.get(plano["formato"], plano["formato"]),
        "valor": formatar_reais(plano["valor"]),
        "ciclo_meses": plano["ciclo_meses"],
        "inicio": (
            plano["inicio"].strftime("%d/%m/%Y") if plano["inicio"] else None
        ),
    }


def _to_pagamento_display(p: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`pagamentos_do_aluno`'s dicts for display.

    ``status_label`` is derived from ``data_pagamento`` (the dict has no
    explicit status field): a payment with a recorded date is "Pago",
    otherwise "Pendente".
    """
    return {
        "competencia": f"{p['mes']:02d}/{p['ano']}",
        "valor": formatar_reais(p["valor"]),
        "data_pagamento": (
            p["data_pagamento"].strftime("%d/%m/%Y")
            if p["data_pagamento"]
            else "—"
        ),
        "status_label": "Pago" if p["data_pagamento"] else "Pendente",
    }


@router.get("/aluno")
async def inicio(request: Request):
    """Render the student's own home page: first name and the next
    scheduled session, if any -- all scoped to the logged-in aluno.

    The remaining lists (treinos, avaliações, agenda, acompanhamento,
    financeiro) live in their own sub-pages; the home's shortcuts are static
    links in the template. Tolerant of a session whose aluno_id no longer
    resolves to an Aluno: everything stays None/empty instead of breaking.
    """
    aluno_id = _aluno_id_da_sessao(request)
    aluno = get_aluno(aluno_id) if aluno_id else None
    primeiro_nome = aluno["name"].split()[0] if aluno else None

    proxima_sessao: Optional[Dict[str, Any]] = None
    if aluno_id:
        hoje = datetime.date.today()
        proxima = next(
            (s for s in list_sessoes(aluno_id) if s["data"] >= hoje), None
        )
        if proxima is not None:
            proxima_sessao = _to_agendamento_display(proxima)

    return templates.TemplateResponse(
        request,
        "area_aluno/inicio.html",
        {
            "primeiro_nome": primeiro_nome,
            "proxima_sessao": proxima_sessao,
        },
    )


@router.get("/aluno/perfil")
async def perfil(request: Request):
    """Render the aluno's own profile (read-only).

    Passes the raw :func:`get_aluno` dict through -- the template is
    responsible for only showing aluno-facing fields (name, foto, contact,
    sex_label, age, age_reported, weekly_frequency_label, objective,
    conditioning_label, health_conditions, medications, restrictions,
    email...) and must never render ``alert``/``notes`` (internal coach
    fields) nor any business indicator.
    """
    aluno_id = _aluno_id_da_sessao(request)
    aluno = get_aluno(aluno_id) if aluno_id else None
    return templates.TemplateResponse(
        request, "area_aluno/perfil.html", {"aluno": aluno}
    )


@router.get("/aluno/treinos")
async def treinos(request: Request):
    """Render the list of the aluno's own workouts (read-only)."""
    aluno_id = _aluno_id_da_sessao(request)
    lista = [_to_treino_display(t) for t in list_treinos(aluno_id)] if aluno_id else []
    return templates.TemplateResponse(
        request, "area_aluno/treinos.html", {"treinos": lista}
    )


@router.get("/aluno/avaliacoes")
async def avaliacoes(request: Request):
    """Render the list of the aluno's own assessments (read-only)."""
    aluno_id = _aluno_id_da_sessao(request)
    lista = (
        [_to_avaliacao_display(a) for a in list_avaliacoes(aluno_id)]
        if aluno_id
        else []
    )
    return templates.TemplateResponse(
        request, "area_aluno/avaliacoes.html", {"avaliacoes": lista}
    )


@router.get("/aluno/agenda")
async def agenda(request: Request):
    """Render the aluno's own schedule (read-only): upcoming sessions and
    past-session history, both scoped to the logged-in aluno.

    :func:`list_sessoes` already returns chronological (ascending) order, so
    "próximas" keeps it and "histórico" is built from the reversed list
    (descending, most recent first).
    """
    aluno_id = _aluno_id_da_sessao(request)
    proximas: List[Dict[str, Any]] = []
    historico: List[Dict[str, Any]] = []
    if aluno_id:
        hoje = datetime.date.today()
        sessoes = list_sessoes(aluno_id)
        proximas = [
            _to_agendamento_display(s) for s in sessoes if s["data"] >= hoje
        ]
        historico = [
            _to_agendamento_display(s)
            for s in reversed(sessoes)
            if s["data"] < hoje
        ]
    return templates.TemplateResponse(
        request,
        "area_aluno/agenda.html",
        {"proximas": proximas, "historico": historico},
    )


@router.get("/aluno/financeiro")
async def financeiro(request: Request):
    """Render the aluno's own plan and payments (read-only).

    Never shows a plan note that may hold an internal coach observation
    (see :func:`_to_plano_display`).
    """
    aluno_id = _aluno_id_da_sessao(request)
    plano: Optional[Dict[str, Any]] = None
    pagamentos: List[Dict[str, Any]] = []
    if aluno_id:
        raw_plano = get_plano(aluno_id)
        plano = _to_plano_display(raw_plano) if raw_plano else None
        pagamentos = [
            _to_pagamento_display(p) for p in pagamentos_do_aluno(aluno_id)
        ]
    return templates.TemplateResponse(
        request,
        "area_aluno/financeiro.html",
        {"plano": plano, "pagamentos": pagamentos},
    )


@router.get("/aluno/acompanhamento")
async def acompanhamento(request: Request):
    """Render the list of the aluno's own held-session records (read-only)."""
    aluno_id = _aluno_id_da_sessao(request)
    sessoes = (
        [_to_sessao_realizada_display(r) for r in list_sessoes_realizadas(aluno_id)]
        if aluno_id
        else []
    )
    return templates.TemplateResponse(
        request, "area_aluno/acompanhamento.html", {"sessoes": sessoes}
    )


@router.get("/aluno/acompanhamento/{registro_id}")
async def acompanhamento_detalhe(request: Request, registro_id: int):
    """Render one of the aluno's own held-session records (read-only).

    404 (never 403) when the record doesn't exist or belongs to another
    aluno.
    """
    aluno_id = _aluno_id_da_sessao(request)
    registro = get_sessao_realizada(registro_id)
    if registro is None or registro["aluno_id"] != aluno_id:
        return _nao_encontrado(request)

    return templates.TemplateResponse(
        request,
        "area_aluno/acompanhamento_detalhe.html",
        {"registro": _to_sessao_realizada_detail_display(registro)},
    )


@router.get("/aluno/foto")
async def foto(request: Request):
    """Serve the logged-in aluno's own stored photo file, or a plain 404.

    The aluno id always comes from the session (never from the URL), so
    this route can only ever serve the requester's own photo. 404 covers
    every case that is not "file on disk": no session aluno, aluno without a
    photo, and an orphaned filename whose file was removed from disk (never
    a 500).
    """
    aluno_id = _aluno_id_da_sessao(request)
    aluno = get_aluno(aluno_id) if aluno_id else None
    if aluno is None or aluno.get("foto") is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    filename = aluno["foto"]
    path = config.fotos_dir() / filename
    if not path.exists():
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = _FOTO_MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(path, media_type=media_type)


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
