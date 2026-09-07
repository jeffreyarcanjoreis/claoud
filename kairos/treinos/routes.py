"""HTTP routes (application layer) for the "treinos" domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.treinos.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).

Slice 9.1: the biblioteca de exercícios (list + create). Workouts (planilhas)
and the agenda link come in later slices.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.alunos.service import get_aluno
from kairos.treinos.service import (
    ValidationError,
    add_item_to_treino,
    create_exercicio,
    create_treino,
    delete_treino,
    get_item,
    get_treino,
    get_treino_detail,
    list_exercicios,
    list_treinos,
    remove_item,
)
from kairos.web import ficha_header, templates

router = APIRouter()

_NO_RECORD = "sem registro"


def _aluno_nao_encontrado(request: Request) -> HTMLResponse:
    """Render the shared 404 page for an absent student or workout."""
    return templates.TemplateResponse(
        request,
        "alunos/nao_encontrado.html",
        {},
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _to_list_display(exercicio: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer exercicio dict to ready-to-print list fields."""
    return {
        "id": exercicio["id"],
        "nome": exercicio["nome"],
        "grupo_muscular": exercicio["grupo_muscular"] or _NO_RECORD,
        "observacao": exercicio["observacao"] or None,
    }


@router.get("/treinos", response_class=HTMLResponse)
async def biblioteca(request: Request) -> HTMLResponse:
    """Render the exercise library (biblioteca de exercícios)."""
    exercicios = [_to_list_display(e) for e in list_exercicios()]
    return templates.TemplateResponse(
        request,
        "treinos/exercicios_lista.html",
        {"exercicios": exercicios},
    )


@router.get("/treinos/novo", response_class=HTMLResponse)
async def new_exercicio_form(request: Request) -> HTMLResponse:
    """Render the new-exercise form."""
    return templates.TemplateResponse(
        request,
        "treinos/exercicio_form.html",
        {},
    )


