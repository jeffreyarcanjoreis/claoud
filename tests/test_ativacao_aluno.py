"""Tests for the student self-service activation link (`/ativar/{token}`).

Covers the functional specification:
- `kairos.auth.tokens`: round-trip generation/reading of the signed,
  time-limited activation token; any tampered or unrelated string reads back
  as None (never raises on untrusted input);
- `GET /ativar/{token}`: shows the "create your access" form for a valid
  token bound to an active student with an e-mail and no Perfil yet; a
  400 "invalid/expired link" screen for any invalid token; a "already
  activated" screen (with a link back to /login) when the student already
  has a Perfil;
- `POST /ativar/{token}` (with `kairos.auth.supabase.signup` mocked, so no
  network call ever reaches Supabase):
  - happy path with an immediately open Supabase session -> redirects to
    "/aluno" and starts a student session; the Perfil is created;
  - happy path with e-mail confirmation enabled (no session token) -> 200
    "confirm your e-mail" screen; the Perfil is still created;
  - password shorter than 8 chars, or password != confirmation -> the form
    is re-rendered with an error, `signup` is never called and no Perfil is
    created;
  - e-mail already registered (`AuthEmailJaRegistrado`) -> "email already
    has an account" screen; no Perfil created;
  - invalid token -> 400 invalid screen, `signup` never called;
  - student already has a Perfil -> "already activated" screen, `signup`
    never called, no second Perfil created;
- the coach's student profile page (`GET /alunos/{id}`) only shows the
  copyable activation link when the student has an e-mail and no Perfil yet
  (access status "aguardando"); it is absent when the student has no e-mail
  or already has an active access.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on setup/teardown. Every test that
exercises the POST endpoint mocks `kairos.auth.supabase.signup` so no test
ever makes a real network call to Supabase.

The single test that checks the student session started by a successful
activation (immediately-open Supabase session) is marked
``@pytest.mark.real_auth``: the suite-wide auto-login-as-coach fixture
(tests/conftest.py) always reports a coach session regardless of what the
route actually put in ``request.session``, which would hide whether
`/ativar` really logs the student in. Every other test in this file does
not need that marker: `/ativar/{token}` itself is a public path (see
``kairos.auth.middleware._is_public``), so the gate never consults
``current_user`` for it, and the coach-ficha tests intentionally rely on
the default auto-login-as-coach behavior.
"""

from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.auth import service
from kairos.auth.supabase import AuthEmailJaRegistrado
from kairos.auth.tokens import gerar_token_ativacao, ler_token_ativacao
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _fake_signup_ok(email: str, senha: str) -> dict:
    return {"user_id": "u-novo", "email": email, "access_token": "tok"}


def _fake_signup_confirm_email(email: str, senha: str) -> dict:
    return {"user_id": "u-confirma", "email": email, "access_token": ""}


def _fake_signup_email_exists(email: str, senha: str) -> dict:
    raise AuthEmailJaRegistrado("Já existe uma conta com esse e-mail.")


def _make_flag_signup(flag: dict, result: Optional[dict] = None):
    """Build a fake `signup` that records whether it was called."""

    def _fake(email: str, senha: str) -> dict:
        flag["called"] = True
        return result or {"user_id": "u-x", "email": email, "access_token": "tok"}

    return _fake


# ---------------------------------------------------------------------------
# kairos.auth.tokens (unit)
# ---------------------------------------------------------------------------


def test_ler_token_ativacao_round_trips_aluno_id() -> None:
    token = gerar_token_ativacao(7)

    assert ler_token_ativacao(token) == 7


def test_ler_token_ativacao_rejects_tampered_token() -> None:
    token = gerar_token_ativacao(7)

    assert ler_token_ativacao(token + "x") is None


def test_ler_token_ativacao_rejects_random_string() -> None:
    assert ler_token_ativacao("not-a-real-token") is None


# ---------------------------------------------------------------------------
# GET /ativar/{token}
# ---------------------------------------------------------------------------


def test_get_ativar_with_valid_token_shows_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        token = gerar_token_ativacao(aluno["id"])

        response = client.get(f"/ativar/{token}")

    assert response.status_code == 200
    assert "marcos@example.com" in response.text
    assert "Crie seu acesso" in response.text


