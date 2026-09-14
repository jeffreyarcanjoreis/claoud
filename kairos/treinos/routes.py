"""HTTP routes (application layer) for the "treinos" domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.treinos.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).

Slice 9.1: the biblioteca de exercícios (list + create). Workouts (planilhas)
and the agenda link come in later slices.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from kairos import config
from kairos.alunos.service import get_aluno
from kairos.treinos.service import (
    FASE_LABELS,
    FASE_OPCOES,
    ValidationError,
    add_item_to_treino,
    agrupar_itens_por_fase,
    create_exercicio,
    create_treino,
    delete_treino,
    get_exercicio,
    get_item,
    get_treino,
    get_treino_detail,
    list_exercicios,
    list_treinos,
    mover_item,
    remove_exercicio_video,
    remove_item,
    set_apresentacao,
    set_exercicio_video,
    update_item,
)
from kairos.web import ficha_header, templates

router = APIRouter()

_NO_RECORD = "sem registro"

_VIDEO_MEDIA_TYPES = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
}


def _safe_next(nxt: Optional[str]) -> str:
    """Return ``nxt`` only when it is a safe, local redirect path.

    Same open-redirect guard used by the auth login flow
    (:func:`kairos.auth.routes._safe_next`): a relative path is fine, a
    protocol-relative ("//host/...") or absolute ("http://...") URL is not.
    Falls back to the exercise library when ``nxt`` is absent or unsafe.
    """
    if (
        nxt
        and nxt.startswith("/")
        and not nxt.startswith("//")
        and "://" not in nxt
    ):
        return nxt
    return "/treinos"


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
        "fase": item["fase"],
        "fase_label": item["fase_label"],
        "variacao_base": item["variacao_base"] or None,
        "variacao_regressao": item["variacao_regressao"] or None,
        "variacao_progressao": item["variacao_progressao"] or None,
        "variacao_escolhida": item["variacao_escolhida"] or None,
        "variacao_escolhida_label": item["variacao_escolhida_label"] or None,
    }


_FASE_OPCOES_DISPLAY = [(v, FASE_LABELS[v]) for v in FASE_OPCOES]


def _fases_display(detalhe: Dict[str, Any]) -> list:
    """Group a workout's items by phase, ready to print."""
    grupos = agrupar_itens_por_fase(detalhe["itens"])
    return [
        {
            "fase": g["fase"],
            "fase_label": g["fase_label"],
            "fase_pergunta": g["fase_pergunta"],
            "itens": [_to_item_display(i) for i in g["itens"]],
        }
        for g in grupos
    ]


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
            "fases": _fases_display(detalhe),
            "fase_opcoes": _FASE_OPCOES_DISPLAY,
            "apresentacao": detalhe["observacao"] or None,
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
    fase: Optional[str] = Form(None),
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
            fase=fase,
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
                "fases": _fases_display(detalhe),
                "fase_opcoes": _FASE_OPCOES_DISPLAY,
                "apresentacao": detalhe["observacao"] or None,
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


