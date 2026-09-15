"""Tests for issue 26 (Fase 3.1): multi-role gate + student landing area.

Covers the functional specification:
- ``GET /aluno`` renders the student's own landing page, greeting them by
  their first name ("Ola, {primeiro_nome}") when the session's ``aluno_id``
  resolves to an existing Aluno;
- when ``aluno_id`` does not resolve to any Aluno, the landing page still
  renders (200) with a generic greeting ("Ola!") instead of crashing;
- the gate routes each role to its own area: a student session hitting a
  coach-only route (``/alunos``, ``/financeiro``) is redirected to
  ``/aluno``; a coach session hitting the student area (``/aluno``) is
  redirected to ``/`` -- neither case falls through to the requested page
  nor loops back to ``/login``;
- ``/alunos`` (the coach's roster) is never captured by the ``/aluno``
  prefix match (regression guard);
- without any session, both ``/aluno`` and ``/alunos`` redirect (302) to
  ``/login?next=...`` (unauthenticated behavior is unchanged by the new
  student area);
- ``POST /login`` resolving a student role opens an "aluno" session and
  redirects (303) to ``/aluno`` (or a safe ``next`` under it), and
  ``GET /login`` while already logged in as a student bounces to
  ``/aluno``; the pre-existing coach login flow keeps working;
- the login screen's subtitle reads "Acesse a sua conta." (no more
  coach-specific wording).

Same isolation pattern as tests/test_auth.py: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on setup/teardown; tests that
need the real AuthGateMiddleware/login flow (rather than the suite-wide
auto-login-as-coach fixture) opt out with ``@pytest.mark.real_auth``.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.auth import service
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    """Override the suite-wide auto-login-as-coach patch with a student
    session for the current test (applied after the autouse fixture runs,
    so it wins for the rest of the test body).

    Patches both the gate's own reference (``kairos.auth.middleware``) and
    the student landing route's directly-imported reference
    (``kairos.area_aluno.routes``), since ``from ... import current_user``
    binds a separate name that a patch on the origin module does not reach.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


def _fake_login_ok(user_id: str, email: str):
    def _login(login_email: str, senha: str) -> dict:
        return {"user_id": user_id, "email": email}

    return _login


# ---------------------------------------------------------------------------
# 1-2. Landing: GET /aluno
# ---------------------------------------------------------------------------


def test_aluno_landing_greets_by_first_name(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Olá, Maria" in response.text


def test_aluno_landing_falls_back_to_generic_greeting_when_aluno_id_unresolvable(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _login_as_aluno(monkeypatch, 999999)  # no Aluno with this id

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Olá!" in response.text
    assert "Olá, " not in response.text


# ---------------------------------------------------------------------------
# 3. Gate: a student hitting a coach-only route is bounced to /aluno
# ---------------------------------------------------------------------------


def test_aluno_session_hitting_alunos_roster_redirects_to_aluno_area(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/alunos", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/aluno"


def test_aluno_session_hitting_financeiro_redirects_to_aluno_area(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/financeiro", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/aluno"


# ---------------------------------------------------------------------------
# 4. Gate: a coach hitting the student area is bounced to /
# ---------------------------------------------------------------------------


def test_coach_session_hitting_aluno_area_redirects_to_root(
    data_dir: Path,
) -> None:
    """Uses the suite-wide auto-login-as-coach fixture (no override)."""
    with TestClient(app) as client:
        response = client.get("/aluno", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/"


# ---------------------------------------------------------------------------
# 5. Regression: /alunos is not captured by the /aluno prefix match
# ---------------------------------------------------------------------------


def test_coach_session_alunos_roster_is_not_captured_by_aluno_prefix(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos", follow_redirects=False)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 6. Gate: no session at all -- unchanged redirect-to-login behavior
# ---------------------------------------------------------------------------


@pytest.mark.real_auth
def test_aluno_area_without_session_redirects_to_login(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/aluno", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")
    assert "aluno" in response.headers["location"]


@pytest.mark.real_auth
def test_alunos_roster_without_session_still_redirects_to_login(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")
    assert "alunos" in response.headers["location"]


# ---------------------------------------------------------------------------
# 7. Login by role
# ---------------------------------------------------------------------------


@pytest.mark.real_auth
def test_post_login_resolving_aluno_role_starts_session_and_redirects_to_aluno_area(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.login",
        _fake_login_ok("uid-aluno", "aluno@x.com"),
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        service.criar_perfil(
            user_id="uid-aluno", papel="aluno", aluno_id=aluno["id"]
        )

        response = client.post(
            "/login",
            data={"email": "aluno@x.com", "senha": "pw", "next": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno"

        # Same client -> cookies persist -> the student area is now reachable.
        landing = client.get("/aluno", follow_redirects=False)

    assert landing.status_code == 200
    assert "Olá, Maria" in landing.text


@pytest.mark.real_auth
def test_post_login_resolving_aluno_role_redirects_to_safe_next_under_aluno_area(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.login",
        _fake_login_ok("uid-aluno", "aluno@x.com"),
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        service.criar_perfil(
            user_id="uid-aluno", papel="aluno", aluno_id=aluno["id"]
        )

        response = client.post(
            "/login",
            data={"email": "aluno@x.com", "senha": "pw", "next": "/aluno"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/aluno"


@pytest.mark.real_auth
def test_post_login_resolving_coach_role_still_redirects_to_root(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-existing coach flow (test_auth.py) is unaffected by the new
    student area/role branch."""
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.login",
        _fake_login_ok("uid-coach", "coach@x.com"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"email": "coach@x.com", "senha": "pw", "next": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        panel = client.get("/", follow_redirects=False)

    assert panel.status_code == 200


@pytest.mark.real_auth
def test_get_login_while_logged_in_as_aluno_bounces_to_aluno_area(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.login",
        _fake_login_ok("uid-aluno", "aluno@x.com"),
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        service.criar_perfil(
            user_id="uid-aluno", papel="aluno", aluno_id=aluno["id"]
        )
        client.post(
            "/login", data={"email": "aluno@x.com", "senha": "pw", "next": ""}
        )

        response = client.get("/login", follow_redirects=False)

    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/aluno"


# ---------------------------------------------------------------------------
# 8. Copy: the login screen's subtitle
# ---------------------------------------------------------------------------


@pytest.mark.real_auth
def test_login_form_shows_generic_subtitle_not_coach_specific(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert "Acesse a sua conta." in response.text
    assert "painel do coach" not in response.text


@pytest.mark.real_auth
def test_login_form_offers_both_coach_and_aluno_entry_buttons(
    data_dir: Path,
) -> None:
    # A tela de login oferece dois caminhos ("Entrar como coach" / "Entrar
    # como aluno"); o roteamento em si segue o papel real da conta.
    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert "Entrar como coach" in response.text
    assert "Entrar como aluno" in response.text
