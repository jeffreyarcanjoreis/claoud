"""Session gate: blocks every non-public route until a coach is logged in.

Sits behind :class:`starlette.middleware.sessions.SessionMiddleware` (which
must run first, i.e. be added after this middleware — Starlette applies
middlewares outside-in in reverse registration order) so ``request.session``
is already available here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

# Paths that never require a logged-in coach. Defined at module level so
# ``AuthGateMiddleware`` and tests share a single source of truth.
_PUBLIC_EXACT_PATHS = {"/login", "/logout", "/vitrine", "/comecar"}


def current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Return the logged-in user stored in the session, or None.

    A thin wrapper around ``request.session`` so callers (and tests, via
    monkeypatch) have a single place to read "who is logged in".
    """
    return request.session.get("user")


def _is_public(path: str) -> bool:
    """Return True when ``path`` may be accessed without a session."""
    if path == "/health":
        return True
    if path.startswith("/static"):
        return True
    if path == "/favicon.ico":
        return True
    if path.startswith("/ativar"):
        return True
    return path in _PUBLIC_EXACT_PATHS


def _is_area_aluno(path: str) -> bool:
    """Return True when ``path`` belongs to the student's own area.

    Matches exactly "/aluno" or anything under "/aluno/". Must NOT match
    "/alunos" (the coach's roster), hence the explicit prefix check instead
    of a plain ``startswith("/aluno")``.
    """
    return path == "/aluno" or path.startswith("/aluno/")


def _home_do_papel(papel: Optional[str]) -> str:
    """Return the landing path for a given role: student area or coach home."""
    return "/aluno" if papel == "aluno" else "/"


class AuthGateMiddleware(BaseHTTPMiddleware):
    """Gate every non-public route behind a logged-in session, routing each
    role to its own area: coaches to the panel, students to "/aluno"."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if _is_public(path):
            return await call_next(request)

        papel_exigido = "aluno" if _is_area_aluno(path) else "coach"

        user = current_user(request)
        if user is None:
            next_url = quote(path)
            return RedirectResponse(
                url=f"/login?next={next_url}", status_code=302
            )

        if user.get("papel") != papel_exigido:
            return RedirectResponse(
                url=_home_do_papel(user.get("papel")), status_code=302
            )

        return await call_next(request)