@router.post("/alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/mover")
async def move_item_route(
    request: Request,
    aluno_id: int,
    treino_id: int,
    item_id: int,
    direcao: Optional[str] = Form(None),
):
    """Move an item up/down within its phase, checking ownership (404 otherwise).

    No-op edge cases (item already first/last in its phase, or a tampered
    ``direcao``) simply redirect back without raising an error.
    """
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

    try:
        mover_item(item_id, direcao)
    except ValidationError:
        # Tampered/invalid "direcao": treat as a no-op, same as an edge move.
        pass

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/treino/{treino_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/editar",
    response_class=HTMLResponse,
)
async def edit_item_form(
    request: Request, aluno_id: int, treino_id: int, item_id: int
) -> HTMLResponse:
    """Render the edit form for a single workout item, or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    detalhe = get_treino_detail(treino_id)
    if detalhe is None or detalhe["aluno_id"] != aluno_id:
        return _aluno_nao_encontrado(request)

    item = next((i for i in detalhe["itens"] if i["id"] == item_id), None)
    if item is None:
        return _aluno_nao_encontrado(request)

    return templates.TemplateResponse(
        request,
        "treinos/item_editar.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "treino",
            "treino": {"id": detalhe["id"], "nome": detalhe["nome"]},
            "item": _to_item_display(item),
            "fase_opcoes": _FASE_OPCOES_DISPLAY,
        },
    )


@router.post("/alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}")
async def update_item_route(
    request: Request,
    aluno_id: int,
    treino_id: int,
    item_id: int,
    series: Optional[str] = Form(None),
    reps: Optional[str] = Form(None),
    carga: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    fase: Optional[str] = Form(None),
    variacao_base: Optional[str] = Form(None),
    variacao_regressao: Optional[str] = Form(None),
    variacao_progressao: Optional[str] = Form(None),
):
    """Update a workout item's prescription; delegate every rule to the service."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    detalhe = get_treino_detail(treino_id)
    if detalhe is None or detalhe["aluno_id"] != aluno_id:
        return _aluno_nao_encontrado(request)

    item = next((i for i in detalhe["itens"] if i["id"] == item_id), None)
    if item is None:
        return _aluno_nao_encontrado(request)

    try:
        update_item(
            item_id,
            series=series,
            reps=reps,
            carga=carga,
            observacao=observacao,
            fase=fase,
            variacao_base=variacao_base,
            variacao_regressao=variacao_regressao,
            variacao_progressao=variacao_progressao,
        )
    except ValidationError as exc:
        values = {
            "id": item_id,
            "exercicio_nome": item["exercicio_nome"],
            "series": series,
            "reps": reps,
            "carga": carga,
            "observacao": observacao,
            "fase": fase,
            "variacao_base": variacao_base,
            "variacao_regressao": variacao_regressao,
            "variacao_progressao": variacao_progressao,
        }
        return templates.TemplateResponse(
            request,
            "treinos/item_editar.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "treino",
                "treino": {"id": detalhe["id"], "nome": detalhe["nome"]},
                "item": values,
                "fase_opcoes": _FASE_OPCOES_DISPLAY,
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/treino/{treino_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/alunos/{aluno_id}/treino/{treino_id}/apresentacao")
async def set_apresentacao_route(
    request: Request,
    aluno_id: int,
    treino_id: int,
    apresentacao: Optional[str] = Form(None),
):
    """Set the workout's apresentacao text, checking ownership (404 otherwise)."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return _aluno_nao_encontrado(request)

    treino = get_treino(treino_id)
    if treino is None or treino["aluno_id"] != aluno_id:
        return _aluno_nao_encontrado(request)

    set_apresentacao(treino_id, apresentacao)
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


# --------------------------------------------------------------------------- #
# Vídeo de demonstração do exercício (biblioteca, não por item do treino)     #
# --------------------------------------------------------------------------- #


@router.get("/exercicios/{exercicio_id}/video")
async def exercicio_video(exercicio_id: int):
    """Serve an exercise's stored demonstration video, or a plain 404.

    404 covers every case that is not "file on disk": exercise not found,
    exercise without a video (``video_filename`` is None), and an orphaned
    ``video_filename`` whose file was removed from disk (never a 500).
    """
    exercicio = get_exercicio(exercicio_id)
    if exercicio is None or exercicio.get("video_filename") is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    filename = exercicio["video_filename"]
    path = config.videos_dir() / filename
    if not path.exists():
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = _VIDEO_MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(path, media_type=media_type)


def _render_planilha_com_video_erro(
    request: Request, aluno: Dict[str, Any], detalhe: Dict[str, Any], erro: str
) -> HTMLResponse:
    """Reexibe a planilha do treino com o erro de validação do vídeo.

    Same "reexibir com erro, 400" mechanism used everywhere else in this
    file for a :class:`ValidationError` (see ``add_item_route`` /
    ``update_item_route``): re-render the exact page the coach was on,
    passing the Portuguese message through ``error`` in the template
    context, instead of a bare redirect that would drop it silently.
    """
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
            "fases": _fases_display(detalhe),
            "fase_opcoes": _FASE_OPCOES_DISPLAY,
            "apresentacao": detalhe["observacao"] or None,
            "exercicios": list_exercicios(),
            "error": erro,
        },
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@router.post("/exercicios/{exercicio_id}/video")
async def upload_exercicio_video_route(
    request: Request,
    exercicio_id: int,
    video: UploadFile = File(...),
    aluno_id: Optional[int] = Form(None),
    treino_id: Optional[int] = Form(None),
    next: Optional[str] = Form(None),
):
    """Upload a new demonstration video for an exercise.

    Thin route: reads the raw bytes and delegates every validation rule
    (format, size) to the service layer. The video belongs to the exercise
    (biblioteca), not to a single planilha item, so this route's own path
    only carries ``exercicio_id``; the form embedded in the coach's planilha
    (``treinos/aluno_detalhe.html``) additionally sends the hidden
    ``aluno_id``/``treino_id`` it already has on that page, so a
    :class:`ValidationError` can reexibir that same planilha with the error —
    the same mechanism ``add_item_route``/``update_item_route`` use, never a
    bare redirect that would drop the message. When those hidden fields are
    absent (upload triggered from elsewhere), ``next`` — the same
    safe-redirect idiom the login flow uses
    (:func:`kairos.auth.routes._safe_next`) — decides where a successful
    upload goes, defaulting to the exercise library.
    """
    exercicio = get_exercicio(exercicio_id)
    if exercicio is None:
        return _aluno_nao_encontrado(request)

    aluno = None
    detalhe = None
    if aluno_id is not None and treino_id is not None:
        aluno = get_aluno(aluno_id)
        detalhe = get_treino_detail(treino_id)
        if aluno is None or detalhe is None or detalhe["aluno_id"] != aluno_id:
            aluno = None
            detalhe = None

    data = await video.read()
    try:
        set_exercicio_video(
            exercicio_id, data, video.content_type or "", video.filename or ""
        )
    except ValidationError as exc:
        if aluno is not None and detalhe is not None:
            return _render_planilha_com_video_erro(request, aluno, detalhe, str(exc))
        # No planilha context to reexibir into: fail closed with the
        # validation status rather than silently redirecting past the error.
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    if detalhe is not None:
        return RedirectResponse(
            url=f"/alunos/{aluno_id}/treino/{treino_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=_safe_next(next), status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/exercicios/{exercicio_id}/video/remover")
async def remove_exercicio_video_route(
    request: Request,
    exercicio_id: int,
    aluno_id: Optional[int] = Form(None),
    treino_id: Optional[int] = Form(None),
    next: Optional[str] = Form(None),
):
    """Remove an exercise's demonstration video, checking existence first."""
    exercicio = get_exercicio(exercicio_id)
    if exercicio is None:
        return _aluno_nao_encontrado(request)

    if aluno_id is not None and treino_id is not None:
        aluno = get_aluno(aluno_id)
        treino = get_treino(treino_id)
        if aluno is not None and treino is not None and treino["aluno_id"] == aluno_id:
            remove_exercicio_video(exercicio_id)
            return RedirectResponse(
                url=f"/alunos/{aluno_id}/treino/{treino_id}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    remove_exercicio_video(exercicio_id)
    return RedirectResponse(
        url=_safe_next(next), status_code=status.HTTP_303_SEE_OTHER
    )

    remove_exercicio_video(exercicio_id)
    return RedirectResponse(
        url=_safe_next(next), status_code=status.HTTP_303_SEE_OTHER
    )
