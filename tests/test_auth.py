"""Tests for issue 26 (Fase 1): Supabase Auth login + AuthGateMiddleware.

Covers the functional specification:
- GET /login shows the login form (email/senha fields) without requiring a
  session;
- every non-public route redirects (302) to /login?next=... when there is
  no coach session (the gate);
- the public paths (/health, /vitrine, /comecar, /login, /logout, /static,
  /favicon.ico) stay reachable without a session;
- POST /login with a valid credential (verified against Supabase Auth)
  starts a coach session and redirects to "next" (bootstrap: the first
  successful login ever becomes "coach");
- POST /login with an invalid credential (AuthError) re-renders the form
  with a 401 and an "inválidos" message, and the panel keeps redirecting
  away afterwards (no session was created);
- POST /login when Supabase Auth is not configured (AuthNaoConfigurado)
  re-renders the form with a "não está configurado" message;
- POST /logout clears the session and sends the coach back to /login;
- "next" is guarded against open-redirect: an external URL always falls
  back to "/";
- kairos.auth.service resolves the coach/aluno role at login time: the
  bootstrap rule (first-ever login becomes coach), an existing Perfil's
  stored role wins, a second new user (once a coach exists) gets no role,
  and criar_perfil rejects an invalid papel.

Every test marked ``@pytest.mark.real_auth`` opts out of the suite-wide
auto-login fixture (tests/conftest.py) so AuthGateMiddleware runs for real.
Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.auth import service
from kairos.auth.supabase import AuthError, AuthNaoConfigurado
from kairos.main import app
from kairos.migrations_runner import run_migrations

pytestmark = pytest.mark.real_auth


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _fake_login_ok(email: str, senha: str) -> dict:
    return {"user_id": "u1", "email": "c@x.com"}


def _fake_login_invalid(email: str, senha: str) -> dict:
    raise AuthError("E-mail ou senha inválidos.")


def _fake_login_not_configured(email: str, senha: str) -> dict:
    raise AuthNaoConfigurado("Login com Supabase não configurado.")


# ---------------------------------------------------------------------------
# GET /login
# ---------------------------------------------------------------------------


def test_login_form_shows_email_and_senha_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert 'name="email"' in response.text
    assert 'name="senha"' in response.text


# ---------------------------------------------------------------------------
# The gate: non-public routes redirect without a session
# ---------------------------------------------------------------------------


def test_root_without_session_redirects_to_login(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")
    assert "next=" in response.headers["location"]


def test_alunos_without_session_redirects_to_login(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")
    assert "alunos" in response.headers["location"]


# ---------------------------------------------------------------------------
# Public paths stay reachable without a session
# ---------------------------------------------------------------------------


def test_vitrine_is_public(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine", follow_redirects=False)

    assert response.status_code == 200


def test_comecar_is_public(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/comecar", follow_redirects=False)

    assert response.status_code == 200


def test_health_is_public(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/health", follow_redirects=False)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /login: success
# ---------------------------------------------------------------------------


def test_post_login_success_starts_session_and_redirects(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_ok)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"email": "c@x.com", "senha": "pw", "next": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        # Same client -> cookies persist -> the panel is now reachable.
        panel = client.get("/", follow_redirects=False)
        assert panel.status_code == 200


def test_post_login_success_redirects_to_next(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_ok)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"email": "c@x.com", "senha": "pw", "next": "/alunos"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/alunos"


def test_post_login_success_bootstraps_first_user_as_coach(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No Perfil exists yet -- the first successful login becomes coach."""
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_ok)

    with TestClient(app) as client:
        client.post("/login", data={"email": "c@x.com", "senha": "pw"})

    perfil = service.get_perfil("u1")
    assert perfil is not None
    assert perfil["papel"] == "coach"


# ---------------------------------------------------------------------------
# POST /login: invalid credential
# ---------------------------------------------------------------------------


def test_post_login_invalid_credential_returns_401_with_message(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_invalid)

    with TestClient(app) as client:
        response = client.post(
            "/login", data={"email": "c@x.com", "senha": "wrong"}
        )

    assert response.status_code == 401
    assert "inválidos" in response.text


def test_post_login_invalid_credential_does_not_create_session(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_invalid)

    with TestClient(app) as client:
        client.post("/login", data={"email": "c@x.com", "senha": "wrong"})

        panel = client.get("/", follow_redirects=False)

    assert panel.status_code == 302
    assert panel.headers["location"].startswith("/login")


# ---------------------------------------------------------------------------
# POST /login: Supabase Auth not configured
# ---------------------------------------------------------------------------


def test_post_login_not_configured_shows_message(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.login", _fake_login_not_configured
    )

    with TestClient(app) as client:
        response = client.post("/login", data={"email": "c@x.com", "senha": "pw"})

    assert "não está configurado" in response.text


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------


def test_logout_clears_session_and_redirects_to_login(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_ok)

    with TestClient(app) as client:
        client.post("/login", data={"email": "c@x.com", "senha": "pw"})
        assert client.get("/", follow_redirects=False).status_code == 200

        response = client.post("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

        panel = client.get("/", follow_redirects=False)
        assert panel.status_code == 302
        assert panel.headers["location"].startswith("/login")


# ---------------------------------------------------------------------------
# Anti-open-redirect
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("evil_next", ["http://evil.com", "//evil.com"])
def test_post_login_rejects_external_next_and_falls_back_to_root(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, evil_next: str
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.login", _fake_login_ok)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"email": "c@x.com", "senha": "pw", "next": evil_next},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


# ---------------------------------------------------------------------------
# kairos.auth.service: role resolution at login time
# ---------------------------------------------------------------------------


def test_resolver_papel_no_login_bootstraps_first_user_as_coach(
    data_dir: Path,
) -> None:
    run_migrations()

    papel = service.resolver_papel_no_login("first-user")

    assert papel == "coach"
    assert service.get_perfil("first-user")["papel"] == "coach"


def test_resolver_papel_no_login_returns_none_for_a_second_new_user(
    data_dir: Path,
) -> None:
    run_migrations()
    service.resolver_papel_no_login("first-user")  # becomes coach

    papel = service.resolver_papel_no_login("second-user")

    assert papel is None
    assert service.get_perfil("second-user") is None


def test_resolver_papel_no_login_returns_stored_role_for_existing_perfil(
    data_dir: Path,
) -> None:
    run_migrations()
    service.resolver_papel_no_login("first-user")  # becomes coach
    service.criar_perfil(user_id="aluno-1", papel="aluno")

    papel = service.resolver_papel_no_login("aluno-1")

    assert papel == "aluno"


def test_existe_coach_reflects_current_state(data_dir: Path) -> None:
    run_migrations()

    assert service.existe_coach() is False

    service.criar_perfil(user_id="c1", papel="coach")

    assert service.existe_coach() is True


def test_criar_perfil_with_invalid_papel_raises_validation_error(
    data_dir: Path,
) -> None:
    run_migrations()

    with pytest.raises(service.ValidationError):
        service.criar_perfil(user_id="x", papel="invalido")

    assert service.get_perfil("x") is None
