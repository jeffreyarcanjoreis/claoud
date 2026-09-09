"""HTTP routes (application layer) for the "registro_treino" (student
post-workout log) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.registro_treino.service`, and render templates. Displayed texts
are in Portuguese (architecture rule 10).

Only the aluno's own side exists here (``/aluno/registro``): ``aluno_id``
always comes from the session (never from the URL), matching the isolation
rule used throughout :mod:`kairos.area_aluno.routes` and
:mod:`kairos.checkin.routes`.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.auth.middleware import current_user
from kairos.registro_treino.service import (
    SENSACAO_LABELS,
    SENSACAO_OPCOES,
    ValidationError,
    list_registros,
    registrar,
)
from kairos.treinos.service import list_treinos
from kairos.web import templates

router = APIRouter()

_SENSACAO_OPCOES_DISPLAY = [(valor, SENSACAO_LABELS[valor]) for valor in SENSACAO_OPCOES]


def _to_display(r: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer registro dict to ready-to-print list fields."""
    return {
        "id": r["id"],
        "data": r["data"].strftime("%d/%m/%Y"),
        "treino_nome": r["treino_nome"],
        "rpe": r["rpe"],
        "sensacao_label": r["sensacao_label"],
        "o_que_mudou": r["o_que_mudou"],
        "dor_nova": r["dor_nova"],
    }


@router.get("/aluno/registro", response_class=HTMLResponse)
async def aluno_registro(request: Request) -> HTMLResponse:
    """Render the aluno's own post-workout log form and history."""
    aluno_id = current_user(request).get("aluno_id")

    registros = [_to_display(r) for r in list_registros(aluno_id)] if aluno_id else []
    treinos = (
        [(t["id"], t["nome"]) for t in list_treinos(aluno_id)] if aluno_id else []
    )

    return templates.TemplateResponse(
        request,
        "area_aluno/registro.html",
        {
            "registros": registros,
            "treinos": treinos,
            "sensacao_opcoes": _SENSACAO_OPCOES_DISPLAY,
            "erro": None,
            "valores": None,
        },
    )


@router.post("/aluno/registro")
async def aluno_registrar(
    request: Request,
    treino_id: Optional[str] = Form(None),
    rpe: Optional[str] = Form(None),
    sensacao: Optional[str] = Form(None),
    o_que_mudou: Optional[str] = Form(None),
    dor_nova: Optional[str] = Form(None),
):
    """Register a post-workout log for the logged-in aluno via the service
    layer; no business rules here."""
    aluno_id = current_user(request).get("aluno_id")

    try:
        registrar(
            aluno_id,
            treino_id=treino_id,
            rpe=rpe,
            sensacao=sensacao,
            o_que_mudou=o_que_mudou,
            dor_nova=dor_nova,
        )
    except ValidationError as exc:
        valores = {
            "treino_id": treino_id,
            "rpe": rpe,
            "sensacao": sensacao,
            "o_que_mudou": o_que_mudou,
            "dor_nova": dor_nova,
        }
        registros = [_to_display(r) for r in list_registros(aluno_id)] if aluno_id else []
        treinos = (
            [(t["id"], t["nome"]) for t in list_treinos(aluno_id)] if aluno_id else []
        )
        return templates.TemplateResponse(
            request,
            "area_aluno/registro.html",
            {
                "registros": registros,
                "treinos": treinos,
                "sensacao_opcoes": _SENSACAO_OPCOES_DISPLAY,
                "erro": str(exc),
                "valores": valores,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/aluno/registro", status_code=status.HTTP_303_SEE_OTHER)
