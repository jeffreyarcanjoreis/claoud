"""HTTP routes (application layer) for the "alunos" (students) domain.

Thin routes only: they collect form data, delegate every business rule to
:mod:`kairos.alunos.service`, and render templates. Displayed texts are in
Portuguese (architecture rule 10).
"""

import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from kairos import config
from kairos.alunos.fotos import delete_foto_file, save_foto
from kairos.alunos.service import (
    FRENTE_LABELS,
    FRENTE_OPCOES,
    ValidationError,
    aluno_tem_historico,
    arquivar_aluno,
    create_aluno,
    excluir_aluno,
    get_aluno,
    list_alunos,
    reativar_aluno,
    set_aluno_foto,
    set_frente,
    update_aluno,
)
from kairos.auth.service import get_perfil_by_aluno
from kairos.auth.tokens import MAX_AGE_SEGUNDOS, gerar_token_ativacao
from kairos.mensagens.service import alunos_com_nao_lidas
from kairos.web import templates

router = APIRouter()

_NO_RECORD = "sem registro"

_FOTO_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

_STATUS_LABELS = {"active": "Ativo", "inactive": "Inativo"}
_STATUS_CLASSES = {"active": "badge-active", "inactive": "badge-inactive"}

_FRENTE_OPCOES_DISPLAY = [(v, FRENTE_LABELS[v]) for v in FRENTE_OPCOES]


def _format_date(value: Optional[datetime.date]) -> str:
    """Format a date as "DD/MM/AAAA", or "sem registro" when absent."""
    if value is None:
        return _NO_RECORD
    return value.strftime("%d/%m/%Y")


def _format_period(
    start: Optional[datetime.date], end: Optional[datetime.date]
) -> str:
    """Build the plan period text (architecture rule 6).

    Both dates absent -> a single "sem registro"; otherwise each side shows
    its date or "sem registro" in its place.
    """
    if start is None and end is None:
        return _NO_RECORD
    return f"{_format_date(start)} → {_format_date(end)}"


def _format_datetime(value: Optional[datetime.datetime]) -> str:
    """Format a datetime as "DD/MM/AAAA HH:MM", or "sem registro" when absent."""
    if value is None:
        return _NO_RECORD
    return value.strftime("%d/%m/%Y %H:%M")


def _format_age(age: Optional[int]) -> str:
    """Format an age in years as "N anos", or "sem registro" when absent."""
    if age is None:
        return _NO_RECORD
    return f"{age} anos"


def _to_display(aluno: Dict[str, Any], msgs_nao_lidas: int = 0) -> Dict[str, Any]:
    """Map a service-layer aluno dict to ready-to-print display fields."""
    return {
        "id": aluno["id"],
        "name": aluno["name"],
        "objective_display": aluno["objective"] or _NO_RECORD,
        "status_label": _STATUS_LABELS.get(aluno["status"], aluno["status"]),
        "status_class": _STATUS_CLASSES.get(aluno["status"], "badge-inactive"),
        "period_display": _format_period(aluno["plan_start"], aluno["plan_end"]),
        "msgs_nao_lidas": msgs_nao_lidas,
    }


