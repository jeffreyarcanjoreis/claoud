"""HTTP routes (application layer) for the "contatos" (lightweight contact
follow-up) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.contatos.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# Aliased so it never shadows this module's own ValidationError: the two
# domains raise distinct exception classes (contatos vs alunos rules).
from kairos.alunos.service import ValidationError as AlunoValidationError
from kairos.contatos.service import (
    FREQUENCIA_LABELS,
    FREQUENCIA_OPCOES,
    NIVEIS_CONDICIONAMENTO,
    NIVEL_LABELS,
    SEXO_LABELS,
    SEXO_OPCOES,
    AlunoDuplicado,
    ValidationError,
    atualizar_status,
    converter_contato_em_aluno,
    create_cadastro,
    create_contato,
    get_contato,
    get_contato_detail,
    remover_contato,
)
from kairos.painel.routes import inicio_context
from kairos.web import templates

logger = logging.getLogger(__name__)

router = APIRouter()


def cadastro_opcoes_context() -> dict:
    """Fixed-option lists for the sign-up form's selects, in display order."""
    return {
        "sexo_opcoes": [(v, SEXO_LABELS[v]) for v in SEXO_OPCOES],
        "niveis": [(v, NIVEL_LABELS[v]) for v in NIVEIS_CONDICIONAMENTO],
        "frequencias": [(v, FREQUENCIA_LABELS[v]) for v in FREQUENCIA_OPCOES],
    }


def _quer_json(request: Request) -> bool:
    """Whether the client expects a JSON response instead of a full page
    render — used by the sign-up form's AJAX (modal) submission path, while
    keeping the plain-HTML fallback (no JS) unchanged."""
    accept = request.headers.get("accept", "")
    requested_with = request.headers.get("x-requested-with", "")
    return "application/json" in accept or requested_with in (
        "fetch",
        "XMLHttpRequest",
    )


@router.get("/comecar", response_class=HTMLResponse)
async def cadastro_form(request: Request) -> HTMLResponse:
    """Render the native public sign-up page (replaces the Google Form)."""
    context = {
        "enviado": False,
        "error": None,
        "values": None,
        **cadastro_opcoes_context(),
    }
    return templates.TemplateResponse(request, "contatos/cadastro.html", context)


