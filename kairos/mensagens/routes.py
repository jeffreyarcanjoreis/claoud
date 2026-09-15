"""HTTP routes (application layer) for the "mensagens" (student-coach
messaging) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.mensagens.service`, and render templates. Displayed texts are
in Portuguese (architecture rule 10).

Two sides share the same conversation:

- The aluno's own side (``/aluno/mensagens``) always resolves ``aluno_id``
  from the session (never from the URL), matching the isolation rule used
  throughout :mod:`kairos.area_aluno.routes`.
- The coach's side (``/alunos/{aluno_id}/mensagens``) takes ``aluno_id``
  from the URL, since the coach manages every aluno's conversation, and
  follows the get-or-404 + ``ficha_header``/``subtab`` pattern used
  throughout :mod:`kairos.acompanhamento.routes`.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.alunos.service import get_aluno
from kairos.auth.middleware import current_user
from kairos.mensagens.service import (
    ValidationError,
    contar_nao_lidas,
    enviar_mensagem,
    listar_conversa,
    marcar_lidas,
)
from kairos.web import ficha_header, templates

router = APIRouter()


def _to_msg_display(m: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer mensagem dict to ready-to-print display fields."""
    return {
        "autor": m["autor"],
        "texto": m["texto"],
        "data": m["created_at"].strftime("%d/%m/%Y %H:%M"),
    }


@router.get("/aluno/mensagens", response_class=HTMLResponse)
async def aluno_mensagens(request: Request) -> HTMLResponse:
    """Render the aluno's own conversation with the coach.

    Tolerant of a session whose aluno_id no longer resolves (or is absent):
    renders an empty conversation instead of breaking.
    """
    aluno_id = current_user(request).get("aluno_id")
    mensagens = []
    if aluno_id is not None:
        marcar_lidas(aluno_id, "aluno")
        mensagens = listar_conversa(aluno_id)

    return templates.TemplateResponse(
        request,
        "area_aluno/mensagens.html",
        {
            "mensagens": [_to_msg_display(m) for m in mensagens],
            "erro": None,
        },
    )


@router.post("/aluno/mensagens")
async def aluno_enviar_mensagem(request: Request, texto: Optional[str] = Form(None)):
    """Send a message as the aluno via the service layer; no business rules
    here."""
    aluno_id = current_user(request).get("aluno_id")

    try:
        enviar_mensagem(aluno_id, "aluno", texto)
    except ValidationError as exc:
        mensagens = listar_conversa(aluno_id) if aluno_id is not None else []
        return templates.TemplateResponse(
            request,
            "area_aluno/mensagens.html",
            {
                "mensagens": [_to_msg_display(m) for m in mensagens],
                "erro": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/aluno/mensagens", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/alunos/{aluno_id}/mensagens", response_class=HTMLResponse)
async def coach_mensagens(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the "Mensagens" sub-tab of the student's ficha, or a 404
    page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    marcar_lidas(aluno_id, "coach")
    mensagens = listar_conversa(aluno_id)

    return templates.TemplateResponse(
        request,
        "mensagens/ficha_mensagens.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "mensagens",
            "mensagens": [_to_msg_display(m) for m in mensagens],
            "erro": None,
        },
    )


@router.post("/alunos/{aluno_id}/mensagens")
async def coach_enviar_mensagem(
    request: Request, aluno_id: int, texto: Optional[str] = Form(None)
):
    """Send a message as the coach via the service layer; no business rules
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
        enviar_mensagem(aluno_id, "coach", texto)
    except ValidationError as exc:
        mensagens = listar_conversa(aluno_id)
        return templates.TemplateResponse(
            request,
            "mensagens/ficha_mensagens.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "mensagens",
                "mensagens": [_to_msg_display(m) for m in mensagens],
                "erro": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/mensagens", status_code=status.HTTP_303_SEE_OTHER
    )
