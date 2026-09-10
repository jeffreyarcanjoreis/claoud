"""HTTP routes (application layer) for the "nivel" (student self-recognized
level) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.nivel.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).

Only the aluno's own side exists here: ``aluno_id`` is always resolved from
the session (never from the URL), matching the isolation rule used
throughout :mod:`kairos.registro_treino.routes`.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.alunos.service import get_aluno
from kairos.auth.middleware import current_user
from kairos.nivel.service import (
    NIVEL_DESCRICOES,
    NIVEL_LABELS,
    NIVEL_OPCOES,
    ValidationError,
    list_reconhecimentos,
    nivel_atual,
    reconhecer,
)
from kairos.web import templates

router = APIRouter()

_NIVEL_OPCOES_DISPLAY = [
    (v, NIVEL_LABELS[v], NIVEL_DESCRICOES[v]) for v in NIVEL_OPCOES
]


def _to_reconhecimento_display(r: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer reconhecimento dict to ready-to-print display
    fields."""
    return {
        "data": r["created_at"].strftime("%d/%m/%Y"),
        "nivel_label": r["nivel_label"],
        "nota": r["nota"],
    }


def _reconhecimentos_display(aluno_id: Optional[int]) -> List[Dict[str, Any]]:
    """Return the logged-in aluno's own self-recognition history as
    ready-to-print display dicts, or an empty list when there is no session
    aluno."""
    if aluno_id is None:
        return []
    return [_to_reconhecimento_display(r) for r in list_reconhecimentos(aluno_id)]


@router.get("/aluno/nivel", response_class=HTMLResponse)
async def aluno_nivel(request: Request) -> HTMLResponse:
    """Render the aluno's own self-recognition form and history."""
    aluno_id = current_user(request).get("aluno_id")

    aluno = get_aluno(aluno_id) if aluno_id else None
    atual = nivel_atual(aluno_id) if aluno_id else None

    return templates.TemplateResponse(
        request,
        "area_aluno/nivel.html",
        {
            "frente_label": aluno["frente_label"] if aluno else None,
            "frente_significado": aluno["frente_significado"] if aluno else None,
            "nivel_opcoes": _NIVEL_OPCOES_DISPLAY,
            "nivel_atual_valor": atual["nivel"] if atual else None,
            "reconhecimentos": _reconhecimentos_display(aluno_id),
            "nota_valor": None,
            "erro": None,
        },
    )


@router.post("/aluno/nivel")
async def aluno_reconhecer(
    request: Request,
    nivel: Optional[str] = Form(None),
    nota: Optional[str] = Form(None),
):
    """Record a new self-recognition of level for the logged-in aluno via the
    service layer; no business rules here."""
    aluno_id = current_user(request).get("aluno_id")

    try:
        reconhecer(aluno_id, nivel=nivel, nota=nota)
    except ValidationError as exc:
        aluno = get_aluno(aluno_id) if aluno_id else None
        return templates.TemplateResponse(
            request,
            "area_aluno/nivel.html",
            {
                "frente_label": aluno["frente_label"] if aluno else None,
                "frente_significado": aluno["frente_significado"] if aluno else None,
                "nivel_opcoes": _NIVEL_OPCOES_DISPLAY,
                "nivel_atual_valor": nivel,
                "reconhecimentos": _reconhecimentos_display(aluno_id),
                "nota_valor": nota,
                "erro": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/aluno/nivel", status_code=status.HTTP_303_SEE_OTHER)
