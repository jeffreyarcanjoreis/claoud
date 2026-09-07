"""HTTP routes (application layer) for the "agenda" (scheduled sessions)
domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.agenda.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.agenda.service import (
    ValidationError,
    cancel_sessao,
    create_sessao,
    get_sessao,
    list_sessoes,
)
from kairos.alunos.service import get_aluno
from kairos.treinos.service import list_treinos
from kairos.web import ficha_header, templates

router = APIRouter()

_NO_RECORD = "sem registro"

_TIPO_LABELS = {"individual": "Individual", "grupo": "Grupo"}


def _to_list_display(sessao: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer sessao dict to ready-to-print list fields."""
    return {
        "id": sessao["id"],
        "data": sessao["data"].strftime("%d/%m/%Y"),
        "hora": sessao["hora"].strftime("%H:%M"),
        "tipo_label": _TIPO_LABELS.get(sessao["tipo"], "Grupo"),
        "duracao": (
            f'{sessao["duracao_min"]} min'
            if sessao["duracao_min"] is not None
            else _NO_RECORD
        ),
        "observacao": sessao["observacao"] or None,
        "treino_id": sessao.get("treino_id"),
        "treino_nome": sessao.get("treino_nome"),
    }


@router.get("/alunos/{aluno_id}/agenda", response_class=HTMLResponse)
async def aluno_agenda(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the student's "Agenda" sub-tab, or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    sessoes = list_sessoes(aluno_id)
    context = {
        "aluno": ficha_header(aluno),
        "subtab": "agenda",
        "sessoes": [_to_list_display(sessao) for sessao in sessoes],
    }
    return templates.TemplateResponse(request, "agenda/lista.html", context)


# Declared before any future "/alunos/{aluno_id}/agenda/{sessao_id}" route
# (issue 05): the literal "nova" segment must win over the parameterized one
# (route registration order matters in FastAPI).
@router.get("/alunos/{aluno_id}/agenda/nova", response_class=HTMLResponse)
async def new_sessao_form(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the new scheduled-session form, or a 404 page when the student
    is absent."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request,
        "agenda/nova.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "agenda",
            "treinos": list_treinos(aluno_id),
        },
    )


@router.post("/alunos/{aluno_id}/agenda")
async def create_sessao_route(
    request: Request,
    aluno_id: int,
    data: Optional[str] = Form(None),
    hora: Optional[str] = Form(None),
    duracao_min: Optional[str] = Form(None),
    tipo: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    treino_id: Optional[str] = Form(None),
):
    """Create a scheduled session via the service layer; no business rules
    here."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        create_sessao(
            aluno_id,
            data=data,
            hora=hora,
            tipo=tipo,
            duracao_min=duracao_min,
            observacao=observacao,
            treino_id=treino_id,
        )
    except ValidationError as exc:
        values = {
            "data": data,
            "hora": hora,
            "duracao_min": duracao_min,
            "tipo": tipo,
            "observacao": observacao,
            "treino_id": treino_id,
        }
        return templates.TemplateResponse(
            request,
            "agenda/nova.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "agenda",
                "treinos": list_treinos(aluno_id),
                "error": str(exc),
                "values": values,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/agenda",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Registered after "/alunos/{aluno_id}/agenda/nova" (issue 05): the literal
# "nova" segment must win over this parameterized "{sessao_id}" route (route
# registration order matters in FastAPI).
@router.post("/alunos/{aluno_id}/agenda/{sessao_id}/cancelar")
async def cancel_sessao_route(request: Request, aluno_id: int, sessao_id: int):
    """Cancel (remove) a scheduled session via the service layer.

    404s both when the student is absent and when the session does not
    exist or does not belong to this student — a session can never be
    cancelled through another student's URL.
    """
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    sessao = get_sessao(sessao_id)
    if sessao is None or sessao["aluno_id"] != aluno_id:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    cancel_sessao(sessao_id)

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/agenda",
        status_code=status.HTTP_303_SEE_OTHER,
    )
