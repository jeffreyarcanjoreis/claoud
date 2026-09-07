"""Integration layer: password login against the Supabase Auth API.

This is a pure read/verification layer (architecture: integration layer):
Kairos never stores a password of its own -- it hands the e-mail/password
pair to Supabase Auth's ``token?grant_type=password`` endpoint and, on
success, only keeps the ``user_id``/``email`` that come back in the
response. No database write, no session handling and no flow decision
happen here; that is for the service/CLI layer that calls :func:`login`.

Only the stdlib is used (``urllib``, ``json``, ``logging``), matching the
style of :mod:`kairos.agenda.gcal`. The Supabase URL and anon key are read
from :mod:`kairos.config`; the password itself is never logged, never put
in a URL and never included in a raised exception's message.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Dict

from kairos import config

logger = logging.getLogger(__name__)

# A local single-user tool talking to Supabase: keep the request bounded so a
# slow or unreachable API never hangs the login screen.
_REQUEST_TIMEOUT_S = 15

_GENERIC_INVALID_MESSAGE = "E-mail ou senha inválidos."
_GENERIC_FAILURE_MESSAGE = "Não foi possível verificar o acesso agora."
_GENERIC_SIGNUP_FAILURE_MESSAGE = "Não foi possível criar o acesso agora."

# Substrings Supabase Auth is known to use (in ``error_code``, ``msg`` or
# ``error_description``) to signal that the e-mail is already registered.
# Matched case-insensitively against the parsed error body.
_EMAIL_JA_REGISTRADO_MARCADORES = (
    "already registered",
    "already exists",
    "user_already_exists",
    "email_exists",
)


class AuthError(Exception):
    """The credential is invalid or the verification could not be completed.

    The message is always a generic, pt-BR string suitable for display: it
    never reveals whether the e-mail or the password was the problem, and
    never carries the password, the token or the ``apikey``.
    """


class AuthNaoConfigurado(Exception):
    """Supabase Auth is not configured (URL and/or anon key are unset)."""


class AuthEmailJaRegistrado(Exception):
    """Sign-up was rejected because the e-mail already has an account."""


def login(email: str, senha: str) -> Dict[str, str]:
    """Verify ``email``/``senha`` against Supabase Auth and return the user.

    Returns ``{"user_id": ..., "email": ...}`` on success. Raises
    :class:`AuthNaoConfigurado` when the Supabase URL or anon key are not
    set, and :class:`AuthError` when the credential is invalid or the
    verification could not be completed (network/timeout/unexpected HTTP
    status). The password only ever travels in the HTTPS request body; it
    is never put in the URL, logged or included in an exception message.
    """
    url = config.supabase_url()
    anon_key = config.supabase_anon_key()
    if not url or not anon_key:
        raise AuthNaoConfigurado("Login com Supabase não configurado.")

    endpoint = f"{url}/auth/v1/token?grant_type=password"
    payload = json.dumps({"email": email, "password": senha}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "apikey": anon_key,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=_REQUEST_TIMEOUT_S
        ) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401):
            raise AuthError(_GENERIC_INVALID_MESSAGE) from exc
        logger.warning(
            "Falha inesperada ao verificar login no Supabase Auth "
            "(status HTTP %s).",
            exc.code,
        )
        raise AuthError(_GENERIC_FAILURE_MESSAGE) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Network/timeout/malformed-URL failures. Never log the exception
        # payload itself: it may echo back parts of the request.
        logger.warning(
            "Falha de rede ao verificar login no Supabase Auth: %s",
            type(exc).__name__,
        )
        raise AuthError(_GENERIC_FAILURE_MESSAGE) from exc

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "Resposta do Supabase Auth em formato inesperado ao verificar login."
        )
        raise AuthError(_GENERIC_FAILURE_MESSAGE) from exc

    user = data.get("user") if isinstance(data, dict) else None
    access_token = data.get("access_token") if isinstance(data, dict) else None
    user_id = user.get("id") if isinstance(user, dict) else None
    if not access_token or not user_id:
        logger.warning(
            "Resposta do Supabase Auth sem access_token/user.id ao verificar login."
        )
        raise AuthError(_GENERIC_FAILURE_MESSAGE)

    user_email = user.get("email") if isinstance(user, dict) else None
    return {"user_id": str(user_id), "email": user_email or email}


def _e_email_ja_registrado(body: bytes) -> bool:
    """Best-effort check whether an HTTPError body means "e-mail in use".

    Parses the body defensively and only inspects known text fields
    (``error_code``, ``msg``, ``error_description``); never logs it, since
    it may echo back parts of the sign-up request.
    """
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    campos = (
        str(data.get("error_code") or ""),
        str(data.get("msg") or ""),
        str(data.get("error_description") or ""),
    )
    texto = " ".join(campos).lower()
    return any(marcador in texto for marcador in _EMAIL_JA_REGISTRADO_MARCADORES)


def signup(email: str, senha: str) -> Dict[str, str]:
    """Create a Supabase Auth account for ``email``/``senha`` and return it.

    Returns ``{"user_id": ..., "email": ..., "access_token": ...}`` on
    success. ``access_token`` is an empty string when the project has
    "Confirm email" enabled and Supabase does not open a session right
    away. Raises :class:`AuthNaoConfigurado` when the Supabase URL or anon
    key are not set, :class:`AuthEmailJaRegistrado` when the e-mail already
    has an account, and :class:`AuthError` for any other failure (weak
    password rejected by Supabase, network/timeout, unexpected HTTP
    status). The password only ever travels in the HTTPS request body; it
    is never put in the URL, logged or included in an exception message.
    """
    url = config.supabase_url()
    anon_key = config.supabase_anon_key()
    if not url or not anon_key:
        raise AuthNaoConfigurado("Cadastro com Supabase não configurado.")

    endpoint = f"{url}/auth/v1/signup"
    payload = json.dumps({"email": email, "password": senha}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "apikey": anon_key,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=_REQUEST_TIMEOUT_S
        ) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 422):
            erro_body = exc.read()
            if _e_email_ja_registrado(erro_body):
                raise AuthEmailJaRegistrado(
                    "Já existe uma conta com esse e-mail."
                ) from exc
            raise AuthError(_GENERIC_SIGNUP_FAILURE_MESSAGE) from exc
        logger.warning(
            "Falha inesperada ao criar acesso no Supabase Auth "
            "(status HTTP %s).",
            exc.code,
        )
        raise AuthError(_GENERIC_SIGNUP_FAILURE_MESSAGE) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Network/timeout/malformed-URL failures. Never log the exception
        # payload itself: it may echo back parts of the request.
        logger.warning(
            "Falha de rede ao criar acesso no Supabase Auth: %s",
            type(exc).__name__,
        )
        raise AuthError(_GENERIC_SIGNUP_FAILURE_MESSAGE) from exc

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "Resposta do Supabase Auth em formato inesperado ao criar acesso."
        )
        raise AuthError(_GENERIC_SIGNUP_FAILURE_MESSAGE) from exc

    user = data.get("user") if isinstance(data, dict) else None
    access_token = data.get("access_token") if isinstance(data, dict) else None
    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        logger.warning(
            "Resposta do Supabase Auth sem user.id ao criar acesso."
        )
        raise AuthError(_GENERIC_FAILURE_MESSAGE)

    user_email = user.get("email") if isinstance(user, dict) else None
    return {
        "user_id": str(user_id),
        "email": user_email or email,
        "access_token": access_token or "",
    }
