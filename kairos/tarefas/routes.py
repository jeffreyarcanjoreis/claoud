"""HTTP routes (application layer) for the "tarefas" (coach's task list)
domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.tarefas.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).
"""

from typing import Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from kairos.painel.routes import inicio_context
from kairos.tarefas.service import (
    ValidationError,
    concluir_tarefa,
    create_tarefa,
    get_tarefa,
    remover_tarefa,
)
from kairos.web import templates

router = APIRouter()


def _quer_json(request: Request) -> bool:
    """Whether the client expects a JSON response instead of a full page
    render — used by the Início's tasks modal (AJAX), while keeping the
    plain-HTML fallback (no JS) unchanged."""
    accept = request.headers.get("accept", "")
    requested_with = request.headers.get("x-requested-with", "")
    return "application/json" in accept or requested_with in (
        "fetch",
        "XMLHttpRequest",
    )


@router.post("/tarefas")
async def create_tarefa_route(
    request: Request,
    titulo: Optional[str] = Form(None),
    categoria: Optional[str] = Form(None),
    prazo: Optional[str] = Form(None),
):
    """Create a task via the service layer; no business rules here."""
    try:
        create_tarefa(titulo=titulo, categoria=categoria, prazo=prazo)
    except ValidationError as exc:
        if _quer_json(request):
            return JSONResponse(
                {"ok": False, "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        values = {"titulo": titulo, "categoria": categoria, "prazo": prazo}
        return templates.TemplateResponse(
            request,
            "painel/inicio.html",
            inicio_context(tarefa_error=str(exc), tarefa_values=values),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if _quer_json(request):
        return JSONResponse({"ok": True})

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/tarefas/{tarefa_id}/concluir")
async def concluir_tarefa_route(request: Request, tarefa_id: int):
    """Mark a task as completed via the service layer, or a 404 page when it
    does not exist."""
    if get_tarefa(tarefa_id) is None:
        if _quer_json(request):
            return JSONResponse(
                {"ok": False, "error": "Tarefa não encontrada."},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    concluir_tarefa(tarefa_id)

    if _quer_json(request):
        return JSONResponse({"ok": True})

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/tarefas/{tarefa_id}/remover")
async def remover_tarefa_route(request: Request, tarefa_id: int):
    """Remove a task via the service layer, or a 404 page when it does not
    exist."""
    if get_tarefa(tarefa_id) is None:
        if _quer_json(request):
            return JSONResponse(
                {"ok": False, "error": "Tarefa não encontrada."},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    remover_tarefa(tarefa_id)

    if _quer_json(request):
        return JSONResponse({"ok": True})

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