def test_get_ativar_with_invalid_token_returns_400(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/ativar/garbage-token")

    assert response.status_code == 400
    assert "Link inválido ou expirado" in response.text


def test_get_ativar_for_aluno_without_email_is_invalid(data_dir: Path) -> None:
    # Sem e-mail não há conta a criar; o link é tratado como inválido (e o
    # formulário nunca chega a exibir "None" no campo de e-mail).
    with TestClient(app) as client:
        aluno = create_aluno(name="Sem Email")
        token = gerar_token_ativacao(aluno["id"])

        response = client.get(f"/ativar/{token}")

    assert response.status_code == 400
    assert "Link inválido ou expirado" in response.text
    assert "Crie seu acesso" not in response.text
    assert ">None<" not in response.text and 'value="None"' not in response.text


def test_get_ativar_with_already_activated_student_shows_ja_ativado(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        service.criar_perfil(user_id="u1", papel="aluno", aluno_id=aluno["id"])
        token = gerar_token_ativacao(aluno["id"])

        response = client.get(f"/ativar/{token}")

    assert response.status_code == 200
    assert "Acesso já criado" in response.text
    assert 'href="/login"' in response.text


# ---------------------------------------------------------------------------
# POST /ativar/{token}: happy paths
# ---------------------------------------------------------------------------


@pytest.mark.real_auth
def test_post_ativar_success_with_session_redirects_and_creates_perfil(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.auth.routes.supabase.signup", _fake_signup_ok)

    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        token = gerar_token_ativacao(aluno["id"])

        response = client.post(
            f"/ativar/{token}",
            data={"senha": "12345678", "confirmar": "12345678"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno"

        perfil = service.get_perfil("u-novo")
        assert perfil is not None
        assert perfil["papel"] == "aluno"
        assert perfil["aluno_id"] == aluno["id"]

        # The response also started a session for the student.
        area = client.get("/aluno", follow_redirects=False)
        assert area.status_code == 200


def test_post_ativar_success_without_session_shows_confirme_email(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.signup", _fake_signup_confirm_email
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        token = gerar_token_ativacao(aluno["id"])

        response = client.post(
            f"/ativar/{token}",
            data={"senha": "12345678", "confirmar": "12345678"},
        )

    assert response.status_code == 200
    assert "Confirme seu e-mail" in response.text

    perfil = service.get_perfil("u-confirma")
    assert perfil is not None
    assert perfil["papel"] == "aluno"
    assert perfil["aluno_id"] == aluno["id"]


# ---------------------------------------------------------------------------
# POST /ativar/{token}: validation errors (signup never called)
# ---------------------------------------------------------------------------


def test_post_ativar_short_password_rerenders_form_without_calling_signup(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.signup", _make_flag_signup(flag)
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        token = gerar_token_ativacao(aluno["id"])

        response = client.post(
            f"/ativar/{token}",
            data={"senha": "curta", "confirmar": "curta"},
        )

    assert response.status_code == 200
    assert "Crie seu acesso" in response.text
    assert flag["called"] is False
    assert service.get_perfil_by_aluno(aluno["id"]) is None


def test_post_ativar_mismatched_passwords_rerenders_form_without_calling_signup(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.signup", _make_flag_signup(flag)
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        token = gerar_token_ativacao(aluno["id"])

        response = client.post(
            f"/ativar/{token}",
            data={"senha": "12345678", "confirmar": "87654321"},
        )

    assert response.status_code == 200
    assert "Crie seu acesso" in response.text
    assert flag["called"] is False
    assert service.get_perfil_by_aluno(aluno["id"]) is None


# ---------------------------------------------------------------------------
# POST /ativar/{token}: e-mail already registered
# ---------------------------------------------------------------------------


def test_post_ativar_email_already_registered_shows_email_existe(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.signup", _fake_signup_email_exists
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        token = gerar_token_ativacao(aluno["id"])

        response = client.post(
            f"/ativar/{token}",
            data={"senha": "12345678", "confirmar": "12345678"},
        )

    assert response.status_code == 200
    assert "Esse e-mail já tem conta" in response.text
    assert 'href="/login"' in response.text
    assert service.get_perfil_by_aluno(aluno["id"]) is None


# ---------------------------------------------------------------------------
# POST /ativar/{token}: invalid token / already activated
# ---------------------------------------------------------------------------


def test_post_ativar_invalid_token_returns_400_without_calling_signup(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.signup", _make_flag_signup(flag)
    )

    with TestClient(app) as client:
        response = client.post(
            "/ativar/garbage-token",
            data={"senha": "12345678", "confirmar": "12345678"},
        )

    assert response.status_code == 400
    assert "Link inválido ou expirado" in response.text
    assert flag["called"] is False


def test_post_ativar_already_activated_student_does_not_create_second_perfil(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = {"called": False}
    monkeypatch.setattr(
        "kairos.auth.routes.supabase.signup", _make_flag_signup(flag)
    )

    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        service.criar_perfil(user_id="u1", papel="aluno", aluno_id=aluno["id"])
        token = gerar_token_ativacao(aluno["id"])

        response = client.post(
            f"/ativar/{token}",
            data={"senha": "12345678", "confirmar": "12345678"},
        )

    assert response.status_code == 200
    assert "Acesso já criado" in response.text
    assert flag["called"] is False

    perfil = service.get_perfil_by_aluno(aluno["id"])
    assert perfil is not None
    assert perfil["user_id"] == "u1"


# ---------------------------------------------------------------------------
# Coach's student profile page: activation link only shown when eligible
# ---------------------------------------------------------------------------


def test_ficha_shows_activation_link_when_email_and_no_perfil(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "/ativar/" in response.text


def test_ficha_hides_activation_link_when_no_email(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email=None)

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "/ativar/" not in response.text


def test_ficha_hides_activation_link_when_perfil_already_exists(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos", email="marcos@example.com")
        service.criar_perfil(user_id="u1", papel="aluno", aluno_id=aluno["id"])

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "/ativar/" not in response.text
