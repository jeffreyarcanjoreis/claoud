"""HTTP routes (application layer) for the "checkin" (student daily
check-in) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.checkin.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).

Two sides exist:

- The aluno's own side (``/aluno/checkin``) always resolves ``aluno_id`` from
  the session (never from the URL), matching the isolation rule used
  throughout :mod:`kairos.area_aluno.routes`.
- The coach's side (``/alunos/{aluno_id}/checkins``) takes ``aluno_id`` from
  the URL, since the coach manages every aluno's history, and follows the
  get-or-404 + ``ficha_header``/``subtab`` pattern used throughout
  :mod:`kairos.acompanhamento.routes`.
"""

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.alunos.service import get_aluno
from kairos.auth.middleware import current_user
from kairos.checkin.service import (
    HUMOR_LABELS,
    HUMOR_OPCOES,
    QUALIDADE_SONO_LABELS,
    QUALIDADE_SONO_OPCOES,
    ValidationError,
    checkin_de_hoje,
    get_checkin,
    list_checkins,
    registrar_checkin,
)
from kairos.web import ficha_header, templates

router = APIRouter()

_QUALIDADE_OPCOES_DISPLAY = [
    (valor, QUALIDADE_SONO_LABELS[valor]) for valor in QUALIDADE_SONO_OPCOES
]
_HUMOR_OPCOES_DISPLAY = [(valor, HUMOR_LABELS[valor]) for valor in HUMOR_OPCOES]


def _to_checkin_display(c: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer checkin dict to ready-to-print display fields."""
    return {
        "id": c["id"],
        "data": c["data"].strftime("%d/%m/%Y"),
        "sono_horas": c["sono_horas"],
        "sono_qualidade_label": c["sono_qualidade_label"],
        "estresse": c["estresse"],
        "energia": c["energia"],
        "humor_label": c["humor_label"],
        "dor_local": c["dor_local"],
        "dor_intensidade": c["dor_intensidade"],
        "observacao": c["observacao"],
    }


@router.get("/aluno/checkin", response_class=HTMLResponse)
async def aluno_checkin(request: Request) -> HTMLResponse:
    """Render the aluno's own check-in form for today.

    Pre-fills the form when a check-in for today already exists.
    """
    aluno_id = current_user(request).get("aluno_id")
    checkin = get_checkin(aluno_id, date.today()) if aluno_id is not None else None

    return templates.TemplateResponse(
        request,
        "area_aluno/checkin.html",
        {
            "checkin": checkin,
            "qualidade_opcoes": _QUALIDADE_OPCOES_DISPLAY,
            "humor_opcoes": _HUMOR_OPCOES_DISPLAY,
            "erro": None,
        },
    )


@router.post("/aluno/checkin")
async def aluno_registrar_checkin(
    request: Request,
    sono_horas: Optional[str] = Form(None),
    sono_qualidade: Optional[str] = Form(None),
    estresse: Optional[str] = Form(None),
    energia: Optional[str] = Form(None),
    humor: Optional[str] = Form(None),
    dor_local: Optional[str] = Form(None),
    dor_intensidade: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Register today's check-in for the logged-in aluno via the service
    layer; no business rules here."""
    aluno_id = current_user(request).get("aluno_id")

    try:
        registrar_checkin(
            aluno_id,
            date.today(),
            sono_horas=sono_horas,
            sono_qualidade=sono_qualidade,
            estresse=estresse,
            energia=energia,
            humor=humor,
            dor_local=dor_local,
            dor_intensidade=dor_intensidade,
            observacao=observacao,
        )
    except ValidationError as exc:
        values = {
            "sono_horas": sono_horas,
            "sono_qualidade": sono_qualidade,
            "estresse": estresse,
            "energia": energia,
            "humor": humor,
            "dor_local": dor_local,
            "dor_intensidade": dor_intensidade,
            "observacao": observacao,
        }
        return templates.TemplateResponse(
            request,
            "area_aluno/checkin.html",
            {
                "checkin": values,
                "qualidade_opcoes": _QUALIDADE_OPCOES_DISPLAY,
                "humor_opcoes": _HUMOR_OPCOES_DISPLAY,
                "erro": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/aluno", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/alunos/{aluno_id}/checkins", response_class=HTMLResponse)
async def coach_checkins(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the "Checkins" sub-tab of the student's ficha, or a 404
    page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    checkins = list_checkins(aluno_id)

    return templates.TemplateResponse(
        request,
        "checkin/ficha_checkins.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "checkins",
            "checkins": [_to_checkin_display(c) for c in checkins],
        },
    )
