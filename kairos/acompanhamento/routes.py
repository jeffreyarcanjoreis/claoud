"""HTTP routes (application layer) for the "acompanhamento" (session
actually held) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.acompanhamento.service`, and render templates. Displayed texts
are in Portuguese (architecture rule 10).
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.acompanhamento.service import (
    ValidationError,
    create_sessao_realizada,
    get_sessao_realizada,
    list_sessoes_realizadas,
    remover_sessao_realizada,
)
from kairos.alunos.service import get_aluno
from kairos.web import ficha_header, templates

router = APIRouter()

_PRESENCA_LABELS = {
    "compareceu": "Compareceu",
    "faltou": "Faltou",
    "remarcada": "Remarcada",
}


def _to_list_display(r: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer registro dict to ready-to-print list fields."""
    return {
        "id": r["id"],
        "data": r["data"].strftime("%d/%m/%Y"),
        "presenca_label": _PRESENCA_LABELS.get(r["presenca"], r["presenca"]),
        "disposicao": r["disposicao"].capitalize() if r["disposicao"] else "sem registro",
        "feedback": r["feedback"] or None,
    }


@router.get("/alunos/{aluno_id}/acompanhamento", response_class=HTMLResponse)
async def aluno_acompanhamento(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the student's "Acompanhamento" sub-tab, or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    registros = list_sessoes_realizadas(aluno_id)
    context = {
        "aluno": ficha_header(aluno),
        "subtab": "acompanhamento",
        "registros": [_to_list_display(r) for r in registros],
    }
    return templates.TemplateResponse(request, "acompanhamento/lista.html", context)


# Declared before any future "/alunos/{aluno_id}/acompanhamento/{registro_id}"
# route (issue 05): the literal "novo" segment must win over the
# parameterized one (route registration order matters in FastAPI).
@router.get("/alunos/{aluno_id}/acompanhamento/novo", response_class=HTMLResponse)
async def new_sessao_realizada_form(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the new held-session form, or a 404 page when the student is
    absent."""
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
        "acompanhamento/novo.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "acompanhamento",
        },
    )


@router.post("/alunos/{aluno_id}/acompanhamento")
async def create_sessao_realizada_route(
    request: Request,
    aluno_id: int,
    data: Optional[str] = Form(None),
    presenca: Optional[str] = Form(None),
    disposicao: Optional[str] = Form(None),
    feedback: Optional[str] = Form(None),
):
    """Create a held session via the service layer; no business rules
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
        create_sessao_realizada(
            aluno_id,
            data=data,
            presenca=presenca,
            disposicao=disposicao,
            feedback=feedback,
        )
    except ValidationError as exc:
        values = {
            "data": data,
            "presenca": presenca,
            "disposicao": disposicao,
            "feedback": feedback,
        }
        return templates.TemplateResponse(
            request,
            "acompanhamento/novo.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "acompanhamento",
                "error": str(exc),
                "values": values,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/acompanhamento",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Registered after "/alunos/{aluno_id}/acompanhamento/novo" (issue 05): the
# literal "novo" segment must win over this parameterized "{registro_id}"
# route (route registration order matters in FastAPI).
@router.post("/alunos/{aluno_id}/acompanhamento/{registro_id}/remover")
async def remover_sessao_realizada_route(
    request: Request, aluno_id: int, registro_id: int
):
    """Remove a held session via the service layer.

    404s both when the student is absent and when the record does not exist
    or does not belong to this student — a record can never be removed
    through another student's URL.
    """
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    reg = get_sessao_realizada(registro_id)
    if reg is None or reg["aluno_id"] != aluno_id:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    remover_sessao_realizada(registro_id)

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/acompanhamento",
        status_code=status.HTTP_303_SEE_OTHER,
    )