def _to_profile_display(aluno: Dict[str, Any]) -> Dict[str, str]:
    """Map a service-layer aluno dict to ready-to-print profile fields.

    Every field arrives at the template as a finished string: empty values
    become "sem registro", dates become "DD/MM/AAAA" and the age becomes
    "N anos" (thin-client templates, architecture rule 10).
    """
    return {
        "id": aluno["id"],
        "name": aluno["name"],
        "status": aluno["status"],
        "status_label": _STATUS_LABELS.get(aluno["status"], aluno["status"]),
        "status_class": _STATUS_CLASSES.get(aluno["status"], "badge-inactive"),
        "birth_date_display": _format_date(aluno["birth_date"]),
        "age_display": _format_age(aluno["age"]),
        "objective_display": aluno["objective"] or _NO_RECORD,
        "phase_display": aluno["phase"] or _NO_RECORD,
        "plan_start_display": _format_date(aluno["plan_start"]),
        "plan_end_display": _format_date(aluno["plan_end"]),
        "restrictions_display": aluno["restrictions"] or _NO_RECORD,
        "alert_display": aluno["alert"] or _NO_RECORD,
        "notes_display": aluno["notes"] or _NO_RECORD,
        "created_at_display": _format_datetime(aluno["created_at"]),
        "foto": aluno.get("foto"),
        "contact_display": aluno.get("contact") or _NO_RECORD,
        "email_display": aluno.get("email") or _NO_RECORD,
        "sex_label": aluno.get("sex_label") or _NO_RECORD,
        "age_reported_display": _format_age(aluno.get("age_reported")),
        "weekly_frequency_label": aluno.get("weekly_frequency_label") or _NO_RECORD,
        "conditioning_label": aluno.get("conditioning_label") or _NO_RECORD,
        "health_conditions_display": aluno.get("health_conditions") or _NO_RECORD,
        "medications_display": aluno.get("medications") or _NO_RECORD,
        "frente": aluno.get("frente") or "",
        "frente_label": aluno.get("frente_label") or _NO_RECORD,
        "frente_significado": aluno.get("frente_significado") or "",
    }


@router.get("/alunos", response_class=HTMLResponse)
async def list_alunos_route(
    request: Request, criado: Optional[str] = None, status: Optional[str] = None
) -> HTMLResponse:
    """Render the student list, with a success message after creation.

    An optional ``status`` query param filters the list; any value other
    than "active"/"inactive" is ignored by the service layer (defensive,
    never a 500).
    """
    nao_lidas = alunos_com_nao_lidas()
    context: dict = {
        "alunos": [
            _to_display(aluno, nao_lidas.get(aluno["id"], 0))
            for aluno in list_alunos(status=status)
        ],
        "current_filter": status,
    }
    if criado is not None:
        context["success"] = f"Aluno {criado} cadastrado."
    return templates.TemplateResponse(request, "alunos/lista.html", context)


@router.get("/alunos/novo", response_class=HTMLResponse)
async def new_aluno_form(request: Request) -> HTMLResponse:
    """Render the new student form."""
    return templates.TemplateResponse(
        request,
        "alunos/novo.html",
        {"action": "/alunos", "submit_label": "Cadastrar"},
    )