@router.post("/comecar")
async def cadastro_submit(
    request: Request,
    nome: Optional[str] = Form(None),
    contato: Optional[str] = Form(None),
    idade: Optional[str] = Form(None),
    sexo: Optional[str] = Form(None),
    objetivo: Optional[str] = Form(None),
    objetivos_secundarios: Optional[str] = Form(None),
    prazo_desejado: Optional[str] = Form(None),
    frequencia_desejada: Optional[str] = Form(None),
    condicoes: Optional[str] = Form(None),
    lesoes: Optional[str] = Form(None),
    medicamentos: Optional[str] = Form(None),
    nivel_condicionamento: Optional[str] = Form(None),
    consentimento: Optional[str] = Form(None),
):
    """Handle the native public sign-up submission; delegates every rule to
    the service layer (including the consent requirement)."""
    consent_bool = consentimento is not None

    try:
        create_cadastro(
            nome=nome,
            contato=contato,
            idade=idade,
            sexo=sexo,
            objetivo=objetivo,
            objetivos_secundarios=objetivos_secundarios,
            prazo_desejado=prazo_desejado,
            frequencia_desejada=frequencia_desejada,
            condicoes=condicoes,
            lesoes=lesoes,
            medicamentos=medicamentos,
            nivel_condicionamento=nivel_condicionamento,
            consentimento=consent_bool,
        )
    except ValidationError as exc:
        if _quer_json(request):
            return JSONResponse(
                {"ok": False, "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        values = {
            "nome": nome,
            "contato": contato,
            "idade": idade,
            "sexo": sexo,
            "objetivo": objetivo,
            "objetivos_secundarios": objetivos_secundarios,
            "prazo_desejado": prazo_desejado,
            "frequencia_desejada": frequencia_desejada,
            "condicoes": condicoes,
            "lesoes": lesoes,
            "medicamentos": medicamentos,
            "nivel_condicionamento": nivel_condicionamento,
            "consentimento": consentimento,
        }
        context = {
            "enviado": False,
            "error": str(exc),
            "values": values,
            **cadastro_opcoes_context(),
        }
        return templates.TemplateResponse(
            request,
            "contatos/cadastro.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if _quer_json(request):
        return JSONResponse({"ok": True})

    return templates.TemplateResponse(
        request,
        "contatos/cadastro.html",
        {"enviado": True, "error": None, "values": None},
    )


@router.get("/contatos/{contato_id}", response_class=HTMLResponse)
async def contato_detalhe(request: Request, contato_id: int) -> HTMLResponse:
    """Render a lead's full profile (panel view), or a 404 page when it does
    not exist."""
    detail = get_contato_detail(contato_id)
    if detail is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request, "contatos/lead_detalhe.html", {"lead": detail}
    )


@router.post("/contatos")
async def create_contato_route(
    request: Request,
    nome: Optional[str] = Form(None),
    contato: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Create a contact via the service layer; no business rules here."""
    try:
        create_contato(nome=nome, contato=contato, observacao=observacao)
    except ValidationError as exc:
        values = {"nome": nome, "contato": contato, "observacao": observacao}
        return templates.TemplateResponse(
            request,
            "painel/inicio.html",
            inicio_context(contato_error=str(exc), contato_values=values),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/contatos/{contato_id}/status")
async def atualizar_status_route(
    request: Request, contato_id: int, status_: str = Form(..., alias="status")
):
    """Update a contact's status via the service layer, or a 404 page when
    it does not exist."""
    if get_contato(contato_id) is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        atualizar_status(contato_id, status_)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "painel/inicio.html",
            inicio_context(contato_error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/contatos/{contato_id}/remover")
async def remover_contato_route(request: Request, contato_id: int):
    """Remove a contact via the service layer, or a 404 page when it does
    not exist."""
    if get_contato(contato_id) is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    remover_contato(contato_id)

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/contatos/{contato_id}/converter")
async def converter_contato_route(
    request: Request, contato_id: int, force: Optional[str] = Form(None)
):
    """Convert a lead into a student via the service layer, or a 404 page
    when the lead does not exist.

    ``force`` is a plain checkbox-style field: present (any value) means the
    coach confirmed the conversion despite an existing Aluno with the same
    name (see ``AlunoDuplicado`` below); absent means the normal duplicate
    check applies.

    ``converter_contato_em_aluno`` delegates the Aluno creation to
    ``kairos.alunos.service.create_aluno`` internally, which can in theory
    raise its own ``ValidationError`` (a distinct class from this domain's).
    A lead that reached this point went through the sign-up/manual-add
    validation already, so that should never happen in practice; caught
    here only as a defensive measure (architecture rule 8 — never a
    silently swallowed error, never a 500 either), sending the coach back
    to the lead's own detail page with the failure logged.
    """
    force_bool = force is not None

    try:
        aluno_id = converter_contato_em_aluno(contato_id, force=force_bool)
    except AlunoValidationError as exc:
        logger.error(
            "Contato-to-Aluno conversion failed: contato_id=%s error=%s",
            contato_id,
            exc,
        )
        return RedirectResponse(
            url=f"/contatos/{contato_id}", status_code=status.HTTP_303_SEE_OTHER
        )
    except AlunoDuplicado as dup:
        detail = get_contato_detail(contato_id)
        return templates.TemplateResponse(
            request,
            "contatos/lead_detalhe.html",
            {
                "lead": detail,
                "duplicado": {
                    "aluno_existente_id": dup.aluno_existente_id,
                    "aluno_existente_nome": dup.aluno_existente_nome,
                },
            },
        )

    if aluno_id is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}", status_code=status.HTTP_303_SEE_OTHER
    )