@router.post("/treinos")
async def create_exercicio_route(
    request: Request,
    nome: Optional[str] = Form(None),
    grupo_muscular: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Create an exercise via the service layer; no business rules here."""
    try:
        create_exercicio(
            nome=nome,
            grupo_muscular=grupo_muscular,
            observacao=observacao,
        )
    except ValidationError as exc:
        values = {
            "nome": nome,
            "grupo_muscular": grupo_muscular,
            "observacao": observacao,
        }
        return templates.TemplateResponse(
            request,
            "treinos/exercicio_form.html",
            {"error": str(exc), "values": values},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url="/treinos",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Treino do aluno (sub-aba "Treino" da ficha)                                 #
# --------------------------------------------------------------------------- #

def _to_treino_list_display(treino: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer treino summary to ready-to-print list fields."""
    n = treino["item_count"]
    return {
        "id": treino["id"],
        "nome": treino["nome"],
        "observacao": treino["observacao"] or None,
        "item_count": n,
        "item_label": "1 exercício" if n == 1 else f"{n} exercícios",
    }


def _to_item_display(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer treino item to ready-to-print detail fields."""
    return {
        "id": item["id"],
        "exercicio_nome": item["exercicio_nome"],
        "grupo_muscular": item["grupo_muscular"] or None,
        "series": item["series"] if item["series"] is not None else _NO_RECORD,
        "reps": item["reps"] or _NO_RECORD,
        "carga": item["carga"] or _NO_RECORD,
        "observacao": item["observacao"] or None,
    }


@router.get("/alunos/{aluno_id}/treino", response_class=HTMLResponse)
async def aluno_treinos(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the student's "Treino" sub-tab: their workouts, or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    treinos = [_to_treino_list_display(t) for t in list_treinos(aluno_id)]
    return templates.TemplateResponse(
        request,
        "treinos/aluno_lista.html",
        {"aluno": ficha_header(aluno), "subtab": "treino", "treinos": treinos},
    )


# Declared before "/alunos/{aluno_id}/treino/{treino_id}": the literal "novo"
# segment must win over the parameterized one (route registration order).
@router.get("/alunos/{aluno_id}/treino/novo", response_class=HTMLResponse)
async def new_treino_form(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the new-workout form, or a 404 page when the student is absent."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    return templates.TemplateResponse(
        request,
        "treinos/aluno_novo.html",
        {"aluno": ficha_header(aluno), "subtab": "treino"},
    )


@router.post("/alunos/{aluno_id}/treino")
async def create_treino_route(
    request: Request,
    aluno_id: int,
    nome: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Create a workout via the service layer; redirect to its detail page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    try:
        treino = create_treino(aluno_id, nome=nome, observacao=observacao)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "treinos/aluno_novo.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "treino",
                "error": str(exc),
                "values": {"nome": nome, "observacao": observacao},
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/treino/{treino['id']}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/alunos/{aluno_id}/treino/{treino_id}", response_class=HTMLResponse)
async def treino_detail(
    request: Request, aluno_id: int, treino_id: int
) -> HTMLResponse:
    """Render a workout's planilha (its exercises) plus the add-exercise form."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    detalhe = get_treino_detail(treino_id)
    if detalhe is None or detalhe["aluno_id"] != aluno_id:
        # Also blocks reaching another student's workout via the URL.
        return _aluno_nao_encontrado(request)

    return templates.TemplateResponse(
        request,
        "treinos/aluno_detalhe.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "treino",
            "treino": {
                "id": detalhe["id"],
                "nome": detalhe["nome"],
                "observacao": detalhe["observacao"] or None,
            },
            "itens": [_to_item_display(i) for i in detalhe["itens"]],
            "exercicios": list_exercicios(),
        },
    )


@router.post("/alunos/{aluno_id}/treino/{treino_id}/itens")
async def add_item_route(
    request: Request,
    aluno_id: int,
    treino_id: int,
    exercicio_id: Optional[str] = Form(None),
    series: Optional[str] = Form(None),
    reps: Optional[str] = Form(None),
    carga: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Add an exercise to the workout; delegate every rule to the service."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    detalhe = get_treino_detail(treino_id)
    if detalhe is None or detalhe["aluno_id"] != aluno_id:
        return _aluno_nao_encontrado(request)

    try:
        add_item_to_treino(
            treino_id,
            exercicio_id=exercicio_id,
            series=series,
            reps=reps,
            carga=carga,
            observacao=observacao,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "treinos/aluno_detalhe.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "treino",
                "treino": {
                    "id": detalhe["id"],
                    "nome": detalhe["nome"],
                    "observacao": detalhe["observacao"] or None,
                },
                "itens": [_to_item_display(i) for i in detalhe["itens"]],
                "exercicios": list_exercicios(),
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/treino/{treino_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/remover")
async def remove_item_route(
    request: Request, aluno_id: int, treino_id: int, item_id: int
):
    """Remove an exercise from the workout, checking ownership (404 otherwise)."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    treino = get_treino(treino_id)
    item = get_item(item_id)
    if (
        treino is None
        or treino["aluno_id"] != aluno_id
        or item is None
        or item["treino_id"] != treino_id
    ):
        return _aluno_nao_encontrado(request)

    remove_item(item_id)
    return RedirectResponse(
        url=f"/alunos/{aluno_id}/treino/{treino_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/alunos/{aluno_id}/treino/{treino_id}/apagar")
async def delete_treino_route(
    request: Request, aluno_id: int, treino_id: int
):
    """Delete a whole workout, checking ownership (404 otherwise)."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    treino = get_treino(treino_id)
    if treino is None or treino["aluno_id"] != aluno_id:
        return _aluno_nao_encontrado(request)

    delete_treino(treino_id)
    return RedirectResponse(
        url=f"/alunos/{aluno_id}/treino",
        status_code=status.HTTP_303_SEE_OTHER,
    )