@router.post("/alunos")
async def create_aluno_route(
    request: Request,
    name: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    objective: Optional[str] = Form(None),
    phase: Optional[str] = Form(None),
    plan_start: Optional[str] = Form(None),
    plan_end: Optional[str] = Form(None),
    restrictions: Optional[str] = Form(None),
    alert: Optional[str] = Form(None),
    status_field: Optional[str] = Form(None, alias="status"),
    notes: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    sex: Optional[str] = Form(None),
    age_reported: Optional[str] = Form(None),
    weekly_frequency: Optional[str] = Form(None),
    conditioning_level: Optional[str] = Form(None),
    health_conditions: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
):
    """Create a student via the service layer; no business rules here."""
    try:
        aluno = create_aluno(
            name=name,
            birth_date=birth_date,
            objective=objective,
            phase=phase,
            plan_start=plan_start,
            plan_end=plan_end,
            restrictions=restrictions,
            alert=alert,
            status=status_field,
            notes=notes,
            contact=contact,
            email=email,
            sex=sex,
            age_reported=age_reported,
            weekly_frequency=weekly_frequency,
            conditioning_level=conditioning_level,
            health_conditions=health_conditions,
            medications=medications,
        )
    except ValidationError as exc:
        values = {
            "name": name,
            "birth_date": birth_date,
            "objective": objective,
            "phase": phase,
            "plan_start": plan_start,
            "plan_end": plan_end,
            "restrictions": restrictions,
            "alert": alert,
            "status": status_field,
            "notes": notes,
            "contact": contact,
            "email": email,
            "sex": sex,
            "age_reported": age_reported,
            "weekly_frequency": weekly_frequency,
            "conditioning_level": conditioning_level,
            "health_conditions": health_conditions,
            "medications": medications,
        }
        return templates.TemplateResponse(
            request,
            "alunos/novo.html",
            {
                "error": str(exc),
                "values": values,
                "action": "/alunos",
                "submit_label": "Cadastrar",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos?criado={quote(aluno['name'])}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _to_edit_values(aluno: Dict[str, Any]) -> Dict[str, str]:
    """Map a service-layer aluno dict to form values for the edit form.

    Date fields must be ISO "YYYY-MM-DD" strings (what a ``type=date`` input
    expects); the remaining fields are passed through as-is (or "").
    """
    return {
        "name": aluno["name"] or "",
        "birth_date": aluno["birth_date"].isoformat() if aluno["birth_date"] else "",
        "objective": aluno["objective"] or "",
        "phase": aluno["phase"] or "",
        "plan_start": aluno["plan_start"].isoformat() if aluno["plan_start"] else "",
        "plan_end": aluno["plan_end"].isoformat() if aluno["plan_end"] else "",
        "restrictions": aluno["restrictions"] or "",
        "alert": aluno["alert"] or "",
        "status": aluno["status"] or "",
        "notes": aluno["notes"] or "",
        "contact": aluno.get("contact") or "",
        "email": aluno.get("email") or "",
        "sex": aluno.get("sex") or "",
        "age_reported": (
            str(aluno["age_reported"]) if aluno.get("age_reported") is not None else ""
        ),
        "weekly_frequency": aluno.get("weekly_frequency") or "",
        "conditioning_level": aluno.get("conditioning_level") or "",
        "health_conditions": aluno.get("health_conditions") or "",
        "medications": aluno.get("medications") or "",
    }


# Declared after /alunos/novo so the literal route wins over the
# parameterized one (route registration order matters in FastAPI). This
# route has an extra path segment ("/editar"), so it never collides with
# /alunos/{aluno_id} regardless of order, but it is kept here for clarity.
@router.get("/alunos/{aluno_id}/editar", response_class=HTMLResponse)
async def edit_aluno_form(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the edit form pre-filled with the student's current values."""
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
        "alunos/editar.html",
        {
            "aluno_id": aluno_id,
            "values": _to_edit_values(aluno),
            "action": f"/alunos/{aluno_id}",
            "submit_label": "Salvar",
            "show_foto": True,
            "has_foto": bool(aluno["foto"]),
        },
    )


@router.post("/alunos/{aluno_id}")
async def update_aluno_route(
    request: Request,
    aluno_id: int,
    name: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    objective: Optional[str] = Form(None),
    phase: Optional[str] = Form(None),
    plan_start: Optional[str] = Form(None),
    plan_end: Optional[str] = Form(None),
    restrictions: Optional[str] = Form(None),
    alert: Optional[str] = Form(None),
    status_field: Optional[str] = Form(None, alias="status"),
    notes: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    sex: Optional[str] = Form(None),
    age_reported: Optional[str] = Form(None),
    weekly_frequency: Optional[str] = Form(None),
    conditioning_level: Optional[str] = Form(None),
    health_conditions: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    remover_foto: Optional[str] = Form(None),
):
    """Update a student via the service layer; no business rules here.

    Applies the photo (new upload, removal or unchanged) atomically with the
    text fields: a validation error on either side leaves nothing written
    (a photo already saved to disk on a failed text update is rolled back).
    """
    aluno0 = get_aluno(aluno_id)
    if aluno0 is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    old_foto = aluno0["foto"]
    has_foto = bool(old_foto)

    values = {
        "name": name,
        "birth_date": birth_date,
        "objective": objective,
        "phase": phase,
        "plan_start": plan_start,
        "plan_end": plan_end,
        "restrictions": restrictions,
        "alert": alert,
        "status": status_field,
        "notes": notes,
        "contact": contact,
        "email": email,
        "sex": sex,
        "age_reported": age_reported,
        "weekly_frequency": weekly_frequency,
        "conditioning_level": conditioning_level,
        "health_conditions": health_conditions,
        "medications": medications,
    }

    new_foto = None
    uploaded = foto is not None and bool(foto.filename)
    if uploaded:
        data = await foto.read()
        try:
            new_foto = save_foto(data, foto.content_type or "", foto.filename)
        except ValidationError as exc:
            return templates.TemplateResponse(
                request,
                "alunos/editar.html",
                {
                    "aluno_id": aluno_id,
                    "error": str(exc),
                    "values": values,
                    "action": f"/alunos/{aluno_id}",
                    "submit_label": "Salvar",
                    "show_foto": True,
                    "has_foto": has_foto,
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    try:
        aluno = update_aluno(
            aluno_id,
            name=name,
            birth_date=birth_date,
            objective=objective,
            phase=phase,
            plan_start=plan_start,
            plan_end=plan_end,
            restrictions=restrictions,
            alert=alert,
            status=status_field,
            notes=notes,
            contact=contact,
            email=email,
            sex=sex,
            age_reported=age_reported,
            weekly_frequency=weekly_frequency,
            conditioning_level=conditioning_level,
            health_conditions=health_conditions,
            medications=medications,
        )
    except ValidationError as exc:
        if new_foto:
            delete_foto_file(new_foto)
        return templates.TemplateResponse(
            request,
            "alunos/editar.html",
            {
                "aluno_id": aluno_id,
                "error": str(exc),
                "values": values,
                "action": f"/alunos/{aluno_id}",
                "submit_label": "Salvar",
                "show_foto": True,
                "has_foto": has_foto,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if aluno is None:
        if new_foto:
            delete_foto_file(new_foto)
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if remover_foto:
        set_aluno_foto(aluno_id, None)
        delete_foto_file(old_foto)
    elif new_foto:
        set_aluno_foto(aluno_id, new_foto)
        delete_foto_file(old_foto)

    return RedirectResponse(
        url=f"/alunos/{aluno_id}?atualizado=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/alunos/{aluno_id}/arquivar")
async def arquivar_aluno_route(request: Request, aluno_id: int):
    """Archive a student (set status to inactive) via the service layer."""
    aluno = arquivar_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return RedirectResponse(
        url=f"/alunos/{aluno_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/alunos/{aluno_id}/reativar")
async def reativar_aluno_route(request: Request, aluno_id: int):
    """Reactivate a student (set status to active) via the service layer."""
    aluno = reativar_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return RedirectResponse(
        url=f"/alunos/{aluno_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/alunos/{aluno_id}/frente")
async def set_frente_route(
    request: Request, aluno_id: int, frente: Optional[str] = Form(None)
):
    """Set (or clear) a student's "frente" via the service layer."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    try:
        set_frente(aluno_id, frente)
    except ValidationError as exc:
        response = _render_ficha(
            request, aluno_id, "perfil", {"erro_frente": str(exc)}
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response
    return RedirectResponse(
        url=f"/alunos/{aluno_id}?atualizado=1", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/alunos/{aluno_id}/excluir", response_class=HTMLResponse)
async def excluir_aluno_confirma(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the permanent-delete confirmation page for a student, or a
    404 page when the student does not exist.

    Shows a warning instead of the confirmation controls when the student
    has dependent history in another domain (architecture rule 6 — never
    silently lose data); the coach can archive it instead.
    """
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
        "alunos/excluir_confirma.html",
        {
            "aluno": {"id": aluno["id"], "name": aluno["name"]},
            "tem_historico": aluno_tem_historico(aluno_id),
        },
    )


@router.post("/alunos/{aluno_id}/excluir")
async def excluir_aluno_route(request: Request, aluno_id: int):
    """Permanently delete a student via the service layer.

    Redirects to the list on success; refuses (re-rendering the
    confirmation page, nothing deleted) when the student has dependent
    history in another domain (architecture rule 6 — never silently lose
    data).
    """
    resultado = excluir_aluno(aluno_id)

    if resultado == "nao_encontrado":
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if resultado == "tem_historico":
        aluno = get_aluno(aluno_id)
        return templates.TemplateResponse(
            request,
            "alunos/excluir_confirma.html",
            {
                "aluno": {"id": aluno["id"], "name": aluno["name"]},
                "tem_historico": True,
            },
            status_code=status.HTTP_200_OK,
        )

    return RedirectResponse(url="/alunos", status_code=status.HTTP_303_SEE_OTHER)


def _acesso_status(aluno: Dict[str, Any]) -> Dict[str, str]:
    """Map a student's login-access situation to a code/label pair.

    "sem_email": no email on file, so no access can ever be granted.
    "ativo": has an email and already logged in at least once (has a
    ``perfis`` row linked to this student).
    "aguardando": has an email but has not logged in yet.
    """
    if not aluno.get("email"):
        return {"acesso_status": "sem_email", "acesso_label": "Sem e-mail"}
    if get_perfil_by_aluno(aluno["id"]) is not None:
        return {"acesso_status": "ativo", "acesso_label": "Acesso ativo"}
    return {"acesso_status": "aguardando", "acesso_label": "Aguardando 1º login"}


def _render_ficha(
    request: Request,
    aluno_id: int,
    subtab: str,
    extra_context: Optional[Dict[str, Any]] = None,
) -> HTMLResponse:
    """Render the student's "ficha" page on the given sub-tab, or 404.

    Shared by the profile route and the placeholder sub-tab routes
    (avaliações, feedback, agenda, financeiro) so the get-or-404 logic and
    template selection live in a single place.
    """
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    context: Dict[str, Any] = {
        "aluno": _to_profile_display(aluno),
        "subtab": subtab,
        "frente_opcoes": _FRENTE_OPCOES_DISPLAY,
    }
    if extra_context:
        context.update(extra_context)
    return templates.TemplateResponse(request, "alunos/ficha.html", context)


# Declared after /alunos/novo and /alunos/{aluno_id}/editar so the literal
# and longer routes win over this parameterized one (route registration
# order matters in FastAPI). The sub-tab routes below share the same
# "/alunos/{aluno_id}/<literal>" shape as /editar, so they are safe from
# collisions for the same reason.
@router.get("/alunos/{aluno_id}", response_class=HTMLResponse)
async def aluno_profile(
    request: Request, aluno_id: int, atualizado: Optional[str] = None
) -> HTMLResponse:
    """Render a student's profile page, or a 404 page when absent."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    extra_context: Dict[str, Any] = dict(_acesso_status(aluno))
    if extra_context["acesso_status"] == "aguardando":
        token = gerar_token_ativacao(aluno_id)
        extra_context["link_ativacao"] = (
            str(request.base_url).rstrip("/") + "/ativar/" + token
        )
        extra_context["link_validade_dias"] = MAX_AGE_SEGUNDOS // 86400
    else:
        extra_context["link_ativacao"] = None
        extra_context["link_validade_dias"] = None
    if atualizado is not None:
        extra_context["success"] = "Perfil atualizado."
    return _render_ficha(request, aluno_id, "perfil", extra_context)


@router.get("/alunos/{aluno_id}/feedback", response_class=HTMLResponse)
async def aluno_feedback(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the student's "Feedback" sub-tab (placeholder)."""
    return _render_ficha(request, aluno_id, "feedback")


@router.get("/alunos/{aluno_id}/foto")
async def aluno_foto(aluno_id: int):
    """Serve a student's stored photo file, or a plain 404 when absent.

    404 covers every case that is not "file on disk": student not found,
    student without a photo (``foto`` is None), and an orphaned ``foto``
    filename whose file was removed from disk (never a 500).
    """
    aluno = get_aluno(aluno_id)
    if aluno is None or aluno.get("foto") is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    filename = aluno["foto"]
    path = config.fotos_dir() / filename
    if not path.exists():
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = _FOTO_MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(path, media_type=media_type)
