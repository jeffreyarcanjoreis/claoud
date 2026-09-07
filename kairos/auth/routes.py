"""HTTP routes (application layer) for the "auth" (login/logout) domain.

Thin routes only: they collect the form, delegate every decision to
:mod:`kairos.auth.supabase` (credential check) and :mod:`kairos.auth.service`
(role resolution), and render templates. Displayed texts are in Portuguese
(architecture rule 10).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from kairos import config
from kairos.alunos.service import get_aluno
from kairos.auth import service, supabase, tokens
from kairos.auth.middleware import _home_do_papel, current_user
from kairos.web import templates

logger = logging.getLogger(__name__)

router = APIRouter()

# Minimum password length accepted on the student's self-service activation
# form. Kept local since it only applies to this flow.
_SENHA_MIN = 8


def _safe_next(nxt: Optional[str]) -> str:
    """Return ``nxt`` only when it is a safe internal path.

    Guards against open-redirect: a safe value starts with "/", does not
    start with "//" (protocol-relative URL) and does not contain "://".
    Anything else falls back to "/".
    """
    if (
        nxt
        and nxt.startswith("/")
        and not nxt.startswith("//")
        and "://" not in nxt
    ):
        return nxt
    return "/"


def _safe_next_aluno(nxt: Optional[str]) -> str:
    """Return ``nxt`` only when it is a safe path under the student's area.

    Same open-redirect guard as :func:`_safe_next`, but only accepts values
    that are "/aluno" or start with "/aluno/"; anything else falls back to
    "/aluno".
    """
    if (
        nxt
        and nxt.startswith("/")
        and not nxt.startswith("//")
        and "://" not in nxt
        and (nxt == "/aluno" or nxt.startswith("/aluno/"))
    ):
        return nxt
    return "/aluno"


def _configurado() -> bool:
    return bool(config.supabase_url() and config.supabase_anon_key())


@router.get("/login")
async def login_form(request: Request):
    """Show the login form, or bounce an already-logged-in user to their
    own area (coach to "/", student to "/aluno")."""
    user = current_user(request)
    if user is not None:
        return RedirectResponse(
            url=_home_do_papel(user.get("papel")), status_code=status.HTTP_303_SEE_OTHER
        )

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "error": None,
            "next": _safe_next(request.query_params.get("next")),
            "configurado": _configurado(),
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    next: str = Form(""),
):
    """Verify the credential against Supabase Auth and start a session for
    coaches; anyone else (or any failure) sees a Portuguese error."""
    safe_next = _safe_next(next)

    try:
        res = supabase.login(email, senha)
        papel = service.resolver_papel_no_login(res["user_id"], res["email"])
    except supabase.AuthNaoConfigurado:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Login ainda não configurado.",
                "next": safe_next,
                "configurado": False,
            },
        )
    except supabase.AuthError:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "E-mail ou senha inválidos.",
                "next": safe_next,
                "configurado": _configurado(),
                "values": {"email": email},
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if papel == "coach":
        request.session["user"] = {
            "user_id": res["user_id"],
            "email": res["email"],
            "papel": "coach",
        }
        return RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)

    if papel == "aluno":
        perfil = service.get_perfil(res["user_id"])
        request.session["user"] = {
            "user_id": res["user_id"],
            "email": res["email"],
            "papel": "aluno",
            "aluno_id": perfil["aluno_id"] if perfil else None,
        }
        safe_next_aluno = _safe_next_aluno(next)
        return RedirectResponse(
            url=safe_next_aluno, status_code=status.HTTP_303_SEE_OTHER
        )

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "error": "Este acesso ainda não está liberado.",
            "next": safe_next,
            "configurado": _configurado(),
        },
        status_code=status.HTTP_403_FORBIDDEN,
    )


@router.post("/logout")
async def logout(request: Request):
    """Clear the session and send the coach back to the login screen."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


def _resolver_alvo_ativacao(token: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Resolve an activation token into a state and (when relevant) a student.

    Returns a ``(estado, aluno)`` pair:

    - ``("invalido", None)``: the token is expired/tampered/malformed, or it
      points at a student that no longer exists or is not active.
    - ``("ja_ativado", None)``: the token is valid, but this student already
      has a Perfil (self-service sign-up already happened, or the coach
      created the access some other way).
    - ``("ok", aluno)``: the token is valid and this student may still go
      through the self-service sign-up form.
    """
    aluno_id = tokens.ler_token_ativacao(token)
    if aluno_id is None:
        return "invalido", None

    aluno = get_aluno(aluno_id)
    if aluno is None or aluno.get("status") != "active":
        return "invalido", None

    # Sem e-mail não há como criar a conta no Supabase (e o link do coach só
    # é gerado quando há e-mail); tratamos como link inválido.
    if not aluno.get("email"):
        return "invalido", None

    if service.get_perfil_by_aluno(aluno_id) is not None:
        return "ja_ativado", None

    return "ok", aluno


@router.get("/ativar/{token}")
async def ativar_form(request: Request, token: str):
    """Show the student's self-service "create your access" form.

    Public route: the activation token itself (not a session) proves the
    student was given this link.
    """
    estado, aluno = _resolver_alvo_ativacao(token)

    if estado == "invalido":
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {"estado": "invalido"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if estado == "ja_ativado":
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {"estado": "ja_ativado"},
        )

    return templates.TemplateResponse(
        request,
        "auth/ativar.html",
        {"estado": "ok", "email": aluno["email"], "token": token},
    )


@router.post("/ativar/{token}")
async def ativar_submit(
    request: Request,
    token: str,
    senha: str = Form(...),
    confirmar: str = Form(...),
):
    """Create the Supabase Auth account and the ``Perfil`` for this student.

    On success with an immediately-open Supabase session, logs the student
    in and redirects to "/aluno"; otherwise renders a Portuguese status
    screen (never puts the password in the template context or in a log).
    """
    estado, aluno = _resolver_alvo_ativacao(token)

    if estado == "invalido":
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {"estado": "invalido"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if estado == "ja_ativado":
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {"estado": "ja_ativado"},
        )

    if len(senha) < _SENHA_MIN or senha != confirmar:
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {
                "estado": "ok",
                "email": aluno["email"],
                "token": token,
                "erro": (
                    "A senha precisa ter pelo menos "
                    f"{_SENHA_MIN} caracteres e as duas senhas "
                    "precisam ser iguais."
                ),
            },
        )

    try:
        res = supabase.signup(aluno["email"], senha)
    except supabase.AuthEmailJaRegistrado:
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {"estado": "email_existe"},
        )
    except (supabase.AuthNaoConfigurado, supabase.AuthError):
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {
                "estado": "ok",
                "email": aluno["email"],
                "token": token,
                "erro": "Não foi possível criar o acesso agora.",
            },
        )

    try:
        service.criar_perfil(
            user_id=res["user_id"], papel="aluno", aluno_id=aluno["id"]
        )
    except IntegrityError:
        # Defensive: a concurrent request already created the Perfil for
        # this student between our check above and this write.
        logger.warning(
            "Perfil já existia para aluno_id=%s ao ativar (corrida).",
            aluno["id"],
        )
        return templates.TemplateResponse(
            request,
            "auth/ativar.html",
            {"estado": "ja_ativado"},
        )

    if res["access_token"]:
        request.session["user"] = {
            "user_id": res["user_id"],
            "email": res["email"],
            "papel": "aluno",
            "aluno_id": aluno["id"],
        }
        return RedirectResponse(url="/aluno", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "auth/ativar.html",
        {"estado": "confirme_email"},
    )
